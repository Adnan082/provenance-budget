"""Core provenance vocabulary — see CLAUDE.md 'Core vocabulary'. Do not invent variants."""
from __future__ import annotations

from typing import Literal, get_args

Trust = Literal["TRUSTED", "USER", "TOOL_OUTPUT", "EXTERNAL"]
Role = Literal["target", "command", "credential", "content", "selector", "control"]

TRUST_VALUES: tuple[Trust, ...] = get_args(Trust)
ROLE_VALUES: tuple[Role, ...] = get_args(Role)

# TRUSTED is most trusted; rank is used only to make merge_trust's min() well-defined.
_RANK: dict[Trust, int] = {t: len(TRUST_VALUES) - i for i, t in enumerate(TRUST_VALUES)}


def merge_trust(*sources: Trust) -> Trust:
    """Conservative merge: min() over contributing sources. Never max, never averaging."""
    if not sources:
        raise ValueError("merge_trust requires at least one source")
    return min(sources, key=_RANK.__getitem__)
