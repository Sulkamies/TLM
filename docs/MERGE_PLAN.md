# Integration plan v2: A0 + A1 + A2 + A3

- **Written by:** A0 (session launched by ry), 2026-11-14. **Supersedes v1** (A1 + A2 only; see git history).
- **Binding for:** the A0 session that performs the integration ("integration agent"). Follow it phase by phase.
  If a step cannot be done as written, stop and ask ry. Do not improvise around this plan.
- **A4 is out of scope** (not implemented). The pipeline ends at a marked A4 slot and returns interim answers without numbers.
- **Baseline:** `main` at `c8e8127`. Verified 2026-11-14: all checks pass, 278 tests.

---

## 1. Architecture basis

This plan follows **AGENTS.md as written**, which is also what the A3 team designed for:

```
upload + question ─► A1 validate ─ invalid ─► "This picture is invalid for our program"
                         │ valid
              ┌──────────┴──────────┐   concurrently
              ▼                     ▼
      A2 interpret(question)   A3 analyze(ValidationResult)    ← A3 never sees the question
              │ ParsedQuestion      │ BlueprintAnalysis         ← everything found in the plan
              └──────────┬──────────┘
                         ▼
                 [ A4 slot: empty ]  ─► interim Answer (no number)
```

- A3 is **question-agnostic**: its tuned counting rules become *which elements it outputs* (see
  `docs/requests/A3-analysis-adapter.md`). A4 will later do the counting, e.g. "how many WC rooms" → count the rooms
  with `room_type=TOILET`.
- This replaces ry's earlier description, where A3 received the question. ry must confirm this basis before phase 4
  (OPEN_QUESTIONS Q8). If the team chooses the other architecture instead, stop: it is a breaking contract change.

## 2. Component status

| Role | Status | Where |
|---|---|---|
| A0 | Contracts v1.0.1, `common/`, config, CI: **merged** | `main` |
| A1 | Input Validator: **merged** (Gemini image check, approved in EXTERNAL_SERVICES) | `main`, `validation/` |
| A2 | Question Interpreter: **merged** | `main`, `question/` |
| A3 | **Not mergeable yet.** Prototype code only, in `blueprints-starter/` (detector, counting rules, tuned thresholds v2: 84.5 % on the CubiCasa test split). Branch base is the very first commit. No `analysis/` package, no `analyze()`, no unit tests. Needs torch/ultralytics/easyocr and weights that are not in git | `a3/SS/cubicasa-detector` |
| Orchestrator / CLI | **Not started.** v1 steps 1 and 3 done (task claim, TASKS housekeeping) | `a0/ry/integration-a1-a2` |

## 3. Decisions (gates)

