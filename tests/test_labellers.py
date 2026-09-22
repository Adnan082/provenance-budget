"""Tests for labellers/{blanket,echo,oracle,noisy}.py."""
from __future__ import annotations

from pathlib import Path

import pytest

from pb.labellers.blanket import BlanketLabeller
from pb.labellers.echo import EchoLabeller
from pb.labellers.noisy import NoisyLabeller
from pb.labellers.oracle import OracleLabeller
from pb.trace.schema import ArgumentFact, Call, RawArgument, Span


def _call(tool: str, call_id: str = "c1", **kwargs: str) -> Call:
    return Call(
        call_id=call_id,
        tool=tool,
        arguments=tuple(RawArgument(param_name=k, value_repr=v) for k, v in kwargs.items()),
    )


def test_blanket_labels_everything_external() -> None:
    call = _call(
        "send_money", recipient="alice@example.com", amount="10", subject="lunch", date="2026-01-01"
    )
    facts = BlanketLabeller().label((), call)
    assert len(facts) == 4
    assert all(f.trust == "EXTERNAL" for f in facts)
    by_param = {f.param_name: f for f in facts}
    assert by_param["recipient"].role == "target"
    assert by_param["amount"].role == "content"


def test_blanket_cost_is_zero() -> None:
    cost = BlanketLabeller().cost()
    assert cost.tokens == 0
    assert cost.dollars == 0.0


def test_echo_attributes_matched_tool_result_content_to_tool_output() -> None:
    prefix = (
        Span(
            span_id="s1",
            kind="tool_result:read_file",
            content_repr="attacker@evil.com wants a refund",
        ),
    )
    call = _call(
        "send_money", recipient="attacker@evil.com", amount="10", subject="refund", date="2026-01-01"
    )
    facts = EchoLabeller().label(prefix, call)
    by_param = {f.param_name: f for f in facts}
    assert by_param["recipient"].source_span_id == "s1"
    assert by_param["recipient"].trust == "TOOL_OUTPUT"


def test_echo_cannot_tell_external_tool_content_from_first_party_tool_output() -> None:
    # The blind spot documented in echo.py's module docstring: an EXTERNAL-origin
    # value (an attacker-authored email body, injected via a tool result) and a
    # legitimate TOOL_OUTPUT value both carry kind="tool_result:*", so echo guesses
    # the same trust for both. This is the failure mode the project measures.
    prefix = (
        Span(span_id="s1", kind="tool_result:get_received_emails", content_repr="wire funds now"),
    )
    call = _call("send_money", recipient="wire funds now", amount="10", subject="x", date="2026-01-01")
    facts = EchoLabeller().label(prefix, call)
    assert facts[0].trust == "TOOL_OUTPUT"  # true label is EXTERNAL; echo can't see the difference


def test_echo_defaults_to_trusted_with_no_source_when_unattributable() -> None:
    prefix = (Span(span_id="s1", kind="user_message", content_repr="pay my rent"),)
    call = _call("send_money", recipient="landlord@example.com", amount="500", subject="rent", date="2026-02-01")
    facts = EchoLabeller().label(prefix, call)
    by_param = {f.param_name: f for f in facts}
    assert by_param["recipient"].trust == "TRUSTED"
    assert by_param["recipient"].source_span_id is None


def test_echo_prefers_the_best_matching_span() -> None:
    prefix = (
        Span(span_id="weak", kind="tool_result:search_files", content_repr="alice"),
        Span(
            span_id="strong",
            kind="user_message",
            content_repr="send it to bob@example.com please",
        ),
    )
    call = _call("send_money", recipient="bob@example.com", amount="10", subject="x", date="2026-01-01")
    facts = EchoLabeller().label(prefix, call)
    by_param = {f.param_name: f for f in facts}
    assert by_param["recipient"].source_span_id == "strong"
    assert by_param["recipient"].trust == "USER"


def test_oracle_round_trips_through_jsonl(tmp_path: Path) -> None:
    jsonl = tmp_path / "oracle.jsonl"
    jsonl.write_text(
        '{"call_id": "c1", "param_name": "recipient", "value_repr": "bob", '
        '"trust": "USER", "role": "target", "source_span_id": "s1"}\n'
    )
    labeller = OracleLabeller.from_jsonl(jsonl)
    facts = labeller.label((), _call("send_money", recipient="bob"))
    assert facts == (
        ArgumentFact(
            call_id="c1",
            param_name="recipient",
            value_repr="bob",
            trust="USER",
            role="target",
            source_span_id="s1",
        ),
    )


def test_oracle_raises_for_unknown_call() -> None:
    labeller = OracleLabeller({})
    with pytest.raises(KeyError):
        labeller.label((), _call("send_money", recipient="bob"))


def test_noisy_labeller_uniform_wraps_oracle(tmp_path: Path) -> None:
    jsonl = tmp_path / "oracle.jsonl"
    jsonl.write_text(
        '{"call_id": "c1", "param_name": "recipient", "value_repr": "bob", '
        '"trust": "EXTERNAL", "role": "target"}\n'
    )
    oracle = OracleLabeller.from_jsonl(jsonl)
    noisy = NoisyLabeller(oracle=oracle, eps_fn=1.0, eps_fp=0.0, model="C-uniform", seed=1)
    facts = noisy.label((), _call("send_money", recipient="bob"))
    assert facts[0].trust in ("USER", "TRUSTED")


def test_noisy_labeller_adversarial_tracks_budget_across_calls(tmp_path: Path) -> None:
    jsonl = tmp_path / "oracle.jsonl"
    jsonl.write_text(
        '{"call_id": "c1", "param_name": "a", "value_repr": "x", "trust": "EXTERNAL", "role": "target"}\n'
        '{"call_id": "c2", "param_name": "b", "value_repr": "y", "trust": "EXTERNAL", "role": "target"}\n'
    )
    oracle = OracleLabeller.from_jsonl(jsonl)
    noisy = NoisyLabeller(
        oracle=oracle,
        eps_fn=0.5,  # budget = round(0.5 * 2) = 1
        eps_fp=0.0,
        model="C-adversarial",
        seed=0,
        n_arguments_total=2,
        attack_relevant_call_ids=frozenset({"c1", "c2"}),
    )
    first = noisy.label((), _call("send_money", call_id="c1", a="x"))
    second = noisy.label((), _call("send_money", call_id="c2", b="y"))
    flipped = sum(1 for f in (*first, *second) if f.trust == "USER")
    assert flipped == 1
