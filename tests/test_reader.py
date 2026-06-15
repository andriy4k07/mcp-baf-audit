"""Тесты reader-утилиты iter_events: ротация, порядок, битые строки, canonical."""

import json

from mcp_baf_audit import AuditWriter, iter_events


def make_writer(tmp_path, **kw):
    # Маленький лимит -> несколько ротаций на десятке событий.
    return AuditWriter("mcp-baf", tmp_path / "audit.log", max_bytes=400, **kw)


def test_iter_events_across_rotation_in_order_with_bad_line(tmp_path):
    w = make_writer(tmp_path)
    n = 12
    for i in range(n):
        # payload раздувает строку, чтобы сработала ротация по размеру.
        w.write("create", f"req-{i}", draft={"i": i, "pad": "x" * 64})

    # Ротация действительно произошла — есть хотя бы один архив.
    archives = list(tmp_path.glob("audit-*.log"))
    assert archives, "ожидалась ротация журнала"

    # Дописываем одну битую строку в активный журнал.
    with open(tmp_path / "audit.log", "a", encoding="utf-8") as f:
        f.write("{не json вовсе\n")

    bad: list[str] = []
    events = list(iter_events(tmp_path / "audit.log", on_bad_line=bad.append))

    # Все валидные события прочитаны, битая — пропущена и посчитана.
    assert len(events) == n
    assert len(bad) == 1

    # Порядок хронологический и сквозной по seq (архивы -> активный журнал).
    assert [e["seq"] for e in events] == list(range(1, n + 1))
    assert [e["request_id"] for e in events] == [f"req-{i}" for i in range(n)]

    # Имя события нормализовано в каноническое.
    assert all(e["event"] == "product.create" for e in events)


def test_iter_events_without_rotation_reads_active_only(tmp_path):
    w = make_writer(tmp_path)
    for i in range(12):
        w.write("create", f"req-{i}", draft={"i": i, "pad": "x" * 64})

    full = list(iter_events(tmp_path / "audit.log", follow_rotation=True))
    active_only = list(iter_events(tmp_path / "audit.log", follow_rotation=False))

    assert len(full) == 12
    # Активный журнал содержит только хвост (после последней ротации).
    assert 0 < len(active_only) < len(full)
    # Это именно последние события.
    tail = [e["seq"] for e in full][-len(active_only):]
    assert [e["seq"] for e in active_only] == tail


def test_iter_events_normalizes_v1_flat_names(tmp_path):
    log = tmp_path / "audit.log"
    lines = [
        {"event": "tool_call", "seq": 1},          # v1 плоское -> tool.call
        {"event": "product.create", "seq": 2},     # уже каноническое
        {"event": "propose_counterparty", "seq": 3},  # -> counterparty.propose
    ]
    log.write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines),
        encoding="utf-8",
    )
    events = list(iter_events(log))
    assert [e["event"] for e in events] == [
        "tool.call", "product.create", "counterparty.propose",
    ]


def test_iter_events_missing_file_is_empty(tmp_path):
    assert list(iter_events(tmp_path / "nope.log")) == []


def test_iter_events_skips_blank_lines_without_counting(tmp_path):
    log = tmp_path / "audit.log"
    log.write_text(
        '{"event":"server_start","seq":1}\n\n   \n{"event":"server_stop","seq":2}\n',
        encoding="utf-8",
    )
    bad: list[str] = []
    events = list(iter_events(log, on_bad_line=bad.append))
    assert [e["event"] for e in events] == ["server.start", "server.stop"]
    assert bad == []  # пустые строки не считаются битыми
