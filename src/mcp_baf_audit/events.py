"""Каноническая таксономия событий аудита.

Единый словарь namespaced-имён событий для всех сервисов BAF. Раньше каждый
сервис писал плоские имена ("create", "tool_call", "propose_counterparty"),
из-за чего одно и то же действие выглядело по-разному и плохо группировалось.
Здесь зафиксированы канонические имена вида ``<домен>.<действие>``.

Совместимость двусторонняя:

* writer нормализует имя каждой записи через :func:`canonical`, поэтому новые
  логи всегда несут канонические имена — даже если доменный код по-прежнему
  передаёт привычное плоское имя ("create" -> "product.create");
* старые логи остаются читаемыми: потребитель прогоняет прочитанное имя через
  ту же :func:`canonical` и получает канонический вид, а имена без записи в
  :data:`ALIASES` (или уже канонические) возвращаются как есть.
"""

from __future__ import annotations

# ── Канонические имена событий ──────────────────────────────────────

# Вызовы инструментов (обёртка traced()).
TOOL_CALL = "tool.call"
TOOL_ERROR = "tool.error"

# Жизненный цикл сервера.
SERVER_START = "server.start"
SERVER_STOP = "server.stop"
SERVER_VERSION_MISMATCH = "server.version_mismatch"

# Номенклатура (каталожная позиция): propose -> validate -> create -> verify.
PRODUCT_PROPOSE = "product.propose"
PRODUCT_VALIDATE = "product.validate"
PRODUCT_CREATE = "product.create"
PRODUCT_VERIFY = "product.verify"
PRODUCT_REFUSED = "product.refused"

# Значения списковых свойств номенклатуры.
PROPERTY_VALUE_PROPOSE = "property_value.propose"
PROPERTY_VALUE_VALIDATE = "property_value.validate"
PROPERTY_VALUE_CREATE = "property_value.create"

# Контрагенты.
COUNTERPARTY_PROPOSE = "counterparty.propose"
COUNTERPARTY_VALIDATE = "counterparty.validate"
COUNTERPARTY_CREATE = "counterparty.create"
COUNTERPARTY_VERIFY = "counterparty.verify"

# Обращения к HTTP-сервису 1С.
ONE_C_HTTP = "one_c.http"

# Поисковый индекс (mcp-baf): обновление, поиск, кэш.
INDEX_REFRESH_START = "index.refresh_start"
INDEX_REFRESH_FINISH = "index.refresh_finish"
INDEX_REFRESH_ERROR = "index.refresh_error"
INDEX_SEARCH = "index.search"
INDEX_CACHE_HIT = "index.cache_hit"
INDEX_CACHE_MISS = "index.cache_miss"


# ── Алиасы: прежние плоские имена -> канонические ───────────────────
#
# Только имена, у которых есть канонический эквивалент в таксономии выше.
# Прочие плоские имена (*_error, *_incomplete, накладные и т.п.) намеренно
# не отображаются и проходят через canonical() без изменений.
ALIASES: dict[str, str] = {
    # Инструменты.
    "tool_call": TOOL_CALL,
    "tool_error": TOOL_ERROR,
    # Сервер.
    "server_start": SERVER_START,
    "server_stop": SERVER_STOP,
    "extension_version_mismatch": SERVER_VERSION_MISMATCH,
    # Номенклатура (плоские имена baf-write).
    "propose": PRODUCT_PROPOSE,
    "validate": PRODUCT_VALIDATE,
    "create": PRODUCT_CREATE,
    "verify": PRODUCT_VERIFY,
    "create_refused": PRODUCT_REFUSED,
    # Значения свойств.
    "propose_property_value": PROPERTY_VALUE_PROPOSE,
    "validate_property_value": PROPERTY_VALUE_VALIDATE,
    "create_property_value": PROPERTY_VALUE_CREATE,
    # Контрагенты.
    "propose_counterparty": COUNTERPARTY_PROPOSE,
    "validate_counterparty": COUNTERPARTY_VALIDATE,
    "create_counterparty": COUNTERPARTY_CREATE,
    "verify_counterparty": COUNTERPARTY_VERIFY,
}


def canonical(name: str) -> str:
    """Нормализует имя события в каноническое.

    Прежнее плоское имя из :data:`ALIASES` отображается в каноническое;
    уже каноническое имя (или имя без алиаса) возвращается без изменений.
    Функция идемпотентна: ``canonical(canonical(x)) == canonical(x)``.
    """
    return ALIASES.get(name, name)