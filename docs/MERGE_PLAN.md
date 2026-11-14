# Merge plan: integrating A0, A1 and A2

- **Written by:** A0 (session launched by ry), 2026-11-14
- **Binding for:** the A0 session that performs the integration ("merging agent"). Follow it step by step.
  If a step cannot be done as written, stop and ask ry. Do not improvise around this plan.
- **Baseline:** `main` at `c8e8127` (PR #4). Verified on 2026-11-14: ruff, `mypy --strict`, the schema check
  and 278 tests pass (98 % coverage).

---

## 1. What "merging" means here

The Git merges of A0, A1 and A2 are **already done**:

| PR | Branch | Content |
|---|---|---|
| #1 | `a0/ry/scaffolding-gemini-wrapper` | Contracts v1.0.1, `common/` (config, log, Gemini wrapper), CI, docs |
| #2 | `a2/ry/question-interpreter` | A2 Question Interpreter + terminal REPL |
| #3 | `a1/ot/validator-gemini` | A1 Input Validator (Gemini image classification) |
| #4 | `a0/ot/validation-config-deps` | A1's dependencies and config, `gemini-3.5-flash-lite` for validation (D-009) |

What is missing is the **integration**: one program that runs the components in order. That is A0's
orchestrator (`src/blueprint_qa/orchestrator/`) and front door (`src/blueprint_qa/api/`). Neither exists yet.
This plan builds them for **A1 → A2** only (part of task #3 in `docs/TASKS.md`).

## 2. Scope

**In scope:** A0 (orchestrator, front door, docs), and the integration of A1 and A2 through their public entry points.

**Out of scope. Do not touch:**

- **A3 (Blueprint Analyzer).** Not finished. Do not merge, rebase or edit `a3/SS/cubicasa-detector`, and do not
  touch `blueprints-starter/`. A3's visualisation features are disregarded too (not deleted, just not part of this work).
- **A4.** Not implemented.
- **The architecture decision** (see §3.3). The team decides it later. Do not pick one.
- **Proposals 001 (fixtures) and 004 (storey levels).** Leave them as they are. 004 matters only once A3/A4 exist.
- **A1's provisional edge cases** (OPEN_QUESTIONS Q7) and **A2's interim storey vocabulary** (DEVIATIONS). Leave them.

## 3. Behaviour to build

### 3.1 Flow (as described by ry, 2026-11-14)

```
upload + question
   │
   ▼
A1 validate(request) ──── ErrorEnvelope ───────────────► user-safe error message
   │
   ├── is_valid = False ──────────────────────────────► "This picture is invalid for our program"
   │
   ▼ is_valid = True
A2 interpret(request_id, question, locale_hint) ─ ErrorEnvelope ─► user-safe error message
   │
   ▼ ParsedQuestion
[ A3 + A4: not available yet ] ─────────────────────► interim Answer (see 3.2)
```

R5.2: when A1 says invalid, A2 MUST NOT be called.

### 3.2 What `run()` returns (contract-conformant, no fabricated numbers)

Entry point per AGENTS.md §6 A0: `orchestrator/pipeline.py :: run(request: PipelineRequest) -> Answer | ErrorEnvelope`.

| Situation | Return |
|---|---|
| A1 or A2 returns an `ErrorEnvelope` | That envelope (after contract validation, §3.4) |
| A1: `is_valid=False` | `Answer(status=CANNOT_ANSWER, value=None, explanation="This picture is invalid for our program", language="en", evidence=[], confidence=<A1 confidence>, unit="count")`. This is the exact text ry asked for. English, because A2 has not run and the question's language is unknown |
| A2: `intent=UNSUPPORTED` | `Answer(status=UNSUPPORTED_QUESTION, value=None, ...)` |
| A2: `clarification_needed` set | `Answer(status=NEEDS_CLARIFICATION, value=None, explanation=<clarification_needed>, language=<ParsedQuestion.language>)` (A2 already wrote it in the user's language) |
| Otherwise | `Answer(status=CANNOT_ANSWER, value=None, explanation="Plan analysis is not available yet.", language="en")` |

- `value` is always `None` in this phase. Never produce a number (R5.3, principle 3).
- **Contract gap:** `Answer.unit` is required even when `value` is `None`. Use `"count"` as a placeholder in
  these interim answers, and record the gap in `docs/OPEN_QUESTIONS.md` (proposal: make `unit` optional when
  `value` is `None`). Do **not** change the contract in this task.
- Keep the fixed texts above in **one** module-level mapping in `pipeline.py` (no hard-coding scattered around),
  so they are easy to change or translate later.

### 3.3 Keep the A3/A4 slot open (architecture undecided)

AGENTS.md says A2 and A3 run in parallel and A4 computes the answer. ry's description sends A2's output into A3
and has A4 phrase the answer. The team will decide later (record this as an open question, step 6). So:

- Build the flow as **one ordered list of stage steps** in `pipeline.py`, with a clearly marked place where the
  A3 (and later A4) step goes. Do not implement or stub A3/A4 calls, and do not add concurrency yet.
- The orchestrator never contains image processing, NLP, IFC parsing or calculations (§6 A0).

### 3.4 Mandatory orchestrator duties (AGENTS.md §6 A0)

- The front door creates `request_id` (UUID4) and `received_at` (UTC), and `run()` passes them through unchanged.
- **Validate every component output against its contract** before using it (re-validate the returned model).
  On a violation, return `ErrorEnvelope(code="INVALID_INPUT", stage=ORCHESTRATOR, details={"producer": "<stage>"})`.
  Also check that `request_id` came back unchanged.
- **No exception escapes `run()`** (R5.1). A component that raises gives `INTERNAL_ERROR` with a debug detail.
- `details` never reach the end user. The front door shows only `message` or `explanation`.
- Log one structured event per stage via `common/log.py` (`request_id`, `stage`, outcome, latency). Never log file
  bytes or the question text at INFO level or above.
- Import components **only** through their public entry points: `from blueprint_qa.validation import validate`
  and `from blueprint_qa.question import interpret`.

### 3.5 Front door (`api/`)

A command line is enough for this phase (an HTTP API can come later):

```
python -m blueprint_qa.api <file> "<question>" [--format PNG|JPEG|PDF|IFC] [--locale fi-FI] [--json] [--debug]
```

- Format: from `--format`, otherwise from the file extension. A1 verifies it against the bytes anyway.
- Default output: one readable line (the answer text or the user-safe message). `--json` prints the `Answer` /
  `ErrorEnvelope` JSON without `details`.
- `--debug` additionally prints the intermediate stage outputs (A1 verdict without image bytes, A2's
  `ParsedQuestion`) to stderr. This is a developer aid; make `run()`'s internals expose them through a private helper.
  Do not add a second public entry point.
- Optional: an interactive mode (`--interactive`) that asks for questions repeatedly about one file. Each question
  is a full `run()` (A1 runs again). Do not cache A1 results between questions: components are stateless (R3.7).

## 4. Files (A0-owned paths only)

```
src/blueprint_qa/orchestrator/__init__.py   exports run only
src/blueprint_qa/orchestrator/pipeline.py   run(): stage steps, contract checks, interim answers, fixed texts
src/blueprint_qa/api/__init__.py            (no public logic)
src/blueprint_qa/api/__main__.py            CLI front door (builds PipelineRequest, prints result)
tests/unit/orchestrator/                    unit tests with fake A1/A2 entry points (monkeypatch)
tests/unit/api/                             CLI tests (fake run())
```

Any new config keys go in `config/default.yaml` (A0) if needed. No hard-coded limits (R3.9).

## 5. Steps

1. **Start.** New Claude Code session in role **A0**. `git checkout main && git pull`, then create branch
   `a0/ry/integration-a1-a2`. Append a claim to `docs/TASKS.md` (task #3, partial: "orchestrator + CLI for A1→A2", A0, ry, date).
2. **Baseline.** Run the check sequence (step 8) on the fresh branch. It must match §0 (278 tests passing). If not, stop and report.
3. **Housekeeping (append-only).** In `docs/TASKS.md`, append status lines saying that tasks 7–10 were merged
   (PRs #3, #4), since their rows still say "not merged". Never rewrite existing rows.
4. **Orchestrator.** Implement §3.1–3.4 in `orchestrator/pipeline.py`.
5. **Front door.** Implement §3.5 in `api/__main__.py`.
6. **Docs.**
   - `docs/OPEN_QUESTIONS.md`: Q8 (architecture: AGENTS.md vs ry's description, see §3.3; the team decides),
     Q9 (`Answer.unit` when `value` is None).
   - `README.md`: how to run the CLI, and the updated layout status table.
   - `docs/CHANGELOG.md`: entry for this task.
7. **Tests** in `tests/unit/orchestrator/` and `tests/unit/api/`, offline, with fakes for A1 and A2:
   - valid → A2 called → interim answer; invalid → **A2 not called** and the exact invalid-picture text;
   - A1 error and A2 error pass through; a component that raises gives `INTERNAL_ERROR`; a component returning a
     changed `request_id` or a contract-invalid object gives `INVALID_INPUT` with `details.producer`;
   - `UNSUPPORTED` → `UNSUPPORTED_QUESTION`; clarification → `NEEDS_CLARIFICATION` with the A2 text;
   - CLI: format detection, `--json` hides `details`, a missing file gives a clear message and a non-zero exit code;
   - coverage ≥ 80 % for `orchestrator` and `api`.
8. **Check sequence** (must all pass):
   ```
   ruff format --check src tests
   ruff check src tests
   python -m mypy
   python -m blueprint_qa.contracts.generate_schema --check
   pytest --cov=blueprint_qa --cov-fail-under=80
   ```
9. **Live demo** with the real Gemini API (key in `GEMINI_API_KEY`, never print it), using A1's test images:
   - `tests/unit/validation/data/house_plan_fi.png` with "Montako makuuhuonetta talossa on?",
     "How many bedrooms are there?" and "Wie viele Schlafzimmer gibt es?" → valid, interim answer, `--debug` shows the
     same `ParsedQuestion` for all three;
   - `tests/unit/validation/data/bar_chart.png` → exactly "This picture is invalid for our program", and the log shows
     no A2 call;
   - `tests/unit/validation/data/prompt_injection.png` → behaves safely.
   Report the actual outputs and timings to ry.
10. **Finish.** Commit with `[A0] ...` messages. **Do not push.** ry reviews, then pushes and opens the pull request.
    A teammate other than ry approves it (§9).

## 6. Rules for the merging agent

- Write only in A0 paths (§4). If A1 or A2 needs a change, write `docs/requests/A1-…md` / `A2-…md` and continue.
  Do not edit `validation/` or `question/`, even for a one-line fix.
- Do not change contracts or AGENTS.md in this task. Gaps go to `docs/OPEN_QUESTIONS.md`.
- Shared docs are append-only. In a conflict, keep both entries, ordered by date.
- Never claim something works without running it (R10.4). Report failures as they are.
- If anything in this plan conflicts with AGENTS.md, stop and ask ry. A human instruction that overrides
  AGENTS.md is recorded in `docs/DEVIATIONS.md`.

## 7. Definition of done

- [ ] `run()` and the CLI implement §3 for A1 → A2; the A3/A4 slot is marked but empty
- [ ] Invalid picture → exactly "This picture is invalid for our program"; A2 not called
- [ ] No exception escapes; every component output contract-checked; no numbers produced
- [ ] Only A0 paths changed; contracts and AGENTS.md unchanged
- [ ] Check sequence passes; coverage ≥ 80 % for `orchestrator` and `api`
- [ ] Live demo done and reported
- [ ] TASKS, OPEN_QUESTIONS (Q8, Q9), README and CHANGELOG updated
- [ ] Committed on `a0/ry/integration-a1-a2`, not pushed
