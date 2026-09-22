"""Wilson score intervals, McNemar's exact + paired bootstrap, Holm-Bonferroni
correction. See CLAUDE.md 'Statistics'."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass(frozen=True, slots=True)
class Interval:
    point: float
    low: float
    high: float


def wilson_interval(successes: int, n: int, confidence: float = 0.95) -> Interval:
    """Wilson score interval for a proportion — not normal approximation (CLAUDE.md
    'Statistics'): normal approximation misbehaves near 0%/100%, exactly where ASR_t
    for the better labellers is expected to sit."""
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= successes <= n:
        raise ValueError("successes must be within [0, n]")
    z = float(stats.norm.ppf(1 - (1 - confidence) / 2))
    p_hat = successes / n
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    margin = z * ((p_hat * (1 - p_hat) / n + z**2 / (4 * n**2)) ** 0.5) / denom
    return Interval(point=p_hat, low=max(0.0, center - margin), high=min(1.0, center + margin))


@dataclass(frozen=True, slots=True)
class McNemarResult:
    statistic: int
    p_value: float
    discordant_ab: int
    discordant_ba: int


def mcnemar_exact(a_outcomes: Sequence[bool], b_outcomes: Sequence[bool]) -> McNemarResult:
    """Exact McNemar's test on paired binary outcomes from the *same* traces (CLAUDE.md
    'Statistics': the paired design is what rescues the power budget). Fails loudly if
    the two sequences aren't the same length, i.e. aren't actually paired."""
    if len(a_outcomes) != len(b_outcomes):
        raise ValueError("a_outcomes and b_outcomes must be paired (same length)")
    discordant_ab = sum(1 for a, b in zip(a_outcomes, b_outcomes) if a and not b)
    discordant_ba = sum(1 for a, b in zip(a_outcomes, b_outcomes) if b and not a)
    n = discordant_ab + discordant_ba
    if n == 0:
        return McNemarResult(statistic=0, p_value=1.0, discordant_ab=0, discordant_ba=0)
    statistic = min(discordant_ab, discordant_ba)
    result = stats.binomtest(statistic, n, p=0.5, alternative="two-sided")
    return McNemarResult(
        statistic=statistic,
        p_value=float(result.pvalue),
        discordant_ab=discordant_ab,
        discordant_ba=discordant_ba,
    )


def paired_bootstrap_ci(
    a_values: Sequence[float],
    b_values: Sequence[float],
    n_resamples: int = 10_000,
    confidence: float = 0.95,
    seed: int = 0,
) -> Interval:
    """Paired bootstrap CI on mean(a - b) over traces, resampling trace *indices* (not a
    and b independently) so pairing is preserved — CLAUDE.md: 'do not accidentally run
    an unpaired comparison.'"""
    if len(a_values) != len(b_values):
        raise ValueError("a_values and b_values must be paired (same length)")
    a = np.asarray(a_values, dtype=float)
    b = np.asarray(b_values, dtype=float)
    n = len(a)
    if n == 0:
        raise ValueError("need at least one paired observation")
    point = float(np.mean(a - b))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_resamples, n))
    diffs = (a[idx] - b[idx]).mean(axis=1)
    alpha = 1 - confidence
    low, high = np.quantile(diffs, [alpha / 2, 1 - alpha / 2])
    return Interval(point=point, low=float(low), high=float(high))


def mean_with_ci(
    values: Sequence[float],
    n_resamples: int = 10_000,
    confidence: float = 0.95,
    seed: int = 0,
) -> Interval:
    """Bootstrap CI on the mean of a single (unpaired) sample — for metrics like ESC
    that aren't a proportion and aren't being compared paired against anything."""
    a = np.asarray(values, dtype=float)
    n = len(a)
    if n == 0:
        raise ValueError("need at least one observation")
    point = float(np.mean(a))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_resamples, n))
    means = a[idx].mean(axis=1)
    alpha = 1 - confidence
    low, high = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return Interval(point=point, low=float(low), high=float(high))


def holm_bonferroni(p_values: Sequence[float], alpha: float = 0.05) -> list[bool]:
    """Holm-Bonferroni step-down correction across a family of comparisons (CLAUDE.md:
    applied across the labeller family). Returns, per input p-value in its original
    order, whether it's significant after correction."""
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    reject = [False] * m
    for rank, i in enumerate(order):
        threshold = alpha / (m - rank)
        if p_values[i] <= threshold:
            reject[i] = True
        else:
            break  # step-down: first failure to reject means every larger p-value fails too
    return reject
