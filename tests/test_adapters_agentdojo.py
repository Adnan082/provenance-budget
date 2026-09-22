"""Tests for adapters/agentdojo.py against the real, installed agentdojo package
(agentdojo==0.1.35) — no model calls, via GroundTruthPipeline. These are integration
tests: they exercise the real suite/task/environment machinery, not a mock of it."""
from __future__ import annotations

import pytest
from agentdojo.task_suite.load_suites import get_suites

from pb.adapters.agentdojo import _raw_argument, messages_to_events, record_ground_truth_trace
from pb.trace.schema import Call, Result, Span, TaskEnd

_ALL_USER_TASKS = [
    (suite_name, task_id)
    for suite_name, suite in get_suites("v1").items()
    for task_id in suite.user_tasks
]


def test_record_ground_truth_trace_banking_user_task_0() -> None:
    events = record_ground_truth_trace("v1", "banking", "user_task_0", seed=0)

    assert isinstance(events[0], Span)
    assert events[0].kind == "user_message"
    assert "bill" in events[0].content_repr

    calls = [e for e in events if isinstance(e, Call)]
    assert [c.tool for c in calls] == ["read_file", "send_money"]
    assert calls[0].call_id == "user_task_0:0:1"
    assert calls[1].call_id == "user_task_0:0:2"

    results = [e for e in events if isinstance(e, Result)]
    assert len(results) == 2
    assert all(r.error is None for r in results)
    assert {r.call_id for r in results} == {calls[0].call_id, calls[1].call_id}

    tool_result_spans = [e for e in events if isinstance(e, Span) and e.kind.startswith("tool_result:")]
    assert [s.kind for s in tool_result_spans] == ["tool_result:read_file", "tool_result:send_money"]
    # each Result points at the span recorded immediately before it
    for result, span in zip(results, tool_result_spans):
        assert result.result_span_id == span.span_id

    task_end = events[-1]
    assert isinstance(task_end, TaskEnd)
    assert task_end.task_id == "user_task_0"
    assert task_end.outcome == "ground_truth"


def test_record_ground_truth_trace_send_money_arguments_are_not_hashed() -> None:
    events = record_ground_truth_trace("v1", "banking", "user_task_0", seed=0)
    send_money = next(e for e in events if isinstance(e, Call) and e.tool == "send_money")
    by_param = {a.param_name: a.value_repr for a in send_money.arguments}
    assert by_param["recipient"] == "'UK12345678901234567890'"
    assert not by_param["recipient"].startswith("sha256:")


def test_record_ground_truth_trace_carries_injected_environment_content() -> None:
    events = record_ground_truth_trace(
        "v1", "banking", "user_task_0", seed=0, injections={"injection_bill_text": "MALICIOUS_PAYLOAD_MARKER"}
    )
    read_file_span = next(
        e for e in events if isinstance(e, Span) and e.kind == "tool_result:read_file"
    )
    assert "MALICIOUS_PAYLOAD_MARKER" in read_file_span.content_repr


def test_raw_argument_hashes_credential_role_values() -> None:
    arg = _raw_argument("update_password", "password", "hunter2")
    assert arg.value_repr.startswith("sha256:")
    assert "hunter2" not in arg.value_repr


def test_raw_argument_truncates_non_credential_values() -> None:
    arg = _raw_argument("send_money", "subject", "x" * 600)
    assert not arg.value_repr.startswith("sha256:")
    assert "truncated" in arg.value_repr


def test_messages_to_events_matches_tool_results_to_calls_in_fifo_order() -> None:
    class _FakeCall:
        def __init__(self, function: str, args: dict[str, object]) -> None:
            self.function = function
            self.args = args

    messages = [
        {
            "role": "assistant",
            "tool_calls": [_FakeCall("get_balance", {}), _FakeCall("get_iban", {})],
        },
        {
            "role": "tool",
            "tool_call": _FakeCall("get_balance", {}),
            "content": [{"type": "text", "content": "100"}],
        },
        {
            "role": "tool",
            "tool_call": _FakeCall("get_iban", {}),
            "content": [{"type": "text", "content": "GB00"}],
        },
    ]
    events = messages_to_events("t1", 0, "do it", messages, outcome="ok")
    calls = [e for e in events if isinstance(e, Call)]
    results = [e for e in events if isinstance(e, Result)]
    assert calls[0].tool == "get_balance" and results[0].call_id == calls[0].call_id
    assert calls[1].tool == "get_iban" and results[1].call_id == calls[1].call_id


@pytest.mark.parametrize("suite_name,task_id", _ALL_USER_TASKS, ids=[f"{s}:{t}" for s, t in _ALL_USER_TASKS])
def test_ground_truth_trace_converts_cleanly_for_every_real_user_task(suite_name: str, task_id: str) -> None:
    """Every ground-truth tool call in AgentDojo v1's 97 user tasks (across all 4
    suites) must resolve a role for every agent-supplied argument via enforce/roles.py
    — this is what tests/test_roles.py's live-signature cross-check is actually for:
    catching a gap here before it surfaces as a RoleNotAssigned deep in a real run."""
    events = record_ground_truth_trace("v1", suite_name, task_id, seed=0)
    assert isinstance(events[-1], TaskEnd)
    assert events[-1].outcome == "ground_truth"


def test_messages_to_events_raises_on_orphan_tool_result() -> None:
    messages = [{"role": "tool", "tool_call": None, "content": []}]
    raised = False
    try:
        messages_to_events("t1", 0, "do it", messages, outcome="ok")
    except ValueError:
        raised = True
    assert raised
