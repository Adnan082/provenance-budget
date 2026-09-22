# SPEC.md — provenance-budget

Referenced as authoritative by `CLAUDE.md`. This is a first draft assembled from decisions already made there, organized as a narrative rather than an operating manual. Sections marked **OPEN** are not yet decided and block the milestone they're attached to.

---

## 1. Research question

Argument-level guardrails for tool-using LLM agents (CaMeL, FIDES, Progent, PACT) report near-perfect security *under oracle provenance labels* — every paper assumes the (source, trust, role) of each tool-call argument is known exactly. Real automatic labellers hit roughly 77% provenance accuracy. No published work measures how much labeller accuracy actually matters to the security/utility outcome, i.e. whether the enforcement rule these papers propose is even the binding constraint once labels are imperfect.

**Method:** freeze one deliberately simple enforcement rule (`src/pb/enforce/`), vary *only* the provenance labeller across a five-point family (`L0`–`L4`) and a three-way corruption model for the noisiest point (`L4`), and plot the resulting surface: attack success vs. benign task completion, as a function of labelling accuracy.

**What this is not:** a new defence. The enforcement rule is intentionally simple and is not the contribution — see the "policy-only condition" (`L3`/oracle) in §3, which isolates what the rule itself can and can't stop, independent of labelling.

**The deliverable is a number allowed to come out badly.** Four failure conditions are pre-registered (§8) precisely because the informative outcome might be "labeller accuracy doesn't matter" (`F1`) or "the rule doesn't work even with perfect labels" (`F4`). Either is a publishable finding; a "fixed" result achieved by quietly discarding either would not be.

## 2. Why hold the enforcement rule fixed

If both the rule and the labeller varied, a security/utility change could be attributed to either, and the paper this repo supports would be making two claims (rule design *and* labelling robustness) with one experiment's worth of evidence. Freezing the rule after week 3 (`src/pb/enforce/`, CLAUDE.md rule 3) is what makes "labeller accuracy" the sole independent variable, and is why that module is a pure function with no model calls (rule 4) — a labeller-shaped hole in the enforcement layer would reintroduce the confound it exists to eliminate.

## 3. The labeller family

| Labeller | id | What it does | Role in the design |
|---|---|---|---|
| Blanket | `L0` | Every tool result is EXTERNAL. | Degenerate "secure" baseline — the utility floor. Any real labeller should beat this on `BTC` or it isn't earning its complexity. |
| Echo | `L1` | Deterministic normalised n-gram / LCS match against prior context. Zero tokens, zero model calls. | The cheap end of the accuracy/cost frontier. `F3` asks whether it's actually distinguishable from `L2`. |
| LLM-infer | `L2` | An LLM assigns (source, trust, role) per argument, PACT-style. | The realistic automatic labeller — this is what "77% accuracy" refers to. |
| Oracle | `L3` | Ground truth. | Upper bound *and* the policy-only condition: `ASR_t` here is the part of the attack surface labelling can never fix (§8, `F4`). |
| Noisy | `L4` | `Noisy(oracle, eps_fn, eps_fp, model)` | The actual instrument. Not a labeller anyone would deploy — a parametric sweep that lets `eps_fn`/`eps_fp` move independently so the surface, not a single accuracy number, is the result. |

`L0`–`L3` are fixed points; `L4` is swept. The headline figure (§6) plots all five plus baselines, with the `L4` sweep drawn as isolines rather than points.

### Corruption models for `L4`

All three are always reported together — no figure shows only one without the other two available in the same section:

- **`C-uniform`** — i.i.d. flips at rate ε. Included only for comparability with prior noise-robustness literature; not informative about this threat model, because a real attacker doesn't corrupt labels uniformly at random.
- **`C-empirical`** — errors resampled from the observed confusion of real labellers (`L1`, `L2`), conditioned on role and on whether the trace is under attack. This is what "realistic noise" actually looks like, as opposed to the uniform idealization.
- **`C-adversarial`** — corrupt exactly the arguments the attack needs, up to ε·N flips. **The headline curve.** An attacker who can influence what a labeller sees (§4 of `THREAT_MODEL.md`, "labeller-targeted injection") doesn't produce uniform or even realistically-distributed errors — it produces the worst ε-budget-constrained error the attack can buy. If the paper shows one curve, it's this one; the other two exist to show it isn't cherry-picked.

