"""Pure function of (ArgumentFact[], Contract[]) -> verdict. No I/O, no network, no
state, no LLM (CLAUDE.md rules 3-4). FROZEN after week 3."""
from __future__ import annotations

from pb.enforce.contracts import Contract
from pb.trace.schema import ArgumentFact, Verdict, trust_at_least

_SEVERITY: dict[Verdict, int] = {"allow": 0, "escalate": 1, "block": 2}


def evaluate(tool: str, arguments: tuple[ArgumentFact, ...], contracts: tuple[Contract, ...]) -> Verdict:
    """The verdict for one call: the most restrictive `on_violation` among every
    contract an argument violates, or 'allow' if none does. A contract applies to an
    argument when the contract's role matches the argument's role and the contract's
    tool is '*' or matches `tool` exactly."""
    worst: Verdict = "allow"
    for argument in arguments:
        for contract in contracts:
            if contract.role != argument.role:
                continue
            if contract.tool not in ("*", tool):
                continue
            if trust_at_least(argument.trust, contract.min_trust):
                continue
            if _SEVERITY[contract.on_violation] > _SEVERITY[worst]:
                worst = contract.on_violation
    return worst
