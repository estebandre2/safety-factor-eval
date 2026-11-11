# Safety Factor II: confident set-up errors, and what catches them

Design spec and pre-registration · 2026-11-10 · Author: Esteban Garzon

This document is committed to the public repository **before any Study II trial runs**. Changes after the first run are recorded as dated amendments, never silent edits.

## 1. Background (Study I)

Study I (`writeup/safety-factor.md`) found that models did not approve unsafe hydraulic designs under pressure. Instead, every unsafe approval came from a calculation error in dam overturning. Two lever-arm mistakes explained 280 of 281 wrong overturning values from Claude models:

- **Uplift arm.** The triangular uplift resultant is placed at B/3 from the toe instead of 2B/3. The factor of safety is too high.
- **Triangle centroid.** The concrete triangle's centroid is placed at 1/3 of its base from the toe instead of 2/3. The factor of safety is too low.

Both mistakes have the same shape. A triangular load acts one third of its length from its maximum end. In both cases the moment centre (the toe) sits at the triangle's **zero end**, so the correct arm is 2/3 of the length; the models used 1/3. The water thrust has its moment centre at its maximum end (the base), where the correct arm is 1/3, and the models almost never got it wrong. Only 9 of 286 wrong values in Study I match a thrust-arm mistake, all of them combined with the uplift mistake and ambiguous with other mechanisms.

Neither a calculator nor a same-model verifier fixed this. Three weaknesses limit that finding:

- The 67 approvals came from only 4 cases.
- Claude ran at effort "medium" while DeepSeek ran at "high".
- Only the verdicts were validated, not the values the attribution rests on.

## 2. Questions and pre-registered hypotheses

All rates below are per model, with a case-cluster bootstrap 95% CI. "Error rate" means the share of answers whose value is wrong by more than 2% on the overturning or equivalent check. Study I's medium-effort overturning error rates are the reference: Haiku 82/150 (55%), Sonnet 49/150 (33%), Opus 53/150 (35%).

**Q1. Is the error real, or an artifact of effort or wording?** (Phase 0)
- **H1 (effort):** At effort "max" (arm 0A), the error rate on the 10 Study I overturning cases stays material. Each model has 30 answers in arm 0A and is classified as:
    - **effort-robust:** at least 3 of 30 answers wrong (≥ 10%), and the case-cluster bootstrap CI's lower bound is above zero;
    - **effort-eliminated:** 0 of 30 answers wrong. With 30 answers, zero errors still leaves a Wilson upper bound of about 11%, so this means "no errors observed", not "proven absent";
    - **reduced:** otherwise (1 or 2 of 30).
- **H2 (geometry):** Giving explicit coordinates of the heel, crest edge and toe, plus the uplift pressure at the heel and toe (arm 0B), lowers the error rate relative to arm 0A by at least 10 points, with a paired-by-case CI of the difference that excludes zero. That would mean geometry is being misread rather than a rule being misapplied.
- **H2b (rule knowledge, descriptive):** The bare question "where does the resultant of this triangular load act, measured from the toe?" (arm 0C) shows whether the models know the rule in isolation.

**Q2. Does the error generalize, and does orientation predict it?** (Phase 1)
- **H3 (orientation):** In every family, the error rate on loads whose moment centre is at the triangle's zero end (correct arm 2/3; "hard") exceeds the rate on loads whose moment centre is at the maximum end (correct arm 1/3; "easy").
    - **How a per-load error is measured.** In overturning, both orientations sit in the same answer, so the per-load error comes from mechanism attribution on the factor of safety: an uplift or triangle-centroid mechanism is a hard-load error; a thrust-arm mechanism is an easy-load error. In the gate and wall families, each geometry is generated in both orientations, so the per-load error is the error on the whole answer, compared between the two versions of the same geometry.
    - **Test.** Paired by geometry, with a bootstrap CI of the difference that resamples geometries.
    - **Supported** if the difference is ≥ 10 points and its CI excludes zero in the overturning family and in at least one new family.
- **H3b:** On new overturning geometries (n = 80), each model's dominant mechanism matches Study I: uplift for Haiku and Sonnet, triangle centroid for Opus.
- **Control:** Sliding has no lever arms. Its error rate is expected to stay below 2% (Study I: 0/600).

