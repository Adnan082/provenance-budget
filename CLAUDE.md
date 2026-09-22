# CLAUDE.md — provenance-budget

Project memory for Claude Code. Read this before touching anything.

---

## What this repo is

A **measurement instrument**, not a defence.

Argument-level guardrails for tool-using LLM agents (CaMeL, FIDES, Progent, PACT) report near-perfect security *under oracle provenance labels*. Real labellers hit ~77% provenance accuracy. Nobody has published how accurate labels need to be before enforcement is worth deploying.

This repo freezes a deliberately simple enforcement rule, varies **only** the provenance labeller, and measures the resulting surface of attack success × benign task completion.

**The deliverable is a number that is allowed to come out badly.** Four failure conditions are pre-registered in `PREREGISTRATION.md`. If one fires, it goes on the README's first screen. Never "fix" a negative result — report it.

Full design rationale: `SPEC.md`. Threat model: `THREAT_MODEL.md`. This file is the operating manual.

---

## Rules that override your defaults

These exist because the obvious helpful action is usually the wrong one here.

1. **Never touch `PREREGISTRATION.md` after week 1.** It is hashed and dated. If it needs a correction, append a dated amendment block at the bottom that says what changed and why. Never edit above the line.
2. **Never read, run against, or tune on `traces/test/`.** The test split is sealed until week 6 and runs exactly once. If a command would touch it outside `make test-final`, stop and ask.
3. **`src/pb/enforce/` is frozen after week 3.** After that date, changes to `monitor.py`, `contracts.py`, `roles.py` or `contracts/*.yaml` invalidate every result. If you believe a change is required, stop and say so — do not make it.
4. **No model calls in `src/pb/enforce/`.** The monitor is a pure function of `(ArgumentFact[], Contract[])`. No I/O, no network, no state, no LLM. If you find yourself wanting one, the logic belongs in a labeller.
5. **Never reimplement a baseline and call it by the published name.** Progent means [sunblaze-ucb/progent](https://github.com/sunblaze-ucb/progent) running as-shipped. CaMeL means [google-research/camel-prompt-injection](https://github.com/google-research/camel-prompt-injection). If one can't be made to run, omit it and say so in `RESULTS.md`. A reimplementation is not a baseline.
6. **Never silently drop traces.** Excluded traces get counted and reported with the reason. A shrinking denominator is the classic way these results become wrong.
7. **Never report a best run.** Every number is mean ± CI over ≥3 seeds. If you only have one seed, label it a pilot.
8. **Never widen the replay rule.** See "Replay discipline" below — this is the most likely source of a silently wrong result in the whole project.
9. **When a kill criterion fires, stop and tell the user.** Do not push through. The kill criteria are in `SPEC.md` §3.6 and are reproduced below.

---

## Core vocabulary — use these exact names

```python
Trust = Literal["TRUSTED", "USER", "TOOL_OUTPUT", "EXTERNAL"]   # totally ordered, descending
Role  = Literal["target", "command", "credential", "content", "selector", "control"]
```

Trust merges conservatively: `min()` over contributing sources. Never `max`, never averaging, never a float.

| Labeller | id | What it does |
|---|---|---|
| Blanket | `L0` / `blanket` | Every tool result is EXTERNAL. The degenerate "secure" defence. Utility lower bound. |
| Echo | `L1` / `echo` | Deterministic. Attributes argument spans to prior context by normalised n-gram / longest-common-substring match. Zero tokens, zero model calls. |
| LLM-infer | `L2` / `llm_infer` | An LLM assigns (source, trust, role) per argument. PACT-style. |
| Oracle | `L3` / `oracle` | Ground truth. Upper bound. **Also the policy-only condition** — residual attack success here is what perfect perception cannot stop. |
| Noisy | `L4` / `noisy` | `Noisy(oracle, ε_fn, ε_fp, model)` — the instrument. |

Corruption models for `L4`, all three always reported:

- `C-uniform` — i.i.d. at rate ε. For comparability only.
- `C-empirical` — errors resampled from the observed confusion of real labellers, conditioned on role and on whether the trace is under attack.
- `C-adversarial` — corrupt exactly the arguments the attack needs, up to ε·N flips. **This is the headline curve.** If only one curve appears in a figure, it is this one.

---

## Metric definitions — do not invent variants

| Name | Meaning |
|---|---|
| `ASR_t` | Targeted attack success — the attacker's goal predicate is satisfied. |
| `ASR_h` | Agent hijacked at all (began following injected instructions). Reported separately. |
| `BTC` | Benign task completion, clean environment. |
| `BTC_ua` | Benign task completion, injected environment. |
| `FPR_act` | Fraction of benign tool calls blocked or escalated. |
| `ESC` | Escalations per benign task. The human-cost metric. Always reported — escalating everything is neither free nor safe. |
| `TrustAcc`, `RoleAcc` | Per-argument labelling accuracy vs oracle. |
| `eps_fn` | EXTERNAL labelled as USER or TRUSTED. The security-relevant error. |
| `eps_fp` | USER or TRUSTED labelled as EXTERNAL. The utility-relevant error. |
| `XStepRecall` | Recall of cross-step provenance (the laundering case). |

**A security number is never reported without a utility number in the same table or figure.** `ASR_t` alone is meaningless — the blanket labeller gets a great one.

Headline figure: `ASR_t` (x) vs `BTC` (y), one point per labeller and baseline, with the `L4` ε-sweep isolines overlaid and the Pareto-dominance region shaded.

---

## Replay discipline

The project's main efficiency lever and its main hazard. Traces are recorded once and re-scored offline; that is what makes six weeks feasible. The rule:

- **Free:** replaying a trace against a different labeller for *labelling-accuracy* metrics. These depend only on the trace prefix.
- **Free:** replaying for end-to-end `ASR_t`/`BTC` **when every decision along the trace is `allow` under both labellers.** Agent behaviour is then provably identical.
- **Must re-run live:** any trace where verdicts diverge at any call. A blocked call changes the model's context and therefore everything after it.

`src/pb/trace/divergence.py` walks a trace, marks the first divergent verdict, sets the trace `DIVERGED`, and queues it for live re-run. **Report the divergence rate.** It is the honest measure of how much of the evaluation was actually free.

If you are ever tempted to approximate a diverged trace rather than re-run it: don't. Mark it, queue it, and if the budget can't cover the queue, say so.

---

## Layout

```
src/pb/
  trace/       record.py  schema.py  replay.py  divergence.py
  labellers/   base.py  blanket.py  echo.py  llm_infer.py  oracle.py  noisy.py
  enforce/     contracts.py  monitor.py  roles.py     # FROZEN after wk3
  eval/        metrics.py  stats.py  sweep.py  corrupt.py
  adapters/    agentdojo.py  agentdyn.py              # only benchmark-specific code
  attacks/     launder.py  paraphrase.py  labeller_inject.py  whitebox.py
contracts/     *.yaml        # the entire policy, ~100 lines
traces/        dev/*.jsonl  test/*.jsonl   # THE ARTIFACT — committed to git
labels/        oracle.jsonl  agreement.json
figures/       headline.png  corruption_models.png  cost.png
```

`traces/` is committed deliberately. It is what lets a reviewer reproduce the headline offline with no API key. Keep it small enough to commit: truncate `value_repr`, hash anything secret-bearing, and never commit raw API responses.

---

## Commands

```
make trace          # record traces from adapters (dev only)   [needs API key]
make traces-live    # re-run DIVERGED traces                   [needs API key]
make oracle         # emit oracle-labelled arguments
make budget         # ε-sweep surface, all three corruption models
make labellers      # accuracy + cost + position on the surface for L0–L2
make baselines      # blanket, spotlighting, tool_filter, detector, Progent, CaMeL
make headline       # regenerate headline figure + number from committed traces
                    # NO API KEY, NO GPU, minutes not hours — keep it that way
make test-final     # the sealed test run. Week 6. Once.
```

`make headline` being free and fast is a design requirement, not a convenience. If a change would make it require an API key or take more than a few minutes, that change is wrong.

---

## Conventions

- Python 3.12+. `uv` for dependency management.
- All records are **frozen dataclasses**. Traces are append-only JSONL, one JSON object per event, ordered, with `event ∈ {span, call, decision, result, task_end}`.
- `span_id` is content-addressed and stable across runs.
- `Labeller.label(prefix, call)` is pure w.r.t. the trace prefix and **must not see spans after `call`**. The prefix is truncated before being passed — do not add a parameter that reintroduces lookahead.
- Every experiment takes an explicit seed. Nothing reads the global RNG.
- Type-check with `mypy --strict` on `src/pb/enforce/` at minimum. That module is load-bearing and small enough to keep clean.
- Tests: `pytest`. The monitor gets property tests (trust merge is a semilattice: associative, commutative, idempotent, `min`-bounded).
- Cost is instrumented, not estimated. `Labeller.cost()` returns real tokens, real wall-clock, real dollars.

---

## Statistics

- Proportions: **Wilson score** intervals. Not normal approximation.
- Paired labeller comparisons: **McNemar's exact** + paired bootstrap (10,000 resamples over traces) for the CI on the difference. The paired design is what rescues the power budget — do not accidentally run an unpaired comparison.
- Multiple comparisons across the labeller family: **Holm–Bonferroni**.
- ≥3 seeds per configuration.

**Effect sizes:** ≥5 pp on `ASR_t` or `BTC` is meaningful; <2 pp is noise. The 2 pp figure is a placeholder based on an assumed seed variance — week 1 measures it, and if measured variance exceeds 5 pp, both thresholds become 2× measured variance and `RESULTS.md` says why.

**Power:** unpaired detection of a 5 pp difference at ASR≈20% with 80% power needs ~901 traces per arm. The corpus targets ~600. The paired design closes the gap, but only if the discordance rate supports it — week 1 measures discordance and sizes the corpus from it. **If the required n exceeds budget, raise the declared MDE and state it. Do not run underpowered and report a point estimate as a finding.**

---

## Pre-registered failure conditions

Reproduced from `PREREGISTRATION.md` for convenience. That file is authoritative.

- **F1 — flat surface.** Under `C-adversarial`, `ASR_t` at ε_fn=0.30 differs from ε_fn=0 by <5 pp **and** `BTC` at ε_fp=0.30 differs from ε_fp=0 by <5 pp. → Perception is not the binding constraint. Report and stop.
- **F2 — no ground truth.** Intra-annotator κ <0.60 on trust or <0.50 on role over 200 doubly-labelled arguments. → Argument-level provenance is not well-posed. That becomes the headline.
- **F3 — cheap labeller indistinguishable.** `echo` vs `llm_infer` paired-difference 95% CIs contain zero on **both** `TrustAcc` and `ASR_t`. → Drop the cheap-labeller claim, keep the budget result.
- **F4 — oracle residual.** `ASR_t` under oracle labels >15%. → Perfect perception doesn't buy security under this rule; the headline inverts to "the attack surface is in the policy layer." Report this *before* any budget result.

---

## Milestones and kill criteria

| Wk | Ships | Kill criterion → pivot |
|---|---|---|
| 1 | `make trace` + `make replay` on 20 AgentDojo tasks × 3 seeds. Seed variance, divergence rate, discordance rate, corpus sizing. `PREREGISTRATION.md` hashed. | Seed variance on `BTC` >10 pp, or required n >3× budget → single suite at higher n, or drop live agents for a purely offline labelling benchmark. Decide this week. |
| 2 | `make oracle`. Roles assigned for all ~70 tools. Annotation agreement report. | Intra-annotator κ below F2 threshold → **F2 fires.** |
| 3 | `make budget` on **dev only**, all three corruption models. **Freeze `enforce/` + `contracts/`.** | Flat surface on dev under C-adversarial → **F1 fires.** Oracle residual >15% → **F4 fires.** Either way: stop, do not spend weeks 4–6. |
| 4 | `make labellers` for L0–L2 + verbatim-copy-rate-by-role table. | `echo` FN rate >60% → drop the cheap-labeller claim, keep the budget result, publish the copy-rate table as a standalone finding. |
| 5 | Baselines running. Adaptive attack families complete incl. one white-box attack on the open-weight labeller. | No published IFC defence runs in two evenings → ship with AgentDojo built-ins + blanket, and say so plainly. |
| 6 | `make test-final` once. Figures, `RESULTS.md`, README, demo. | None. Ship what happened. |

---

## Corpus hygiene

- **Split by generator family, never by sample.** Samples within an attack family are near-duplicates; a sample-level split leaks.
- Dev = AgentDojo families + 50% of authored families. Test = AgentDyn + the held-out 50%.
- **AgentDojo is saturating** ([issue #201](https://github.com/ethz-spylab/agentdojo/issues/201): 0/560 successful attacks vs a current frontier model). Filter to task×attack pairs where the *undefended* agent is compromised in ≥1 of 3 seeds, and report the surviving fraction per suite as a first-class number.
- Where a frontier model is too robust to measure anything, run the loop on a weaker open-weight model and say so prominently in the figure caption, not a footnote.
- Tuning budget: ≤20 configurations each for `echo`'s threshold and `llm_infer`'s prompt, on dev only. Record every configuration tried in `RESULTS.md`.

---

## Ground truth

Oracle labels are programmatic where the injected payload is known by construction, hand-adjudicated at the boundaries. **LLM annotators are gated, not trusted:** 200 arguments hand-labelled by the author, human-vs-LLM κ reported, and LLM annotation used for the bulk corpus only if κ ≥0.75 (trust) and ≥0.70 (role). Below the gate the corpus shrinks to hand-labelled scale and the README says why.

Never let LLM-only annotation become ground truth by default. If you're about to expand the corpus with LLM labels, check the gate first.

---

## Writing style for repo prose

README, `RESULTS.md`, figure captions:

- Lead with the number, including when it's the wrong number.
- State what's out of scope on the first screen: text-to-text harms, side channels, multi-agent trust boundaries, compromised tool implementations.
- Cite PACT in the README's second paragraph with the delta stated explicitly. Claiming novelty against a paper the reviewer already knows is how you lose them in thirty seconds.
- No "we believe", no "promising", no "significantly" without a p-value attached.
- Anything unmeasured is labelled a guess, in those words.
