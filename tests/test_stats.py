"""Tests for eval/stats.py — CLAUDE.md 'Statistics': Wilson intervals, McNemar's exact,
paired bootstrap, Holm-Bonferroni."""
from __future__ import annotations

import math

import pytest

from pb.eval.stats import (
    holm_bonferroni,
    mcnemar_exact,
    mean_with_ci,
    paired_bootstrap_ci,
    wilson_interval,
)


def test_wilson_interval_point_estimate() -> None:
    result = wilson_interval(42, 100)
    assert result.point == pytest.approx(0.42)


def test_wilson_interval_contains_point() -> None:
    result = wilson_interval(7, 10)
    assert result.low <= result.point <= result.high


def test_wilson_interval_bounded_in_unit_range() -> None:
    for successes, n in [(0, 10), (10, 10), (1, 1), (5, 1000)]:
        result = wilson_interval(successes, n)
        assert 0.0 <= result.low <= result.high <= 1.0


def test_wilson_interval_symmetric_at_half() -> None:
    result = wilson_interval(50, 100)
    assert result.point == pytest.approx(0.5)
    assert (result.point - result.low) == pytest.approx(result.high - result.point, abs=1e-9)


def test_wilson_interval_converges_to_normal_approx_for_large_n() -> None:
    # Independent cross-check: for large n, Wilson should be close to the normal
    # (Wald) approximation p_hat +/- z*sqrt(p_hat*(1-p_hat)/n).
    n, successes = 100_000, 20_000
    result = wilson_interval(successes, n)
    p_hat = successes / n
    z = 1.959963984540054
    margin = z * math.sqrt(p_hat * (1 - p_hat) / n)
    assert result.low == pytest.approx(p_hat - margin, abs=1e-3)
    assert result.high == pytest.approx(p_hat + margin, abs=1e-3)


def test_wilson_interval_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        wilson_interval(1, 0)
    with pytest.raises(ValueError):
        wilson_interval(11, 10)


def test_mcnemar_exact_counts_discordant_pairs() -> None:
    a = [True, True, False, False, True]
    b = [True, False, False, True, True]
    result = mcnemar_exact(a, b)
    assert result.discordant_ab == 1  # index 1: a wins
    assert result.discordant_ba == 1  # index 3: b wins
    assert result.p_value == pytest.approx(1.0)


def test_mcnemar_exact_no_discordant_pairs() -> None:
    a = [True, False, True]
    b = [True, False, True]
    result = mcnemar_exact(a, b)
    assert result.p_value == 1.0
    assert result.statistic == 0


def test_mcnemar_exact_requires_paired_input() -> None:
    with pytest.raises(ValueError):
        mcnemar_exact([True, False], [True])


def test_paired_bootstrap_ci_point_is_exact_mean_difference() -> None:
    a = [1.0, 2.0, 3.0, 4.0]
    b = [0.5, 1.5, 2.5, 3.5]
    result = paired_bootstrap_ci(a, b, n_resamples=2000, seed=1)
    assert result.point == pytest.approx(0.5)


def test_paired_bootstrap_ci_is_reproducible_for_fixed_seed() -> None:
    a = [1.0, 0.0, 1.0, 1.0, 0.0, 1.0]
    b = [0.0, 0.0, 1.0, 0.0, 0.0, 1.0]
    first = paired_bootstrap_ci(a, b, n_resamples=500, seed=42)
    second = paired_bootstrap_ci(a, b, n_resamples=500, seed=42)
    assert first == second


def test_paired_bootstrap_ci_requires_paired_input() -> None:
    with pytest.raises(ValueError):
        paired_bootstrap_ci([1.0, 2.0], [1.0])


def test_mean_with_ci_point_is_exact_mean() -> None:
    result = mean_with_ci([1.0, 2.0, 3.0, 4.0, 5.0], n_resamples=1000, seed=0)
    assert result.point == pytest.approx(3.0)
    assert result.low <= result.point <= result.high


def test_holm_bonferroni_known_example() -> None:
    # p = [0.01, 0.02, 0.03, 0.20], alpha=0.05: thresholds 0.0125, 0.01667, 0.0167, 0.05
    # in rank order; 0.01 <= 0.0125 rejects, 0.02 > 0.01667 stops the step-down there.
    p_values = [0.01, 0.02, 0.03, 0.20]
    reject = holm_bonferroni(p_values, alpha=0.05)
    assert reject == [True, False, False, False]


def test_holm_bonferroni_all_significant() -> None:
    p_values = [0.001, 0.002, 0.003]
    reject = holm_bonferroni(p_values, alpha=0.05)
    assert reject == [True, True, True]


def test_holm_bonferroni_none_significant() -> None:
    p_values = [0.5, 0.6, 0.7]
    reject = holm_bonferroni(p_values, alpha=0.05)
    assert reject == [False, False, False]
