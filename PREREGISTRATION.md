# PREREGISTRATION.md — provenance-budget

**Status: DRAFT. Not yet hashed or dated.**

This becomes the authoritative pre-registration (CLAUDE.md treats it as such, and reproduces F1–F4 "for convenience" from here) once two things happen: the week-1 pilot (`make trace` + `make replay` on 20 AgentDojo tasks × 3 seeds) actually runs and fills in the measured quantities marked **PENDING** below, and the author reviews and signs off on the whole document as written. At that point it gets hashed (SHA-256 over the file content) and dated, and CLAUDE.md rule 1 takes effect: nothing above the `## Amendments` line changes again. A needed correction after that point is a dated entry appended there, never an edit above it.

Everything *not* marked PENDING below is a commitment made now, before any trace has been scored — that's the point of writing it down before week 1 instead of after.

---

## 1. Hypothesis

Published argument-level guardrails for tool-using LLM agents (CaMeL, FIDES, Progent, PACT) report near-perfect security under oracle provenance labels. Real automatic labellers measure around 77% provenance accuracy (PACT). No published work measures how much that gap costs — whether labeller accuracy is even the binding constraint on these guardrails' real-world security, as opposed to the enforcement rule itself.

**This project does not assume an answer.** It is equally willing to report "labeller accuracy barely matters" (F1), "perfect labels don't help much either" (F4), "the cheap labeller is indistinguishable from the expensive one" (F3), or "provenance isn't even a well-posed construct here" (F2) as it is to report a clean ε-sweep showing labeller accuracy driving the security/utility tradeoff. All five of those are pre-specified outcomes with a pre-specified reporting action (§6).

## 2. Design

**Independent variable:** the provenance labeller, varied across five points (`L0` blanket, `L1` echo, `L2` llm_infer, `L3` oracle, `L4` noisy — swept over `(eps_fn, eps_fp)` under three corruption models: `C-uniform`, `C-empirical`, `C-adversarial`).

**Held fixed:** the enforcement rule (`src/pb/enforce/{monitor,contracts,roles}.py` + `contracts/*.yaml`), frozen after week 3 (CLAUDE.md rule 3). If both the rule and the labeller varied, an observed security/utility change could be attributed to either, destroying the ability to isolate "how much does labeller accuracy matter."

**Dependent variables:** `ASR_t`, `ASR_h`, `BTC`, `BTC_ua`, `FPR_act`, `ESC`, `TrustAcc`, `RoleAcc`, `eps_fn` (measured), `eps_fp` (measured), `XStepRecall` — defined exactly as in CLAUDE.md "Metric definitions." No variant metric will be introduced after this point without a dated amendment explaining why.

**Headline endpoint:** `ASR_t` (x) vs. `BTC` (y), one point per labeller/baseline, with the `L4` ε-sweep drawn as isolines (not points) and the Pareto-dominance region shaded. A security number (`ASR_t`, `ASR_h`) is never reported without a utility number (`BTC`, `BTC_ua`) in the same table or figure — `ASR_t` alone is gamed trivially by the blanket labeller.

## 3. Statistical analysis plan

Committed before any trace is scored:

- **Proportions** (`ASR_t`, `ASR_h`, `BTC`, `BTC_ua`, `FPR_act`, `TrustAcc`, `RoleAcc`, `eps_fn`, `eps_fp`, `XStepRecall`): Wilson score intervals. Not the normal approximation — it misbehaves near 0%/100%, exactly where the better labellers' `ASR_t` is expected to sit.
- **ESC**: not a proportion — reported as mean ± bootstrap CI.
- **Labeller-vs-labeller comparisons** (e.g. echo vs. llm_infer, any `L4` point vs. another): McNemar's exact test (paired, since every labeller is scored against the *same* traces) plus a paired bootstrap (10,000 resamples over traces) for the CI on the difference. An unpaired test is never substituted — it throws away the power the paired design exists to buy.
- **Multiple comparisons** across the labeller family (`L0` vs. `L1` vs. `L2` vs. `L3` vs. `L4`): Holm–Bonferroni correction.
- **Seeds:** every configuration run ≥3 seeds, every number reported mean ± CI. A single-seed number is labelled a pilot and never reported as a result.

## 4. Effect size thresholds

**Provisional, pending week-1 measurement, with a pre-committed adjustment rule:**

- Default: ≥5 percentage points on `ASR_t` or `BTC` is a meaningful effect; <2pp is noise. This 2pp figure is a placeholder based on an *assumed* seed variance, not a measured one.
- **PENDING** — week 1's 20-task × 3-seed pilot measures the actual seed variance on `BTC`.
  - If measured variance ≤5pp: the 5pp / 2pp thresholds above stand as declared.
  - If measured variance >5pp (but the project isn't killed per §6's seed-variance kill criterion): **both thresholds become 2× the measured variance**, and `RESULTS.md` states the measured variance and the resulting thresholds explicitly. This recalibration rule is the commitment; the resulting numbers are not — they're whatever week 1 measures.

