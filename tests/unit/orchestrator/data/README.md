# Orchestrator test data (A0)

`*.analysis.json`: `BlueprintAnalysis` snapshots produced by A3's adapter (`analysis.analyze`, `cubicasa-yolo11m-v2+rules-v2`)
from the recorded detector outputs in `tests/unit/analysis/data/` (derived from CubiCasa5K, licence CC BY-NC-SA 4.0).
`request_id` is the fixed test id. Used as the A3 stage output in the phase 4/5 pipeline tests, so they do not depend on
A3's internals. Regenerate when the analysis contract or A3's mapping changes.
