# Request to A0: add fixed storey levels to the contracts

- **From:** A2 (session launched by ry), 2026-11-14
- **Requested by human:** ry (OPEN_QUESTIONS Q5: "For now, create fixed values.")
- **Proposal:** `docs/contract-changes/004-storey-levels.md`. It gives the exact diff, the semantics for A4,
  and two approval options: MAJOR (type change, 2 humans) or MINOR (documented convention, 1 human).

## What A0 needs to do

1. Get the approval that matches the chosen option (R4.3).
2. Apply 004: add `StoreyLevel` and its `DESCRIPTIONS` entry in `vocabulary.py`, `EntityRef.storey`
   (if the MAJOR option is chosen), and `Storey.level`. Regenerate the schemas and update AGENTS.md §4.2.
3. Tell A3 to fill `Storey.level`, and A4 to match storeys by level.

## What A2 has done meanwhile

The values are in `src/blueprint_qa/question/interim_vocabulary.yaml`, and A2 emits nothing else.
No A2 code change is needed when 004 lands. A2 will delete the interim entry and re-record its cassettes.

## Update (A2 · ry · 2026-11-14)

ry chose the **lighter option**: apply parts 1 and 3 of proposal 004 only. `EntityRef.storey` stays `str | None`;
document in AGENTS.md §4.2 that it holds a `StoreyLevel` value. A2 is ready for this: once `StoreyLevel` is in
`contracts.VOCABULARIES`, A2 uses the contract values with no code change (unit test
`test_lighter_option_contract_values_win_and_are_still_enforced`). Afterwards A2 deletes the `values:` block in
`question/interim_vocabulary.yaml` and re-records its cassettes if the descriptions changed.
