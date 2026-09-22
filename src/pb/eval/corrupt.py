"""C-uniform, C-empirical, C-adversarial corruption models for the L4 noisy labeller.
See CLAUDE.md 'Core vocabulary', all three always reported together (SPEC.md §3).

C-empirical needs a measured labeller confusion distribution and C-adversarial needs to
know which calls an attack depends on — neither is invented here. Both are accepted as
parameters so the caller (labellers/noisy.py, eval/sweep.py once it exists) supplies
real data; this module only implements the corruption mechanism once that data is
available."""
from __future__ import annotations

import random
from typing import Literal

from pb.trace.schema import ArgumentFact, Role, Trust

CorruptionModel = Literal["C-uniform", "C-empirical", "C-adversarial"]

# (true_trust, role, under_attack) -> weighted (predicted_trust, probability) outcomes.
ConfusionTable = dict[tuple[Trust, Role, bool], tuple[tuple[Trust, float], ...]]


def uniform_corrupt(
    facts: tuple[ArgumentFact, ...], eps_fn: float, eps_fp: float, rng: random.Random
) -> tuple[ArgumentFact, ...]:
    """C-uniform: i.i.d. flips at rate `eps_fn` (EXTERNAL -> USER/TRUSTED) and `eps_fp`
    (USER/TRUSTED -> EXTERNAL). Comparability baseline only (SPEC.md §3) — not
    informative about this project's threat model on its own."""
    corrupted = []
    for fact in facts:
        trust = fact.trust
        if trust == "EXTERNAL" and rng.random() < eps_fn:
            trust = rng.choice(("USER", "TRUSTED"))
        elif trust in ("USER", "TRUSTED") and rng.random() < eps_fp:
            trust = "EXTERNAL"
        corrupted.append(fact if trust == fact.trust else with_trust(fact, trust))
    return tuple(corrupted)


def empirical_corrupt(
    facts: tuple[ArgumentFact, ...],
    confusion: ConfusionTable,
    under_attack: bool,
    rng: random.Random,
) -> tuple[ArgumentFact, ...]:
    """C-empirical: resamples each fact's trust from a measured labeller confusion
    distribution conditioned on (true trust, role, under_attack). Facts whose
    (trust, role, under_attack) key isn't in `confusion` pass through unchanged rather
    than raising — an incomplete confusion table is a coverage gap to report, not a
    reason to fail the whole trace (CLAUDE.md rule 6: report exclusions, don't drop
    silently — callers should check `confusion` coverage themselves before relying on
    this)."""
    corrupted = []
    for fact in facts:
        outcomes = confusion.get((fact.trust, fact.role, under_attack))
        if not outcomes:
            corrupted.append(fact)
            continue
        trusts, weights = zip(*outcomes)
        trust = rng.choices(trusts, weights=weights, k=1)[0]
        corrupted.append(fact if trust == fact.trust else with_trust(fact, trust))
    return tuple(corrupted)


def adversarial_corrupt(
    facts: tuple[ArgumentFact, ...],
    budget: int,
    attack_relevant_call_ids: frozenset[str],
    rng: random.Random,
) -> tuple[tuple[ArgumentFact, ...], int]:
    """C-adversarial: spends up to `budget` flips (computed by the caller as
    round(eps * N) over the whole trace — this function only spends what it's given)
    turning EXTERNAL, attack-relevant facts into USER, the minimum change that lets
    them clear a policy gated at USER (SPEC.md §3: 'corrupt exactly the arguments the
    attack needs'). Candidates are shuffled before selection so which facts get spent
    first is reproducible from `rng` but not order-dependent on trace position. Returns
    the corrupted facts and how many flips were actually spent, so a caller tracking a
    trace-wide budget across multiple calls decrements by what happened, not by the
    upper bound offered."""
    candidates = [
        i
        for i, fact in enumerate(facts)
        if fact.call_id in attack_relevant_call_ids and fact.trust == "EXTERNAL"
    ]
    rng.shuffle(candidates)
    spend = set(candidates[:budget])
    corrupted = tuple(
        with_trust(fact, "USER") if i in spend else fact for i, fact in enumerate(facts)
    )
    return corrupted, len(spend)


def with_trust(fact: ArgumentFact, trust: Trust) -> ArgumentFact:
    return ArgumentFact(
        call_id=fact.call_id,
        param_name=fact.param_name,
        value_repr=fact.value_repr,
        trust=trust,
        role=fact.role,
        source_span_id=fact.source_span_id,
    )