| Gate | Decision | Needed for | Status |
|---|---|---|---|
| G1 | **Contract change 001, fixtures** (final diff in `docs/contract-changes/001-fixture-entities.md`, revision 2). Additive → v1.1.0. Needs A0 + 1 human | Phase 2 | Awaiting ry's approval |
| G2 | **Contract change 004, storey levels**, lighter option (already chosen by ry). Needs A0 approval | Phase 2 | A0 approves when applying |
| G3 | **Heavy A3 libraries** as an optional `vision` extra in `pyproject.toml`; CI installs the base package only | Phase 2 | A0 + 1 human (shared file) |
| G4 | **`--debug-overlay` not required** for this integration: ry said to disregard visualisation (§6 A3 requires it, so record a deviation) | Phase 3 | Integration agent records it in `docs/DEVIATIONS.md` |
| G5 | **Original file passthrough** (A3's second proposal: give A3 the original PDF/path for DXF/SVG/IFC companion files). **Not part of this integration.** It conflicts with §6 A0 ("pass A1's normalized outputs to A3, never the raw upload"), and real uploads have no companion files next to them. Record it as proposal **005** for a team decision | Later | Team decision |

## 4. Phases and who does what

Each phase is its own branch and pull request. Merge with "Create a merge commit". A teammate other than the
launcher approves each one (§9). Delete branches after merging.

### Phase 1: orchestrator and CLI for A1 → A2 (integration agent, A0)

Branch: continue on `a0/ry/integration-a1-a2`. Build what v1 §3–§5 described, unchanged:

- `orchestrator/pipeline.py :: run(request) -> Answer | ErrorEnvelope`: A1 first; on `is_valid=False` return the
  interim answer with exactly **"This picture is invalid for our program"** and do **not** call A2 (R5.2); otherwise A2.
- Contract-check every component output (`INVALID_INPUT`, `details.producer`), check that `request_id` comes back
  unchanged, never let an exception escape (R5.1), log one event per stage, never produce a number.
- Interim answers (fixed texts in one module-level mapping): A1 invalid → `CANNOT_ANSWER` + the invalid-picture text
  (`language="en"`); `UNSUPPORTED` → `UNSUPPORTED_QUESTION`; `clarification_needed` → `NEEDS_CLARIFICATION` with
  A2's text; otherwise `CANNOT_ANSWER`, "Plan analysis is not available yet.". `unit="count"` as a placeholder, and
  record the gap as OPEN_QUESTIONS Q9 (`Answer.unit` when `value` is None).
- Structure the flow as an ordered list of stage steps with **a marked A3 step slot and an A4 slot**. Phase 4 fills A3.
- CLI `python -m blueprint_qa.api <file> "<question>" [--format] [--locale] [--json] [--debug]`. `--json` hides
  `details`; `--debug` prints the stage outputs (no image bytes) to stderr.
- Tests in `tests/unit/orchestrator/` and `tests/unit/api/` with fake A1/A2; coverage ≥ 80 %. Live demo with A1's
  test images (`house_plan_fi.png` asked in fi/en/de; `bar_chart.png` must give the invalid text with no A2 call).
- Docs: OPEN_QUESTIONS Q8 (architecture basis, §1) and Q9; README; CHANGELOG.

### Phase 2: contracts, config and dependencies for A3 (integration agent, A0)

Branch: `a0/ry/contracts-fixtures` from `main` (after phase 1 is merged, or from `main` in parallel; the two touch
different files). **Only after G1 is approved** (G2 and G3 go in the same branch):

1. Apply **001 revision 2** (fixtures) and **004** (lighter option: `StoreyLevel` + `Storey.level`, `EntityRef.storey`
   stays `str`): `vocabulary.py` (+ `DESCRIPTIONS`), `analysis.py`, `question.py`. Contract version **1.1.0**.
   Regenerate the schemas, update AGENTS.md §4.2, add tests (vocabulary coverage, round trips).
2. `config/default.yaml`: new `analysis:` section with the detector thresholds and strategies from A3's request
   (`docs/requests/A0-detector-thresholds.md`; values from `eval/thresholds_vision_v2.json` on the A3 branch) and the
   detector options (`conf`, `imgsz`, weights path or env name). No secrets.
3. `pyproject.toml`: optional extra `vision = ["torch…", "ultralytics…", "easyocr…"]`, pinned to minor ranges (R3.4).
   Base install and CI stay light. CI must not install the extra.
4. **R4.5: merge together with A2's adaptation.** After step 1, A2's tests fail on purpose: every vocabulary value
   needs synonyms in en/de/fi, and cassettes miss because the rendered prompt changed. Write
   `docs/requests/A2-fixture-vocabulary.md` (the work items in phase 2b). Phase 2 and 2b merge as one unit: either
   A2 bases its branch on `a0/ry/contracts-fixtures` and both PRs are merged back to back, or A2's commits are
   added to the phase 2 PR.

### Phase 2b: A2 adapts to v1.1.0 (A2 session, launched by any human)

Branch: `a2/<initials>/fixture-vocabulary` from `a0/ry/contracts-fixtures`.
- Synonyms and few-shot examples for `FixtureType` in en/de/fi (e.g. "toilet bowl" / "WC-Schüssel" / "wc-istuin";
  "How many showers and bathtubs?" → `COUNT`, `SUM`, two `FIXTURE` targets: `SHOWER` and `BATHTUB`).
  Keep the distinction: a TOILET **room** vs a TOILET **fixture**.
- Storeys: delete the interim `values:` block in `question/interim_vocabulary.yaml` (004 is now in the contracts)
  and close the deviation entry.
- Re-record the cassettes. All A2 tests and the live test pass.

### Phase 3: A3 adapter (A3 session, SS)

Brief: **`docs/requests/A3-analysis-adapter.md`** (acceptance criteria; hand this to the A3 agent).
Branch: `a3/SS/analysis-adapter` from `main` **after phase 2(+2b) is merged** (it needs `Fixture`, `StoreyLevel` and
the `analysis:` config). A3 can start porting earlier from `main` and rebase later.
The old branch `a3/SS/cubicasa-detector` is **not merged**. Keep it as an archive; do not delete it.

### Phase 4: wire A3 into the pipeline (integration agent, A0)

Branch: `a0/ry/integration-a3` from `main` after phase 3 is merged.
1. Validity check of the merged A3 code, the same way as for A2: ownership, entry point, no vendor LLM SDK,
   vocabulary only from contracts, no exceptions across the boundary, lazy heavy imports, CI green without weights.
2. Fill the A3 slot: after A1 says valid, run **A2 and A3 concurrently** (§6 A0), passing A3 the `ValidationResult`
   (never the raw upload). Contract-check both outputs. The A4 slot stays empty: the interim answer is unchanged, and
   `--debug` additionally prints a `BlueprintAnalysis` summary (JSON, no image bytes).
3. A failure in A3 returns its `ErrorEnvelope` (user-safe message), even if A2 succeeded.
4. Live demo on ry's machine with the real weights (`models/fetch.py`): a CubiCasa plan plus "Montako makuuhuonetta?",
   "How many toilet bowls are there?", "Wie viele Fenster gibt es?". Report A1's verdict, A2's `ParsedQuestion`, A3's
   rooms/fixtures/openings by type and the timings. Also an IFC file, if A3 delivered the IFC path; otherwise check that
   A3 returns a clean `ErrorEnvelope`.

## 5. Rules for the integration agent

- Write only in A0 paths: `orchestrator/`, `api/`, `common/`, `contracts/`, `config/`, `tests/unit/{orchestrator,api,common,contracts}/`,
  `pyproject.toml`, `.github/`, and A0 docs. Shared docs are append-only.
- Never edit `validation/`, `question/` or `analysis/`, `models/`, or anything on A3's branches, and never touch
  `blueprints-starter/`. Write `docs/requests/<role>-<title>.md` instead.
- Apply contract changes only with the recorded approvals (§3). Never implement proposal 005.
- Never print or log `GEMINI_API_KEY`. Never commit model weights.
- Run the check sequence before every commit that changes code:
  `ruff format --check src tests` · `ruff check src tests` · `python -m mypy` ·
  `python -m blueprint_qa.contracts.generate_schema --check` · `pytest --cov=blueprint_qa --cov-fail-under=80`
- Never claim something works without running it (R10.4). Commit with `[A0] …`. **Do not push**; ry pushes and opens the pull requests.

## 6. Definition of done

- [ ] Phase 1 merged: CLI runs A1 → A2; the invalid picture gives exactly the required text; no numbers produced
- [ ] Phase 2 + 2b merged together: contracts v1.1.0 (fixtures, storey levels), `analysis:` config, `vision` extra; A2 green
- [ ] Phase 3 merged: `analysis.analyze()` meets `docs/requests/A3-analysis-adapter.md`
- [ ] Phase 4 merged: A2 ∥ A3 in the pipeline, contract-checked, live demo reported
- [ ] OPEN_QUESTIONS Q8/Q9, proposal 005, the G4 deviation, README and CHANGELOG recorded
