"""L0: every tool result is EXTERNAL. The degenerate 'secure' defence, and the utility
lower bound.

Role is filled in from enforce/roles.py's deterministic assignment, not guessed —
blanket doesn't need to guess it, since which parameter position an argument occupies
is knowable from the tool's schema regardless of how much we trust its value. Only
trust is degenerate here."""
from __future__ import annotations

from pb.enforce.roles import assign_role
from pb.labellers.base import Labeller, LabellerCost
from pb.trace.schema import ArgumentFact, Call, Span


class BlanketLabeller(Labeller):
    id = "blanket"

    def label(self, prefix: tuple[Span, ...], call: Call) -> tuple[ArgumentFact, ...]:
        return tuple(
            ArgumentFact(
                call_id=call.call_id,
                param_name=arg.param_name,
                value_repr=arg.value_repr,
                trust="EXTERNAL",
                role=assign_role(call.tool, arg.param_name),
            )
            for arg in call.arguments
        )

    def cost(self) -> LabellerCost:
        return LabellerCost()