### Role assignment: deterministic vs. predicted

A design question the labeller descriptions above don't settle on their own: does *role* (the six-way taxonomy) get predicted by each labeller the way trust does, or is it fixed infrastructure?

Resolved as: **role is a deterministic function of `(tool, param_name)`** (`src/pb/enforce/roles.py`), applied identically for `L0`, `L1`, `L3`, and `L4` — because which parameter position an argument occupies is knowable from the tool's own schema, not something genuinely ambiguous the way *how much to trust it* is. `L2` (llm_infer) is the one exception: it predicts role independently, the way a real PACT-style labeller would when it doesn't have privileged access to a hand-built schema table, which is what makes `RoleAcc` a non-trivial metric specifically for `L2` (and, once role prediction is added there, any future labeller in the same position). This is also why `F3`'s echo-vs-llm_infer comparison is scoped to `TrustAcc` and `ASR_t` only, not `RoleAcc` — trust is the axis both labellers are actually competing on.

Consequence: the `eps_fn`/`eps_fp` corruption directions in `L4` only ever perturb trust, never role, consistent with the metric definitions in §4 below being trust-specific.

## 4. Metrics — why these and not others

| Name | Meaning | Why it's here |
|---|---|---|
| `ASR_t` | Targeted attack success. | The security number, but only ever reported paired with a utility number (`BTC`) — `ASR_t` alone is gamed trivially by `L0`. |
| `ASR_h` | Agent hijacked at all. | Separates "started following injected instructions" from "achieved the attacker's goal" — a guardrail that stops the second but not the first is a different (weaker) claim than one that stops both. |
| `BTC` / `BTC_ua` | Benign completion, clean / injected environment. | `BTC_ua` catches a guardrail that only preserves utility when nothing adversarial is present — the injected-environment number is the one that generalizes. |
| `FPR_act` | Fraction of benign calls blocked/escalated. | The mechanism behind a `BTC` drop — needed to diagnose *why* utility falls, not just that it does. |
| `ESC` | Escalations per benign task. | The human-cost metric. A labeller that escalates everything has `ASR_t = 0` and looks perfect on the ASR/BTC plot alone; `ESC` is what stops that from reading as a free win. |
| `TrustAcc`, `RoleAcc` | Per-argument accuracy vs. oracle. | The labeller-quality numbers, independent of any downstream agent behavior — needed to separate "the labeller is inaccurate" from "the enforcement rule doesn't use accurate labels well." |
| `eps_fn` | EXTERNAL labelled as USER/TRUSTED. | The security-relevant error direction — this is what lets an attack through. |
| `eps_fp` | USER/TRUSTED labelled as EXTERNAL. | The utility-relevant error direction — this is what breaks benign tasks. Reporting `eps_fn`/`eps_fp` separately (never a single blended error rate) is what makes the `L4` sweep two-dimensional instead of one. |
| `XStepRecall` | Recall of cross-step provenance. | Specifically targets the laundering attack family (`THREAT_MODEL.md` §4) — a labeller can have high single-step `TrustAcc` and still miss laundering entirely. |

**Headline figure:** `ASR_t` (x) vs `BTC` (y), one point per labeller/baseline, `L4` ε-sweep isolines overlaid, Pareto-dominance region shaded. Everything else supports or explains this one plot.

## 5. Replay discipline — why it's the main hazard

Traces are recorded once, live, against real tools and models, and re-scored offline against every labeller afterward — this is what makes evaluating five labellers × three corruption models × several ε values feasible in six weeks instead of requiring a full live run per configuration.

