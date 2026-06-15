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

## Схема запису (v2)

Кожен рядок журналу — один JSON-об'єкт зі спільним конвертом:

```json
{
  "schema_version": "2",
  "ts": "2026-06-14T10:51:23.354+00:00",
  "service": "baf-write-mcp",
  "session": "d6dfd09f2d7d",
  "seq": 1043,
  "trace_id": "abc123…",
  "event": "product.create",
  "level": "info",
  "tool": "create_product_catalog_item",
  "request_id": "req-7",
  "object": { "type": "product", "ref": "uuid…", "code": "000001", "name": "Болт" },
  "actor": "write-svc",
  "source_channel": "mcp",
  "ok": true,
  "duration_ms": 87,
  "status": 200,
  "payload": { },
  "error": null
}
```

`service` — ім'я сервіса (`mcp-baf` | `baf-write-mcp` | `hermes`);
`session` — hex12, один на процес; `seq` — монотонний лічильник у сеансі;
`trace_id` — наскрізний ідентифікатор операції між сервісами, **ніколи не
null у нових записах** (вкладені події успадковують його через contextvar).

Optional-поля конверта v2 (`request_id`, `object`, `actor`, `source_channel`,
`ok`, `duration_ms`, `status`) nullable: їхня відсутність у рядку (зокрема в
логах v1) не ламає читання. Редакція секретів застосовується і до `payload`,
і до `object`.

> Будь-яка зміна формату рядка → bump `SCHEMA_VERSION` у `writer.py`
> і minor/major тега пакета. v2 додав optional-поля конверта; читач
> розуміє і v1, і v2.

## Канонічні імена подій

`events.py` фіксує namespaced-таксономію (`tool.call`, `product.create`,
`counterparty.propose`, `one_c.http`, `index.search`, …). Writer нормалізує
ім'я кожного запису через `canonical()`, тож **нові логи завжди канонічні** —
навіть якщо доменний код передає звичне плоске ім'я. Старі логи лишаються
читабельними: той самий `canonical()` мапить плоскі імена v1 у канонічні.

```python
from mcp_baf_audit import canonical, events

canonical("create")             # -> "product.create"
canonical("tool_call")          # -> "tool.call"
canonical("product.create")     # -> "product.create" (ідемпотентно)
events.PRODUCT_CREATE           # "product.create"
```

## Використання

```python
from mcp_baf_audit import AuditWriter, traced, iter_events

audit = AuditWriter(service="mcp-baf", path="/path/to/audit.log")
audit.server_start(version="1.2.3")

# Канонічний метод v2 (payload і object редагуються від секретів):
audit.event("product.create", tool="create_product_catalog_item",
            request_id="req-7", status=200, duration_ms=12, ok=True,
            obj={"type": "product", "ref": "uuid…", "name": "Болт"},
            payload={"name": "Болт"})

# Обгортка інструмента: пише tool.call/tool.error, міряє duration,
# гарантує не-null trace_id (явний -> contextvar -> новий) і фіксує його
# в contextvar, щоб вкладені події успадкували.
result_json = await traced(audit, "query", call, args={"limit": 10})
```

### Читання журналу

`iter_events()` — єдина читацька функція. Вона обходить ротовані архіви в
хронологічному порядку, мовчки пропускає биті рядки (повідомляє про кожен
через `on_bad_line`) і нормалізує `event` через `canonical()`. На ній
будуються зовнішні проєкція/дашборд — сама бібліотека ні БД, ні форматів
представлення не знає.

```python
from mcp_baf_audit import iter_events

bad: list[str] = []
for ev in iter_events("/path/to/audit.log", on_bad_line=bad.append):
    print(ev["seq"], ev["event"], ev.get("trace_id"))
print("пропущено битих рядків:", len(bad))
```

### HTTP-події `one_c.http`

`baf-write-mcp` передає аудит у HTTP-клієнт (`OneCClient(config, audit=audit)`),
і кожен виклик 1С лишає рівно одну подію `one_c.http` (метод, ендпоінт,
статус, `duration_ms`, `response_bytes`, `request_id`, `trace_id`). **Тіло
запиту/відповіді не логується**; помилки пишуться з `level:"error"`, `ok:false`.

### Секрети

Редакція централізована у writer'і: ключі `password|token|authorization|secret`
(регістронезалежно, рекурсивно) замінюються на `***` у кожному записі.
Передавати «сирий» payload безпечно — секрети у лог не потрапляють.

## Постачання / версіонування

Тег `v0.2.0` (minor-bump: формат запису перейшов на schema v2). Споживачі
пінять версію:

```
pip install "git+https://github.com/andriy4k07/mcp-baf-audit.git@v0.2.0"
```

У монорепо — path-залежність від сусіднього каталогу:

```
pip install -e ../mcp-baf-audit
```
