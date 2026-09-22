"""Tests for trace/record.py: content addressing, truncation, secret hashing, and
JSONL round-tripping."""
from __future__ import annotations

from pathlib import Path

from pb.trace.record import content_address, hash_secret, read_trace, truncate_repr, write_trace
from pb.trace.schema import Call, Decision, RawArgument, Result, Span, TaskEnd


def test_content_address_is_deterministic() -> None:
    assert content_address("user_message", "hello") == content_address("user_message", "hello")


def test_content_address_differs_for_different_content() -> None:
    assert content_address("user_message", "hello") != content_address("user_message", "goodbye")


def test_content_address_differs_for_different_kind() -> None:
    assert content_address("user_message", "hello") != content_address("system_prompt", "hello")


def test_truncate_repr_leaves_short_text_unchanged() -> None:
    assert truncate_repr("short", max_len=100) == "short"


def test_truncate_repr_truncates_long_text() -> None:
    text = "x" * 600
    result = truncate_repr(text, max_len=500)
    assert result.startswith("x" * 500)
    assert "truncated 100 chars" in result
    assert len(result) < len(text)


def test_hash_secret_never_contains_the_raw_value() -> None:
    result = hash_secret("hunter2")
    assert "hunter2" not in result
    assert result.startswith("sha256:")


def test_hash_secret_is_deterministic() -> None:
    assert hash_secret("hunter2") == hash_secret("hunter2")


def test_write_and_read_trace_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    events = [
        Span(span_id="s1", kind="user_message", content_repr="pay my rent"),
        Call(call_id="c1", tool="send_money", arguments=(RawArgument("recipient", "'bob'"),)),
        Span(span_id="s2", kind="tool_result:send_money", content_repr="ok"),
        Result(call_id="c1", result_span_id="s2"),
        Decision(call_id="c1", labeller_id="oracle", verdict="allow"),
        TaskEnd(task_id="t1", seed=0, outcome="benign_success"),
    ]
    write_trace(path, events, mode="w")
    read_back = read_trace(path)
    assert read_back == events


def test_write_trace_appends_by_default(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    first = [TaskEnd(task_id="t1", seed=0, outcome="a")]
    second = [TaskEnd(task_id="t2", seed=0, outcome="b")]
    write_trace(path, first, mode="w")
    write_trace(path, second)
    assert read_trace(path) == [*first, *second]


def test_read_trace_rejects_unknown_event_type(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    path.write_text('{"event": "mystery"}\n', encoding="utf-8")
    try:
        read_trace(path)
        raised = False
    except ValueError:
        raised = True
    assert raised