The validity of that offline replay depends entirely on one fact: **if the monitor's verdict is `allow` at every call under both labellers being compared, the agent's behavior is provably identical**, because the agent never saw a different context between the two runs. The moment a verdict diverges — one labeller blocks a call the other allows — the blocked run's context differs from that point forward, and nothing about the recorded trace tells you what the agent would have done next. That trace must be re-run live.

This is why `src/pb/trace/divergence.py` exists as its own module rather than a flag inside replay: divergence detection is the correctness boundary of the entire offline-evaluation strategy, and **the divergence rate must be reported** — it's the honest measure of how much of the evaluation was actually free versus how much required live re-runs. Widening what counts as "safe to replay" (CLAUDE.md rule 8) would silently convert some fraction of results from measured to approximated, in a way that wouldn't show up in any metric except by being wrong.

## 6. Statistics — why these tests

- **Wilson score intervals**, not normal approximation, for proportions — normal approximation misbehaves near 0% and 100%, which is exactly where `ASR_t` for the better labellers is expected to sit.
- **McNemar's exact + paired bootstrap (10,000 resamples)** for labeller-vs-labeller comparisons — the design is paired (every labeller is scored against the *same* traces), and an unpaired test throws away the statistical power that pairing buys. This is the difference between the ~600-trace corpus being adequately powered and not (§7).
- **Holm–Bonferroni** across the labeller family, because the comparisons of interest (`L0` vs `L1` vs `L2` vs `L3` vs `L4`) are a family, not a single test.
- **≥3 seeds**, always mean ± CI — a single-seed number is labelled a pilot, never a result (CLAUDE.md rule 7).

**Effect size thresholds:** ≥5pp on `ASR_t`/`BTC` meaningful, <2pp noise — provisional, based on an *assumed* seed variance. Week 1 measures the actual seed variance on a 20-task pilot; if it exceeds 5pp, both thresholds double to 2× measured variance, and `RESULTS.md` states why the thresholds changed. This is a pre-committed adjustment rule, not a post-hoc one.

**Power:** unpaired detection of a 5pp `ASR_t` difference at ASR≈20%, 80% power, needs ~901 traces/arm — well above the ~600-trace target. The paired design is what closes this gap, but only if the discordance rate (how often two labellers actually disagree on the same trace) is high enough to matter; week 1 measures discordance and sizes the corpus from it rather than assuming pairing rescues the budget by default. **If the required n still exceeds budget after that, the declared minimum detectable effect (MDE) is raised and stated — an underpowered point estimate is never reported as a finding.**

## 7. Corpus design

