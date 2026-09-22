"""Replays a committed trace against a labeller without live model calls. See
CLAUDE.md 'Replay discipline'."""
from __future__ import annotations

from pb.enforce.contracts import Contract
from pb.enforce.monitor import evaluate as monitor_evaluate
from pb.labellers.base import Labeller
from pb.trace.record import TraceEvent
from pb.trace.schema import Call, Decision, Span


def replay(
    events: tuple[TraceEvent, ...], labeller: Labeller, contracts: tuple[Contract, ...]
) -> tuple[Decision, ...]:
    """Walks a recorded trace in order, maintaining the Span prefix a real labeller
    would have observed at each point, and computes one Decision per Call. Never
    passes a labeller spans recorded after the call it's labelling — CLAUDE.md:
    label() 'must not see spans after call'; this function is what enforces that,
    not the labeller."""
    prefix: list[Span] = []
    decisions: list[Decision] = []
    for event in events:
        if isinstance(event, Span):
            prefix.append(event)
        elif isinstance(event, Call):
            facts = labeller.label(tuple(prefix), event)
            verdict = monitor_evaluate(event.tool, facts, contracts)
            decisions.append(Decision(call_id=event.call_id, labeller_id=labeller.id, verdict=verdict))
    return tuple(decisions)