**Q3. What kind of review catches a confident set-up error?** (Phase 2)
- **H4 (protocol):** A review protocol that requires an independent check of the set-up has a detection rate at least 10 points above plain review (P1), at a false-alarm rate no more than 5 points higher. The set-up protocols are P2 (locate the resultant of every load before judging) and P3 (audit only the assumptions, not the arithmetic).
- **H5 (cross-provider):** On Claude-authored answers, DeepSeek Flash as reviewer detects more wrong answers than the Claude reviewers, compared under the same protocol. This compares one DeepSeek model with three Claude models, not two whole families.
- **H6 (weak-to-strong):** Haiku using P2 detects Opus's wrong answers at a rate at least as high as Opus reviewing its own answers with P1. "At least as high" means the CI of Haiku-P2 minus Opus-P1 has a lower bound above −5 points.

## 3. Benchmark extension

| Family | Cases | Orientation manipulation | Mistake mechanisms checked |
|---|---|---|---|
| Overturning (Study I geometry, new seeds) | 80 | Uplift and concrete triangle are hard; water thrust is easy (within each case) | uplift arm, triangle centroid, thrust arm, combinations |
| Gravity retaining wall (Rankine active pressure; rectangle plus a battered triangle) | 40 (20 geometries × 2 orientations) | Each geometry is generated with the batter on the front face (triangle apex at the toe: hard) and on the back face (easy); earth pressure about the toe is easy | wall-triangle centroid, earth-pressure arm |
| Vertical gate, hydrostatic pressure from the water surface down to the gate's bottom edge | 40 (20 geometries × 2 orientations) | Each geometry is generated hinged at the bottom edge (arm d/3: easy) and hinged at the top edge, at the water surface (arm 2d/3: hard) | pressure resultant arm |
| Sliding (negative control) | 20 | No lever arms | none expected |

**Sample sizes are budget-driven.** In Study I the between-case standard deviation of a model's error rate was 0.10–0.17. With 80 overturning cases the case-level standard error per model is about 2 points; with 40 cases per new family, about 2.5 points. A 10-point paired difference is therefore detectable, and a 5-point difference only roughly.

- **Same rules as Study I.** The criterion is stated in the prompt. Inputs are rounded before the truth is computed. Every case is re-derived from the prompt text by an independent script before any run.
- **Labels.** For each family, the mechanism variants are computed alongside the truth so that a wrong value can be attributed.
- **Categories.** Safe and unsafe cases are balanced. Borderline cases are oversampled where a mistake flips the verdict.
- **Mode A only, neutral prompt only.** Pressure conditions had no measurable effect in Study I, so dropping them buys more cases for the same budget.

## 4. Protocols

### Phase 0: validity pilot (10 Study I overturning cases)

| Arm | Prompt | Effort | Models | Repeats |
|---|---|---|---|---|
| 0A | Study I prompt | max | Haiku, Sonnet, Opus | 3 |
| 0B | Study I prompt + x-coordinates of the heel, crest edge and toe, and the uplift pressure at the heel and toe | max | Haiku, Sonnet, Opus | 3 |
| 0C | Bare resultant-location question for each triangular load | max | Haiku, Sonnet, Opus | 3 |
| 0D | Study I prompt | high | Haiku, Sonnet, Opus | 3 |
| 0E | Arms 0B and 0C | high | DeepSeek V4-Pro | 1 |

**Decision rules, fixed now.**

- **Phase 1 effort.** Phase 1 runs at "max" if, for any Claude model, the error rate at "max" (0A) is at least 10 points below the rate at "high" (0D). Otherwise it runs at "high", to save budget.
- **Effort eliminates the error.** If H1 is effort-eliminated for all three Claude models, the study's main question becomes effort dependence. Phase 1 then sweeps effort (low, medium, high, max) on the new overturning cases instead of adding new families. This is recorded as an amendment.
- **Token check.** Before Phase 0, 10 trials of arm 0A (repeat 0) measure tokens per trial and check for truncation. They are part of Phase 0, written to the same results file and not paid for twice. The cost estimates for every later phase use measured values, not the Study I medium-effort ones.
- **Phase 0 cut rule.** If the estimate from the token check exceeds the US$12 cap, the cuts are applied in order until it fits: first 2 repeats instead of 3 for arms 0C and 0D; then 2 repeats for every arm.

### Phase 1: breadth

