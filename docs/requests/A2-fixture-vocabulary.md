# Request to A2: adapt the Question Interpreter to contracts 1.1.0 (MERGE_PLAN phase 2b)

- **From:** A0 (integration agent, session launched by ry), 2026-11-14.
- **To:** an A2 session launched by ry.
- **Branch:** `a2/ry/fixture-vocabulary`, created **from `a0/ry/contracts-1.1`** (not from `main`). The two PRs are merged
  back to back: phase 2 first, then this one immediately after (R4.5: `main` never disagrees with the contracts).

## What changed in the contracts (1.0.1 → 1.1.0)

- `contracts/vocabulary.py`:
  - new `FixtureType` (TOILET, SINK, SHOWER, BATHTUB, SAUNA_BENCH, OTHER);
  - new `StoreyLevel` (BASEMENT, GROUND, UPPER, UPPER_1, UPPER_2, UPPER_3, ATTIC);
  - `EntityCategory` gains `"FIXTURE"`.
  
  All three have `DESCRIPTIONS` and `VOCABULARIES` entries.
- `contracts/question.py`: `EntityRef.fixture_type: FixtureType | None = None`, set iff `category == "FIXTURE"`.
  `EntityRef.storey` stays `str | None` (004 lighter option) and must hold a `StoreyLevel` value.
- `schema_version` is `"1.1.0"` on every contract.

## Why A2's tests fail on `a0/ry/contracts-1.1` (expected, 29 tests in `tests/unit/question/`)

A0 ran the full suite on that branch. Every failure is in A2's area. All other tests pass (98.37 % coverage).

| Cause | Tests |
|---|---|
| `synonyms/{en,de,fi}.yaml` have no words for `EntityCategory.FIXTURE` (and the `FixtureType` values) | `test_synonyms.py::test_every_vocabulary_value_has_words[en/de/fi]` |
| Cassettes no longer match: the prompt/schema now contain the new vocabulary, so the cassette key changes and the mock backend returns an `ErrorEnvelope` | `test_interpreter.py` (22 tests), `test_repl.py::test_repl_as_module_with_piped_questions_offline` |
| `vocabulary_view` now also finds `FixtureType → fixture_type`, and `StoreyLevel` exists in the contracts, so the interim entry is inactive | `test_vocabulary_view.py::test_question_fields_found_from_entity_ref`, `::test_interim_storey_levels_are_active_until_the_contract_has_them` |
| Hard-coded `schema_version == "1.0.1"` | `test_mapping.py::test_code_owned_fields_are_filled` (and the `"1.0.1"` literal in `test_interpreter.py`) |

## Work items

1. **Fixture synonyms and examples** in `synonyms/en.yaml`, `de.yaml`, `fi.yaml`, for `FIXTURE` and every `FixtureType`
   value, for example "toilet bowl" / "WC-Schüssel" / "wc-istuin", "sink, washbasin" / "Waschbecken" / "pesuallas,
   lavuaari", "bathtub" / "Badewanne" / "kylpyamme", "shower" / "Dusche" / "suihku", "sauna bench" / "Saunabank" /
   "lauteet". Add a few-shot example: "How many showers and bathtubs?" → `COUNT`, `SUM`, two `FIXTURE` targets
   (`SHOWER`, `BATHTUB`).
2. **Keep the TOILET room vs TOILET fixture distinction:** "How many separate WC rooms?" / "Wie viele Gäste-WCs?" /
   "Montako erillistä WC:tä?" → `ROOM` + `room_type=TOILET`; "How many toilet bowls?" / "Wie viele Toiletten
   (WC-Becken)?" / "Montako wc-istuinta?" → `FIXTURE` + `fixture_type=TOILET`. Cover both in en/de/fi tests.
3. **Enforce `fixture_type` iff `category == "FIXTURE"`** in A2's output validator (the contract documents this invariant
   but does not enforce it, see OPEN_QUESTIONS Q3).
4. **Storey levels:** delete the interim `values:` block in `question/interim_vocabulary.yaml` (keep `field: storey`),
   adapt `test_vocabulary_view.py`, and close the A2 deviation in `docs/DEVIATIONS.md` (append an update line).
5. **Version literals:** compare with `blueprint_qa.contracts.CONTRACT_VERSION` instead of `"1.0.1"`.
6. **Prompt:** if the prompt text changes, create `interpret.v2.md` (R7.7, never edit v1). Re-record **all cassettes**
   (R7.12) and run the live suite once (`pytest -m live tests/unit/question`).
7. CHANGELOG entry; the check sequence from MERGE_PLAN §6 must be fully green **on your branch**.

## Acceptance (A0's validity check before opening your PR)

- Only A2-owned paths changed (`src/blueprint_qa/question/`, `tests/unit/question/`, shared docs append-only).
- Full check sequence green: ruff format/check, mypy, schema check, `pytest --cov` ≥ 80 %.
- Live check by A0: the CLI or REPL with "How many toilet bowls are there?", "Wie viele Fenster gibt es?", "Montako
  makuuhuonetta?" and "How many showers and bathtubs?" gives the expected `ParsedQuestion`s.
