# Historical AgriFM Compare Ready-to-Paste Fix Prompts

> Superseded by [FIX_PROMPTS_2026-11-18.md](FIX_PROMPTS_2026-11-18.md), which addresses only gaps still verified in the current tree. The prompts below correspond to the earlier pre-fix audit.

Each prompt below is self-contained and corresponds to a verified finding in [AUDIT.md](AUDIT.md). Paste one at a time, or paste all prompts in order. The prompts require evidence-based implementation and explicitly prohibit fabricated performance claims.

## GAP-01 - Restore the required project structure

```text
Bring this AgriFM Compare repository into the explicitly required structure: Next.js frontend at apps/web, FastAPI backend at apps/api, and a dedicated ml/ pipeline location. First inspect the actual repository; it currently uses Vite + React under src/ and FastAPI under backend/. Preserve existing working pages, API behavior, demo-data disclosures, no-upload/no-PII constraints, tests, and truthful Phase-II placeholders during the migration.

Do not silently remove features or invent new product requirements. Move/refactor code in a controlled way, update root scripts and README setup instructions, and ensure the documented local startup command(s) start the web app and API reliably. Keep ML components clearly separate from the API and UI. Do not add a fake ML package or report an evaluation merely to fill the ml/ directory.

Add or update tests to prove the migrated frontend and API still work. Run the relevant tests and production builds, report exact command output/counts/exit codes, and update docs/QA_LEDGER.md. If any requirement cannot be completed in this checkout, document the exact blocker rather than claiming success.
```

## GAP-02 - Implement a real evaluation pipeline

```text
Implement the missing AgriFM Compare evaluation pipeline so the application can report real, reproducible model comparisons instead of context-only runs. The current backend returns null metrics and does not download imagery, load models, perform inference, or calculate ground-truth metrics.

Before implementation, inventory only assets and credentials actually available in this repository/environment: model checkpoints, imagery, ground-truth labels, split definitions, licenses, and target compute. Never fabricate data, metrics, model outputs, or successful evaluation status. Do not use synthetic/example scores as a substitute for real measurements. Do not store user uploads or PII.

Use the supplied and authorized data/checkpoints only. Define and document the preprocessing and model adapters needed for the selected candidates; ensure a defensible held-out, geographically controlled evaluation; calculate the currently advertised metrics only from actual predictions and labels; and capture evaluation logs, failures, hardware/runtime context, and per-model status. Preserve an explicit unevaluated/blocked state until valid inputs exist. A failed or unavailable model must be reported as failed/blocked, not assigned a success-shaped placeholder.

Wire the pipeline through the FastAPI API and the comparison UI with explicit job state and surfaced errors. Keep the demo banner and prevent demo records from being mistaken for evaluated results. Add focused tests for input validation, successful evaluation with a small authorized fixture, invalid/missing assets, and model failure handling. Do not mock the model/data path being tested; mocks may be used only for external downloads. Run the relevant tests and report exact outputs and exit codes.

If the required authorized checkpoints, labels, or compute are absent, do not claim the pipeline is complete: implement only verifiable scaffolding, keep all metrics unevaluated, and report each missing prerequisite precisely.
```

## GAP-03 - Record reproducible evaluation provenance

```text
Make AgriFM Compare saved evaluations auditable and reproducible. Today a run records only region, crop, season, dataset ID, and model IDs; it does not identify the exact data/label release, evaluation split, model checkpoint revision, preprocessing/configuration, or runtime environment.

Design typed API/database fields for the provenance needed by the actual evaluation protocol. At minimum, assess and record: dataset and label source/version, acquisition or date range, spatial/temporal split identifier and method, model/checkpoint revision, preprocessing and input resolution, metric/aggregation configuration, random seed where applicable, software/code revision, and hardware/runtime details for latency. Distinguish required from not-applicable fields and validate them; do not invent defaults that appear to be measured facts.

Add a safe SQLite schema migration that preserves prior context-only runs and marks their absent provenance as unavailable. Return and display this metadata when viewing a run and include it in a documented export format. Keep no-upload/no-PII behavior. Add tests proving new provenance persists and round-trips, legacy runs remain readable without fabricated values, and invalid provenance is rejected. Update the methodology/README to define the fields and explain any remaining limitations. Run relevant tests and report exact outputs and exit codes.
```

## GAP-04 - Align research-integrity copy with actual capabilities

```text
Audit AgriFM Compare user-facing and API methodology text for claims that contradict the actual implementation. In particular, src/App.jsx currently says “Seeded performance scores exist,” while the API emits null metric values; the API methodology says F1 “is used” as a ranking metric, while no ranking is performed.

Update all affected UI, API, README, and tests so they consistently say that no performance scores or rankings are currently available, and that F1 and other metrics are proposed evaluation measures until a real validated pipeline produces them. Do not expose or imply old/fabricated values. Preserve the demo banner and “Not yet evaluated — Phase-II” behavior.

Add focused regression tests that assert the stale claims are absent and the no-evaluation status is explicit in the methodology/About UI and API response. Run the relevant tests and report exact outputs and exit codes.
```

## GAP-05 - Make dataset readiness labels truthful

```text
Correct the AgriFM Compare dataset catalog so “Ready” cannot imply that imagery is ingested or usable for model evaluation when the current application only displays metadata and has no ingestion pipeline.

Define explicit, typed status meanings such as “Metadata only,” “Reference,” and “Available for evaluation.” Only report an evaluation-ready state when the application can verify that the exact authorized data artifact and required labels are present and usable. For the current catalog-only state, change statuses and explanatory UI copy to accurately indicate metadata/reference status. Keep source/provider names and dataset claims factual; do not imply downloads or access that were not tested.

Add API and UI tests for the status semantics and for the current no-ingestion state. Update the README and QA ledger. Run relevant tests and report exact outputs and exit codes.
```
