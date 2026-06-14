"""Тесты централизованной редакции секретов."""

from mcp_baf_audit import REDACTED, default_redactor


def test_redacts_known_secret_keys_case_insensitive():
    out = default_redactor(
        {"user": "vasya", "Password": "p@ss", "TOKEN": "abc", "ok": 1}
    )
    assert out == {"user": "vasya", "Password": REDACTED, "TOKEN": REDACTED, "ok": 1}


def test_redacts_substring_matches():
    out = default_redactor(
        {"access_token": "x", "api_secret": "y", "Authorization": "Bearer z"}
    )
    assert out == {
        "access_token": REDACTED,
        "api_secret": REDACTED,
        "Authorization": REDACTED,
    }


def test_redacts_recursively_in_nested_structures():
    out = default_redactor(
        {
            "level1": {"password": "secret", "name": "n"},
            "items": [{"token": "t1"}, {"id": 5}],
        }
    )
    assert out == {
        "level1": {"password": REDACTED, "name": "n"},
        "items": [{"token": REDACTED}, {"id": 5}],
    }


def test_does_not_mutate_input():
    src = {"password": "secret", "nested": {"token": "t"}}
    default_redactor(src)
    assert src == {"password": "secret", "nested": {"token": "t"}}


def test_non_secret_scalars_pass_through():
    assert default_redactor("plain") == "plain"
    assert default_redactor(42) == 42
    assert default_redactor([1, 2, 3]) == [1, 2, 3]
