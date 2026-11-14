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