- **Split by generator family, never by sample.** Samples within an attack family are near-duplicates of each other; a sample-level train/test-style split would let the test split leak information about the dev split's attack family, inflating any generalization claim.
- **Dev** = AgentDojo families + 50% of authored attack families. **Test** = AgentDyn + the held-out 50% of authored families — sealed until week 6 (`CLAUDE.md` rule 2).
- **AgentDojo saturation.** [Issue #201](https://github.com/ethz-spylab/agentdojo/issues/201) reports 0/560 successful attacks against a current frontier model undefended — i.e. many AgentDojo task×attack pairs no longer produce a signal at all with a strong base model. Filtering to pairs where the *undefended* agent is compromised in ≥1 of 3 seeds keeps the corpus from silently diluting itself with pairs that can't move any metric; the surviving fraction per suite is reported as a first-class number precisely because a low surviving fraction is itself informative about how the threat model has aged.
- Where even the surviving pairs are too robust to measure against a frontier model, the loop runs on a weaker open-weight model instead, stated prominently in the figure caption — not a footnote, because it changes what the number means.
- **Tuning budget:** ≤20 configurations each for `echo`'s matching threshold and `llm_infer`'s prompt, dev-split only, every configuration tried recorded in `RESULTS.md`. The cap exists so the reported `L1`/`L2` numbers reflect a bounded search, not an unbounded one that happens to be reported as if it were the first attempt.

## 8. Pre-registered failure conditions

Authoritative copy lives in `PREREGISTRATION.md` (not yet created — a week-1 deliverable per the milestone table, hashed and dated once written, never edited above the line after that per CLAUDE.md rule 1). Reproduced here with the *reason each one is pre-registered*, which is the part a bare list loses:

- **F1 — flat surface.** Under `C-adversarial`, `ASR_t` at ε_fn=0.30 differs from ε_fn=0 by <5pp **and** `BTC` at ε_fp=0.30 differs from ε_fp=0 by <5pp. → Perception isn't the binding constraint; the labeller-accuracy question this whole project asks turns out not to matter much, and that's reported, not massaged into significance by picking a different ε or corruption model after the fact.
- **F2 — no ground truth.** Intra-annotator κ <0.60 (trust) or <0.50 (role) over 200 doubly-labelled arguments. → If the author can't agree with themselves on provenance labels, "argument-level provenance" isn't a well-posed construct for this threat model, and that becomes the headline instead of any downstream number that would rest on ill-defined ground truth.
- **F3 — cheap labeller indistinguishable.** `echo` vs `llm_infer` paired-difference 95% CIs contain zero on **both** `TrustAcc` and `ASR_t`. → The "you get more security by paying for an LLM labeller" claim doesn't hold; drop it, keep the budget-vs-ε result, which doesn't depend on it.
- **F4 — oracle residual.** `ASR_t` under oracle labels >15%. → Perfect perception doesn't buy security under this enforcement rule; the finding inverts from "how much labelling accuracy do you need" to "the attack surface is in the policy layer, not the perception layer" — and this check runs *before* any budget result is interpreted, because a high oracle residual changes what every subsequent number means.

## 9. Ground truth protocol

Oracle labels are programmatic where the injected payload is known by construction (i.e. the test harness planted it, so its trust/role is definitionally known), hand-adjudicated at the boundaries where construction alone doesn't resolve ambiguity.

**LLM annotators are gated, not trusted by default:** 200 arguments hand-labelled by the author first, human-vs-LLM κ computed, and LLM annotation used to scale the rest of the corpus *only if* κ ≥0.75 (trust) and ≥0.70 (role). Below that gate, the corpus stays at hand-labelled scale and `README.md` states why — the alternative (using ungated LLM labels to hit a larger target corpus size) would make the ground truth the same kind of imperfect labeller the project exists to measure against, which is circular.

## 10. Milestones and kill criteria

See `CLAUDE.md` "Milestones and kill criteria" for the authoritative week-by-week table — not duplicated here to avoid the two copies drifting. The one thing worth restating: **weeks 4–6 are conditional on week 3 not killing the project** (flat surface or oracle residual >15%). The milestone table is a decision tree, not a schedule.

---

## Open questions before this is final

1. `contracts/*.yaml` — **draft exists** (`contracts/policy.yaml`, 6 generic role-level rules, no tool-specific overrides), but not reviewed or frozen. `src/pb/enforce/monitor.py` and its tests are built against the draft; auditing individual tools (e.g. does `send_money`'s `target` really only need USER-level trust?) is still open.
2. `PREREGISTRATION.md` itself — this document summarizes what it will say; it still needs to be written and hashed as a week-1 deliverable.
3. Exact AgentDojo family → dev/test split list, and the "50% of authored families" split — needs the authored attack families to exist first (`src/pb/attacks/`).
4. The open-weight model used for both `L4`'s empirical corruption model and the week-5 white-box attack — not yet chosen.
5. `src/pb/enforce/roles.py` has a **draft** `(tool, param) -> Role` table covering all 74 AgentDojo v1 tools (agentdojo==0.1.35), cross-checked against the live package's signatures so it's at least internally consistent — but it's one person's (Claude's) first pass by naming heuristics, not the human annotation-agreement pass the week-2 milestone requires. Treat every entry as reviewable, not final.
6. `make trace` and `L2` (llm_infer) are blocked on an API key — nothing in this environment has one configured. Everything else in weeks 1–3 that doesn't require a live model call (schema, monitor, roles, stats, metrics, blanket/echo/oracle/noisy labellers) is implemented and tested; recording real traces and running the LLM-based labeller are the next things that need credentials before they can move.
