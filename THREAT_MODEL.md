# THREAT_MODEL.md — provenance-budget

Referenced as authoritative by `CLAUDE.md`. This is a first draft assembled from decisions already made there; sections marked **OPEN** need a decision from the author before week 1 ships, per the CLAUDE.md milestone table.

---

## 1. Setting

A tool-using LLM agent executes a task by calling tools (file I/O, browser, email, code execution, ...) whose arguments the agent constructs and whose outputs re-enter the agent's context. An **argument-level guardrail** — the family this project measures (CaMeL, FIDES, Progent, PACT) — inspects the arguments of each tool call before it executes and blocks or escalates calls that violate a policy.

The guardrail's decision is a pure function of two things per argument: its **provenance** (where did this value come from, and how much should it be trusted) and its **role** (what is this value being used *as* in the call). This project's enforcement layer (`src/pb/enforce/`) assumes both are available as labels and asks: how much does the accuracy of those labels matter?

## 2. Trust levels

```python
Trust = Literal["TRUSTED", "USER", "TOOL_OUTPUT", "EXTERNAL"]   # totally ordered, descending
```

- **TRUSTED** — originates in the system/developer prompt, contract, or code the agent did not receive as data.
- **USER** — originates in the human principal's own input for this task.
- **TOOL_OUTPUT** — originates in the return value of a tool call the agent itself issued, where the tool's target was within the trust boundary (e.g. a first-party API the user authorized).
- **EXTERNAL** — originates outside the trust boundary: web content, email bodies, documents the agent did not create, third-party API responses, anything an adversary could plausibly have written.

Merge rule when a value is built from multiple sources: **`min()`**, conservative, never `max`, never averaged (`src/pb/trace/schema.py::merge_trust`). A string built by concatenating a TRUSTED template with an EXTERNAL field is EXTERNAL.

## 3. Roles

```python
Role = Literal["target", "command", "credential", "content", "selector", "control"]
```

Six-way taxonomy of what an argument *does* in a call (`src/pb/enforce/roles.py`, frozen after week 3). **OPEN:** the per-role policy (which (trust, role) combinations are blocked, escalated, or allowed) lives in `contracts/*.yaml` and is not yet written — that's the actual defence under test, and needs to exist before `make budget` can run in week 3. A first pass at this file is separate follow-up work from this document.

## 4. Attacker

**Goal.** Get the agent to take an action that satisfies the attacker's predicate (`ASR_t`) — e.g. exfiltrate data, send a message, perform an unauthorized action — by controlling content that flows into the agent's context.

**Capability.** The attacker can write to any **EXTERNAL** source the agent's task legitimately causes it to read: a web page, an email, a file, a tool response from a third party. This is standard prompt-injection capability. The attacker cannot directly write TRUSTED or USER content — that is the definition of the trust boundary, not an assumption defended elsewhere.

**Attack families in scope** (`src/pb/attacks/`):
- **Direct injection** — instructions embedded in EXTERNAL content, unmodified.
- **Paraphrase** (`paraphrase.py`) — reworded injections intended to evade echo-style span-matching (`L1`) without changing intent, testing whether label accuracy tracks surface form rather than meaning.
- **Laundering** (`launder.py`) — the attacker gets EXTERNAL content copied into a TOOL_OUTPUT or USER-adjacent context across multiple steps, attempting to acquire higher trust than its origin warrants. `XStepRecall` measures whether labellers catch this.
- **Labeller-targeted injection** (`labeller_inject.py`) — content crafted to manipulate the labeller itself (for `L2`/`L4`, which are LLM-based) into mislabelling, as distinct from manipulating the downstream agent.
- **White-box** (`whitebox.py`, week 5 only) — attacker has weights/gradient access to the one open-weight labeller in the study, and constructs adversarial content with that access. Not attempted against closed-weight labellers.

**OPEN — adaptive knowledge.** Does the attacker know which labeller (`L0`–`L4`) is deployed, and can it query the labeller adaptively before committing to a payload? Current assumption implicit in the attack families above: attacks are constructed against a *labeller family* (e.g. "beat echo-style matching") without adaptive query access, except in the white-box case where full access is explicit. If a stronger adaptive-black-box setting is wanted, it needs to be named as a distinct attack family, not folded into the above.

## 5. Defender

The enforcement rule is fixed across the entire study — only the labeller varies (this is the experiment's independent variable). `src/pb/enforce/monitor.py` is a pure function of `(ArgumentFact[], Contract[])`: no I/O, no network, no model calls, no state (CLAUDE.md rule 4). It cannot itself be attacked at inference time — the only lever an attacker has against the defender is degrading the labels the monitor is given, which is exactly what `L4`'s three corruption models simulate.

**Trusted:** the contract policy (`contracts/*.yaml`), the monitor logic, the role-assignment logic, and the oracle labels. **Untrusted / the thing being measured:** the labeller's output for `L1`, `L2`, `L4`.

## 6. Explicitly out of scope

Stated in CLAUDE.md's writing-style rules and reproduced here so it's paired with the rest of the threat model rather than only appearing in a caption:

- **Text-to-text harms** — content that is harmful in itself (not by hijacking a tool call) is not this project's target.
- **Side channels** — timing, resource-usage, or other non-content channels for exfiltration.
- **Multi-agent trust boundaries** — this project assumes a single agent with a single guardrail; multi-agent delegation and the provenance questions it raises are out of scope.
- **Compromised tool implementations** — the tools themselves are assumed to execute as specified. An attacker who has compromised the tool's *implementation* (as opposed to controlling data that flows through it) is a supply-chain problem, not a provenance-labelling problem.

## 7. Relationship to the measurement

`ASR_t` under `L3` (oracle) is the residual: what the attacker can still achieve when labelling is perfect. If that number is high (>15%, `F4`), it means this threat model's attack surface lives in the **contract policy**, not in labeller accuracy, and the headline result inverts accordingly (CLAUDE.md, pre-registered failure conditions). Everything below `L3` in the labeller table measures how fast that residual grows as labelling degrades, under each of the three corruption models, and that surface — not a single point estimate — is the deliverable.

---

## Open questions before this is final

1. `contracts/*.yaml` policy content — the actual (trust, role) → verdict table.
2. Whether adaptive/query-access attacks are in scope beyond the white-box family.
3. Full tool inventory (~70 tools per CLAUDE.md week-2 milestone) and their role assignments — needed to make roles.py concrete.
4. Whether a compromised-but-authorized TOOL_OUTPUT source (e.g. a first-party API later found to be malicious) is EXTERNAL by definition or a separate case — current draft treats trust boundary membership as fixed per source, not per observed behavior.
