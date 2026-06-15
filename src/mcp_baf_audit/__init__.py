"""mcp-baf-audit — единый JSONL-аудит для сервисов BAF (mcp-baf, baf-write-mcp, hermes).

Схема записи общая (см. writer.SCHEMA_VERSION). Публичный API намеренно
повторяет знакомые из baf-write имена, чтобы интеграция была минимальной.
"""

from __future__ import annotations

from . import events
from .events import ALIASES, canonical
from .reader import iter_events
from .redact import REDACTED, default_redactor
from .trace import (
    get_trace_id,
    new_trace_id,
    set_trace_id,
    to_json,
    traced,
)
from .writer import (
    DEFAULT_AUDIT_ARCHIVES,
    DEFAULT_AUDIT_MAX_SIZE_MIB,
    DEFAULT_MAX_BYTES,
    SCHEMA_VERSION,
    AuditLog,
    AuditWriter,
    default_cache_dir,
    user_cache_dir,
)

__version__ = "0.2.0"

__all__ = [
    "AuditWriter",
    "AuditLog",
    "traced",
    "to_json",
    "set_trace_id",
    "get_trace_id",
    "new_trace_id",
    "default_redactor",
    "REDACTED",
    "events",
    "canonical",
    "ALIASES",
    "iter_events",
    "SCHEMA_VERSION",
    "DEFAULT_AUDIT_MAX_SIZE_MIB",
    "DEFAULT_AUDIT_ARCHIVES",
    "DEFAULT_MAX_BYTES",
    "default_cache_dir",
    "user_cache_dir",
    "__version__",
]
