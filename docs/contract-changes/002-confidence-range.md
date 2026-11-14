# 002: Enforce confidence in [0.0, 1.0]

- **Proposed by:** A0 (session launched by ry), 2026-11-14 (from OPEN_QUESTIONS Q3)
- **Status:** APPROVED and APPLIED, 2026-11-14. Approved by A0 and human ry (R4.3: A0 + 1 human).
- **Affected roles:** every producer of a `confidence` value (A1, A2, A3, A4). A5's contract tests now catch out-of-range values.
- **Breaking:** no. Version 1.0.0 → **1.0.1** (PATCH).

## Motivation

§4.1 already requires every confidence to be a float in `[0.0, 1.0]`, but the models typed it as a bare
`float`, so values like `1.5` or `-1` passed validation. This change makes the models enforce the existing rule.

## Diff

```python
# src/blueprint_qa/contracts/common.py
+Confidence = Annotated[float, Field(ge=0.0, le=1.0)]

# every `confidence: float` in ValidationResult, ParsedQuestion, Scale, Room, Opening,
# TextAnnotation and Answer:
-    confidence: float
+    confidence: Confidence

# every top-level contract:
-    schema_version: str = "1.0.0"
+    schema_version: str = "1.0.1"
```

The JSON Schemas now carry `"minimum": 0.0, "maximum": 1.0` on each `confidence`. AGENTS.md §4.2 was updated
in the same change (document version 1.2.0 → 1.2.1), per R4.5.

## Why PATCH and not MINOR

No field, type or enum value is added, removed or renamed. The change only enforces a rule §4.1 already stated,
so any output that conformed to v1.0.0 is still valid. R4.3 doesn't cover this case explicitly, so A0 classified
it as a semver PATCH. If the team disagrees, re-label it 1.1.0 by a further change.
