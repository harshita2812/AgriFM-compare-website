# Historical AgriFM Compare Gap Audit

> Superseded by the current-state audit in [AUDIT_2026-11-18.md](AUDIT_2026-11-18.md). This file records the earlier pre-fix findings and should not be read as the current project state.

Audit date: 2026-11-17

## Scope and limits

This is a read-only audit of the repository as present in this workspace. The only files created for this audit are under `docs/gaps/`.

The verified source evidence includes `README.md`, `package.json`, `backend/main.py`, `src/App.jsx`, and `docs/QA_LEDGER.md`. The project is a Vite + React frontend with a FastAPI backend. The available prior requirements explicitly describe a Next.js `apps/web`, FastAPI `apps/api`, and `ml/` project, along with a research-grade, region-controlled model comparison. The QA ledger also records that those directories were not present.

The current Master Prompt 3 message ends immediately after the heading `1. SOURCES OF TRUTH (read all before judging)`; the promised source list is not present. The original Prompt 1 details are also incomplete in the available conversation history. Therefore, this report lists only gaps supported by available explicit requirements or contradictions in current source text. It cannot certify completeness against requirements that were not supplied.

## Verified gaps

### GAP-01 — Required application/repository structure is absent

**Priority:** P0 - delivery scope

**Expected:** The available Prompt 2 requirement names Next.js `apps/web`, FastAPI `apps/api`, and an `ml/` pipeline.

**Evidence:** `README.md:64` states that the repository does not contain those paths and describes it as Vite + React with FastAPI. `package.json:7-8,15` uses Vite for development/build and dependencies. `docs/QA_LEDGER.md` records the same scope as BLOCK-01 and BLOCK-02.

**Impact:** The requested Next.js application and ML project cannot be built, wired, or tested from this checkout.

**Paste-ready fix:** See GAP-01 in [FIX_PROMPTS.md](FIX_PROMPTS.md#gap-01--restore-the-required-project-structure).

### GAP-02 — No real imagery-to-metrics evaluation path exists

**Priority:** P0 - core research capability

**Expected:** A comparative study that can evaluate candidate models on appropriate agricultural imagery and ground-truth labels before reporting model performance.

**Evidence:** `README.md:58-60` says the app does not download imagery, train/load models, perform inference, or calculate ground-truth metrics, and explicitly says no ML pipeline is included. `backend/main.py:157-171` constructs results with every metric set to `None`; `backend/main.py:253-297` saves those context-only results. The methodology endpoint says to use a held-out labeled dataset at `backend/main.py:332-335`.

**Impact:** The UI can save and display evaluation context, but it cannot produce a measured comparison or support a conclusion about which model works better.

**Paste-ready fix:** See GAP-02 in [FIX_PROMPTS.md](FIX_PROMPTS.md#gap-02--implement-a-real-evaluation-pipeline).

### GAP-03 — Saved runs do not capture enough research provenance for reproducibility

**Priority:** P1 - research validity

**Expected:** The product is described as a research-grade, region-controlled comparative study. Its methodology calls for documenting sampling, label provenance, dates, and spatial train/test separation before interpreting metrics (`src/App.jsx:328`).

**Evidence:** The `runs` table stores only ID, timestamp, region, crop, season, dataset ID, model IDs, results, and demo flag (`backend/main.py:105-109`). `RunRequest` has only region, crop, season, dataset, and model IDs (`backend/main.py:175-180`). No run fields identify the data/label release or date range, split, model checkpoint/revision, preprocessing, evaluation configuration, or runtime environment.

**Impact:** Once real evaluation is added, a saved run would not by itself identify enough inputs and settings to reproduce or audit its results.

**Paste-ready fix:** See GAP-03 in [FIX_PROMPTS.md](FIX_PROMPTS.md#gap-03--record-reproducible-evaluation-provenance).

### GAP-04 — Research-integrity copy contradicts the actual no-score behavior

**Priority:** P1 - user-facing accuracy

**Expected:** Demo values and unevaluated metrics must not be presented as real; the application and API should describe unimplemented ranking as proposed rather than active.

**Evidence:** `src/App.jsx:328` says, “Seeded performance scores exist only to make the UI and comparison workflow testable.” But `README.md:58` says no model performance scores are available, and `backend/main.py:164-168` sets all returned metric values to `None`. Separately, `backend/main.py:326` says F1 is “used here as the primary ranking metric,” while the dashboard returns no top model or score at `backend/main.py:299-319`.

**Impact:** Readers receive conflicting accounts of whether scores exist and whether F1 ranking is implemented.

**Paste-ready fix:** See GAP-04 in [FIX_PROMPTS.md](FIX_PROMPTS.md#gap-04--align-research-integrity-copy-with-actual-capabilities).

### GAP-05 — Dataset catalog labels sources “Ready” despite having no ingestion or evaluation pipeline

**Priority:** P1 - user-facing accuracy

**Expected:** Dataset availability labels should accurately describe what is usable in the application.

**Evidence:** `backend/main.py:74,76` marks Sentinel-2 and Sentinel-1 + Sentinel-2 as `Ready`. `src/App.jsx:313` renders the status value directly in the dataset table. `README.md:58` says imagery is not downloaded and the catalog is descriptive only, not an ingestion pipeline.

**Impact:** “Ready” can reasonably be read as available for an evaluation, although the app only stores catalog metadata and cannot retrieve or process those sources.

**Paste-ready fix:** See GAP-05 in [FIX_PROMPTS.md](FIX_PROMPTS.md#gap-05--make-dataset-readiness-labels-truthful).

## Unverified - not counted as gaps

- The rest of the Prompt 3 source-of-truth list is absent, so requirements beyond the text available in this conversation cannot be checked.
- The complete Prompt 1 page/API/chart requirements are not present in the available history; their completeness is not asserted.
- No authorized model checkpoints, agricultural ground-truth labels, or ingestion credentials are listed in the repository inventory. Their availability, licensing, and ability to run on the target hardware were not verified.
- The exact scientifically appropriate classes, spatial and temporal split design, aggregation protocol, thresholding, and per-model adaptation procedures are not specified in the available requirements. This audit does not prescribe them as facts.
- Model-card parameter counts and descriptive model claims were not independently checked against primary sources.

## Fix prompt index

| Gap | Paste-ready prompt |
|---|---|
| GAP-01 | [Restore required project structure](FIX_PROMPTS.md#gap-01--restore-the-required-project-structure) |
| GAP-02 | [Implement a real evaluation pipeline](FIX_PROMPTS.md#gap-02--implement-a-real-evaluation-pipeline) |
| GAP-03 | [Record reproducible evaluation provenance](FIX_PROMPTS.md#gap-03--record-reproducible-evaluation-provenance) |
| GAP-04 | [Align integrity copy with actual capabilities](FIX_PROMPTS.md#gap-04--align-research-integrity-copy-with-actual-capabilities) |
| GAP-05 | [Make dataset readiness labels truthful](FIX_PROMPTS.md#gap-05--make-dataset-readiness-labels-truthful) |
