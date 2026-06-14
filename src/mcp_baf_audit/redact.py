"""Централизованная редакция секретов перед записью в журнал.

Секреты не должны попадать в аудит ни при каких условиях. Редакция
выполняется в writer'е для каждой записи, поэтому доменный код может
передавать payload как есть — ключи password/token/authorization/secret
(регистронезависимо, на любой глубине) заменяются заглушкой.
"""

from __future__ import annotations

from typing import Any

# Заглушка вместо значения секрета. Сам факт наличия ключа сохраняется
# (полезно для отладки), но значение не раскрывается.
REDACTED = "***"

# Подстроки имён ключей, значения которых считаются секретами. Совпадение
# по подстроке (регистронезависимо) ловит и производные имена:
# access_token, api_secret, Authorization, X-Auth-Token и т.п.
SECRET_KEY_SUBSTRINGS = ("password", "token", "authorization", "secret")


def _is_secret_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    low = key.lower()
    return any(sub in low for sub in SECRET_KEY_SUBSTRINGS)


def default_redactor(value: Any) -> Any:
    """Рекурсивно заменяет значения секретных ключей на заглушку.

    Возвращает новую структуру (исходные dict/list не мутируются).
    Скаляры возвращаются как есть.
    """
    if isinstance(value, dict):
        return {
            k: (REDACTED if _is_secret_key(k) else default_redactor(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [default_redactor(v) for v in value]
    return value
