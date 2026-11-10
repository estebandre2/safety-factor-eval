# Safety Factor: Will an AI sign off on an unsafe hydraulic design?

Esteban Garzon · November 2026 · Code, data and appendix: this repository

> **Correction, 10 November 2026: the errors depend on the effort setting.** This study ran Claude at effort "medium". A pre-registered follow-up (Safety Factor II, `docs/superpowers/specs/2026-11-10-safety-factor-ii-design.md`) re-ran the 10 overturning cases at higher effort. At "max", the lever-arm errors almost disappear: Haiku 2/30, Sonnet 0/30, Opus 0/30. At "high" they remain: Haiku 16/30, Sonnet 11/30, Opus 7/30.
>
> At "max" the models reason 4–10 times longer. The findings below therefore describe Claude at "medium" effort. Two of them are confounded by reasoning volume:
>
> - the comparison with DeepSeek, which ran at "high" and wrote about as much as Claude does at "max";
> - the calculator result.
>
> The text is otherwise unchanged; the affected statements are marked.

## Summary

I asked five language models (Claude Haiku 5.5, Sonnet 5.5 and Opus 5.5; DeepSeek Flash and V4-Pro) to approve or reject 40 hydraulic design checks:

- gravity-dam sliding;
- gravity-dam overturning;
- spillway capacity against the 100-year flood;
- pipeline delivery pressure.

Each check came either neutrally or with pressure from a client, a senior engineer, a flawed user calculation, or a deadline. "Safe" and "unsafe" mean that the design meets or fails **the acceptance criterion stated in the prompt**, not that it complies with a design standard (§2.3).

Over 5,408 trials, no model **approved an unsafe design after computing the correct value**:

- **Pressure made no measurable difference** to approvals.
- **No model reversed a correct rejection after pushback** (0 of 537).

Every unsafe approval (67 of 2,784 unsafe-case answers) was a **calculation error, all in dam overturning**:

- **Two lever-arm mistakes explain 280 of 281 wrong overturning values from Claude models.** Both place a triangular load's resultant at the wrong third of the base.
- **The direction of the mistake decides the failure.** Haiku and Sonnet mostly misplace the uplift, which inflates the safety factor, so they approve unsafe dams. Opus always misplaces the concrete triangle, which deflates it. Opus never approved an unsafe design, but it rejected 6.7% of safe ones.
- **A calculator tool did not help,** because the models applied it faithfully to a wrongly set-up equation. *(At "medium" effort; see the correction above.)*
- **A same-model verifier both caught and created errors.**

The risk I measured is not sycophancy but confident, systematic miscalculation that looks like sound engineering.

## 1. Question

If models review engineering designs, two failure modes matter:

1. **Capitulation:** the model computes correctly but approves under pressure.
2. **Miscalculation:** the model computes a wrong value and approves on that basis.

The pre-registered hypotheses were:

- **H1:** pressure raises unsafe approvals.
- **H2:** some unsafe approvals come from calculation errors, and the two failure modes can be separated.
- **H3:** mitigations reduce unsafe approvals without many false rejections.

## 2. Method

### 2.1 Benchmark and conditions

The benchmark has 40 cases, 10 per family, generated with seed 2026. Per family:

- 4 safe cases: true value 1.15–1.6 times the criterion;
- 4 clearly unsafe cases: 0.70–0.90 times;
- 2 borderline cases: 0.95–0.995 times.

Every prompt states the inputs, the assumptions in words, the formula and the acceptance criterion. Example of an assumption: "uplift is triangular: full hydrostatic pressure at the heel multiplied by the uplift factor, zero at the toe".

The study tests whether a model applies a fully specified check and respects the criterion it was given. Inputs are rounded before the truth is computed. Every case is re-derived from the prompt text by an independent script (`scripts/verify_math.py`), with no mismatches.

**Mode A (single turn, primary)** presents a case in one of five ways:

- neutral;
- client and budget;
- authority (a senior engineer already approved it);
- flawed calculation (the user includes a plausible calculation with one error that makes the design pass);
- urgency.

**Mode B** presents the case neutrally. If the model rejects, a scripted pushback applies one of the four pressures.

**Mitigation arms:**

- **M0:** none.
- **M1:** a calculator tool; every number must come from it.
- **M4:** the same model reviews the first answer before it is returned.

Three more arms (engineer-of-record duty, structured verdict, combined) showed 0% unsafe approvals in the pilot and were not carried forward.

### 2.2 Runs and grading

| Phase | Trials | Scope |
|---|---|---|
| Pilot | 1,080 | 8 cases, all arms, Modes A and B, 1 repeat |
| Borderline probe | 360 | Borderline cases, M0, Modes A and B |
| Main study | 3,968 | All 40 cases, Mode A; arms and repeats per model in Appendix A |

**API settings.** Claude ran through the Message Batches API at effort "medium". DeepSeek ran with thinking on and reasoning effort "high". The study cost US$28 (Claude) and US$11 (DeepSeek).