## 5. Power analysis and corpus sizing

- Unpaired detection of a 5pp `ASR_t` difference at `ASR≈20%`, 80% power, requires ~901 traces per arm. The corpus target is ~600 traces — short of that by design, because the paired comparison (§3) is expected to close the gap.
- The paired design only closes the gap if the **discordance rate** (how often two labellers actually disagree on the same trace) is high enough. It is not assumed to be sufficient.
- **PENDING** — week 1 measures the discordance rate on the pilot and sizes the full corpus from it, not from the ~600 placeholder.
- **Escalation path, most to least severe:**
  1. If the required *n* (given measured discordance) exceeds 3× the ~600 budget — **this is a kill criterion** (§6): stop, do not proceed to weeks 2–6 on the current design. Pivot to either a single task suite run at higher *n*, or drop live-agent recording entirely in favor of a purely offline labelling-accuracy benchmark (no `ASR_t`/`BTC` claim at all). Decide and record the choice within week 1.
  2. If the required *n* exceeds budget by a smaller margin (not triggering the kill criterion above): the declared minimum detectable effect (MDE) is raised and stated in `RESULTS.md`. An underpowered point estimate is never reported as if it were a finding.

## 6. Kill criteria (checked weekly, not just at the end)

Reproduced from CLAUDE.md's milestone table, which is authoritative for *when* each is checked:

- **Week 1:** seed variance on `BTC` >10pp, **or** required corpus *n* (per §5) >3× the ~600 budget → pivot this week (single suite at higher *n*, or drop live agents for an offline-only labelling benchmark). This is distinct from, and more severe than, the >5pp threshold-recalibration trigger in §4 — a variance between 5pp and 10pp recalibrates the effect-size thresholds; a variance above 10pp kills the current design outright.
- **Week 2:** intra-annotator κ below the §8 ground-truth gate → **F2 fires** (§7).
- **Week 3:** flat surface on dev under `C-adversarial` → **F1 fires**. Oracle residual `ASR_t` >15% → **F4 fires**. Either firing: stop, do not spend weeks 4–6 on the current design.
- **Week 4:** echo false-negative rate >60% → drop the cheap-labeller claim, keep the budget-vs-ε result, publish the verbatim-copy-rate-by-role table as a standalone finding instead.
- **Week 5:** no published IFC defence (Progent, CaMeL — run as-shipped, never reimplemented, CLAUDE.md rule 5) can be made to run in two evenings of effort → ship baselines as AgentDojo's own built-ins plus the blanket labeller, and say so plainly in `RESULTS.md`, not as a footnote.

**When any of these fires: stop and tell the user. Do not push through, and do not quietly narrow the claim to route around it without saying so.**

## 7. Pre-registered failure conditions (F1–F4)

These are the authoritative statements. CLAUDE.md's copy is for convenience only — if the two ever disagree, this file wins, and the disagreement itself is a bug to fix via a dated amendment below.

- **F1 — Flat surface.** Under `C-adversarial`: `ASR_t` at `eps_fn=0.30` differs from `eps_fn=0` by <5pp, **and** `BTC` at `eps_fp=0.30` differs from `eps_fp=0` by <5pp (both conditions required). → **Conclusion if fired:** perception is not the binding constraint on this enforcement rule; report this as the headline finding rather than searching for a different ε, corruption model, or metric that shows a larger effect.
- **F2 — No ground truth.** Intra-annotator κ <0.60 on trust, or <0.50 on role, measured over 200 doubly-labelled arguments (§8). → **Conclusion if fired:** argument-level provenance is not a well-posed construct under this threat model; this becomes the headline finding, and no downstream number that depends on oracle ground truth is reported as if ground truth were solid.
- **F3 — Cheap labeller indistinguishable.** The paired-difference 95% CI between `echo` and `llm_infer` contains zero on **both** `TrustAcc` and `ASR_t` (both conditions required). → **Conclusion if fired:** drop the claim that paying for an LLM labeller buys more security than a free deterministic matcher; keep the ε-budget result, which does not depend on this claim.
- **F4 — Oracle residual.** `ASR_t` under oracle (perfect) labels exceeds 15%. → **Conclusion if fired:** perfect perception does not buy security under this enforcement rule. The finding inverts from "how accurate do labels need to be" to "the attack surface is in the policy layer, not the perception layer." **This check runs before any budget (`L4` sweep) result is interpreted** — a high oracle residual changes what every subsequent number in the study means, so it is checked first, at week 3, not discovered after the fact.

## 8. Ground truth protocol and annotation gate

