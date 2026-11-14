# Request to A3: compare `schema_version` with `CONTRACT_VERSION`, not a literal

- **From:** A0 (session launched by ry), 2026-11-14. Cause: contract change 006 (`docs/contract-changes/006-validation-receipt.md`)
  takes the contracts from 1.1.0 to **1.2.0** (two optional fields, nothing that A3 reads).
- **Problem:** `tests/unit/analysis/test_analyzer.py` line 81 asserts `a.schema_version == "1.1.0"`, so
  `test_output_follows_the_contract[...]` (3 cases) fails on 1.2.0. A0 must not edit A3's tests (R2.1).
- **Change (one line):** `assert a.schema_version == CONTRACT_VERSION` with
  `from blueprint_qa.contracts import CONTRACT_VERSION`. No production code changes.
- **Branch:** `a3/<initials>/contract-version` from `a0/ry/validation-receipt`; PR into that branch. Check sequence green
  on your branch. A2 already uses `CONTRACT_VERSION` (phase 2b), so this keeps future MINOR bumps from breaking A3.
