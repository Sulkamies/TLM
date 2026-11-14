# 005: Give A3 the original upload (file passthrough)

- **Proposed by:** A3 (SS), as its "change 2" during integration planning, 2026-11-14. Recorded by A0 (session
  launched by ry) as MERGE_PLAN v3 decision D6.
- **Status:** FOR TEAM DECISION. **Not part of the current integration.** Not applied; A0 must not implement it
  unless the humans decide so.
- **Affected roles:** A0 (orchestrator, possibly contracts), A1 (what it passes on), A3 (consumer), A5 (fixtures).
- **Breaking:** depends on the option chosen (see below).

## Motivation (A3)

A3 would like the original file (the uploaded PDF, or a path to it) instead of only the normalized PNG. With it,
A3 could read vector content from a PDF, and companion files that sit next to a plan in the training data
(DXF/SVG/IFC), to get more exact geometry than raster detection gives.

## Conflicts with the current rules

1. **§6 A0:** "MUST pass A1's normalized outputs (`plan_image` or `ifc_bytes`) to A3, never the raw upload."
2. **§1.1 principle 2:** all formats produce the same `BlueprintAnalysis`, and A3 sees one normalized input per format.
   Raw-file handling would duplicate A1's format checks (magic bytes, page count, EXIF) inside A3.
3. **Real uploads have no companion files.** A user sends one file through the API; there is no folder next to it.
   A path is meaningless across a service boundary (R3.3) and with stateless components (R3.7).

## Options for the team

| Option | Change | Version |
|---|---|---|
| A. Reject | Keep the rules as they are. A3 works from `plan_image` / `ifc_bytes` only | none |
| B. Vector PDF bytes | A1 also passes the single-page PDF bytes: `ValidationResult.pdf_bytes: bytes \| None = None` (PDF only, unchanged, like `ifc_bytes`). §6 A0 is amended to allow it. No paths, no companion files | MINOR (additive, optional), A0 + 1 human, and an AGENTS.md change |
| C. Full passthrough | A3 receives `PipelineRequest.input_bytes` and the filename | Changes §6 A0 and §1.1; needs 2 of 4 humans |

A0's view: B covers the useful part (vector PDF content) without the problems in 2 and 3. A and B are both acceptable;
C is not recommended.

## Decision

_Pending (team)._
