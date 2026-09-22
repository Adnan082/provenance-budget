"""Tests for labellers/{blanket,echo,oracle,noisy}.py."""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from pb.labellers.blanket import BlanketLabeller
from pb.labellers.echo import EchoLabeller
from pb.labellers.noisy import (
    NoisyLabeller,
    adversarial_corrupt,
    empirical_corrupt,
    uniform_corrupt,
)
from pb.labellers.oracle import OracleLabeller
from pb.trace.schema import ArgumentFact, Call, RawArgument, Role, Span, Trust


def _call(tool: str, call_id: str = "c1", **kwargs: str) -> Call:
    return Call(
        call_id=call_id,
        span_id="s-call",
        tool=tool,
        arguments=tuple(RawArgument(param_name=k, value_repr=v) for k, v in kwargs.items()),
    )


def _oracle_fact(trust: Trust, role: Role = "target", call_id: str = "c1", param: str = "recipient") -> ArgumentFact:
    return ArgumentFact(call_id=call_id, param_name=param, value_repr="v", trust=trust, role=role)


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


def test_uniform_corrupt_is_deterministic_for_fixed_seed() -> None:
    facts = tuple(_oracle_fact("EXTERNAL", param=f"p{i}") for i in range(50))
    out1 = uniform_corrupt(facts, eps_fn=0.5, eps_fp=0.0, rng=random.Random(7))
    out2 = uniform_corrupt(facts, eps_fn=0.5, eps_fp=0.0, rng=random.Random(7))
    assert out1 == out2


def test_uniform_corrupt_zero_epsilon_is_identity() -> None:
    facts = tuple(_oracle_fact(t, param=f"p{i}") for i, t in enumerate(("EXTERNAL", "USER", "TRUSTED")))
    out = uniform_corrupt(facts, eps_fn=0.0, eps_fp=0.0, rng=random.Random(0))
    assert out == facts


def test_empirical_corrupt_passes_through_uncovered_keys() -> None:
    facts = (_oracle_fact("EXTERNAL"),)
    out = empirical_corrupt(facts, confusion={}, under_attack=False, rng=random.Random(0))
    assert out == facts


def test_empirical_corrupt_samples_from_confusion_table() -> None:
    facts = (_oracle_fact("EXTERNAL"),)
    confusion = {("EXTERNAL", "target", False): (("TRUSTED", 1.0),)}
    out = empirical_corrupt(facts, confusion=confusion, under_attack=False, rng=random.Random(0))
    assert out[0].trust == "TRUSTED"


def test_adversarial_corrupt_only_spends_on_attack_relevant_external_facts() -> None:
    facts = (
        _oracle_fact("EXTERNAL", call_id="attack_call", param="a"),
        _oracle_fact("USER", call_id="attack_call", param="b"),
        _oracle_fact("EXTERNAL", call_id="benign_call", param="c"),
    )
    corrupted, spent = adversarial_corrupt(
        facts, budget=10, attack_relevant_call_ids=frozenset({"attack_call"}), rng=random.Random(0)
    )
    assert spent == 1
    by_param = {f.param_name: f for f in corrupted}
    assert by_param["a"].trust == "USER"
    assert by_param["b"].trust == "USER"
    assert by_param["c"].trust == "EXTERNAL"


def test_adversarial_corrupt_respects_budget() -> None:
    facts = tuple(_oracle_fact("EXTERNAL", call_id="attack_call", param=f"p{i}") for i in range(10))
    corrupted, spent = adversarial_corrupt(
        facts, budget=3, attack_relevant_call_ids=frozenset({"attack_call"}), rng=random.Random(0)
    )
    assert spent == 3
    assert sum(1 for f in corrupted if f.trust == "USER") == 3


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
