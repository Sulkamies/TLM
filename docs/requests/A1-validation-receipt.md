# Request to A1: issue and verify a validation receipt (contract change 006)

- **From:** A0 (session launched by ry), 2026-11-14. Proposal: `docs/contract-changes/006-validation-receipt.md`
  (approved by ry and A0).
- **Goal (ry):** during one chat about one picture, the picture is checked by A1's LLM **only once**. Later questions
  about the same picture carry a receipt; A1 verifies it and skips `classifier.classify(...)`.
- **Branch:** `a1/<initials>/validation-receipt`, created **from `a0/ry/validation-receipt`** (it has contracts 1.2.0,
  the config section and the API pass-through). Your PR targets that branch, not `main`.

## What A0 already did (do not change)

- `PipelineRequest.validation_token: str | None = None` and `ValidationResult.validation_token: str | None = None`.
- `config/default.yaml -> validation_receipt: {ttl_s: 3600, key_env: BP_VALIDATION_RECEIPT_KEY}`. Read it with
  `load_section("validation_receipt")` (a separate section: your `validation:` settings use `extra="forbid"`).
- The server and the web page pass the token in and out. Nothing else reads it.

## What A1 implements (only in `src/blueprint_qa/validation/` and `tests/unit/validation/`)

1. **Issue.** When the result is `is_valid=True` after the LLM classification of a PNG, JPEG or PDF, set
   `validation_token` to `v1.<payload>.<signature>`:
   - `payload` = base64url (no padding) of compact JSON
     `{"h": sha256 hex of request.input_bytes, "f": verified input format, "p": verdict.provider,
       "c": classification confidence, "e": expiry as Unix seconds (now + ttl_s)}`;
   - `signature` = base64url of HMAC-SHA256(key, `"v1." + payload`).
   No receipt for invalid pictures, IFC (no LLM call there) or errors.
2. **Key.** The bytes of the environment variable named by `key_env`. If it is unset or empty, generate 32 random bytes
   once per process (receipts then stop working after a restart, which only means one more LLM check). Never log, echo
   or return the key (R3.8).
3. **Verify.** If `request.validation_token` is set, accept it only if **all** hold:
   - it parses as `v1.<payload>.<signature>` and the signature matches (`hmac.compare_digest`);
   - `h` equals the sha256 of *this* request's `input_bytes`, and `f` equals the format you detected from the bytes;
   - `e` is in the future;
   - `p` equals the provider string your classifier would report now (a model or prompt change invalidates receipts);
   - `c` is still ≥ `validation.min_confidence`.
4. **Use.** With an accepted receipt, still run the local steps (format sniffing, `normalize_raster` /
   `render_single_page`), because A3 needs `plan_image`, but **do not call the classifier**. Return
   `is_valid=True, reason=OK, confidence=c, provider="receipt:" + p, validation_token=<the same token>`.
5. **Reject quietly.** Any other token (malformed, wrong signature, other picture, expired, model changed): ignore it
   and validate normally (one LLM call), issuing a fresh receipt if valid. Never an error, never raise. Log one event
   `receipt_rejected` with a short reason code; never log the token itself.
6. **Logging.** One event `receipt_used` (or `receipt_rejected`), with `request_id` and `stage`, no token, no key.

## Tests (no network; mock classifier)

Round trip (issue, then verify skips the classifier: assert the mock classifier was called once for two requests);
tampered payload; tampered signature; another picture with a valid token; expired (inject the clock); provider changed;
key changed; key env unset (random key works within one process); IFC and invalid pictures get no receipt; receipt
path still returns `plan_image`; the existing cassettes still pass. Coverage ≥ 80 % for `validation/`. Check sequence
(MERGE_PLAN §6) green **on your branch**, except A3's three version-literal tests until A3's fix is merged into the A0
branch (`docs/requests/A3-contract-version-literal.md`).

## Acceptance (A0's validity check before opening your PR)

- Only A1 paths changed (shared docs append-only).
- Live: ask three questions about the same picture through `python -m blueprint_qa.api.server`; the log shows one LLM
  call (`llm_call`, component `validation`) for the first question and `receipt_used` for the next two.
