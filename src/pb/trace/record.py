"""Records live agent runs into append-only JSONL traces. See CLAUDE.md 'Layout' and
'Commands'.

Also holds the shared low-level helpers (content addressing, truncation, secret
hashing, JSONL read/write) that any recorder — AgentDojo now, AgentDyn later — needs,
so adapters/*.py only has to supply the benchmark-specific message conversion."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pb.trace.schema import Call, Decision, RawArgument, Result, Span, TaskEnd

TraceEvent = Span | Call | Decision | Result | TaskEnd

_VALUE_MAX_LEN = 500

_EVENT_CLASSES: dict[str, type[TraceEvent]] = {
    "span": Span,
    "call": Call,
    "decision": Decision,
    "result": Result,
    "task_end": TaskEnd,
}


def content_address(*parts: str) -> str:
    """Deterministic id for a span: identical content always gets the same id,
    regardless of when it was recorded (CLAUDE.md 'Conventions': 'span_id is
    content-addressed and stable across runs')."""
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def truncate_repr(text: str, max_len: int = _VALUE_MAX_LEN) -> str:
    """Never commit an unbounded raw payload to a trace (CLAUDE.md 'Layout': 'truncate
    value_repr ... never commit raw API responses')."""
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}...[truncated {len(text) - max_len} chars]"


def hash_secret(text: str) -> str:
    """For a credential-role argument's value_repr: never store the raw value at all,
    truncated or not (CLAUDE.md 'Layout': 'hash anything secret-bearing')."""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_trace(path: Path, events: Iterable[TraceEvent], mode: str = "a") -> None:
    """Appends events as one JSON object per line, in order (CLAUDE.md 'Conventions')."""
    with path.open(mode, encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(asdict(event)) + "\n")


def read_trace(path: Path) -> list[TraceEvent]:
    """Reads a recorded trace back into typed events, dispatching on each line's
    `event` field."""
    events: list[TraceEvent] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                events.append(_event_from_dict(json.loads(line)))
    return events


def _event_from_dict(raw: dict[str, Any]) -> TraceEvent:
    kind = raw.get("event")
    cls = _EVENT_CLASSES.get(kind)  # type: ignore[arg-type]
    if cls is None:
        raise ValueError(f"unknown trace event type {kind!r}")
    if cls is Call:
        raw = {**raw, "arguments": tuple(RawArgument(**a) for a in raw["arguments"])}
    return cls(**raw)
