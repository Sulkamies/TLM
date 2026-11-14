# Integration plan v3: A0 + A1 + A2 + A3

- **Written by:** A0 (session launched by ry), 2026-11-14. **Supersedes v1 and v2** (see git history).
- **Binding for:** the A0 session that performs the integration ("integration agent"). Follow it phase by phase.
  If a step cannot be done as written, stop and ask ry. Do not improvise around this plan.
- **A4 is out of scope** (not implemented). The pipeline ends at a marked A4 slot and returns interim answers without numbers.
- **Baseline:** `main` at `c8e8127`. Verified 2026-11-14: all checks pass, 278 tests.

---

## 1. Decisions already made (ry, 2026-11-14)

| # | Decision |
|---|---|
| D1 | **Architecture = AGENTS.md as written.** A3 is question-agnostic (`analyze(ValidationResult) -> BlueprintAnalysis`), A2 and A3 run concurrently, A4 (later) computes the answer. ry approved (D-010). |
| D2 | **Contract change 001, fixtures, revision 2: APPROVED** by ry and A0. **004, storey levels, lighter option: APPROVED** by ry and A0. Apply both in phase 2 → contracts **1.1.0**. |
| D3 | **A3 writes its own adapter** (R2.1 stays intact). The integration agent determines A3's real output format and writes the exact mapping spec; the A3 session implements it. |
| D4 | **The integration agent opens the pull requests**, for its own branches and, after its validity check, for A2's and A3's branches. It **never merges** (a teammate other than the launcher approves and merges, §9) and never pushes to `main`. |
| D5 | **Visualisation (`--debug-overlay`) is not part of this integration** (ry). Record it as a deviation from §6 A3 in `docs/DEVIATIONS.md`. |
| D6 | **A3's "original file passthrough" idea is not part of this integration.** It conflicts with §6 A0 (never pass the raw upload to A3) and needs a team decision: record it as proposal **005**. |

## 2. Where A3's code really is

**Nothing from A3 has been merged.** The `blueprints-starter/` folder on `main` is the old prototype and is **not**
A3's current code. A3's current code is only on branch **`origin/a3/SS/cubicasa-detector`** (based on the very first
commit; latest commit `35597e2`, "CubiCasa counting rules + tuned settings (v2: 84.5% test)"). Its relevant files:
`blueprints-starter/vision/analyze.py` (detector + OCR), `blueprints-starter/handlers/raster_count.py` (counting rules),
`blueprints-starter/handlers/raster.py` (room codes), `blueprints-starter/eval/thresholds_vision_v2.json`
(tuned thresholds and strategies), `blueprints-starter/eval/cubicasa_check.py`.

Read them with `git show origin/a3/SS/cubicasa-detector:<path>`. **Do not check out, merge, rebase or modify that branch.**
The A3 output format is **not known for certain**. Determining it is phase 0.

## 3. Pull requests

- Before the first push, check `gh --version` and `gh auth status`. If `gh` is missing or not logged in, ask ry to run
  `! winget install --id GitHub.cli` and then `! gh auth login` (interactive). Never handle the GitHub token yourself.
- One PR per phase, base `main`, created with `gh pr create`. Title `[A0] …` (or the owning role's prefix for A2/A3
  branches). Body: what changed, how it was verified (the check sequence output and the live demo), open questions,
  "Merge with: Create a merge commit", and which PRs it must be merged together with or after.
- Push only your own branch (`git push -u origin <branch>`). After creating a PR, give ry its URL and stop for that
  phase until it is merged, unless the next phase does not depend on it.

## 4. Phases

### Phase 0: analyse A3 and publish the spec (integration agent)

Branch: `a0/ry/integration-a1-a2` (it already holds this plan and the task claim; v1 steps 1 and 3 are done).

1. `git fetch`. Check that `origin/main` is still `c8e8127`; if not, report what changed before continuing.
2. **Analyse A3's real output** from the branch files in §2: the exact JSON produced by `Vision.analyze()` (fields,
   types, coordinate conventions, class names) and what each counting rule/strategy in `raster_count.py` and
   `thresholds_vision_v2.json` selects. If the code can be run without weights (e.g. on recorded/cached output), do so
   and use real output. If it cannot, say so, and base the spec on reading the code. **Mark every point as verified
   (ran/read) or assumed.** Compare with A3's own description in `docs/requests/A3-analysis-adapter.md` and list any differences.
3. **Write the mapping spec**: append a section "Verified mapping spec (phase 0)" to
   `docs/requests/A3-analysis-adapter.md`, field by field from detector output to `BlueprintAnalysis` v1.1.0 (rooms,
   openings, fixtures, storeys incl. `Storey.level`, texts, scale, warnings, IDs, confidences, thresholds from config).
   Where A3's code has no equivalent for a contract field, say what A3 must emit (usually `None`/`[]` + a warning).
