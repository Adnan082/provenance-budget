"""Tests for eval/metrics.py — see CLAUDE.md 'Metric definitions'."""
from __future__ import annotations

import pytest

from pb.eval.metrics import (
    cross_step_recall,
    eps_fn_rate,
    eps_fp_rate,
    escalations_per_task,
    rate,
    role_accuracy,
    trust_accuracy,
)
from pb.trace.schema import ArgumentFact, Role, Trust


def _fact(call_id: str, param: str, trust: Trust, role: Role = "target") -> ArgumentFact:
    return ArgumentFact(call_id=call_id, param_name=param, value_repr="v", trust=trust, role=role)


def test_rate_basic() -> None:
    result = rate([True, True, True, False])
    assert result.point == pytest.approx(0.75)


def test_rate_rejects_empty() -> None:
    with pytest.raises(ValueError):
        rate([])


def test_escalations_per_task_mean() -> None:
    result = escalations_per_task([0, 2, 4])
    assert result.point == pytest.approx(2.0)


def test_escalations_per_task_rejects_empty() -> None:
    with pytest.raises(ValueError):
        escalations_per_task([])


def test_trust_accuracy_perfect_match() -> None:
    oracle = [_fact("c1", "a", "EXTERNAL"), _fact("c1", "b", "USER")]
    predicted = [_fact("c1", "a", "EXTERNAL"), _fact("c1", "b", "USER")]
    result = trust_accuracy(predicted, oracle)
    assert result.point == pytest.approx(1.0)


def test_trust_accuracy_missing_prediction_counts_as_wrong() -> None:
    oracle = [_fact("c1", "a", "EXTERNAL"), _fact("c1", "b", "USER")]
    predicted = [_fact("c1", "a", "EXTERNAL")]  # "b" missing
    result = trust_accuracy(predicted, oracle)
    assert result.point == pytest.approx(0.5)


def test_trust_accuracy_rejects_empty_oracle() -> None:
    with pytest.raises(ValueError):
        trust_accuracy([], [])


def test_role_accuracy_scores_role_not_trust() -> None:
    oracle = [_fact("c1", "a", "EXTERNAL", role="target")]
    predicted = [_fact("c1", "a", "TRUSTED", role="target")]  # wrong trust, right role
    result = role_accuracy(predicted, oracle)
    assert result.point == pytest.approx(1.0)


def test_eps_fn_rate_counts_external_mislabelled_as_trusted_or_user() -> None:
    oracle = [_fact("c1", "a", "EXTERNAL"), _fact("c1", "b", "EXTERNAL"), _fact("c1", "c", "USER")]
    predicted = [_fact("c1", "a", "USER"), _fact("c1", "b", "EXTERNAL"), _fact("c1", "c", "USER")]
    result = eps_fn_rate(predicted, oracle)
    # denominator = 2 oracle-EXTERNAL args (a, b); only "a" was mislabelled up
    assert result.point == pytest.approx(0.5)


def test_eps_fn_rate_rejects_no_external_in_oracle() -> None:
    with pytest.raises(ValueError):
        eps_fn_rate([], [_fact("c1", "a", "USER")])


def test_eps_fp_rate_counts_trusted_or_user_mislabelled_as_external() -> None:
    oracle = [_fact("c1", "a", "USER"), _fact("c1", "b", "TRUSTED"), _fact("c1", "c", "EXTERNAL")]
    predicted = [_fact("c1", "a", "EXTERNAL"), _fact("c1", "b", "TRUSTED"), _fact("c1", "c", "EXTERNAL")]
    result = eps_fp_rate(predicted, oracle)
    # denominator = 2 oracle-USER/TRUSTED args (a, b); only "a" was mislabelled down
    assert result.point == pytest.approx(0.5)


def test_cross_step_recall_computes_recall_over_laundered_keys() -> None:
    oracle = [_fact("c1", "a", "EXTERNAL"), _fact("c1", "b", "EXTERNAL")]
    predicted = [_fact("c1", "a", "EXTERNAL"), _fact("c1", "b", "USER")]  # "b" laundered through
    result = cross_step_recall(predicted, oracle, laundered_keys=frozenset({("c1", "a"), ("c1", "b")}))
    assert result.point == pytest.approx(0.5)


def test_cross_step_recall_rejects_key_not_oracle_external() -> None:
    oracle = [_fact("c1", "a", "USER")]
    predicted = [_fact("c1", "a", "USER")]
    with pytest.raises(ValueError):
        cross_step_recall(predicted, oracle, laundered_keys=frozenset({("c1", "a")}))


def test_cross_step_recall_rejects_empty_keys() -> None:
    with pytest.raises(ValueError):
        cross_step_recall([], [], laundered_keys=frozenset())
