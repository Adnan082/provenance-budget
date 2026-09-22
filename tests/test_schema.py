"""Property tests for trust merge: semilattice (associative, commutative, idempotent,
min-bounded) — see CLAUDE.md 'Core vocabulary' and 'Conventions'."""
from __future__ import annotations

from itertools import product

from pb.trace.schema import Trust, TRUST_VALUES, merge_trust

# Independent of schema.py's internal ranking: least-trusted first.
_LEAST_TRUSTED_FIRST: tuple[Trust, ...] = ("EXTERNAL", "TOOL_OUTPUT", "USER", "TRUSTED")
_ORDER = {t: i for i, t in enumerate(_LEAST_TRUSTED_FIRST)}


def test_commutative() -> None:
    for a, b in product(TRUST_VALUES, repeat=2):
        assert merge_trust(a, b) == merge_trust(b, a)


def test_associative() -> None:
    for a, b, c in product(TRUST_VALUES, repeat=3):
        assert merge_trust(merge_trust(a, b), c) == merge_trust(a, merge_trust(b, c))


def test_idempotent() -> None:
    for a in TRUST_VALUES:
        assert merge_trust(a, a) == a


def test_min_bounded() -> None:
    for a, b in product(TRUST_VALUES, repeat=2):
        expected = a if _ORDER[a] <= _ORDER[b] else b
        assert merge_trust(a, b) == expected
