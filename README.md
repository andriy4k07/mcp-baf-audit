# mcp-baf-audit

Єдиний JSONL-журнал аудиту для сервісів BAF. Формат запису — спільний
контракт, щоб логи не розходилися між сервісами.

Пакет **повністю незалежний**: без рантайм-залежностей, тільки стандартна
бібліотека Python (≥3.11). Він нічого не імпортує зі споживачів — навпаки,
споживачі залежать від нього.

## Споживачі

- [mcp-baf](https://github.com/andriy4k07/mcp-baf) — MCP-сервер читання 1С
  (інтеграція запланована окремим PR).
- [baf-write-mcp](https://github.com/andriy4k07/baf-write-mcp) — MCP-сервер
  контрольованого створення номенклатури в 1С (вже переведений на цей пакет).
- hermes — інтеграція запланована.

## Схема запису

Кожен рядок журналу — один JSON-об'єкт зі спільним конвертом:

```json
{
  "schema_version": "1",
  "ts": "2026-06-14T10:51:23.354+00:00",
  "service": "baf-write-mcp",
  "session": "d6dfd09f2d7d",
  "seq": 1043,
  "trace_id": "abc123…",
  "event": "tool_call",
  "level": "info",
  "tool": "create",
  "duration_ms": 87,
  "status": 200,
  "payload": { },
  "error": null
}
```

`service` — ім'я сервіса (`mcp-baf` | `baf-write-mcp` | `hermes`);
`session` — hex12, один на процес; `seq` — монотонний лічильник у сеансі;
`trace_id` — наскрізний ідентифікатор операції між сервісами (або `null`).

> Будь-яка зміна формату рядка → bump `SCHEMA_VERSION` у `writer.py`
> і minor/major тега пакета.

## Використання

```python
from mcp_baf_audit import AuditWriter, traced, set_trace_id

audit = AuditWriter(service="mcp-baf", path="/path/to/audit.log")
audit.server_start(version="1.2.3")

# Канонічний метод (payload — подіє-специфічний, уже редагується):
audit.event("tool_call", tool="query", status=200, duration_ms=12,
            payload={"sql": "…"})

# Обгортка інструмента: пише tool_call/tool_error, міряє duration,
# підхоплює trace_id з аргументу або contextvar.
result_json = await traced(audit, "query", call, args={"limit": 10})
```

### Секрети

Редакція централізована у writer'і: ключі `password|token|authorization|secret`
(регістронезалежно, рекурсивно) замінюються на `***` у кожному записі.
Передавати «сирий» payload безпечно — секрети у лог не потрапляють.

## Постачання / версіонування

Тег `v0.1.0`. Споживачі пінять версію:

```
pip install "git+https://github.com/andriy4k07/mcp-baf-audit.git@v0.1.0"
```

У монорепо — path-залежність від сусіднього каталогу:

```
pip install -e ../mcp-baf-audit
```