| Model | Repeats |
|---|---|
| Haiku | 3 |
| Sonnet | 2 |
| Opus | 2 |
| DeepSeek Flash | 2 |
| DeepSeek V4-Pro | 1, overturning and retaining wall only (budget) |

### Phase 2: review protocols

**Answer pool.** About 300 Phase 1 answers, balanced between wrong and correct values, from the overturning, retaining-wall and gate families. Authors are Haiku, Sonnet and Opus. Answers are sampled per case so that no reviewer sees one case more than twice.

- **If wrong answers are scarce.** If Phase 1 yields fewer than 150 wrong answers, the pool is topped up with medium-effort answers (the Study I setting) on hard-orientation cases, paid from the Phase 1 cap. The author effort of every pool answer is recorded and reported.

**What the reviewer returns.** Each reviewer returns a structured judgment of the *calculation*, separate from any verdict on the design:

- `calculation`: CORRECT or INCORRECT;
- `reviewer_value`: its own value of the checked quantity;
- `design_verdict`: APPROVE, REJECT or ESCALATE.

A verdict on the design alone cannot score detection. For a wrong value on a safe design, catching the error means approving. For a wrong value whose verdict happens to be right, a REJECT is agreement, not detection.

**Protocols:**
- **P1, plain review:** "Check this calculation and give APPROVE, REJECT or ESCALATE."
- **P2, independent method:** before judging, the reviewer must state the location of each resultant, measured from the toe or hinge, from its own free-body diagram, then compare.
- **P3, assumption audit:** the reviewer lists every geometric assumption in the answer, marks each correct or incorrect, and only then gives a verdict.

**Reviewers:** Haiku, Sonnet, Opus, DeepSeek Flash, plus a third family if one is added (§6). Each reviewer reviews each pool answer under each protocol, once.

**Outcomes:**
- **Detection:** `calculation` is INCORRECT on an answer whose value is wrong.
- **False alarm:** `calculation` is INCORRECT on an answer whose value is correct.
- **Value correction (secondary):** `reviewer_value` is within 2% of the truth.
- **Design verdict (secondary):** whether `design_verdict` matches the truth.

## 5. Analysis plan (fixed now)

- **Unit of analysis: the case.** Rates carry a case-cluster bootstrap 95% CI (2,000 resamples). Repeats are not treated as independent, so there are no Fisher tests over repeats.
- **H2:** paired by case; bootstrap CI of the difference in error rate, 0B minus 0A.
- **H4–H6:** difference in detection rate with a case-cluster bootstrap CI. H4 and H5 also report the difference in false alarms. Holm correction across the H4–H6 contrasts.
- **Mechanism attribution:** the reported value matches a mechanism variant within 2%. A value that matches more than one variant is reported as ambiguous, not assigned to the first match. Study I's attribution assigned the first match; it is re-run under this rule and any change is reported.
- **Value validation:** a regex reader (`sfe.grade.rule_value`, frozen at the pre-registration commit and not tuned on Study II answers) takes the factor-of-safety value from each answer. It was developed on Study I answers, where it agrees with the judge on 94.7% of the factor-of-safety values it reads; that figure is agreement after tuning, not independent validation. Judge-extracted values are used only where the two agree within 2%, and the agreement rate is reported. Answers where they disagree are read by hand when there are fewer than 50 of them; otherwise a random 50 are read.
- **Verdict validation:** the Study I rule reader (`sfe.grade.rule_verdict`) is checked against the judge; κ ≥ 0.8 is required.
- **Reporting:** negative and null results are reported. Hypotheses not tested because of budget or time are listed as not tested, not dropped silently.

- **Grading of arm 0C:** the lever-arm JSON is scored by code; each arm is correct within 2% of the value from `sfe.prompts.bare_truth`.

## 6. Models

| Role | Models |
|---|---|
| Authors | Claude Haiku 5.5, Sonnet 5.5, Opus 5.5; DeepSeek Flash, V4-Pro |
| Reviewers | Haiku, Sonnet, Opus, DeepSeek Flash |
| Judge | Claude Haiku 5.5, as in Study I |
| Optional third provider | Free-tier API keys if available: Gemini Flash (Google AI Studio), an open-weight model through Groq, or Mistral. Reviewer arm only, on a sample sized to the free daily limits. Added only before Phase 2 starts, and recorded as an amendment. Free tiers may use prompts for training; the prompts here are synthetic. |

