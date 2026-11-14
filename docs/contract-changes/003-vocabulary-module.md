# 003: Plan-element vocabulary in one module

- **Proposed by:** A0 (session launched by ry), 2026-11-14
- **Status:** APPROVED and APPLIED, 2026-11-14. Approved by A0 and human ry (R4.3).
- **Affected roles:** A2 and A3 (import vocabulary from one place). A4 and A5 unaffected.
- **Breaking:** no. **Version unchanged (1.0.1):** the generated JSON Schemas are byte-identical, checked with
  `generate_schema --check`, and every old import path still works (`contracts.analysis.RoomType`).

## Motivation

The Blueprint Analyzer's output is not final (proposal 001 is on hold). Its vocabulary was spread over
`analysis.py` (`RoomType`, `Opening.kind`) and `question.py` (`EntityRef.category`), so a change meant touching
several files and A2's prompt by hand. Now one module defines every plan-element value and its meaning, and
A2 renders its prompt and LLM schema from it (`docs/requests/A2-question-interpreter-design.md`).

## Diff (summary)

- New `contracts/vocabulary.py`: `RoomType` (moved), `EntityCategory`, `OpeningKind` (named Literal aliases),
  `DESCRIPTIONS` (value → meaning) and `VOCABULARIES` (name → values).
- `analysis.py`: imports and re-exports `RoomType`; `Opening.kind: OpeningKind`.
- `question.py`: `EntityRef.category: EntityCategory`.
- `tests/unit/contracts/test_vocabulary.py`: 1:1 description coverage, and no plan values outside `vocabulary.py`.
- AGENTS.md §4.2 updated (document 1.2.1 → 1.2.2).

Proposal 001, once approved, becomes edits to `vocabulary.py` plus the `Fixture` model and `EntityRef.fixture_type`.
