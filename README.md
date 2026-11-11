# Safety Factor: Will an AI sign off on an unsafe hydraulic design?

An empirical AI-safety study in a domain where errors cost lives. Language models review hydraulic design checks with code-computed ground truth: dam sliding, dam overturning, spillway capacity against the 100-year flood, and pipeline delivery pressure. Some designs meet the criterion stated in the prompt, some fail it, and some fail by less than 5%. The criteria are illustrative textbook checks, not a design standard; the write-up compares them with USACE, FEMA P-94 and Bulletin 17C. The checks are presented neutrally and under pressure from a client, a superior, a flawed user calculation, or urgency, and with mitigations that come from engineering practice.

The write-up is in [`writeup/safety-factor.md`](writeup/safety-factor.md) (PDF: `writeup/safety-factor.pdf`), with detail tables in [`writeup/appendix.md`](writeup/appendix.md).

## Study II (pre-registered follow-up)

[`writeup/safety-factor-ii.md`](writeup/safety-factor-ii.md) (PDF: `writeup/safety-factor-ii.pdf`; exploratory detail in [`writeup/safety-factor-ii-appendix.md`](writeup/safety-factor-ii-appendix.md)). Pre-registration and dated amendments: [`docs/superpowers/specs/2026-11-10-safety-factor-ii-design.md`](docs/superpowers/specs/2026-11-10-safety-factor-ii-design.md). In short: the lever-arm error depends on reasoning effort and on prompt wording, not on knowledge; it is specific to the dam overturning check; it is not specific to Claude (gpt-oss-120b and Gemini 3 Flash make it too); a second model's review catches most of it, far more cheaply than maximum effort. Scripts: `scripts/phase0.py`, `phase1.py`, `phase2.py`, `explore.py`, `explore_local.py` and the matching `analyze_*` scripts; summary tables in `results/tables/`. Graded answers are in `results/graded/`; the Phase 2 reviews and pool are committed in `results/raw/phase2*.jsonl`; other raw API outputs are not committed because of their size.

> **Correction (10 Nov 2026):** Study I ran Claude at effort "medium". A pre-registered follow-up shows the lever-arm errors almost disappear at effort "max" (see the correction at the top of the write-up and `docs/superpowers/specs/2026-11-10-safety-factor-ii-design.md`).

## What is measured

- **Unsafe approval rate:** unsafe or borderline designs approved.
- **Error attribution:** an approval caused by a wrong computed value versus an approval with the right value, given anyway.
- **False rejections** of safe designs.
- **Flips** after pushback (pilot only).
- **Escalation.**
- **Citations of standards** that were not given in the prompt.

Rates are reported with Wilson intervals and a case-cluster bootstrap.

## Mitigation arms

| Arm | Mitigation |
|---|---|
| M0 | None |
| M1 | Numbers by code (calculator tool) |
| M2 | Engineer-of-record duty |
| M3 | Structured verdict |
| M4 | Second-model verifier |
| M5 | M1 + M2 + M3 |

## Reproduce

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest -q                       # physics, cases, prompts, engine, backends, grading, analysis
uv run python scripts/gen_cases.py     # regenerates data/cases.jsonl (seed 2026) and data/cases_review.md
```

API keys come only from the environment, for example from a local `.env` file that is never committed:

```
ANTHROPIC_API_KEY=...
DEEPSEEK_API_KEY=...
```

Run, grade, analyze:

```bash
set -a; . ./.env; set +a
uv run sfe-run --phase pilot --models claude-haiku-5-5 --arms M0 --modes A --out results/raw/pilot.jsonl
uv run sfe-run --phase full  --models claude-sonnet-5-5 --arms M0,M1,M4 --modes A --repeats 3 \
  --confirm-budget 20 --out results/raw/full_claude.jsonl     # refuses to start above the approved budget
uv run sfe-grade results/raw/full_claude.jsonl results/graded/full_claude.jsonl
uv run python scripts/analyze.py      # tables in results/tables, figures in results/figures
```

How the runner calls each provider:
- **Claude** runs through the Message Batches API (one batch per conversation round).
- **DeepSeek** runs through its OpenAI-compatible API, with 8 requests in parallel.
- **Interrupted runs resume** without re-paying for finished trials.

## Layout

| Path | Content |
|---|---|
| `src/sfe/physics.py` | Design-check formulas |
| `src/sfe/cases.py` | Seeded generator of 40 cases, with flawed calculations |
| `src/sfe/prompts.py` | Pressure conditions, mitigations, calculator, verdict schema |
| `src/sfe/engine.py` | Trial state machine (tools, pushback, verifier) |
| `src/sfe/backends/` | Claude (batches), DeepSeek, Ollama |
| `src/sfe/run.py` | Trial matrix, budget gate, resume |
| `src/sfe/grade.py` | Code grading, judge model, agreement with human labels |
| `src/sfe/analyze.py` | Metrics, intervals, contrasts, figures |
| `docs/superpowers/` | Design spec and implementation plan |

## Author

Esteban Garzon, civil engineer (hydraulics and hydropower) turned data and AI engineer · [estebangarzon.com](https://www.estebangarzon.com)
