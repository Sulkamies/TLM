# A2 design: Question Interpreter that follows the plan vocabulary

- **From:** A0 (session launched by ry), 2026-11-14. Requested by ry.
- **Binding for:** the A2 session that builds `src/blueprint_qa/question/` (task #2 in `docs/TASKS.md`).
  Read together with `docs/requests/A2-question-interpreter-gemini.md` (what to build) and AGENTS.md §6 A2.
- **Why:** the Blueprint Analyzer's exact input/output is not final (see proposal 001). The interpreter must
  adapt to vocabulary changes **without code changes**, and its structure must be clear enough for an
  agent to merge branches safely.

## 1. Core idea

What a plan can contain is defined in **one place**: `blueprint_qa.contracts.vocabulary`
(`RoomType`, `EntityCategory`, `OpeningKind`, plus `DESCRIPTIONS` and `VOCABULARIES`). The interpreter
never spells these values out in code. Instead:

- its **LLM output schema** is built from the contract types (so Gemini's structured output can only
  return current values), and
- its **prompt** lists the current values and their meanings, rendered at runtime from `VOCABULARIES` and
  `DESCRIPTIONS` into placeholders of a versioned template (`Prompt.render`).

So when A0 adds a value to the vocabulary, the schema and the prompt follow automatically. Recorded
cassettes then miss loudly (their key includes the rendered prompt and the schema, see D-006), which tells A2
exactly what to re-record.

## 2. File map (fixed; one responsibility per file)

```
src/blueprint_qa/question/
├── __init__.py          exports `interpret` only (R3.6)
├── interpreter.py       ENTRY POINT. interpret(request_id, question, locale_hint) -> ParsedQuestion | ErrorEnvelope.
│                        Picks the provider, catches everything (R5.1). No parsing logic.
├── vocabulary_view.py   THE ONLY bridge to contracts.vocabulary. Renders the prompt sections
│                        (allowed values + meanings) and loads/validates synonyms YAML against VOCABULARIES.
├── llm_output.py        LlmParse: the Pydantic model Gemini must fill. Composed from contract types
│                        (Intent, Aggregation, EntityRef, ...). No request_id/provider/original_question.
├── mapping.py           Pure, deterministic: LlmParse -> ParsedQuestion. Fills code-owned fields, converts
│                        comparison thresholds to SI, checks invariants. No I/O, no LLM.
├── providers/
│   ├── base.py          QuestionProvider protocol
│   ├── llm.py           LlmQuestionProvider: render prompt -> common.llm -> mapping
│   ├── mock.py          MockQuestionProvider: canned ParsedQuestions for tests
│   └── rules.py         (optional) LocalRuleProvider: regex fast path for common templates
├── prompts/
│   └── interpret.v1.md  template with {{PLAN_VOCABULARY}}, {{SYNONYMS}}, {{EXAMPLES}} placeholders
├── synonyms/
│   ├── en.yaml  de.yaml  fi.yaml     language data only (no code)
└── __main__.py          terminal chat REPL: `python -m blueprint_qa.question`
tests/unit/question/
├── cassettes/           interpret@v1.json (recorded Gemini responses)
├── test_vocabulary_view.py  test_mapping.py  test_interpreter.py  test_synonyms.py  test_repl.py
```

Data flow: `interpret` → provider → (`vocabulary_view` → `Prompt.render` → `common.llm` → `LlmParse`) → `mapping` → `ParsedQuestion`.

## 3. Rules (binding for A2)

- **Q1 · No hard-coded vocabulary.** No room, entity or opening value (e.g. `"BEDROOM"`, `RoomType.SAUNA`) may
  appear in `question/*.py`, except in tests. Values live in contracts; language data lives in `synonyms/*.yaml`.
  A test greps for this, like `tests/unit/contracts/test_vocabulary.py` does for contracts.
- **Q2 · Schema by composition.** `LlmParse` reuses contract types (`targets: list[EntityRef]`, `intent: Intent`, ...).
  When `EntityRef` gains a field (e.g. `fixture_type` from proposal 001), the LLM schema gains it too.
- **Q3 · Prompt by rendering.** Value lists and meanings in the prompt come from `vocabulary_view`, which iterates
  `VOCABULARIES`/`DESCRIPTIONS`. The template file holds only the instructions and placeholders.
- **Q4 · Synonyms are validated data.** `synonyms/<lang>.yaml` maps vocabulary values to words. At load time,
  `vocabulary_view` rejects keys that are not in `VOCABULARIES`. A test fails if a vocabulary value has no
  entry in `en`, `de` and `fi`, which tells A2 to add words after a vocabulary change.
- **Q5 · Code computes.** The LLM returns the threshold value and its unit as written ("12 m²", "120 sq ft").
  `mapping.py` converts to SI. The LLM never does arithmetic (§1 principle 3).
- **Q6 · One provider output.** Every provider returns the same `ParsedQuestion` for the same question
  (`provider` field excepted). Shared tests run against all providers.
- **Q7 · The REPL is a client.** `__main__.py` only calls `interpret()` and prints the JSON. No logic of its own.

### Synonyms YAML format

```yaml
# synonyms/de.yaml: keys MUST be vocabulary names/values from contracts.VOCABULARIES
RoomType:
  BEDROOM: [Schlafzimmer, SZ, Kinderzimmer]
  TOILET: [WC, Gäste-WC]
EntityCategory:
  WINDOW: [Fenster]
examples:              # few-shot, rendered into {{EXAMPLES}}; also used as test cases
  - question: "Wie viele Schlafzimmer gibt es?"
    expect: {intent: COUNT, aggregation: SUM, targets: [{category: ROOM, room_type: BEDROOM}]}
```

## 4. Interfaces

```python
# vocabulary_view.py
def render_plan_vocabulary() -> str: ...                  # for {{PLAN_VOCABULARY}}
def load_synonyms(lang: str) -> Synonyms: ...             # validated against VOCABULARIES
def render_synonyms(langs: Sequence[str]) -> str: ...     # for {{SYNONYMS}}
def render_examples(langs: Sequence[str]) -> str: ...     # for {{EXAMPLES}}

# mapping.py
def to_parsed_question(llm: LlmParse, *, request_id: str, question: str,
                       provider: str) -> ParsedQuestion | ErrorEnvelope: ...

# providers/base.py
class QuestionProvider(Protocol):
    def parse(self, request_id: str, question: str,
              locale_hint: str | None) -> ParsedQuestion | ErrorEnvelope: ...
```

Use `common.llm.load_prompt(...).render(PLAN_VOCABULARY=..., SYNONYMS=..., EXAMPLES=...)`, then
`get_llm_client("question").generate_structured(..., output_model=LlmParse)`. The provider tag comes from
`LlmResult.provider` (`llm:gemini-3.8-flash:interpret@v1`).

## 5. Change playbook (for humans and the merging agent)

| Change | Files to edit (owner) | A2 code change? | Cassettes |
|---|---|---|---|
| New value in an existing vocabulary (e.g. a `RoomType`) | `contracts/vocabulary.py` + `DESCRIPTIONS` (A0, §4.3 MINOR) | **None.** Add words to `synonyms/*.yaml` (A2; test Q4 fails until done) | Re-record (misses show which) |
| Fixtures (proposal 001) | `contracts/vocabulary.py` (`FixtureType`, `"FIXTURE"`) + `EntityRef.fixture_type` + `analysis.Fixture` (A0) | **None** if Q2 is followed. Synonyms + examples (A2) | Re-record |
| Remove or rename a value | vocabulary (A0, §4.3 **MAJOR**, 2 humans) | None; synonyms YAML fails validation until updated | Re-record |
| Analyzer output changes outside the vocabulary (new fields in `BlueprintAnalysis`, other detector) | `contracts/analysis.py` (A0) + `analysis/` (A3) | **None.** A2 never sees `BlueprintAnalysis` | Unaffected |
| Prompt wording | new `prompts/interpret.v(N+1).md`, bump the version constant in `providers/llm.py` (A2) | One constant | Re-record (new file) |
| Model | `config/llm.yaml` (A0) | None | Still replay (model not in key); run `pytest -m live` |

## 6. Notes for the merging agent

- **Merge order:** contract/vocabulary branches (A0) first, then rebase component branches (A2, A3) on them.
- **Conflict surface:** each role owns disjoint paths (AGENTS.md §2), so code conflicts mean a rule was broken.
  Report them; don't resolve by editing another role's files. Shared docs (`docs/TASKS.md`, `CHANGELOG.md`,
  `OPEN_QUESTIONS.md`, ...) are append-only: keep **both** entries, ordered by date.
- **`contracts/vocabulary.py` conflicts:** keep only values from approved `docs/contract-changes/*.md` entries. Never invent values.
- **After merging, run in order:** `python -m blueprint_qa.contracts.generate_schema --check` → `ruff format --check` →
  `ruff check` → `mypy` → `pytest`. Cassette misses (`INTERNAL_ERROR`, detail `cassette miss`) mean
  "re-record with `BP_LLM_RECORD=1`". This is a task for A2, not a code fix.
