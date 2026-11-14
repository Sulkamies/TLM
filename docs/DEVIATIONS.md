# Deviations

Append-only. When a human instruction overrides a rule in AGENTS.md, the agent records it here: date, role,
human, rule, what was done instead, and why.

_No deviations recorded._

### 2026-11-14 · A2 · ry · Interim storey vocabulary outside the contracts
- **Rule:** design rule Q1 and the fixed file map in `docs/requests/A2-question-interpreter-design.md` (plan values live
  only in `contracts.vocabulary`), together with R4.1 (only A0 edits contracts).
- **Instruction:** ry, answering OPEN_QUESTIONS Q5: "For now, create fixed values" for storeys.
- **Done instead:** A2 added `src/blueprint_qa/question/interim_vocabulary.yaml` with seven `StoreyLevel` values, in the
  same shape as `VOCABULARIES`/`DESCRIPTIONS`. `vocabulary_view.py` renders and validates them like contract
  vocabulary. Still no values are spelled out in `question/*.py`; the Q1 test now covers the interim values too.
- **Why / exit:** contracts cannot change until A0 applies proposal 004. The interim entry is ignored automatically
  once `StoreyLevel` exists in `contracts.VOCABULARIES`, and A2 then deletes it.
- **Update (A2 · ry · 2026-11-14):** ry chose the lighter option of 004 (`EntityRef.storey` stays `str`). The exit
  condition changes: once `StoreyLevel` is in the contracts, A2 deletes only the `values:` block. The `field: storey`
  link stays, so A2 keeps enforcing the convention. The deviation then ends, because the values live in the contracts.

### 2026-11-14 · A0 · ry · No `--debug-overlay` for A3 in this integration
- **Rule:** §6 A3: "MUST provide a `--debug-overlay` CLI that draws the detections on the image (raster) or a 2D plan (IFC)."
- **Instruction:** ry, MERGE_PLAN v3 decision D5: visualisation is not part of this integration.
- **Done instead:** the A3 adapter brief (`docs/requests/A3-analysis-adapter.md`) does not require the overlay, and the
  A0 validity check in phase 3 does not review it. If A3 already has one, it may stay.
- **Why / exit:** focus the integration on a working A1 → A2 ∥ A3 pipeline. The deviation ends when A3 adds the overlay
  in a later task, or the rule is changed through §4.3.
- **Update (A2 · ry · 2026-11-14, phase 2b):** contracts 1.1.0 define `StoreyLevel`. A2 deleted the `values:` block in
  `interim_vocabulary.yaml` (only `field: storey` remains); the values and meanings now come from
  `contracts.VOCABULARIES`/`DESCRIPTIONS`. **This deviation is closed.**

### 2026-11-14 · A2 · ry · New data file `question/field_rules.yaml` outside the fixed file map
- **Rule:** the fixed file map in `docs/requests/A2-question-interpreter-design.md` §2, together with design rule Q1
  (no vocabulary values such as `"FIXTURE"` in `question/*.py`).
- **Instruction:** ry, when asked where to put the rule "`EntityRef.fixture_type` is set iff `category == "FIXTURE"`"
  (request `A2-fixture-vocabulary.md`, item 3): "New field_rules.yaml".
- **Done instead:** A2 added `src/blueprint_qa/question/field_rules.yaml` (`fixture_type: FIXTURE`).
  `vocabulary_view.category_fields()` loads it and validates it against `EntityRef` and its `category` type;
  `LlmParse` enforces the rule in both directions, so a violation makes the wrapper re-ask the LLM (R7.8).
- **Why / exit:** Q1 forbids the value in code, and the contract documents the rule without enforcing it (OPEN_QUESTIONS
  Q3). The file stays until the contract models enforce the rule themselves; then A2 deletes the file and the check.

### 2026-11-14 · UI · at · New top-level directory `android-app/` and a branch without a role prefix
- **Rule:** R2.4 (no new top-level directory without approval from A0 and one human) and §9 (branch name
  `<role>/<initials>/<description>`; no role owns a user interface).
- **Instruction:** at (the human who launched this session), who asked for the Android user interface to be pushed to a new
  branch of this repository.
- **Done instead:** branch `ui/at/webpage` adds `android-app/` (Kotlin + Jetpack Compose) and this entry. Nothing under
  `src/`, `config/`, `tests/` or `blueprints-starter/` is touched. The app contains no recognition code: it runs in demo mode
  until a server address is set, then calls `POST /ask` (see `android-app/README.md`).
- **Why / exit:** the UI is a separate Android project that does not fit the Python `src` layout. It needs A0 plus one human
  to approve the directory (R2.4) before merging to `main`; the pull request must not be merged without that approval.
- **Update (UI · at · 2026-11-14):** the same branch also adds `web-app/`, a static web page (`index.html`, no build,
  no recognition code) with three CubiCasa sample plans credited in `web-app/samples/LICENSE.md`. Same reasoning and
  same exit as above: R2.4 approval (A0 + one human) is needed before merging to `main`.
