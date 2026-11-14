# 006: Validation receipt (`validation_token`): check a picture with the LLM only once

- **Proposed by:** A0 (session launched by ry), 2026-11-14, on ry's request ("check the picture only once per chat
  session, with one API call by A1").
- **Status:** APPROVED by ry and A0 (R4.3, MINOR) on 2026-11-14 (ry chose the "signed receipt, by the rules" option).
  **Contract part APPLIED** on branch `a0/ry/validation-receipt`; A1's implementation follows
  (`docs/requests/A1-validation-receipt.md`).
- **Affected roles:** A0 (contracts, orchestrator, API, web page), A1 (issues and verifies the receipt), A3 (one test
  literal, `docs/requests/A3-contract-version-literal.md`), UI/at (the Android app may send the receipt back).
- **Breaking:** no. Two optional fields. Version 1.1.0 → **1.2.0**.

## Motivation

In a chat, every question about the same picture runs A1 again, and A1's LLM classification costs one Gemini call and
about 1.5–2.5 s per question. The obvious fix, the server remembering validated pictures, breaks R3.7 (components are
stateless, no caching of user data across requests) and §6 A0 (the orchestrator MUST call A1 first). A signed receipt
held by the client avoids both: the server stores nothing, A1 is still called first, and A1 alone decides whether to
skip its LLM call.

## Diff

```python
# contracts/request.py
class PipelineRequest(BaseModel):
    ...
    validation_token: str | None = None   # receipt from an earlier ValidationResult; only A1 reads it

# contracts/validation.py
class ValidationResult(BaseModel):
    ...
    validation_token: str | None = None   # signed receipt issued by A1 when is_valid; opaque to others
```

`schema_version` and `CONTRACT_VERSION` → `"1.2.0"`; schemas regenerated; AGENTS.md §4.2 updated (document 1.4.0).

Outside the contracts (A0): the HTTP API returns the receipt as `AskAnswer.validation_token` and accepts it as the
optional form field `validation_token` (`docs/API.md`, additive); the web page keeps it per picture. Config:
`config/default.yaml -> validation_receipt` (`ttl_s`, `key_env`), a section of its own so A1's strict `validation:`
settings keep loading before A1 implements it. Secret: `BP_VALIDATION_RECEIPT_KEY` (`.env.example`, R3.8).

## Merge order (R4.5)

The A0 branch is safe on its own (the fields stay `None`, behaviour unchanged), but three A3 tests compare
`schema_version` with the literal `"1.1.0"`. So: A3's one-line fix and A1's implementation are merged **into**
`a0/ry/validation-receipt`, then that branch goes to `main` in one merge (as phases 2 and 2b).
