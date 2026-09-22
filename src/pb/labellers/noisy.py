"""L4: Noisy(oracle, eps_fn, eps_fp, model) — the instrument. See CLAUDE.md 'Core
vocabulary' for the three corruption models; the models themselves live in
eval/corrupt.py, this class is just the Labeller wrapper around them."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from pb.eval.corrupt import ConfusionTable, CorruptionModel, adversarial_corrupt, empirical_corrupt, uniform_corrupt
from pb.labellers.base import Labeller, LabellerCost
from pb.trace.schema import ArgumentFact, Call, Span


@dataclass
class NoisyLabeller(Labeller):
    id = "noisy"

    oracle: Labeller
    eps_fn: float
    eps_fp: float
    model: CorruptionModel
    seed: int
    n_arguments_total: int = 0
    confusion: ConfusionTable = field(default_factory=dict)
    under_attack: bool = False
    attack_relevant_call_ids: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        self._adversarial_budget = round(self.eps_fn * self.n_arguments_total)

    def label(self, prefix: tuple[Span, ...], call: Call) -> tuple[ArgumentFact, ...]:
        oracle_facts = self.oracle.label(prefix, call)
        if self.model == "C-uniform":
            return uniform_corrupt(oracle_facts, self.eps_fn, self.eps_fp, self._rng)
        if self.model == "C-empirical":
            return empirical_corrupt(oracle_facts, self.confusion, self.under_attack, self._rng)
        if self.model == "C-adversarial":
            corrupted, spent = adversarial_corrupt(
                oracle_facts, self._adversarial_budget, self.attack_relevant_call_ids, self._rng
            )
            self._adversarial_budget -= spent
            return corrupted
        raise ValueError(f"unknown corruption model {self.model!r}")

    def cost(self) -> LabellerCost:
        return self.oracle.cost()