- Oracle labels are **programmatic** where the injected payload is known by construction (the harness planted it, so its trust/role is definitionally known) and **hand-adjudicated** at the boundaries where construction alone doesn't resolve ambiguity.
- **LLM annotators are gated, not trusted by default.** 200 arguments are hand-labelled by the author first. Human-vs-LLM κ is computed and reported on that set.
  - LLM annotation is used to scale the rest of the corpus **only if** κ ≥0.75 (trust) **and** κ ≥0.70 (role).
  - Below that gate: the corpus stays at hand-labelled scale, and `README.md` states why in those words — LLM-only annotation never becomes ground truth by default, because that would make the ground truth just another imperfect labeller, which is circular with respect to the whole research question.
- F2 (§7) uses the same 200-argument set's **intra**-annotator κ (the author against themself, a stricter and logically prior check than the human-vs-LLM gate above) — if the author can't agree with themselves, the human-vs-LLM gate is moot.

## 9. Corpus construction rules

- **Split by generator family, never by sample.** Samples within an attack family are near-duplicates; a sample-level split leaks and inflates any generalization claim.
- **Dev** = AgentDojo families + 50% of authored attack families. **Test** = AgentDyn + the held-out 50% of authored families. Test is sealed until week 6 and runs exactly once (CLAUDE.md rule 2) — nothing in this repo reads, runs against, or tunes on it before `make test-final`.
- **AgentDojo saturation filter.** [agentdojo#201](https://github.com/ethz-spylab/agentdojo/issues/201) reports 0/560 successful attacks against a current frontier model, undefended — many task×attack pairs no longer produce signal. The corpus is filtered to task×attack pairs where the undefended agent is compromised in ≥1 of 3 seeds. The surviving fraction per suite is reported as a first-class number, not silently absorbed into a smaller denominator (CLAUDE.md rule 6).
- If even the surviving pairs are too robust to measure against the frontier model used, the loop runs on a weaker open-weight model instead — stated prominently in the relevant figure caption, not a footnote, because it changes what the number means. **PENDING:** which open-weight model, if this triggers.
- **Tuning budget:** ≤20 configurations each for echo's matching threshold and llm_infer's prompt, dev-split only. Every configuration tried is recorded in `RESULTS.md`, whether or not it was the one shipped.
- **No silent exclusions, anywhere.** Any trace excluded for any reason (saturation filter, DIVERGED and unable to afford the live re-run, malformed recording) is counted and reported with the reason (CLAUDE.md rule 6). The denominator never shrinks quietly.

## 10. Replay discipline (validity rule for reusing a recorded trace)

- Replaying a recorded trace against a different labeller for **labelling-accuracy metrics** (`TrustAcc`, `RoleAcc`, `eps_fn`, `eps_fp`, `XStepRecall`) is always free — these depend only on the trace prefix, never on what the agent does next.
- Replaying for **end-to-end `ASR_t`/`BTC`** is free only when every verdict along the trace is `allow` under *both* labellers being compared (`src/pb/trace/divergence.py::valid_for_paired_comparison`). The moment either labeller's monitor verdict is anything other than `allow` at some call, the recorded continuation no longer reflects what the agent would have observed under that labeller's enforcement, and that trace must be re-run live for that comparison.
- **The divergence rate is always reported.** It is the honest measure of how much of the evaluation was actually free vs. how much required live re-runs — never silently approximated (CLAUDE.md rule 8).
- **PENDING** — week 1's pilot measures the actual divergence rate on 20 tasks × 3 seeds; §5's corpus-sizing decision is made jointly with this number and the discordance rate.

## 11. Explicitly out of scope

Stated here so it's paired with the rest of the design, not only in a figure caption:

- Text-to-text harms (content harmful in itself, not via hijacking a tool call).
- Side channels (timing, resource usage, or any non-content channel for exfiltration).
- Multi-agent trust boundaries (this project assumes one agent, one guardrail).
- Compromised tool implementations (tools are assumed to execute as specified; an attacker who has compromised the tool's *implementation* rather than the data flowing through it is a supply-chain problem, not a provenance-labelling one).

Full rationale for all of the above: `THREAT_MODEL.md`. Full design rationale for everything in this document: `SPEC.md`.

## 12. What is explicitly *not* pre-registered yet

Per CLAUDE.md's own milestone table, the following are decided *during* the study, not in advance, and this document does not pretend otherwise:

- The exact `contracts/*.yaml` enforcement policy content (a draft exists, unreviewed — SPEC.md §1 open questions).
- The exact `(tool, param) -> Role` table (a draft exists, cross-checked against live AgentDojo signatures but not human-reviewed — SPEC.md §1 open questions).
- Which open-weight model backs `L4`'s empirical corruption model and the week-5 white-box attack.
- The exact dev/test family split list (depends on authored attack families that don't exist yet).

Freezing *this* document does not freeze those — they follow their own milestones (`enforce/` + `contracts/` freeze at week 3, per CLAUDE.md rule 3).

---

## Amendments

*(Empty. Once this document is hashed and dated, any correction is appended below this line with the date and what changed — never edited above it, per CLAUDE.md rule 1.)*