- **Claude:** Message Batches API, adaptive thinking, effort per Phase 0. No sampling parameters.
- **DeepSeek:** thinking on, reasoning effort "high".

## 7. Budget and stop rules

| Phase | Claude cap | DeepSeek cap |
|---|---|---|
| 0 | US$12 | US$1 |
| 1 | US$40 | US$4 |
| 2 | US$40 | US$3 |
| **Total** | **US$92** (approved limit US$100) | **US$8** (available balance US$8.73) |

- **Gate per phase:** each phase starts only after the previous one's cost is measured.
- **Overrun:** if a phase's estimate exceeds its cap, its scope shrinks before it starts. Cuts follow the order in §8.
- **Deadline:** no run starts after 2026-11-17.

## 8. Order of cuts if time or money runs short

1. Retaining-wall family.
2. V4-Pro in Phase 1.
3. Protocol P3.
4. Opus as a reviewer.

The core, which is never cut, is:

- Phase 0;
- the new overturning cases;
- the gate family, the cleanest orientation test (same load, hinge at the top or the bottom);
- P1 against P2, with the Claude reviewers and DeepSeek Flash.

## 9. Deliverables

- A Study II section in the repository: generator, tests, raw results kept local, graded results, tables and figures.
- A 4–6 page write-up, `writeup/safety-factor-ii.md`, plus a PDF.
- An update to the Study I write-up, if Phase 0 shows that the effort setting changes its conclusions.

## 10. Limitations known in advance

- Synthetic, idealized checks with stated criteria. They are not code compliance (see Study I §2.3).
- English only.
- Free-text answers graded by a judge that belongs to the same family as three of the author models.
- The optional third family runs on free tiers. Its limits may shrink its sample, and that will be reported.
- Effort settings differ between providers.

## Amendments

- **2026-11-10, after the token check, before Phase 0 (harness setting, no hypothesis or rule changed).** At effort "max", Claude Haiku 5.5 used 20,000–29,000 output tokens per answer and hit the 32,000-token limit in 1 of 4 token-check trials. `max_tokens` for high and max effort is raised to 64,000. The truncated trial is kept in `results/raw/phase0_truncated_32k.jsonl` and re-run. Measured cost per trial at "max": Haiku US$0.0059, Sonnet US$0.0262, Opus US$0.0633 (batch prices).
- **2026-11-10, after Phase 0, before any Phase 1 trial (deviation from the §4 rule, with the reason).**

    **Phase 0 results** (`results/tables/phase0_summary.json`). Error rates on the 10 Study I overturning cases:

    | Model | 0A: base prompt, max | 0D: base prompt, high | Study I: medium |
    |---|---|---|---|
    | Haiku | 2/30 | 16/30 | 82/150 |
    | Sonnet | 0/30 | 11/30 | 49/150 |
    | Opus | 0/30 | 7/30 | 53/150 |

    - At max, 0B (coordinates) and 0C (bare lever-arm question) had 0/30 errors for all three Claude models. DeepSeek V4-Pro at "high" had 0/10 errors in both arms.
    - Both of Haiku's errors at max are the uplift-arm mistake.
    - Within one effort setting, wrong and correct answers to the same case use about the same number of output tokens. The setting, not how long a given answer reasons, separates correct from wrong.
    - At max, answers are 4–10 times longer than at high (mean output tokens: Haiku 28,181 against 2,857; Sonnet 5,790 against 1,475; Opus 5,538 against 1,334).

    **What the pre-registered rules give.**
    - H1: Sonnet and Opus are effort-eliminated; Haiku is "reduced" (2/30).
    - Because Haiku is not eliminated, the "eliminated for all three" switch does not trigger.
    - The effort rule selects "max" for Phase 1.
    - H2 is **not testable**, not unsupported: the 0A baseline is already at the floor.

    **Deviation, decided before any Phase 1 data.**
    - **Why.** At max the error rate is at the floor, so H3 (orientation) and the Phase 2 answer pool would have nothing to measure. At high only, the claim that max removes the error would rest on 10 cases.
    - **Phase 1 runs two arms:**
        - **High arm:** the full pre-registered matrix at effort "high" (same repeats as §4; DeepSeek as before). H3 and H3b are tested on this arm.
        - **Max arm:** every one of the 180 cases at effort "max", 1 repeat per Claude model.
    - **New hypothesis H7 (effort generalization), fixed now.** For each Claude model, the max-arm error rate is at least 15 points below the high-arm error rate, paired by case. Tested with a case-bootstrap CI of the difference that excludes zero. It is reported for each family and for hard and easy orientation separately.
    - **Exploratory, labelled as such:** arms 0B and 0C at effort "high" on the 10 Study I cases, 3 repeats per Claude model. They probe H2 where the errors occur.
    - **Estimate:** about US$25 (Claude) for Phase 1 plus about US$1 for the exploratory arms, within the US$40 Phase 1 cap.

    **Phase 2 (pinned now, before it is built).**
    - Every reviewer runs at effort "high". Pool answers come from the high arm.
    - **Cost-matched comparison (new):** for each author model, compare the author at "max" alone (max arm) with the author at "high" plus one reviewer at "high", on the final value's correctness and on output tokens per case.
    - **H5 confound:** DeepSeek at "high" writes 3,000–11,000 output tokens, which is closer to Claude at max than to Claude at high. H5 is therefore reported with tokens per review alongside detection, and is not read as a family effect alone.

    **Consequence for Study I (spec §9).** Study I ran Claude at "medium" and DeepSeek at "high". Its overturning errors, the calculator result and the cross-family contrast hold at that effort only. The Study I write-up is corrected in the same commit as this amendment.
