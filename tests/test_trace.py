"""Тесты сквозного trace_id и обёртки traced()."""

import asyncio
import json

import pytest

from mcp_baf_audit import (
    AuditWriter,
    get_trace_id,
    new_trace_id,
    set_trace_id,
    traced,
)


def make_writer(tmp_path):
    return AuditWriter("mcp-baf", tmp_path / "audit.log")


def last_event(tmp_path):
    lines = (tmp_path / "audit.log").read_text("utf-8").splitlines()
    return json.loads(lines[-1])


def teardown_function():
    set_trace_id(None)


def test_new_trace_id_unique():
    assert new_trace_id() != new_trace_id()


def test_set_get_trace_id():
    assert get_trace_id() is None
    set_trace_id("abc123")
    assert get_trace_id() == "abc123"


def test_traced_logs_tool_call_with_duration(tmp_path):
    w = make_writer(tmp_path)

    async def call():
        return {"types": []}

    out = asyncio.run(traced(w, "metadata", call, args={"a": 1}))
    assert json.loads(out) == {"types": []}

    ev = last_event(tmp_path)
    assert ev["event"] == "tool_call"
    assert ev["tool"] == "metadata"
    assert ev["args"] == {"a": 1}
    assert ev["ok"] is True
    assert isinstance(ev["duration_ms"], int)
    assert ev["service"] == "mcp-baf"
    assert ev["trace_id"] is None


def test_traced_picks_request_id_from_result(tmp_path):
    w = make_writer(tmp_path)

    async def call():
        return {"complete": True, "request_id": "req-7"}

    asyncio.run(traced(w, "propose", call))
    assert last_event(tmp_path)["request_id"] == "req-7"


def test_traced_marks_error_result_not_ok(tmp_path):
    w = make_writer(tmp_path)

    async def call():
        return {"error": "неизвестный request_id"}

    asyncio.run(traced(w, "create", call))
    ev = last_event(tmp_path)
    assert ev["event"] == "tool_call"
    assert ev["ok"] is False


def test_traced_logs_tool_error_on_exception(tmp_path):
    w = make_writer(tmp_path)

    async def call():
        raise RuntimeError("1C недоступна")

    with pytest.raises(RuntimeError):
        asyncio.run(traced(w, "validate", call, request_id="req-1"))

    ev = last_event(tmp_path)
    assert ev["event"] == "tool_error"
    assert ev["level"] == "error"
    assert ev["tool"] == "validate"
    assert ev["request_id"] == "req-1"
    assert "1C недоступна" in ev["error"]
    assert "duration_ms" in ev


def test_traced_explicit_trace_id(tmp_path):
    w = make_writer(tmp_path)

    async def call():
        return {"ok": True}

    asyncio.run(traced(w, "query", call, trace_id="trace-1"))
    assert last_event(tmp_path)["trace_id"] == "trace-1"


def test_traced_picks_trace_id_from_contextvar(tmp_path):
    w = make_writer(tmp_path)
    set_trace_id("ctx-trace")

    async def call():
        return {"ok": True}

    asyncio.run(traced(w, "query", call))
    assert last_event(tmp_path)["trace_id"] == "ctx-trace"
