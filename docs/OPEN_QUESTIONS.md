# Open questions

Append-only (R10.1). Format: number, role, initials, date, question, then any answer appended below it.

### Q1 · A0 · ry · 2026-11-14 · Status of `blueprints-starter/`
`blueprints-starter/` is a top-level directory outside the §2.1 layout. It calls the Anthropic SDK
directly (conflicts with R7.5: all LLM calls through `common/llm.py`, now Gemini). Is it (a) reference-only,
to be ported piece by piece into the owning components, or (b) to be deleted once ported? Until decided,
A0 treats it as reference-only. Ruff/mypy/pytest exclude it.

### Q2 · A0 · ry · 2026-11-14 · Gemini approval scope for images
ry approved Google Gemini for **question text** (A2). A1 MUST send every plan image to "the LLM API"
(§6 A1), and A3 may use a vision LLM. Does the approval also cover sending **plan images** to Gemini?
`docs/EXTERNAL_SERVICES.md` lists only question text until a human confirms.

### Q3 · A0 · ry · 2026-11-14 · Enforce documented invariants in the contract models?
§4.2 states invariants that the Pydantic models do not enforce, because the code mirrors the document exactly:
confidence in `[0,1]`; `Answer.value` non-null iff `ANSWERED`; `comparison` required iff `COMPARISON`;
`targets` ≥ 1 (exactly 2 for `DISTANCE`). A0 could add `Field(ge=0, le=1)` and `model_validator`s
(stricter, not shape-changing, but it changes the JSON Schema). Should this be a MINOR contract change, or
should the orchestrator check these at the boundary instead?

### Q4 · A0 · ry · 2026-11-14 · Fixture questions
See `docs/contract-changes/001-fixture-entities.md`. The CubiCasa detector finds toilets, sinks, bathtubs,
showers and sauna benches, but v1.0.0 cannot represent them. Approve, change or reject the proposal?

---
**Answers (ry, 2026-11-14, recorded by A0):**
- **Q1:** `blueprints-starter/` will be deleted and replaced by a new implementation. Nothing should be ported from it; agents can ignore it.
- **Q2:** A1 is implemented independently and decides its own LLM use. `docs/EXTERNAL_SERVICES.md` still lists only question text for Gemini; if A1 sends images to Gemini, it must get that approved and recorded there itself.
- **Q3:** Yes, confidence must be in [0, 1]. Applied as contract change 002 (v1.0.1). The other invariants (value iff ANSWERED, comparison iff COMPARISON, target counts) stay unenforced in the models for now.
- **Q4:** Pending. ry asked what proposal 001 is; A0 explained it and is awaiting a decision.
- **Q4 (update, ry, 2026-11-14):** Proposal 001 is **on hold** until the Blueprint Analyzer's output is final. Meanwhile the vocabulary was centralised (change 003) so that 001 becomes a single-module edit.

### Q5 · A2 · ry · 2026-11-14 · Storey names in `EntityRef.storey`
`EntityRef.storey` is free text, but A2 must output language-independent data. A2 currently tells the LLM to
write the storey as a short **English** phrase ("ground floor", "first floor", "basement", ...), so
"alakerta" / "Erdgeschoss" / "ground floor" give the same `ParsedQuestion`. A4 then has to match that phrase
against `Storey.name` (plan text in any language, e.g. "1. krs", "EG"). Is that the agreed convention, or
should storeys become a canonical value (e.g. a storey index or level enum) through §4.3?

### Q6 · A2 · ry · 2026-11-14 · Comparison threshold with no unit
For "Is the kitchen bigger than 10?" A2 assumes the SI unit of the measure (10 m²) and does not ask for
clarification. Confirm, or should a missing unit set `clarification_needed`?
