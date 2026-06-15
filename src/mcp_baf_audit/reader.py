"""Чтение журнала аудита — единственная «читающая» функция библиотеки.

:func:`iter_events` отдаёт события из активного журнала и (по умолчанию) из
ротированных архивов в хронологическом порядке. Битые строки молча
пропускаются — о каждой сообщается через callback ``on_bad_line``, чтобы
потребитель мог их посчитать. Имя события нормализуется через
:func:`mcp_baf_audit.events.canonical`, поэтому старые плоские имена (v1) и
канонические (v2) приходят к читателю единообразно.

На этой функции строятся внешние проекции/дашборд: сама библиотека ни БД,
ни форматов представления не знает.
"""

from __future__ import annotations

import glob
import json
import logging
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from .events import canonical

logger = logging.getLogger(__name__)


def _sort_key(file_path: str) -> str:
    """Ключ сортировки архивов: имя без расширения .log.

    Имена архивов: ``<stem>-<YYYYMMDD-HHMMSS>[-<n>].log``. Сортировка по
    строке без ".log" ставит базовый архив метки раньше его collision-версии
    ``-<n>`` (та же секунда), потому что более короткая строка-префикс идёт
    первой; точка ".log" не вмешивается в сравнение.
    """
    return file_path[:-4] if file_path.endswith(".log") else file_path


def _files_in_order(path: str | Path, follow_rotation: bool) -> list[str]:
    """Архивы (старые -> новые) и затем активный журнал последним."""
    p = str(path)
    files: list[str] = []
    if follow_rotation:
        directory = os.path.dirname(p) or "."
        name = os.path.basename(p)
        stem = name[:-4] if name.endswith(".log") else name
        pattern = os.path.join(directory, f"{stem}-*.log")
        files.extend(sorted(glob.glob(pattern), key=_sort_key))
    files.append(p)  # активный журнал — самый свежий, читаем последним
    return files


def iter_events(
    path: str | Path,
    *,
    follow_rotation: bool = True,
    on_bad_line: Callable[[str], None] | None = None,
) -> Iterator[dict[str, Any]]:
    """Итерирует события журнала аудита в хронологическом порядке.

    path — путь к активному журналу (например ``<cache>/audit.log``).
    follow_rotation — включать ротированные архивы ``<stem>-*.log`` перед
    активным журналом (по умолчанию да).
    on_bad_line — вызывается с исходным текстом каждой пропущенной (битой)
    строки; удобно для подсчёта. Битой считается строка, которая не парсится
    как JSON или не является JSON-объектом. Пустые строки пропускаются молча.

    Каждое отданное событие — dict с нормализованным каноническим ``event``.
    Отсутствующие/недоступные файлы пропускаются без ошибки.
    """
    for file_path in _files_in_order(path, follow_rotation):
        try:
            handle = open(file_path, encoding="utf-8")
        except OSError:
            continue  # файла нет или нет доступа — не наша забота
        with handle as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue  # пустые строки не считаем битыми
                try:
                    record = json.loads(line)
                except ValueError:
                    logger.debug("audit reader: пропущена битая строка")
                    if on_bad_line is not None:
                        on_bad_line(line)
                    continue
                if not isinstance(record, dict):
                    logger.debug("audit reader: пропущена не-объектная строка")
                    if on_bad_line is not None:
                        on_bad_line(line)
                    continue
                event = record.get("event")
                if isinstance(event, str):
                    record["event"] = canonical(event)
                yield record
