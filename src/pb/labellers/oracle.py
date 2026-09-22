"""L3: ground truth. Upper bound, and the policy-only condition — residual attack
success here is what perfect perception cannot stop.

The ground-truth labels themselves (labels/oracle.jsonl) come from the annotation
pipeline in SPEC.md §9 — programmatic where the payload is known by construction,
hand-adjudicated at the boundaries. This class is only the lookup adapter: it makes
oracle labels available through the same Labeller interface as every other labeller,
so oracle can be swapped in anywhere any other labeller is used (replay, sweep, etc.)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from pb.labellers.base import Labeller, LabellerCost
from pb.trace.schema import ArgumentFact, Call, Role, Span, Trust


def _fact_from_record(record: dict[str, Any]) -> ArgumentFact:
    return ArgumentFact(
        call_id=str(record["call_id"]),
        param_name=str(record["param_name"]),
        value_repr=str(record["value_repr"]),
        trust=cast(Trust, record["trust"]),
        role=cast(Role, record["role"]),
        source_span_id=record.get("source_span_id"),
    )


class OracleLabeller(Labeller):
    id = "oracle"

    def __init__(self, facts_by_call: dict[str, tuple[ArgumentFact, ...]]) -> None:
        self._facts_by_call = facts_by_call

    @classmethod
    def from_jsonl(cls, path: Path) -> "OracleLabeller":
        facts_by_call: dict[str, list[ArgumentFact]] = {}
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                fact = _fact_from_record(json.loads(line))
                facts_by_call.setdefault(fact.call_id, []).append(fact)
        return cls({call_id: tuple(facts) for call_id, facts in facts_by_call.items()})

    def label(self, prefix: tuple[Span, ...], call: Call) -> tuple[ArgumentFact, ...]:
        try:
            return self._facts_by_call[call.call_id]
        except KeyError:
            raise KeyError(f"no oracle labels recorded for call_id={call.call_id!r}") from None

    def cost(self) -> LabellerCost:
        return LabellerCost()