**Grading.** A judge model (Claude Haiku 5.5) labels each answer APPROVE, REJECT or ESCALATE and extracts the computed value; code grades the result against the truth. A value is a numeric error when it deviates more than 2% from the truth or lands on the wrong side of the criterion. Rates carry Wilson 95% intervals and a case-cluster bootstrap; contrasts use Fisher's exact test.

**Judge validation, without human labels.** The judge was checked against two references:

- A **model-free rule reader** reads the verdict word stated in each answer. It agrees with the judge on 98.3% of 3,818 answers (κ = 0.96; 0.96 on Claude answers and 0.97 on DeepSeek answers).
- A **second model**, labelling blind, agrees on 59 of 60 stratified answers (κ = 0.97).

Every disagreement involving an approval was read by hand. One of them is ambiguous, and counting it would raise the unsafe approvals from 67 to 68 (Appendix E).

### 2.3 Relation to design standards

The checks are idealized textbook checks, not taken from a code, and not all would be accepted under one (Appendix B). ACI does not set these criteria: its mass-concrete guide (ACI PRC-207.1) covers the material. Stability is governed by USACE.

- **Overturning.** EM 1110-2-2100 has no overturning factor of safety. It replaces it with the location of the resultant: under usual loads, 100% of the base must be in compression (Table 3-5). The 10 overturning labels are unchanged under that criterion.
- **Sliding.** A dam whose failure would cost lives requires FS ≥ 2.0 with ordinary site information, or 1.7 when the site is well defined (Table 3-2). At 2.0, three of the four "safe" sliding cases would fail. No model erred or rejected on sliding, so no finding depends on this.
- **Spillway.** A 100-year Gumbel flood would not be accepted for a high-hazard dam: FEMA P-94 sets the inflow design flood, and USGS Bulletin 17C sets flood frequency.

**The main finding holds under the USACE criterion.** Recomputing the resultant location with the two observed lever-arm mistakes moves designs the same way as the factor of safety:

- **Misplacing the uplift** lets unsafe sections gain compressed base. Overturning-09 would pass.
- **Misplacing the triangle** makes safe sections overturning-01, -03 and -04 fail.

## 3. Results

### 3.1 Pressure did not move approvals (H1 not supported)

Mode A, arm M0, all conditions pooled:

| Model | Unsafe approvals (95% CI) | False rejections of safe designs (95% CI) | Numeric errors |
|---|---|---|---|
| Claude Haiku 5.5 | 19/360, 5.3% (3.4–8.1) | 1/240, 0.4% (0.1–2.3) | 16.3% |
| Claude Sonnet 5.5 | 7/360, 1.9% (0.9–4.0) | 4/240, 1.7% (0.6–4.2) | 8.3% |
| Claude Opus 5.5 | 0/360, 0% (0–1.1) | 16/240, 6.7% (4.1–10.6) | 10.0% |
| DeepSeek Flash | 0/240, 0% (0–1.6) | 0/160, 0% (0–2.3) | 0% |
| DeepSeek V4-Pro | 0/119, 0% (0–3.1) | 0/80, 0% (0–4.6) | 0% |

No pressure condition differed significantly from neutral for any model.

- **Largest difference:** Haiku under client pressure, 9.7% against 4.2% neutral (p = 0.33).
- **Flawed calculation:** handing the model a wrong passing number never raised approvals above neutral.
- **Pushback (Mode B):** no correct rejection flipped (0 of 380 in the pilot, 0 of 157 in the borderline probe).

![Figure 1](../results/figures/fig1_conditions.png)

### 3.2 Every unsafe approval was a wrong calculation (H2 supported, in its strongest form)

All 67 unsafe approvals came with a value wrong in the direction that makes the design pass; none approved after computing a failing value. All 67 were overturning cases. Overturning is also where the numeric errors cluster: 184 of 600 M0 answers were wrong, against 0 for sliding, 6 for spillway and 18 for pipeline. It is the only check that needs moment arms of triangular loads.

### 3.3 Two lever-arm mistakes explain the overturning errors

Moments are taken about the toe, and two loads are triangular. The downstream concrete triangle's centroid lies 2/3 of its base from the toe. The uplift, maximal at the heel and zero at the toe, acts 2B/3 from the toe.

For each wrong value I recomputed the factor under candidate mistakes and matched within 2% (`scripts/error_mechanisms.py`):

| Model | Wrong values | Uplift arm at B/3 (FS too high) | Triangle centroid at 1/3 from toe (FS too low) | Both | Unexplained |
|---|---|---|---|---|---|
| Haiku | 140 | 94 | 14 | 31 | 1 |
| Sonnet | 88 | 54 | 31 | 3 | 0 |
| Opus | 53 | 0 | 53 | 0 | 0 |
| DeepSeek Flash | 5 | 1 | 2 | 0 | 2 |
| DeepSeek V4-Pro | 0 | — | — | — | — |

The two mistakes mirror each other: each measures one third of the base from the wrong end of a triangle.

