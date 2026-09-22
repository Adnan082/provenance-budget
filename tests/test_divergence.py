"""Tests for trace/divergence.py — CLAUDE.md 'Replay discipline'."""
from __future__ import annotations

from pathlib import Path

import pytest

from pb.adapters.agentdojo import record_ground_truth_trace
from pb.enforce.contracts import load_contracts
from pb.labellers.blanket import BlanketLabeller
from pb.labellers.echo import EchoLabeller
from pb.labellers.oracle import OracleLabeller
from pb.trace.divergence import divergence_rate, find_divergence, valid_for_paired_comparison
from pb.trace.replay import replay
from pb.trace.schema import ArgumentFact, Decision, Role, Trust, Verdict

POLICY_PATH = Path(__file__).resolve().parents[1] / "contracts" / "policy.yaml"


def _decision(call_id: str, verdict: Verdict) -> Decision:
    return Decision(call_id=call_id, labeller_id="x", verdict=verdict)


def _fact(call_id: str, param: str, trust: Trust, role: Role) -> ArgumentFact:
    return ArgumentFact(call_id=call_id, param_name=param, value_repr="v", trust=trust, role=role)


def test_find_divergence_all_allow() -> None:
    decisions = (_decision("c1", "allow"), _decision("c2", "allow"))
    result = find_divergence(decisions)
    assert result.diverged is False
    assert result.first_divergent_call_id is None


def test_find_divergence_stops_at_first_non_allow() -> None:
    decisions = (_decision("c1", "allow"), _decision("c2", "block"), _decision("c3", "allow"))
    result = find_divergence(decisions)
    assert result.diverged is True
    assert result.first_divergent_call_id == "c2"


def test_find_divergence_escalate_also_counts() -> None:
    result = find_divergence((_decision("c1", "escalate"),))
    assert result.diverged is True


def test_valid_for_paired_comparison_requires_both_all_allow() -> None:
    all_allow = (_decision("c1", "allow"),)
    has_block = (_decision("c1", "block"),)
    assert valid_for_paired_comparison(all_allow, all_allow) is True
    assert valid_for_paired_comparison(all_allow, has_block) is False
    assert valid_for_paired_comparison(has_block, all_allow) is False
    assert valid_for_paired_comparison(has_block, has_block) is False


def test_divergence_rate() -> None:
    results = [find_divergence((_decision("c1", "allow"),)), find_divergence((_decision("c1", "block"),))]
    assert divergence_rate(results) == pytest.approx(0.5)


def test_divergence_rate_rejects_empty() -> None:
    with pytest.raises(ValueError):
        divergence_rate([])


def test_divergence_against_real_trace_all_trusted_oracle_never_diverges() -> None:
    # An oracle that (hypothetically) labelled every argument TRUSTED clears every
    # rule in the draft policy, so replaying it against the real recorded trace
    # should never diverge from the implicit "allow" reference.
    events = tuple(record_ground_truth_trace("v1", "banking", "user_task_0", seed=0))
    contracts = load_contracts(POLICY_PATH)
    oracle = OracleLabeller(
        {
            "user_task_0:0:1": (_fact("user_task_0:0:1", "file_path", "TRUSTED", "selector"),),
            "user_task_0:0:2": (
                _fact("user_task_0:0:2", "recipient", "TRUSTED", "target"),
                _fact("user_task_0:0:2", "amount", "TRUSTED", "content"),
                _fact("user_task_0:0:2", "subject", "TRUSTED", "content"),
                _fact("user_task_0:0:2", "date", "TRUSTED", "control"),
            ),
        }
    )
    decisions = replay(events, oracle, contracts)
    assert find_divergence(decisions).diverged is False


def test_blanket_and_echo_diverge_on_the_same_real_trace() -> None:
    events = tuple(record_ground_truth_trace("v1", "banking", "user_task_0", seed=0))
    contracts = load_contracts(POLICY_PATH)
    blanket_decisions = replay(events, BlanketLabeller(), contracts)
    echo_decisions = replay(events, EchoLabeller(), contracts)
    assert valid_for_paired_comparison(blanket_decisions, echo_decisions) is False
