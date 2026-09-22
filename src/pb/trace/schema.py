"""Core provenance vocabulary and trace record types — see CLAUDE.md 'Core vocabulary'
and 'Conventions'. Do not invent variants. All records are frozen dataclasses; traces
are append-only JSONL, one JSON object per event, ordered."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, get_args

Trust = Literal["TRUSTED", "USER", "TOOL_OUTPUT", "EXTERNAL"]
Role = Literal["target", "command", "credential", "content", "selector", "control"]
Verdict = Literal["allow", "block", "escalate"]
EventType = Literal["span", "call", "decision", "result", "task_end"]

TRUST_VALUES: tuple[Trust, ...] = get_args(Trust)
ROLE_VALUES: tuple[Role, ...] = get_args(Role)
VERDICT_VALUES: tuple[Verdict, ...] = get_args(Verdict)
EVENT_TYPES: tuple[EventType, ...] = get_args(EventType)

# TRUSTED is most trusted; rank is used only to make merge_trust's min() well-defined.
_RANK: dict[Trust, int] = {t: len(TRUST_VALUES) - i for i, t in enumerate(TRUST_VALUES)}


def merge_trust(*sources: Trust) -> Trust:
    """Conservative merge: min() over contributing sources. Never max, never averaging."""
    if not sources:
        raise ValueError("merge_trust requires at least one source")
    return min(sources, key=_RANK.__getitem__)


def trust_at_least(observed: Trust, required: Trust) -> bool:
    """True if `observed` is at least as trusted as `required` in the total order."""
    return _RANK[observed] >= _RANK[required]


@dataclass(frozen=True, slots=True)
class Span:
    """A unit of content the agent observed: a system prompt, a user message, a tool
    result. `span_id` is content-addressed and stable across runs (CLAUDE.md
    'Conventions') so the same content always gets the same id regardless of when it
    was recorded. `content_repr` is truncated at write time — never the raw payload.

    Deliberately carries no `trust` field. A span's *true* trust (especially for a
    tool-result span: is this TOOL_OUTPUT or EXTERNAL?) is exactly what this project
    measures labellers guessing — if the recorded trace told them the answer, every
    labeller would score perfectly by construction. `kind` is the only thing a
    labeller may use to infer trust (e.g. echo treats every "tool_result:*" kind
    identically, which is precisely the blind spot that makes it unable to
    distinguish TOOL_OUTPUT from EXTERNAL — see labellers/echo.py). The true trust
    lives only in labels/oracle.jsonl, addressed by argument, not by span, and is
    never passed into a Labeller's `prefix`."""

    span_id: str
    kind: str
    content_repr: str
    event: EventType = "span"


@dataclass(frozen=True, slots=True)
class RawArgument:
    """One argument as the agent supplied it, before any labeller has seen it."""

    param_name: str
    value_repr: str


@dataclass(frozen=True, slots=True)
class Call:
    """A tool invocation the agent attempted, as recorded live — prior to, and
    independent of, any labeller's verdict. Recorded once; replayed against every
    labeller under evaluation (CLAUDE.md 'Replay discipline')."""

    call_id: str
    span_id: str
    tool: str
    arguments: tuple[RawArgument, ...] = field(default_factory=tuple)
    event: EventType = "call"


@dataclass(frozen=True, slots=True)
class ArgumentFact:
    """The (source, trust, role) triple a labeller assigns to one tool-call argument
    (CLAUDE.md: 'An LLM assigns (source, trust, role) per argument'). This is a
    labeller's *output*, not part of the recorded trace — it's recomputed on each
    replay pass and can differ per labeller for the same call. `source_span_id` is
    None only for arguments with no attributable origin span (e.g. a literal the agent
    invented itself, which is TRUSTED by construction)."""

    call_id: str
    param_name: str
    value_repr: str
    trust: Trust
    role: Role
    source_span_id: str | None = None


@dataclass(frozen=True, slots=True)
class Decision:
    """A labeller's verdict on one call. One trace can carry a Decision per labeller
    under evaluation, all keyed to the same `call_id` — that's what makes offline
    replay comparisons possible (CLAUDE.md 'Replay discipline')."""

    call_id: str
    labeller_id: str
    verdict: Verdict
    reason: str = ""
    event: EventType = "decision"


@dataclass(frozen=True, slots=True)
class Result:
    """The outcome of executing a call that was allowed. `result_span_id` is the span
    recording the tool's return value, re-entering the agent's context as TOOL_OUTPUT
    or EXTERNAL depending on the tool's target."""

    call_id: str
    result_span_id: str | None
    error: str | None = None
    event: EventType = "result"


@dataclass(frozen=True, slots=True)
class TaskEnd:
    """Terminal event for one (task, seed) run. `outcome` is a free-text label
    interpreted by eval/metrics.py, not enumerated here, so new benchmarks can report
    their own outcome taxonomy without touching this schema."""

    task_id: str
    seed: int
    outcome: str
    event: EventType = "task_end"
