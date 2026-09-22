"""Tests for eval/corrupt.py — the three L4 corruption models."""
from __future__ import annotations

import random

from pb.eval.corrupt import adversarial_corrupt, empirical_corrupt, uniform_corrupt
from pb.trace.schema import ArgumentFact, Role, Trust


def _oracle_fact(trust: Trust, role: Role = "target", call_id: str = "c1", param: str = "recipient") -> ArgumentFact:
    return ArgumentFact(call_id=call_id, param_name=param, value_repr="v", trust=trust, role=role)


def test_uniform_corrupt_is_deterministic_for_fixed_seed() -> None:
    facts = tuple(_oracle_fact("EXTERNAL", param=f"p{i}") for i in range(50))
    out1 = uniform_corrupt(facts, eps_fn=0.5, eps_fp=0.0, rng=random.Random(7))
    out2 = uniform_corrupt(facts, eps_fn=0.5, eps_fp=0.0, rng=random.Random(7))
    assert out1 == out2


def test_uniform_corrupt_zero_epsilon_is_identity() -> None:
    facts = tuple(_oracle_fact(t, param=f"p{i}") for i, t in enumerate(("EXTERNAL", "USER", "TRUSTED")))
    out = uniform_corrupt(facts, eps_fn=0.0, eps_fp=0.0, rng=random.Random(0))
    assert out == facts


def test_empirical_corrupt_passes_through_uncovered_keys() -> None:
    facts = (_oracle_fact("EXTERNAL"),)
    out = empirical_corrupt(facts, confusion={}, under_attack=False, rng=random.Random(0))
    assert out == facts


def test_empirical_corrupt_samples_from_confusion_table() -> None:
    facts = (_oracle_fact("EXTERNAL"),)
    confusion = {("EXTERNAL", "target", False): (("TRUSTED", 1.0),)}
    out = empirical_corrupt(facts, confusion=confusion, under_attack=False, rng=random.Random(0))
    assert out[0].trust == "TRUSTED"


def test_adversarial_corrupt_only_spends_on_attack_relevant_external_facts() -> None:
    facts = (
        _oracle_fact("EXTERNAL", call_id="attack_call", param="a"),
        _oracle_fact("USER", call_id="attack_call", param="b"),
        _oracle_fact("EXTERNAL", call_id="benign_call", param="c"),
    )
    corrupted, spent = adversarial_corrupt(
        facts, budget=10, attack_relevant_call_ids=frozenset({"attack_call"}), rng=random.Random(0)
    )
    assert spent == 1
    by_param = {f.param_name: f for f in corrupted}
    assert by_param["a"].trust == "USER"
    assert by_param["b"].trust == "USER"
    assert by_param["c"].trust == "EXTERNAL"


def test_adversarial_corrupt_respects_budget() -> None:
    facts = tuple(_oracle_fact("EXTERNAL", call_id="attack_call", param=f"p{i}") for i in range(10))
    corrupted, spent = adversarial_corrupt(
        facts, budget=3, attack_relevant_call_ids=frozenset({"attack_call"}), rng=random.Random(0)
    )
    assert spent == 3
    assert sum(1 for f in corrupted if f.trust == "USER") == 3
