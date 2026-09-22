"""Tests for trace/replay.py — CLAUDE.md 'Replay discipline'."""
from __future__ import annotations

from pathlib import Path

from pb.adapters.agentdojo import record_ground_truth_trace
from pb.enforce.contracts import Contract, load_contracts
from pb.labellers.base import Labeller, LabellerCost
from pb.labellers.blanket import BlanketLabeller
from pb.labellers.echo import EchoLabeller
from pb.trace.record import TraceEvent
from pb.trace.replay import replay
from pb.trace.schema import ArgumentFact, Call, RawArgument, Span

POLICY_PATH = Path(__file__).resolve().parents[1] / "contracts" / "policy.yaml"


class _PrefixRecordingLabeller(Labeller):
    """Records exactly what prefix it was handed at each call, so tests can assert on
    lookahead directly rather than trusting replay() not to peek ahead."""

    id = "prefix-recorder"

    def __init__(self) -> None:
        self.seen_prefixes: list[tuple[Span, ...]] = []

    def label(self, prefix: tuple[Span, ...], call: Call) -> tuple[ArgumentFact, ...]:
        self.seen_prefixes.append(prefix)
        return tuple(
            ArgumentFact(call_id=call.call_id, param_name=a.param_name, value_repr=a.value_repr, trust="TRUSTED", role="content")
            for a in call.arguments
        )

    def cost(self) -> LabellerCost:
        return LabellerCost()


def test_replay_never_shows_a_labeller_spans_recorded_after_its_call() -> None:
    events: tuple[TraceEvent, ...] = (
        Span(span_id="s1", kind="user_message", content_repr="first"),
        Call(call_id="c1", tool="t", arguments=(RawArgument("p", "v"),)),
        Span(span_id="s2", kind="tool_result:t", content_repr="second"),
        Call(call_id="c2", tool="t", arguments=(RawArgument("p", "v"),)),
        Span(span_id="s3", kind="tool_result:t", content_repr="third"),
    )
    labeller = _PrefixRecordingLabeller()
    replay(events, labeller, contracts=())
    assert [s.span_id for s in labeller.seen_prefixes[0]] == ["s1"]
    assert [s.span_id for s in labeller.seen_prefixes[1]] == ["s1", "s2"]


def test_replay_produces_one_decision_per_call_with_labeller_id() -> None:
    events: tuple[TraceEvent, ...] = (
        Span(span_id="s1", kind="user_message", content_repr="hi"),
        Call(call_id="c1", tool="t", arguments=()),
        Call(call_id="c2", tool="t", arguments=()),
    )
    decisions = replay(events, _PrefixRecordingLabeller(), contracts=())
    assert [d.call_id for d in decisions] == ["c1", "c2"]
    assert all(d.labeller_id == "prefix-recorder" for d in decisions)
    assert all(d.verdict == "allow" for d in decisions)  # no contracts govern "content"


def test_replay_applies_monitor_verdicts_from_contracts() -> None:
    events: tuple[TraceEvent, ...] = (Call(call_id="c1", tool="t", arguments=(RawArgument("p", "v"),)),)
    contracts = (Contract(role="content", min_trust="USER", on_violation="block"),)
    decisions = replay(events, _PrefixRecordingLabeller(), contracts)  # labels role="content" as TRUSTED
    assert decisions[0].verdict == "allow"  # TRUSTED satisfies min_trust=USER


def test_replay_against_real_recorded_trace_blanket_vs_echo() -> None:
    events = tuple(record_ground_truth_trace("v1", "banking", "user_task_0", seed=0))
    contracts = load_contracts(POLICY_PATH)

    blanket_decisions = replay(events, BlanketLabeller(), contracts)
    echo_decisions = replay(events, EchoLabeller(), contracts)

    # blanket: every argument is forced EXTERNAL, so both calls violate something.
    assert [d.verdict for d in blanket_decisions] == ["escalate", "block"]
    # echo: file_path matches the user message (USER-trust), satisfying the selector
    # rule; recipient matches the bill's tool-result span (TOOL_OUTPUT-trust default),
    # which is below what `target` requires.
    assert [d.verdict for d in echo_decisions] == ["allow", "block"]
