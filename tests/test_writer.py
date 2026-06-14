"""Тесты JSONL-writer'а аудита: схема, сессия/seq, ротация, редакция."""

import json

from mcp_baf_audit import (
    DEFAULT_AUDIT_ARCHIVES,
    DEFAULT_AUDIT_MAX_SIZE_MIB,
    SCHEMA_VERSION,
    AuditLog,
    AuditWriter,
    REDACTED,
)


def read_events(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def make_writer(tmp_path, **kw):
    return AuditWriter("baf-write-mcp", tmp_path / "audit.log", **kw)


def test_event_has_full_schema_envelope(tmp_path):
    w = make_writer(tmp_path)
    w.event(
        "tool_call", tool="create", status=200, duration_ms=87,
        payload={"name": "Болт"},
    )
    (rec,) = read_events(tmp_path / "audit.log")
    assert rec["schema_version"] == SCHEMA_VERSION
    assert rec["service"] == "baf-write-mcp"
    assert rec["event"] == "tool_call"
    assert rec["tool"] == "create"
    assert rec["status"] == 200
    assert rec["duration_ms"] == 87
    assert rec["level"] == "info"
    assert rec["trace_id"] is None
    assert rec["error"] is None
    assert rec["payload"] == {"name": "Болт"}
    assert rec["seq"] == 1
    assert "ts" in rec and rec["ts"].endswith("+00:00")


def test_write_keeps_flat_details_and_request_id(tmp_path):
    w = make_writer(tmp_path)
    w.write("propose", "req-1", draft={"name": "Тест"})
    w.write("create", "req-1", result={"ref": "x"})

    first, second = read_events(tmp_path / "audit.log")
    assert first["event"] == "propose"
    assert first["request_id"] == "req-1"
    assert first["draft"] == {"name": "Тест"}
    assert first["schema_version"] == SCHEMA_VERSION
    assert first["service"] == "baf-write-mcp"
    assert second["result"] == {"ref": "x"}


def test_session_and_seq(tmp_path):
    w = make_writer(tmp_path)
    w.server_start()
    w.write("tool_call", tool="x")

    first, second = read_events(tmp_path / "audit.log")
    assert first["session"] == second["session"] == w.session_id
    assert (first["seq"], second["seq"]) == (1, 2)

    other = make_writer(tmp_path)
    assert other.session_id != w.session_id


def test_explicit_trace_id_wins(tmp_path):
    w = make_writer(tmp_path)
    w.event("tool_call", trace_id="trace-xyz")
    w.write("create", "req-1", trace_id="trace-xyz")
    a, b = read_events(tmp_path / "audit.log")
    assert a["trace_id"] == b["trace_id"] == "trace-xyz"


def test_secrets_never_reach_the_log(tmp_path):
    w = make_writer(tmp_path)
    w.event(
        "server_start",
        payload={"user": "vasya", "password": "p@ss", "Authorization": "Bearer z"},
    )
    w.write("login", body={"token": "abc", "nested": {"secret": "s"}})

    text = (tmp_path / "audit.log").read_text(encoding="utf-8")
    assert "p@ss" not in text
    assert "abc" not in text
    assert "Bearer z" not in text
    assert "\"s\"" not in text

    ev, wr = read_events(tmp_path / "audit.log")
    assert ev["payload"]["password"] == REDACTED
    assert ev["payload"]["Authorization"] == REDACTED
    assert ev["payload"]["user"] == "vasya"
    assert wr["body"]["token"] == REDACTED
    assert wr["body"]["nested"]["secret"] == REDACTED


def test_rotates_by_size_and_prunes_archives(tmp_path):
    w = make_writer(tmp_path, max_bytes=1 << 20, backups=1)
    payload = "x" * 65536
    for _ in range(40):  # ~2.5 MiB суммарно -> минимум две ротации
        w.write("bulk", data=payload)

    archives = sorted(tmp_path.glob("audit-*.log"))
    assert len(archives) == 1  # старые архивы сверх лимита удалены
    current = read_events(tmp_path / "audit.log")
    assert all(e["event"] == "bulk" for e in current)
    assert (tmp_path / "audit.log").stat().st_size < 1 << 20


def test_swallows_io_errors(tmp_path):
    blocker = tmp_path / "blocked"
    blocker.write_text("file, not a dir", encoding="utf-8")
    w = AuditWriter("svc", blocker / "audit.log")
    w.write("propose", "req-1")  # не должно бросать


def test_context_manager(tmp_path):
    with make_writer(tmp_path) as w:
        w.server_start()
    assert len(read_events(tmp_path / "audit.log")) == 1


def test_auditlog_compat_constructor(tmp_path):
    audit = AuditLog(str(tmp_path))
    audit.write("server_start", version="0.3.0")
    (rec,) = read_events(tmp_path / "audit.log")
    assert rec["service"] == "baf-write-mcp"
    assert rec["event"] == "server_start"
    assert rec["version"] == "0.3.0"
    # Дефолты ротации совпадают с прежним baf-write.
    assert DEFAULT_AUDIT_MAX_SIZE_MIB == 50
    assert DEFAULT_AUDIT_ARCHIVES == 20
