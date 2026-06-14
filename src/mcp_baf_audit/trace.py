"""Сквозной trace_id и обёртка инструмента traced().

trace_id связывает все события одной логической операции между сервисами
(mcp-baf -> baf-write-mcp -> hermes). Он хранится в contextvar, поэтому
вложенные вызовы автоматически наследуют его без явной передачи.
"""

from __future__ import annotations

import contextvars
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # без рантайм-импорта writer — избегаем цикла
    from .writer import AuditWriter

_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "mcp_baf_audit_trace_id", default=None
)


def new_trace_id() -> str:
    """Генерирует новый trace_id (hex16)."""
    return uuid.uuid4().hex[:16]


def set_trace_id(tid: str | None) -> str | None:
    """Устанавливает trace_id текущего контекста (None — очистка)."""
    _trace_id.set(tid)
    return tid


def get_trace_id() -> str | None:
    """Текущий trace_id или None."""
    return _trace_id.get()


def to_json(value: Any) -> str:
    """Читаемый JSON-ответ инструмента (без ASCII-escape)."""
    return json.dumps(value, ensure_ascii=False, indent=2)


async def traced(
    audit: AuditWriter,
    tool: str,
    call: Callable[[], Awaitable[Any]],
    *,
    request_id: str = "",
    args: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> str:
    """Выполняет инструмент со сквозным аудитом и возвращает JSON-ответ.

    Каждый вызов любого инструмента (включая read-only) оставляет событие
    tool_call (tool, args, ok, duration_ms) либо tool_error с текстом
    исключения. args — компактная выжимка аргументов для журнала; полные
    payload'ы пишут доменные события.

    trace_id берётся в приоритете: явный аргумент -> contextvar -> None.
    """
    if trace_id is None:
        trace_id = get_trace_id()

    start = time.monotonic()
    try:
        result = await call()
    except Exception as exc:
        audit.write(
            "tool_error", request_id,
            level="error", trace_id=trace_id,
            tool=tool, args=args or {}, error=str(exc),
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        raise

    if not request_id and isinstance(result, dict):
        # propose выдаёт request_id только в результате — подхватываем.
        request_id = str(result.get("request_id") or "")
    ok = not (isinstance(result, dict) and result.get("error"))
    audit.write(
        "tool_call", request_id,
        trace_id=trace_id,
        tool=tool, args=args or {}, ok=ok,
        duration_ms=int((time.monotonic() - start) * 1000),
    )
    return to_json(result)
