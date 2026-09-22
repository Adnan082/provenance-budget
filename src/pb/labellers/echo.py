"""L1: deterministic. Attributes argument spans to prior context by normalised n-gram /
longest-common-substring match. Zero tokens, zero model calls.

Matching uses difflib's longest-matching-block, which is a standard,
well-tested implementation of the same idea rather than a hand-rolled LCS. An
argument's value is attributed to whichever prior span it overlaps with the most (as a
fraction of the argument's own length); below `_MATCH_THRESHOLD` it's treated as
unattributable and, per schema.py's ArgumentFact convention, assumed to be a literal
the agent constructed itself — TRUSTED, no source span.

Role, as with blanket, comes from enforce/roles.py's deterministic assignment."""
from __future__ import annotations

from difflib import SequenceMatcher

from pb.enforce.roles import assign_role
from pb.labellers.base import Labeller, LabellerCost
from pb.trace.schema import ArgumentFact, Call, Span, Trust

_MATCH_THRESHOLD = 0.6


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _match_ratio(value: str, content: str) -> float:
    """Longest matching block between `value` and `content`, as a fraction of
    len(value). 0.0 if either string is empty."""
    if not value or not content:
        return 0.0
    matcher = SequenceMatcher(a=value, b=content, autojunk=False)
    block = matcher.find_longest_match(0, len(value), 0, len(content))
    return block.size / len(value)


def _best_match(value_repr: str, prefix: tuple[Span, ...]) -> tuple[Span | None, float]:
    value = _normalize(value_repr)
    best_span: Span | None = None
    best_ratio = 0.0
    for span in prefix:
        ratio = _match_ratio(value, _normalize(span.content_repr))
        if ratio > best_ratio:
            best_span, best_ratio = span, ratio
    return best_span, best_ratio


class EchoLabeller(Labeller):
    id = "echo"

    def label(self, prefix: tuple[Span, ...], call: Call) -> tuple[ArgumentFact, ...]:
        facts = []
        for arg in call.arguments:
            span, ratio = _best_match(arg.value_repr, prefix)
            trust: Trust
            source_span_id: str | None
            if span is not None and ratio >= _MATCH_THRESHOLD:
                trust, source_span_id = span.trust, span.span_id
            else:
                trust, source_span_id = "TRUSTED", None
            facts.append(
                ArgumentFact(
                    call_id=call.call_id,
                    param_name=arg.param_name,
                    value_repr=arg.value_repr,
                    trust=trust,
                    role=assign_role(call.tool, arg.param_name),
                    source_span_id=source_span_id,
                )
            )
        return tuple(facts)

    def cost(self) -> LabellerCost:
        return LabellerCost()
