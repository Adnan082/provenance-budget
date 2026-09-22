"""Walks a trace, marks the first divergent verdict, sets the trace DIVERGED, and
queues it for live re-run. See CLAUDE.md 'Replay discipline'.

A recorded trace reflects one specific, undefended execution — nothing was blocked
while it was being recorded. Replaying it against a labeller's Decision sequence is
only "free" (reusing the recorded outcome, no live re-run) for as long as every
verdict is 'allow': the agent's next observed input is then provably identical to
what it was when the trace was recorded. The first non-'allow' verdict — block or
escalate — means that labeller's enforcement would have changed what the agent saw
from that point on, and nothing about the rest of the recorded trace says what
actually would have happened next. That's the divergence point."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pb.trace.schema import Decision


@dataclass(frozen=True, slots=True)
class DivergenceResult:
    diverged: bool
    first_divergent_call_id: str | None


def find_divergence(decisions: tuple[Decision, ...]) -> DivergenceResult:
    """`decisions` must be in trace order (the order the calls were made)."""
    for decision in decisions:
        if decision.verdict != "allow":
            return DivergenceResult(diverged=True, first_divergent_call_id=decision.call_id)
    return DivergenceResult(diverged=False, first_divergent_call_id=None)


def valid_for_paired_comparison(
    decisions_a: tuple[Decision, ...], decisions_b: tuple[Decision, ...]
) -> bool:
    """True only if the recorded trace's outcome can be reused for both labellers in a
    paired comparison without a live re-run for either — CLAUDE.md: 'every decision
    along the trace is allow under both labellers.'"""
    return not find_divergence(decisions_a).diverged and not find_divergence(decisions_b).diverged


def divergence_rate(results: Sequence[DivergenceResult]) -> float:
    """The honest measure of how much of the evaluation was actually free (CLAUDE.md:
    'Report the divergence rate. It is the honest measure of how much of the
    evaluation was actually free.')."""
    if not results:
        raise ValueError("need at least one trace")
    return sum(1 for r in results if r.diverged) / len(results)