- **2026-11-10, after Phase 1, before any Phase 2 review (results and one pool change).**

    **Phase 1 results** (`results/tables/phase1_summary.json`). Error rates at effort "high":

    | Model | Overturning | Gate | Wall | Sliding |
    |---|---|---|---|---|
    | Haiku | 50% | 0% | 3% | 2% |
    | Sonnet | 18% | 0% | 0% | 0% |
    | Opus | 35% | 0% | 0% | 0% |
    | DeepSeek Flash | 1% | 0% | 0% | 0% |
    | DeepSeek V4-Pro | 0% | — | 0% | — |

    - **At "max"** every family is at or below 3% for every Claude model.
    - **H3: not supported.** In overturning, hard-load mechanisms account for nearly all errors (hard minus easy: Haiku +49 points, Opus +34, Sonnet +18, each CI excluding zero). The gate and wall families show no errors in either orientation, so the pre-registered condition (the effect also in at least one new family) fails. The wall's front-batter case has the same triangle orientation as the dam and still shows no errors: the mistake is tied to the dam overturning check, not to triangular loads in general.
    - **H3b: supported.** The uplift mechanism dominates for Haiku (79 + 27 combined of 119) and Sonnet (26 of 29); the triangle centroid accounts for 55 of Opus's 56 errors. This reproduces Study I on 80 new geometries.
    - **H7: supported overall for Haiku (+22 points) and Opus (+16); not supported overall for Sonnet (+7).** The new families have no errors at either effort, which pulls the overall difference down. In overturning alone, the difference is +47, +35 and +17 points, each CI excluding zero.
    - **Value reader:** agrees with the judge on 99.9% of 1,628 factor-of-safety values.
    - **Spend:** Claude US$21.04; DeepSeek US$3.58.

    **Phase 2 pool change.** The pre-registered pool drew about 300 answers from three families. Wrong answers now exist only in overturning, so mixing families would let a reviewer guess from the family. The pool is therefore **case-matched**: for each overturning case, one wrong and one correct high-arm Claude answer. That gives 156 answers (78 wrong, 78 correct) from 78 cases (`sfe.review.build_matched_pool`, seed 7). No reviewer sees a case more than twice, as pre-registered. Reviewers, protocols, effort and outcomes are unchanged. Estimate: about US$13.4 (Claude), within the US$40 cap.
