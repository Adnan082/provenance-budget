"""Loads and validates contracts/*.yaml. FROZEN after week 3 — see CLAUDE.md rule 3."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from pb.trace.schema import ROLE_VALUES, TRUST_VALUES, VERDICT_VALUES, Role, Trust, Verdict


@dataclass(frozen=True, slots=True)
class Contract:
    """One policy rule: an argument in `role`, on tool `tool` (or '*' for every tool),
    must carry trust at least `min_trust`; violations get `on_violation`."""

    role: Role
    min_trust: Trust
    on_violation: Verdict
    tool: str = "*"


def _parse_rule(raw: dict[str, Any], index: int) -> Contract:
    missing = {"role", "min_trust", "on_violation"} - raw.keys()
    if missing:
        raise ValueError(f"contracts rule {index}: missing field(s) {sorted(missing)}")

    role = raw["role"]
    if role not in ROLE_VALUES:
        raise ValueError(f"contracts rule {index}: unknown role {role!r}")

    min_trust = raw["min_trust"]
    if min_trust not in TRUST_VALUES:
        raise ValueError(f"contracts rule {index}: unknown trust {min_trust!r}")

    on_violation = raw["on_violation"]
    if on_violation not in VERDICT_VALUES:
        raise ValueError(f"contracts rule {index}: unknown verdict {on_violation!r}")

    return Contract(
        role=cast(Role, role),
        min_trust=cast(Trust, min_trust),
        on_violation=cast(Verdict, on_violation),
        tool=raw.get("tool", "*"),
    )


def load_contracts(path: Path) -> tuple[Contract, ...]:
    """Parses and validates a contracts/*.yaml policy file. Raises ValueError on any
    malformed rule rather than skipping it — a silently-dropped rule is a silently
    weakened policy (CLAUDE.md rule 6, applied here to policy rules, not just traces)."""
    text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(text)
    rules = raw.get("rules", []) if raw else []
    return tuple(_parse_rule(rule, i) for i, rule in enumerate(rules))
