"""Common interface every labeller implements: label(prefix, call) and cost(). See
CLAUDE.md 'Conventions' and 'Core vocabulary'.

label() is pure w.r.t. the trace prefix and must not see spans after `call` — the
`prefix` passed in is already truncated to what preceded `call`; do not add a
parameter that reintroduces lookahead."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from pb.trace.schema import ArgumentFact, Call, Span


@dataclass(frozen=True, slots=True)
class LabellerCost:
    """Real tokens, wall-clock, dollars accumulated by a labeller instance since it was
    constructed (CLAUDE.md 'Conventions': 'Cost is instrumented, not estimated')."""

    tokens: int = 0
    wall_clock_s: float = 0.0
    dollars: float = 0.0


class Labeller(ABC):
    id: str

    @abstractmethod
    def label(self, prefix: tuple[Span, ...], call: Call) -> tuple[ArgumentFact, ...]:
        """One ArgumentFact per argument in `call`, given only the spans in `prefix`."""

    @abstractmethod
    def cost(self) -> LabellerCost:
        """Cumulative cost of every label() call made on this instance so far."""
