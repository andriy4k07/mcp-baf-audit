"""JSONL-журнал аудита — единый контракт логирования для всех сервисов.

Каждая операция (lifecycle сервера, вызовы инструментов, доменные события
и их ошибки) пишется одной строкой JSON в файл журнала. Каждая запись
несёт общий конверт: schema_version, ts, service, session (идентификатор
запуска процесса), seq (сквозной номер в сеансе), trace_id и event.
Вместе с request_id (доменное поле) это позволяет восстановить полную
историю операции между сервисами.

Журнал ротируется по размеру: при превышении лимита текущий файл
переименовывается в <stem>-<метка времени>.log, старые архивы сверх
лимита удаляются. Сбой записи аудита не должен ломать инструменты —
ошибки ввода-вывода проглатываются (с предупреждением в логе сервиса).
"""

from __future__ import annotations

import glob
import json
import logging
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .redact import default_redactor
from .trace import get_trace_id

logger = logging.getLogger(__name__)

# Версия схемы записи. Любое изменение формата строки -> bump этой
# константы и minor/major тега пакета.
SCHEMA_VERSION = "1"

_MIB = 1 << 20

# Дефолты ротации. Аудит — журнал бизнес-операций, поэтому дефолты
# щедрые: ~50 MiB это сотни тысяч событий, 20 архивов про запас.
DEFAULT_AUDIT_MAX_SIZE_MIB = 50
DEFAULT_AUDIT_ARCHIVES = 20
DEFAULT_MAX_BYTES = DEFAULT_AUDIT_MAX_SIZE_MIB * _MIB

Redactor = Callable[[Any], Any]


def user_cache_dir() -> str:
    """Платформенный каталог кэша пользователя."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return base
        return os.path.expanduser(r"~\AppData\Local")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Caches")
    return os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")


def default_cache_dir(app: str = "baf-write-mcp") -> str:
    return os.path.join(user_cache_dir(), app)


def _utc_now_iso_ms() -> str:
    """ISO8601 UTC с миллисекундами."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class AuditWriter:
    """JSONL-журнал аудита с общим конвертом записи.

    service — имя сервиса (mcp-baf | baf-write-mcp | hermes).
    path — путь к файлу журнала (например <cache>/audit.log); архивы
    ротации именуются по основе имени файла (<stem>-<ts>.log).
    Запись потокобезопасна; session и seq общие на процесс.
    """

    def __init__(
        self,
        service: str,
        path: str | Path,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        backups: int = DEFAULT_AUDIT_ARCHIVES,
        redactor: Redactor | None = None,
        session: str | None = None,
    ) -> None:
        self._service = service
        self._path = str(path)
        self._dir = os.path.dirname(self._path) or "."
        name = os.path.basename(self._path)
        # Основа имени для архивов: "audit.log" -> "audit".
        self._stem = name[:-4] if name.endswith(".log") else name
        self._max_bytes = max_bytes
        self._backups = backups
        self._redactor = redactor or default_redactor
        # Идентификатор сеанса: один на запуск процесса.
        self._session = session or uuid.uuid4().hex[:12]
        self._seq = 0
        self._lock = threading.Lock()

    @property
    def path(self) -> str:
        return self._path

    @property
    def session_id(self) -> str:
        return self._session

    @property
    def service(self) -> str:
        return self._service

    # ── Канонический API ────────────────────────────────────────────

    def event(
        self,
        event: str,
        *,
        level: str = "info",
        tool: str | None = None,
        trace_id: str | None = None,
        duration_ms: int | None = None,
        status: int | None = None,
        payload: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Пишет запись по единой схеме (payload — событие-специфичное)."""
        record: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "ts": _utc_now_iso_ms(),
            "service": self._service,
            "session": self._session,
            "seq": 0,  # проставляется под локом в _emit
            "trace_id": trace_id if trace_id is not None else get_trace_id(),
            "event": event,
            "level": level,
            "tool": tool,
            "duration_ms": duration_ms,
            "status": status,
            "payload": self._redactor(payload) if payload else {},
            "error": error,
        }
        self._emit(record)

    # ── Обратная совместимость (плоские поля события) ───────────────

    def write(
        self,
        event: str,
        request_id: str = "",
        *,
        level: str = "info",
        trace_id: str | None = None,
        **details: Any,
    ) -> None:
        """Пишет событие с деталями на верхнем уровне (как в baf-write).

        Сохранена знакомая сигнатура: write(event, request_id, **details).
        Конверт (schema_version/service/session/seq/trace_id) добавляется
        автоматически; details редактируются перед записью.
        """
        record: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "ts": _utc_now_iso_ms(),
            "service": self._service,
            "session": self._session,
            "seq": 0,  # проставляется под локом в _emit
            "trace_id": trace_id if trace_id is not None else get_trace_id(),
            "event": event,
            "level": level,
        }
        if request_id:
            record["request_id"] = request_id
        record.update(self._redactor(details))
        self._emit(record)

    # ── Удобные шорткаты lifecycle ──────────────────────────────────

    def server_start(self, **details: Any) -> None:
        self.write("server_start", **details)

    def server_stop(self, **details: Any) -> None:
        self.write("server_stop", **details)

    # ── Внутреннее ──────────────────────────────────────────────────

    def _emit(self, record: dict[str, Any]) -> None:
        with self._lock:
            self._seq += 1
            record["seq"] = self._seq
            try:
                os.makedirs(self._dir, exist_ok=True)
                self._rotate_if_needed()
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            except OSError as exc:
                logger.warning(
                    "audit: не удалось записать событие %s: %s",
                    record.get("event"), exc,
                )

    def _rotate_if_needed(self) -> None:
        """Ротация по размеру: <path> -> <stem>-<ts>.log, обрезка архивов."""
        try:
            size = os.path.getsize(self._path)
        except OSError:
            return  # файла ещё нет — ротация не нужна
        if size < self._max_bytes:
            return

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        candidate = os.path.join(self._dir, f"{self._stem}-{stamp}.log")
        n = 1
        while os.path.exists(candidate):
            candidate = os.path.join(self._dir, f"{self._stem}-{stamp}-{n}.log")
            n += 1
        os.replace(self._path, candidate)
        logger.info("audit: ротация журнала -> %s", candidate)

        archives = sorted(glob.glob(os.path.join(self._dir, f"{self._stem}-*.log")))
        for old in archives[: max(0, len(archives) - self._backups)]:
            try:
                os.remove(old)
            except OSError:
                pass

    def close(self) -> None:
        """Ничего не буферизуется (файл открывается на каждую запись)."""

    def __enter__(self) -> AuditWriter:
        return self

    def __exit__(self, *exc: object) -> bool:
        self.close()
        return False


class AuditLog(AuditWriter):
    """Совместимость с прежним baf-write AuditLog.

    Прежняя сигнатура: AuditLog(cache_dir, max_size_mib, archives). Пишет
    в <cache_dir>/audit.log с service="baf-write-mcp" по умолчанию.
    """

    def __init__(
        self,
        cache_dir: str = "",
        max_size_mib: int = DEFAULT_AUDIT_MAX_SIZE_MIB,
        archives: int = DEFAULT_AUDIT_ARCHIVES,
        *,
        service: str = "baf-write-mcp",
        redactor: Redactor | None = None,
    ) -> None:
        directory = cache_dir or default_cache_dir(service)
        super().__init__(
            service,
            os.path.join(directory, "audit.log"),
            max_bytes=max_size_mib * _MIB,
            backups=archives,
            redactor=redactor,
        )
