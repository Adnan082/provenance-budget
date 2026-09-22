"""L1: deterministic. Attributes argument spans to prior context by normalised n-gram /
longest-common-substring match. Zero tokens, zero model calls.

Matching uses difflib's longest-matching-block, which is a standard,
well-tested implementation of the same idea rather than a hand-rolled LCS. An
argument's value is attributed to whichever prior span it overlaps with the most (as a
fraction of the argument's own length); below `_MATCH_THRESHOLD` it's treated as
unattributable and, per schema.py's ArgumentFact convention, assumed to be a literal
the agent constructed itself — TRUSTED, no source span.

Once a span is matched, trust is read off `span.kind` via `_KIND_TRUST`, not from any
hidden ground truth (schema.Span carries none — see its docstring). Every kind other
than "system_prompt"/"user_message" — i.e. every flavor of tool-result span — maps to
the same TOOL_OUTPUT guess. That's not a simplification to fix later: it's the actual,
structural blind spot a same-only-matches-text labeller has. Echo has no way to tell
"my own account balance" from "an email body an attacker wrote" — both are just
"content that came back from a tool call" to a matcher that only looks at text
overlap. That blind spot is exactly what this project measures the cost of.

Role, as with blanket, comes from enforce/roles.py's deterministic assignment."""
from __future__ import annotations

from difflib import SequenceMatcher

from pb.enforce.roles import assign_role
from pb.labellers.base import Labeller, LabellerCost
from pb.trace.schema import ArgumentFact, Call, Span, Trust

_MATCH_THRESHOLD = 0.6

_KIND_TRUST: dict[str, Trust] = {
    "system_prompt": "TRUSTED",
    "user_message": "USER",
}
_DEFAULT_KIND_TRUST: Trust = "TOOL_OUTPUT"


def _trust_for_kind(kind: str) -> Trust:
    return _KIND_TRUST.get(kind, _DEFAULT_KIND_TRUST)


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
                trust, source_span_id = _trust_for_kind(span.kind), span.span_id
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