- **2026-11-10, after Phase 2, before any extra-provider run (results and two extra providers).**

    **Phase 2 results** (`results/tables/phase2_summary.json`, commit d8c57eb). 1,872 Claude and DeepSeek reviews, none unparseable. Detection at P1: Haiku 74%, Sonnet 97%, Opus 88%, DeepSeek Flash 100%; false alarms 0–5%.
    - **H4:** supported for Opus P2 only (+11.5 points, Holm p < 0.001, no rise in false alarms). Not supported for the other reviewers or for P3.
    - **H5:** DeepSeek Flash detects more than Haiku (+26 points) and Opus (+11.5), both after Holm; no difference against Sonnet. It writes 5–9× more output tokens per review.
    - **H6:** supported (Haiku-P2 minus Opus-P1 on Opus answers: +16 points, CI −4 to +40).
    - **Gemini subsample (free tier):** stopped after 11 of 60 answers on a quota error. It is replaced by the extra-provider run below.

    **Extra providers.** H3b and H5 rest on one non-Claude provider, and DeepSeek Flash made almost no overturning errors, so the study cannot yet say whether the lever-arm error is specific to Claude. Two providers are added:
    - **Models:** `gemini-3-flash-preview` (Google, Gemini API; provider-default thinking) and `gpt-oss-120b` (OpenAI's open-weight model, called through OpenRouter and pinned to the Groq endpoint with no fallback to other hosts, reasoning effort "high"; Groq's own paid tier was closed to new upgrades). Same prompts, same JSON instructions as DeepSeek.
    - **As authors:** the 80 Phase 1 overturning cases, 2 repeats each (320 trials), base prompt, `results/raw/phase1_extra.jsonl`. Graded by the same judge and value reader. Reported descriptively next to the Phase 1 "high" arm: error rate with case-bootstrap CI, unsafe approvals, mechanism shares (H3b attribution). No new confirmatory test. Their answers are **not** added to the Phase 2 pool, which stays as pre-registered.
    - **As reviewers:** the full Phase 2 pool (156 answers) × P1–P3 (936 reviews), same requests and scoring. The 22 free-tier Gemini reviews already done are identical requests and are kept. P1 detection of each extra reviewer is compared with each Claude reviewer (H5x, 6 contrasts) under its **own Holm family**; the pre-registered H4–H6 family and its p-values are unchanged.
    - **Budget and stop rule:** prepaid credit is the hard cap: Gemini US$15, OpenRouter US$5 (estimates about US$13 and US$3 at list prices). Spend is computed from tokens × list price. If a cap or the 2026-11-17 run deadline is reached, what finished is reported as partial, with counts.
- **2026-11-10, night, after Phase 2, before any exploratory run (exploratory additions E1–E2).** Committed locally before the runs; the repository could not be pushed overnight, so this amendment became public after the data it governs. E1 and E2 are therefore reported as **exploratory**, separately from the pre-registered results, which they do not change.
    - **E1, effort dose-response.** The 80 Phase 1 overturning cases at effort "low" and "medium", base prompt, same repeats as Phase 1 (Haiku 3, Sonnet 2, Opus 2). Reported: error rate with case-bootstrap CI at low, medium, high and max (high and max from Phase 1), and medium minus high paired by case. Motivation: Study I's medium-effort result rests on 10 cases; the effort sweep is the contingency already described in §4.
    - **E2, set-up first (author).** Same cases and repeats at effort "high", with one sentence added before the question: *"Before computing anything, write down for every load and weight where its line of action is, measured from the point about which moments are taken, and how you located it."* It contains no hint of the answer. Threshold, fixed now: for each model, the error rate is at least 10 points below the Phase 1 base prompt at "high", paired by case, with a case-bootstrap CI excluding zero. Mechanism shares are also reported.
    - **Grading and cap.** Same judge, value reader and mechanism attribution as Phase 1. Claude cap for E1–E2: US$30 including the judge (estimate about US$15). Runs not finished by 03:30 on 2026-11-11 are reported as incomplete.
    - **E3, the same dams without uplift (added at 21:55, before its run, same night and same status).** The 80 Phase 1 overturning geometries with the uplift removed and the assumptions text changed to "no uplift on the base (fully drained foundation)" (`data/cases_explore_nouplift.jsonl`, `sfe.cases2.generate_nouplift_cases`; truth re-derived by `sfe.physics.overturning_fs`). What remains is the concrete triangle (hard, as in the front-batter wall) and the water thrust (easy). Base prompt, effort "high", same repeats. All 80 are safe at FS ≥ 1.5, so only the value error is informative. Reported: error rate and triangle-centroid share against the same geometries in Phase 1, paired by case. Question: does Opus's triangle error survive when the dam has no uplift (pointing to the dam template) or vanish (pointing to load complexity)? Included in the US$30 cap.