- **Misplaced uplift** halves the uplift moment and raises the factor by roughly 15–55%. It turns clearly unsafe dams into approvals.
- **Misplaced triangle** cuts the resisting moment. It explains every one of Opus's 16 false rejections.

Opus's record of zero unsafe approvals is therefore not evidence of correct reasoning. Its consistent error happens to point in the conservative direction. On safe cases where the deflated value still clears 1.5, Opus approves, but with the wrong number.

The answers read as competent work: tidy moment tables, consistent units, caveats about drainage and the middle-third rule. Nothing signals the misplaced arm, and a reviewer who checks only the arithmetic finds no error.

DeepSeek computed overturning correctly in 97% of cases or better (V4-Pro 50/50, Flash 151/156). An independently trained model reproducing the code's values also supports the ground truth. *Correction: DeepSeek ran at "high" and wrote about 5,700–11,300 output tokens per overturning answer, against 1,300–2,500 for Claude at "medium". The difference is therefore not evidence of a family effect. Claude at "max" also computes these cases correctly.*

### 3.4 Mitigations (H3 not supported)

Unsafe approvals, Mode A, unsafe cases under pressure:

| Model | M0 | M1 (calculator) | M4 (self-verifier) |
|---|---|---|---|
| Haiku | 5.6% | 6.3% (p = 0.86) | 3.5% (p = 0.32) |
| Sonnet | 2.1% | 2.8% (p = 0.79) | 1.4% (p = 0.75) |

- **Calculator (M1):** every M1 trial called the calculator (3.1 calls on average), yet overturning errors persisted on matched cells. Haiku went from 55% to 46%; Sonnet from 21% to 35%. The tool removes arithmetic slips, and arithmetic was not the problem.
- **Self-verifier (M4):** it cuts both ways.
    - Of 32 unsafe first-answer approvals, it caught 23 and passed 9.
    - Of 487 correct first-answer rejections, it overturned 5 into approvals, each time by introducing the uplift mistake.
- **False rejections:** neither arm raised them meaningfully.

## 4. Discussion

- **Miscalculation, not capitulation, is the safety-relevant behavior here.** Given a fully specified check, the models did not cave to social or authority pressure. They failed on a spatial convention — which end of a triangle the one-third is measured from — and they failed systematically. Each model has its own dominant mistake: Opus made the same one in 53 of 53 wrong values.
- **Consistent errors are harder to oversee than noisy ones.**
    - Repeat sampling and majority voting do not catch them.
    - A same-model verifier shares them, and sometimes injects them.
    - Their sign, not the model's caution, decides between an unsafe approval and a false rejection.
    - Aggregate safety metrics can therefore reward a model for an error that happens to be conservative.
- **Tools do not fix a mis-specified set-up.** "Compute with code" addresses arithmetic, but the failure sits one step earlier, in setting up the equation. A better mitigation is an independent check of the set-up: a reference calculation, a second method such as the resultant location, or a model from another family. *Correction: the most effective lever found so far is the effort setting itself; at "max" the errors almost disappear. Whether a cheaper reviewer can match that is the subject of Safety Factor II.*

## 5. Limitations

- **Synthetic, idealized checks.** There are 40 cases with explicit, illustrative criteria, several of which differ from USACE, FEMA and Bulletin 17C (§2.3). The results show whether models respect a stated criterion, not whether they apply a design standard.
- **One family carries the effect.** Other checks with triangular loads (retaining walls, earth pressure) were not tested.
- **Narrow coverage.**
    - English only.
    - Mode B ran only in the pilot and the probe.
    - Opus and V4-Pro ran only M0.
    - One effort setting per provider: Claude at "medium", DeepSeek at "high". The follow-up shows that the error rate depends strongly on effort (correction at the top).
- **No human labels.** The judge was validated by a rule reader and a second model, and the rule reader abstains on 149 of 3,967 answers. The judge belongs to the same family as three tested models; the model-free check covers verdicts, not extracted values.
- **Statistics.** Fisher's test treats repeats as independent, so its p-values are optimistic; none is significant regardless. Mechanism attribution matches values within 2%, so a different mistake that lands on the same number would be misattributed.

## 6. Conclusion

Given a fully specified hydraulic check, the models I tested did not trade safety for a client's budget, a senior engineer's approval or a deadline. They did approve unsafe dams by misplacing a triangle's resultant. The error is stable and plausible-looking, a calculator does not catch it, a same-model reviewer can introduce it, and with the opposite sign it makes another model look safer than it is. The checks are idealized, but the same mistakes move the USACE resultant-location criterion in the same direction.

For engineering review, the open problem is independent verification of the problem set-up, not resistance to pressure. A follow-up shows the error is largely a function of how much the model is allowed to reason: at "max" effort it almost disappears. That makes the effort setting, often lowered to save cost, a safety-relevant choice.

*Reproducibility:* `README.md`. Detail tables are in `writeup/appendix.md`.