4. Record D1–D6: append OPEN_QUESTIONS Q8 (architecture: answered by ry, D1), add proposal
   `docs/contract-changes/005-original-file.md` (status: for team decision), and add the D5 deviation entry.
5. Run the check sequence (§6), commit, push, and open **PR "[A0] Integration plan v3 and A3 adapter spec"** (docs only).
   It is mergeable at once, so SS can read the spec from `main`. Tell ry to send SS the link.

### Phase 1: orchestrator and CLI for A1 → A2 (integration agent)

Branch: `a0/ry/orchestrator` from `a0/ry/integration-a1-a2` (or from `main` once phase 0 is merged).

- `orchestrator/pipeline.py :: run(request) -> Answer | ErrorEnvelope`: A1 first; on `is_valid=False` return the
  interim answer with exactly **"This picture is invalid for our program"** and do **not** call A2 (R5.2); otherwise A2.
- Contract-check every component output (on a violation: `INVALID_INPUT` with `details.producer`), check that
  `request_id` comes back unchanged, never let an exception escape (R5.1), log one event per stage, never produce a number.
- Interim answers (fixed texts in one module-level mapping): A1 invalid → `CANNOT_ANSWER` + the invalid text
  (`language="en"`); A2 `UNSUPPORTED` → `UNSUPPORTED_QUESTION`; `clarification_needed` → `NEEDS_CLARIFICATION` with
  A2's text; otherwise `CANNOT_ANSWER`, "Plan analysis is not available yet.". `unit="count"` as a placeholder;
  record the gap as OPEN_QUESTIONS Q9 (`Answer.unit` when `value` is None).
- An ordered list of stage steps with **a marked A3 slot (concurrent with A2) and an A4 slot**, both empty for now.
- CLI `python -m blueprint_qa.api <file> "<question>" [--format] [--locale] [--json] [--debug]`. `--json` hides
  `details`; `--debug` prints the stage outputs (no image bytes) to stderr.
- Tests in `tests/unit/orchestrator/` and `tests/unit/api/` with fakes for A1 and A2; coverage ≥ 80 %. Live demo:
  `tests/unit/validation/data/house_plan_fi.png` asked in fi/en/de (the same `ParsedQuestion` in `--debug`);
  `bar_chart.png` → exactly the invalid text, with no A2 call; `prompt_injection.png` → safe.
- README (how to run the CLI) and CHANGELOG. Check sequence, commit, push, **open the PR**.

### Phase 2: contracts 1.1.0, config and dependencies (integration agent)

Branch: `a0/ry/contracts-1.1` from `main`. It can run in parallel with phase 1 (different files).

1. Apply **001 revision 2** and **004 (lighter option)** exactly as written in their proposals: `vocabulary.py`
   (`FixtureType`, `StoreyLevel`, `"FIXTURE"`, `DESCRIPTIONS`), `analysis.py` (`Fixture`, `BlueprintAnalysis.fixtures`,
   `Storey.level`), `question.py` (`EntityRef.fixture_type`). `schema_version` "1.1.0", `CONTRACT_VERSION`, regenerated
   schemas, AGENTS.md §4.2 (+ the note that `EntityRef.storey` holds a `StoreyLevel` value), tests. Mark 001 and 004 as APPLIED.
2. `config/default.yaml → analysis:` with the thresholds and strategies found in phase 0 (from
   `thresholds_vision_v2.json`) and the detector options (`conf`, `imgsz`, weights path / env var name).
3. `pyproject.toml`: optional extra `vision` (torch, ultralytics, easyocr; minor-range pins, R3.4). CI must not install it.
4. Write `docs/requests/A2-fixture-vocabulary.md` (phase 2b work items).
5. Check sequence. Note: A2's own tests **fail on this branch on purpose** (missing fixture synonyms, stale cassettes).
   That is expected. Push and **open the PR as a draft**, marked "merge together with the A2 PR from phase 2b" (R4.5).

### Phase 2b: A2 adapts to 1.1.0 (A2 session, launched by ry)

Branch: `a2/ry/fixture-vocabulary` from `a0/ry/contracts-1.1`. Work items (from the request): en/de/fi synonyms and
examples for `FixtureType` ("toilet bowl" / "WC-Schüssel" / "wc-istuin"; "How many showers and bathtubs?" → `COUNT`,
`SUM`, two `FIXTURE` targets), keeping the TOILET **room** vs TOILET **fixture** distinction; delete the interim storey
`values:` block and close the deviation; re-record the cassettes.
**Integration agent:** run the validity check on that branch (ownership, check sequence, live test), then open its
PR stacked on the phase 2 PR, mark the phase 2 PR ready, and tell ry to merge **phase 2 first, then 2b immediately after**.

### Phase 3: A3 implements the adapter (A3 session, SS)

