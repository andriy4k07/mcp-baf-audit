"""Тесты канонической таксономии событий (events.py) и нормализации writer'ом."""

import json

import pytest

from mcp_baf_audit import ALIASES, AuditWriter, canonical, events


def read_events(path):
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()]


def test_canonical_maps_known_flat_names():
    assert canonical("create") == "product.create"
    assert canonical("tool_call") == "tool.call"
    assert canonical("tool_error") == "tool.error"
    assert canonical("server_start") == "server.start"
    assert canonical("extension_version_mismatch") == "server.version_mismatch"
    assert canonical("propose_counterparty") == "counterparty.propose"
    assert canonical("validate_property_value") == "property_value.validate"


def test_canonical_passes_through_unknown_and_canonical_names():
    # Имя без алиаса (например, *_error или накладные) не меняется.
    assert canonical("validate_error") == "validate_error"
    assert canonical("create_incoming_invoice") == "create_incoming_invoice"
    # Уже каноническое имя остаётся собой.
    assert canonical("product.create") == "product.create"
    assert canonical("one_c.http") == "one_c.http"


def test_canonical_is_idempotent():
    for name in ("create", "tool_call", "propose_counterparty", "bulk"):
        assert canonical(canonical(name)) == canonical(name)


def test_aliases_target_only_canonical_names():
    # Все цели алиасов — значения констант таксономии (namespaced, с точкой).
    canonical_values = {
        getattr(events, n)
        for n in dir(events)
        if n.isupper() and isinstance(getattr(events, n), str)
    }
    for src, target in ALIASES.items():
        assert "." in target, target
        assert target in canonical_values, target
        # Алиас и цель различны (алиас — именно прежнее плоское имя).
        assert src != target


def test_writer_normalizes_event_name_on_write(tmp_path):
    w = AuditWriter("baf-write-mcp", tmp_path / "audit.log")
    w.write("create", "req-1", result={"ref": "x"})
    w.event("tool_call", tool="create_product_catalog_item")
    w.write("create_incoming_invoice", "req-2")  # без алиаса — как есть

    a, b, c = read_events(tmp_path / "audit.log")
    assert a["event"] == "product.create"
    assert b["event"] == "tool.call"
    assert c["event"] == "create_incoming_invoice"


@pytest.mark.parametrize(
    "const,value",
    [
        (events.TOOL_CALL, "tool.call"),
        (events.PRODUCT_CREATE, "product.create"),
        (events.SERVER_VERSION_MISMATCH, "server.version_mismatch"),
        (events.ONE_C_HTTP, "one_c.http"),
        (events.INDEX_REFRESH_START, "index.refresh_start"),
        (events.INDEX_CACHE_MISS, "index.cache_miss"),
    ],
)
def test_canonical_constants_have_expected_values(const, value):
    assert const == value