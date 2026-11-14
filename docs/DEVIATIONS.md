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