SS implements `analysis.analyze()` on `a3/SS/analysis-adapter` (from `main` after phase 2+2b is merged), following
`docs/requests/A3-analysis-adapter.md` including the phase 0 spec. The old branch `a3/SS/cubicasa-detector` stays
unmerged as an archive.
**Integration agent:** when SS reports the branch is ready, run the validity check against the brief's acceptance
criteria (ownership, entry point, never raises, vocabulary only from contracts, lazy heavy imports, CI green without
weights, spec followed). If anything fails, write `docs/requests/A3-<title>.md` with the findings and do not open the PR.
If everything passes, **open the PR** (title `[A3] …`, noting it was validated by A0).

### Phase 4: A2 ∥ A3 in the pipeline (integration agent)

Branch: `a0/ry/integration-a3` from `main` after phases 1 and 3 are merged.
- Fill the A3 slot: after A1 says valid, run **A2 and A3 concurrently**, passing A3 the `ValidationResult`
  (never the raw upload). Contract-check both. An A3 `ErrorEnvelope` is returned (user-safe) even if A2 succeeded.
  The A4 slot stays empty. `--debug` adds a `BlueprintAnalysis` summary (JSON, no image bytes).
- Tests with fakes. Live demo on ry's machine with the real weights (`models/fetch.py`): a CubiCasa plan with
  "Montako makuuhuonetta?", "How many toilet bowls are there?", "Wie viele Fenster gibt es?". Report the outputs per
  stage and the timings.
- Check sequence, commit, push, **open the PR**.

## 5. Rules for the integration agent

- Write only in A0 paths: `orchestrator/`, `api/`, `common/`, `contracts/`, `config/`,
  `tests/unit/{orchestrator,api,common,contracts}/`, `pyproject.toml`, `.github/`, A0 docs. Shared docs are append-only.
- Never edit `validation/`, `question/`, `analysis/` or `models/`, and never touch `blueprints-starter/` or any A3 branch.
  Use `docs/requests/<role>-<title>.md`.
- Apply only the contract changes approved in §1. Never implement proposal 005.
- Never print or log `GEMINI_API_KEY` or a GitHub token. Never commit model weights.
- Never merge a PR, never push to `main`, never force-push a branch someone else has pushed.
- Never claim something works without running it (R10.4). Commit messages `[A0] …`.

## 6. Check sequence (before every commit that changes code)

```
ruff format --check src tests
ruff check src tests
python -m mypy
python -m blueprint_qa.contracts.generate_schema --check
pytest --cov=blueprint_qa --cov-fail-under=80
```

## 7. Definition of done

- [ ] Phase 0 PR: plan v3 + verified A3 mapping spec; Q8, proposal 005 and the D5 deviation recorded
- [ ] Phase 1 PR: CLI runs A1 → A2; the invalid picture gives exactly the required text; no numbers
- [ ] Phase 2 + 2b PRs: contracts 1.1.0, `analysis:` config, `vision` extra; A2 green; merged back to back
- [ ] Phase 3 PR: A3 adapter validated against the brief
- [ ] Phase 4 PR: A2 ∥ A3 in the pipeline, live demo reported
- [ ] Every PR has the check results in its description; ry has the URLs

---

## Update v3.1 (A0 · ry · 2026-11-14): A4 in scope, actual merge order

- **Done:** phase 0 (PR #5), phase 1 (PR #7), phase 2 + 2b (PR #6 with #8 merged into it first: `main` requires green CI,
  so 2b was merged into the phase 2 branch and the combination merged into `main` once).
- **Phase 3:** the A3 session is launched by SS on `a3/SS/analysis-adapter`, with the addendum in the A3 spec §I.
- **A4 is in scope (D-011).** New **phase 3b:** an A4 session launched by ry builds `reasoning.answer()` on
  `a4/ry/answer-reasoner` from `docs/requests/A4-answer-reasoner.md`, in parallel with phase 3. The integration agent
  runs the validity check against that brief and prepares the PR (as for A3).
- **Phase 4** is unchanged (A2 ∥ A3 in the pipeline).
- **New phase 5:** fill the A4 slot in `orchestrator/pipeline.py` (`answer(question, analysis)` after A2 ∥ A3, contract
  check, the interim texts are kept only for the stages that stop early) and show the number in the CLI. Live demo: the
  phase 4 questions now return numbers. Precondition: phases 3b and 4 merged.
- **Status (A0 · ry · 2026-11-14, later):** phase 3 merged (PR #10, A3 adapter; PR #12, weights hosted as GitHub
  Release `models-cubicasa-v2`) and phase 3b merged (PR #9, A4). Both were validated by A0 before their PRs. Next:
  phases 4 and 5 (A2 ∥ A3, then A4, in the orchestrator).
- **Phases 4 and 5 (A0 · ry · 2026-11-14):** done together on `a0/ry/integration-a3-a4` (one PR, ry agreed). Live demo
  with the real model on the three CubiCasa plans: 27/27 answers equal A3's tuned counts (see CHANGELOG).