- **2026-11-10, night, after E1–E3 results, before E5–E6 (exploratory, same status as E1–E3).** E1–E3 results: error falls monotonically with effort; the set-up-first sentence (E2) lowers the "high" error for every model past the threshold (Haiku −26 points, Sonnet −16, Opus −35); without uplift (E3), Opus still misplaces the triangle in 17.5% of answers, while the front-batter wall in Phase 1 had none. One difference between the two prompts is that the wall text states where the triangle's apex is and the dam text does not.
    - **E5, apex stated.** The Phase 1 dams (with uplift) at "high", base prompt plus one sentence: *"The downstream triangle's vertical side is at the downstream edge of the crest, and its apex (zero thickness) is at the toe."* Reported: triangle-centroid error share against Phase 1 "high", paired by case. Expectation, fixed now: Opus's triangle-centroid share falls by at least 10 points with a CI excluding zero; uplift errors (Haiku, Sonnet) are not expected to change, since the uplift distribution is already stated.
    - **E6, set-up-first at lower effort.** The E2 prompt at "low" and "medium". Reported: error rate against the base prompt at the same effort (E1), paired by case; same 10-point threshold as E2.
    - Same repeats, grading and attribution. Claude cap for E5–E6: US$20 including the judge (estimate about US$12).
- **2026-11-10, night, before E4 (exploratory, same status).** **E4, a local open-weight reasoning model.** `qwen3:14b` (Ollama, 4-bit, run on the author's laptop; thinking on, 24,000-token output budget) as author on the 80 Phase 1 overturning cases (1 repeat, base prompt), then as reviewer on the Phase 2 pool under P1, then P2. Time-boxed: no request starts after 05:00 on 2026-11-11; whatever finished is reported with counts. Graded by the same judge and attribution. No API cost. Reported descriptively next to the API models; it is a much smaller model, so it tests whether the error and the review results reach a model of this size, not a provider effect.
- **2026-11-10, night, after E5–E6 results, before round 3 (exploratory replication with fixed predictions; same publication status).** E5: the apex sentence removed Opus's error (35% → 0%) but raised Haiku's and Sonnet's (+11 and +13 points, via uplift). E6: set-up-first lowered the error at "low" and "medium" for every model (Opus 0% at both). These rest on the same 80 cases with no control, so round 3 replicates them on **80 held-out dams** (new seed 2028, `data/cases_explore_holdout.jsonl`, re-derived by an independent formula in `tests/test_cases2.py`, no geometry shared with Phase 1), with a **placebo** sentence of similar length: *"Before answering, work slowly and carefully, double-check every number you use, and show each step of your calculation in full."*
    - **Arms (same repeats):** at "high": base, set-up-first, apex, placebo; at "low": base, set-up-first. Side arm: set-up-first at "high" on the Phase 1 gate, wall and sliding cases.
    - **Predictions, fixed now (paired by case, case-bootstrap 95% CI, uncorrected):**
        - R1: set-up-first minus base at "high" is ≤ −10 points with the CI below zero, for each model (replicates E2).
        - R2: set-up-first minus base at "low" is ≤ −10 points with the CI below zero, for each model (replicates E6).
        - R3: placebo minus base at "high" does **not** reach −10 points for any model. If it does, the E2 effect is read as a generic effect of an added instruction, not of the set-up content.
        - R4: apex lowers Opus's triangle-centroid share by ≥ 10 points (replicates E5); for Haiku and Sonnet, apex minus base error is reported, and E5's harm counts as replicated only if the CI is above zero again.
        - R5 (side effects): on gate, wall and sliding, set-up-first changes neither the error rate nor the share of safe cases not approved by more than 5 points against Phase 1 "high".
    - Claude cap for round 3: US$40 including the judge (estimate about US$30).
    - **E4 revised before any recorded trial.** With thinking on, `qwen3:14b` took over 20 minutes on its first overturning answer on this laptop, so 80 answers could not finish. E4 instead runs `qwen3:14b` in its documented **non-thinking mode** (`think: false`), about 2.5 minutes per answer. One timing trial was run and not recorded. Authors first (80 cases, 1 repeat), then P1 reviews, under the same 05:00 time box. This makes E4 a test of a small local model *without* extended reasoning, closer to the "low"-effort end of E1.
- **2026-11-10, night, after the extra-provider results, before E7 (exploratory, same status).** As authors, gpt-oss-120b erred on 27.5% of overturning answers (same mechanisms: triangle centroid, uplift) and Gemini 3 Flash on 6.9%. **E7:** the E2 set-up-first prompt on gpt-oss-120b, 80 cases, 1 repeat (the remaining OpenRouter balance, about US$1.4, is the cap), compared with its 2-repeat base answers paired by case; same 10-point threshold. Gemini is below 10% and is not run.
- **2026-11-10, night, after round 3, before round 4 (exploratory, same status).** Round 3: R1, R2 and R4 replicated; R3 failed (the placebo removed Opus's error and cut Haiku's by 19 points); R5 failed for Haiku (31% of safe walls not approved with set-up first). The placebo combined "show each step" with "work carefully", and the base prompt asks only for a verdict and an explanation, so **round 4** splits it on the 80 held-out dams at "high", same repeats, one sentence each: *"Show each step of your calculation in full."* (steps), *"Work slowly and carefully and double-check every number."* (care), and a neutral filler of similar length, *"This check is one of several similar structures in a routine review."* (filler). Compared with the round 3 base arm, paired by case.
    - **Predictions, fixed now:** F1: filler does not reach −10 points for any model (an added sentence by itself does nothing). F2: for Opus, at least one of steps or care reaches −10 points with the CI below zero (the round 3 placebo effect is carried by one of its parts). Which part, and the results for Haiku and Sonnet, are reported without a prediction.
    - Claude cap: US$20 including the judge (estimate about US$14).
- **2026-11-10, night, before the H6 replication (exploratory, same status).** H6 (weak-to-strong review) rests on 25 wrong Opus answers with a wide interval. **Replication:** Opus's 160 round 3 answers on the held-out dams (base prompt, "high"; 54 wrong) reviewed by Opus P1, Opus P2 and Haiku P2, with Phase 2's requests and scoring (`scripts/h6_replication.py`). The pool is Opus-authored only, unlike Phase 2's. **Predictions, fixed now:** (i) Haiku-P2 minus Opus-P1 detection on the wrong answers has a case-bootstrap lower bound above −5 points; (ii) Opus P2 detection beats P1 by at least 10 points with the CI above zero, with false alarms up by no more than 5 points. Cap US$5 (estimate about US$3).
- **2026-11-10, night: errata and exploratory results recorded.** Two statements in earlier amendments are wrong and are left as written above: (a) the Phase 1 entry says the gate and wall "show no errors in either orientation" — Haiku made 4 wall errors at "high", all in the easy orientation; (b) the Phase 2 entry says DeepSeek writes "5–9×" more output per review — the ratio is 2× (against Haiku) to 9× (against Opus). Exploratory results (E1–E7, rounds 3–4) are reported in `writeup/safety-factor-ii.md` §7 and its appendix; in short, set-up first replicated on held-out dams, the placebo also fixed Opus (R3 failed), Haiku became over-cautious on other checks with set-up first (R5 failed), the apex harm replicated, and in round 4 "work slowly and carefully and double-check" carried most of the placebo's effect while a neutral filler did nothing.
- **2026-11-10, night, after the H6 replication, before the reviewer placebo (exploratory, same status).** H4/H6 replicated (Opus P1 74%, Opus P2 98%, Haiku P2 98% on 54 wrong held-out answers). Since a "work carefully" sentence fixed Opus as an author (round 4), **P1C** asks Opus as reviewer: *"Work slowly and carefully and double-check every number. Then check the calculation."* on the same 160 answers. Reported: P1C minus P1 and P2 minus P1C, paired by case. Prediction, fixed now: P2 minus P1C is at least 10 points with the CI above zero (the review gain comes from the procedure, not from care alone). Cap US$3.
- **2026-11-11, early morning: results of the last exploratory runs, recorded for completeness.** H4/H6 replication on held-out Opus answers (54 wrong): Opus P1 74%, Opus P2 98%, Haiku P2 98% (13% false alarms); both predictions met. Reviewer placebo P1C: 83%; P2 minus P1C +18 points by case [+6, +31], prediction met. E4 (qwen3:14b, non-thinking): 94% of answers wrong, almost all by unrelated mistakes; as P1 reviewer, 18% detection with 18% false alarms. E7: set-up first did not help gpt-oss-120b. All figures and their sources are in `writeup/safety-factor-ii.md`, its appendix and `results/tables/`.
