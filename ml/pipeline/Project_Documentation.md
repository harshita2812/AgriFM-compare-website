# AgriFM Compare - Consolidated Project Documentation

**Project:** Foundation Model for Precision Agriculture: A Comparative Study
**Institution:** IILM University, Greater Noida, School of CSE
**Academic session:** 2026-27
**Document location:** `ml/pipeline/Project_Documentation.md`
**Last consolidated:** 2026-11-23

---

## 1. Project objective

AgriFM Compare is a local research dashboard for a region-controlled comparative study of foundation and supervised models in Indian precision agriculture.

The system is intended to compare:

- Prithvi-EO-2.0
- SatMAE
- CROMA
- ResNet-50 supervised baseline

The current implementation includes the application, data infrastructure, asset management, metric utilities, split utilities, and evaluation gating. It does **not** contain verified model performance results or an end-to-end inference pipeline.

No app, API, asset, or report output should be interpreted as evidence that a model works for Indian crop mapping until authorized imagery, compatible labels, exact spatial splits, and model-specific adapters have been validated.

---

## 2. Project scope

### 2.1 Implemented scope

- Next.js research dashboard.
- FastAPI application and REST API.
- SQLite database with SQLAlchemy and Alembic.
- Optional PostgreSQL support and SQLite migration tooling.
- Model, region, crop, and dataset catalogs.
- Context-only comparison runs.
- Typed provenance declarations.
- CSV export of saved comparison context.
- Open-Meteo weather ingestion and caching.
- English/Hindi farmer advisory interface and API.
- Pinned ML asset fetch plan and SHA-256 verification.
- Asset readiness and ingestion status APIs.
- Scheduled weather refresh and asset re-verification.
- Asset-gated evaluation jobs.
- Multiclass segmentation metrics.
- Deterministic leave-one-region-out and spatial-block split utilities.
- Block-bootstrap confidence intervals.
- Development and production build coverage.
- API and browser test suites.

### 2.2 Explicitly out of scope

- Satellite tile downloading through the application.
- Upload or storage of user imagery.
- Model training.
- Model inference.
- Fabricated or inferred model rankings.
- Verification of downloaded candidate labels as five-crop ground truth.
- Reporting performance scores before a complete evaluation is available.

---

## 3. Application architecture

### 3.1 Frontend

The Next.js application is located in `apps/web/app/`.

Primary pages and areas:

- Overview dashboard.
- Comparison workspace.
- Model library.
- Dataset catalog.
- Methodology and project disclaimer.
- Farmer guide.
- Saved-run and provenance displays.

The prior Vite entry point remains under `src/` for compatibility. It is not the primary Next.js application.

### 3.2 Backend

The FastAPI application is located in `apps/api/`.

Important modules:

- `apps/api/main.py`: application startup, health, scheduling, and compatibility setup.
- `apps/api/db.py`: SQLAlchemy engine and database session setup.
- `apps/api/models.py`: SQLAlchemy models.
- `apps/api/seed.py`: seed and startup migration behavior.
- `apps/api/asset_inventory.py`: asset readiness and verification.
- `apps/api/routers/catalog.py`: model, region, crop, and dataset routes.
- `apps/api/routers/data.py`: weather and data-source routes.
- `apps/api/routers/evaluations.py`: evaluation-job routes.
- `apps/api/scheduling.py`: scheduled refresh and verification tasks.

### 3.3 Database

The default database is:

```text
backend/agrifm.db
```

The database file is local and excluded from Git. SQLAlchemy 2 manages application records and Alembic manages schema migrations.

For PostgreSQL:

```text
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/agrifm
```

The repository includes a transactional SQLite-to-PostgreSQL migration script at `scripts/migrate_sqlite_to_postgres.py`.

### 3.4 ML modules

- `ml/evaluation.py`: binary and multiclass segmentation metrics and block bootstrap.
- `ml/pipeline/splits.py`: deterministic region and spatial-block splits.
- `ml/pipeline/README.md`: ML pipeline status.
- `assets.lock.json`: pinned assets and source metadata.
- `scripts/fetch_assets.py`: checksum-guarded asset fetcher.
- `requirements-ml.txt`: CPU-oriented ML environment.

---

## 4. Approved evaluation protocol

The following protocol is approved as a foundation for future evaluation.

### 4.1 Task

Six-class semantic segmentation:

1. Wheat
2. Rice
3. Cotton
4. Sugarcane
5. Maize
6. Other

### 4.2 Study regions

- Punjab
- Western Uttar Pradesh
- Maharashtra
- Rajasthan
- Tamil Nadu/Cauvery Delta

Region definitions remain subject to exact coordinate/AOI approval.

### 4.3 Split protocol

- Outer split: leave-one-region-out.
- Inner split: spatial-block cross-validation within each outer training set.
- Spatial folds: five, by default.
- Shared random seed: 42.
- Stable sample and `spatial_block_id` values are mandatory.
- Exact AOIs and block assignments remain pending.

The split utility:

- rejects unknown regions;
- rejects duplicate sample IDs;
- requires a spatial block ID for every sample;
- requires every region to contain samples;
- prevents spatial leakage across inner validation and training groups;
- serializes data canonically;
- produces a SHA-256 value for a split file.

### 4.4 Proposed metrics

- Per-class precision and recall
- Per-class IoU
- Per-class F1
- Mean IoU
- Macro-F1
- Overall accuracy
- 1,000-resample spatial-block bootstrap 95% confidence intervals
- Measured compute cost

Model ranking is not permitted unless meaningful uncertainty is supported and compatible, verified data are available.

### 4.5 Default model setup

- Frozen pretrained encoder.
- Lightweight linear/UPerNet-lite segmentation head.
- Shared preprocessing and training protocol.
- Shared seed and metric configuration.

No model-specific adapter is currently implemented or verified.

---

## 5. Data and asset status

All asset identities and pinned revisions are recorded in `assets.lock.json`.

### 5.1 Verified downloaded checkpoints

| Asset | Size | SHA-256 status | License |
|---|---:|---|---|
| Prithvi-EO-2.0-300M | 1,326,658,396 bytes | Verified | Apache-2.0 |
| SatMAE ViT-Base | 1,338,694,433 bytes | Verified | CC-BY-4.0 |
| CROMA-Base | 777,563,846 bytes | Verified | MIT |
| ResNet-50 A1 IN1K | 102,469,840 bytes | Verified | Apache-2.0 |

Verified hashes prove file identity. They do not prove that a checkpoint is suitable for a target crop task or that its reported performance has been established.

### 5.2 Verified candidate label archive

`cropharvest-labels` is downloaded and hash-verified:

- Size: 70,581,424 bytes
- SHA-256: `a37b1c9b8bb6fb5a1768cd0110e4beb0d0a8de2807e9b7d5f9c954a01ba41889`
- License: CC-BY-SA-4.0

A coarse scan found 95,186 polygons and 2,742 feature centers in a broad India bounding box. The box includes neighboring countries. The labels are binary crop presence plus generalized classes, not verified labels for Wheat, Rice, Cotton, Sugarcane, Maize, and Other.

Accordingly, CropHarvest is a candidate reference only. It is not authorized or verified ground truth for this study.

### 5.3 Blocked imagery sources

The repository records these sources as blocked or reference-only:

- Sentinel-2 L2A (Copernicus Data Space, candidate imagery source)
- Sentinel-1 GRD
- ESA WorldCover 2021
- Google Dynamic World

Sentinel catalog entries require item-level license resolution and exact study AOIs. WorldCover is a land-cover source, not independent five-crop ground truth. Dynamic World requires Earth Engine access and is model-derived.

The Western Uttar Pradesh coordinate currently needs correction to the intended study AOI.

Five approximate Sentinel-2 L2A benchmark chips are available in `ml/data/sentinel2_samples/` for public-sample exploration. They cover Punjab, Western Uttar Pradesh, Maharashtra, Karnataka, and Bihar for 2025-10-01 through 2026-04-30 and contain B02, B03, B04, and B08. These files are not approved AOIs or crop ground truth and do not activate evaluation.

### 5.4 Confirmed candidate source links

The following links were checked and returned HTTP 200 on 2026-11-23. Availability of a source does not by itself make it licensed or suitable for the study.

| Source | Verified link | Current assessment |
|---|---|---|
| Sentinel-2 L2A | [Copernicus Data Space Browser](https://dataspace.copernicus.eu/browser/) | Free account required; imagery can be searched and downloaded. USGS is not an active fallback source for this archive. Bulk API usage and download policy must be reviewed in the [Copernicus documentation](https://documentation.dataspace.copernicus.eu/Applications/Browser.html). |
| AgriFieldNet India | [Source Cooperative dataset](https://source.coop/radiantearth/agrifieldnet-competition) | Public competition imagery and labels are available without an application form. Fields include parts of Uttar Pradesh and Rajasthan. Other sources are needed for Punjab, Maharashtra, and Tamil Nadu; Cotton is not listed among the documented crop classes. License and exact archive contents require confirmation before use. |
| AgriFieldNet competition description | [Zindi competition data page](https://zindi.africa/competitions/agrifieldnet-india-challenge/data) | The documented crop classes include Wheat, Rice, Maize, Sugarcane, Mustard, Lentil, Gram, Potato, and other entries, not Cotton. It is not evidence of coverage for every required study region or class. |
| SICKLE | [WACV 2024 paper](https://openaccess.thecvf.com/content/WACV2024/html/Sani_SICKLE_A_Multi-Sensor_Satellite_Imagery_Dataset_Annotated_With_Multiple_Key_WACV_2024_paper.html) | Relevant mainly to the Cauvery Delta in Tamil Nadu and predominantly paddy-oriented work. Dataset files require author access; it is not an out-of-the-box five-region, six-class dataset. |

For this project, no single known free dataset is confirmed to cover all five regions and all six required classes:

- Wheat
- Rice
- Cotton
- Sugarcane
- Maize
- Other

The current practical data options are therefore:

1. **Reduce the study scope to available data:** use AgriFieldNet for available Uttar Pradesh/Rajasthan coverage and SICKLE for a Tamil Nadu paddy component, then state in the methodology that regions and classes are limited by open-data availability.
2. **Extend the label program:** obtain Cotton and region-specific labels for Punjab and Maharashtra from local agriculture departments, ICAR/MNCFC, or another authorized survey or annotation source.

### 5.4 Runtime

- CPU-only PyTorch environment.
- No CUDA GPU is available.
- ML dependencies are isolated in `requirements-ml.txt`.
- No model currently loads or performs inference through a tested application pipeline.

---

## 6. Implementation completed

### 6.1 Research integrity

- Removed or cleared legacy fabricated demo scores.
- All demo catalog and run records use explicit demo markings.
- Runs return null metrics unless real evaluation records exist.
- Comparison setup and saved-run operations remain context-only.
- API and UI state never claim an active winner or ranking.
- User-supplied provenance is stored separately from verified evidence.
- Provenance is labeled `declared_unverified` or `not_recorded`.
- Amber disclaimers explain that no ground-truth evaluation is available.

### 6.2 Database and migrations

Completed:

- SQLAlchemy 2 integration.
- SQLite startup migration and seeding.
- Alembic schema support.
- PostgreSQL configuration.
- SQLite-to-PostgreSQL migration utility.
- Foreign keys and indexes.
- Legacy demo-score cleanup.
- Provenance persistence and validation.

### 6.3 Weather and farmer advisory

Completed:

- Live Open-Meteo source integration.
- SQLite weather caching.
- Source, asset, and ingestion-job records.
- Scheduled daily refresh.
- Region validation and provider error tracking.
- English/Hindi farmer advisory copy.
- Planning-only disclaimers.
- Responsive weather and advisory UI.

### 6.4 Asset management

Completed:

- Pinned asset registry.
- Dry-run and download fetch modes.
- Disk-budget guard.
- SHA-256 verification.
- Asset root support through `AGRIFM_ASSET_ROOT`.
- Startup registration of fetched assets.
- Asset readiness API.
- Scheduled weekly hash re-verification.
- Missing and blocked input reporting.

### 6.5 Evaluation framework

Completed:

- Asset-gated evaluation-job persistence.
- Explicit blocked status and prerequisite explanations.
- Manifest validation for future evaluation jobs.
- Binary metric utilities.
- Multiclass metric utilities.
- Confusion matrices.
- Per-class IoU/F1.
- Mean IoU and macro-F1.
- Overall accuracy.
- Deterministic spatial-block bootstrap.
- Leave-one-region-out split generation.
- Inner spatial-block cross-validation.
- Group-leakage checks.
- Canonical split serialization and hashing.

An evaluation manifest has not been generated. No manifest is activated until task-compatible imagery and labels, exact AOIs, spatial-block assignments, and supported adapters exist.

### 6.6 SICKLE dataset reference

SICKLE is retained only as a reference dataset.

Reported repository metadata:

- Cauvery Delta, Tamil Nadu.
- January 2018-March 2021.
- 388 surveyed plots.
- 2,370 time-series samples.
- Approximately 209,000 satellite images.
- Landsat-8, Sentinel-1, and Sentinel-2 sources.
- Crop type, variety, season, and yield fields.

The repository does not distribute the full dataset directly. Dataset access is requested through the authors' access form.

SICKLE does not replace this project's required five-region, six-class evaluation data. It cannot be used as ground truth until licensed files, compatible label mappings, versions, permissions, and spatial splits are verified.

---

## 7. API summary

Key endpoint groups:

| Area | Endpoints |
|---|---|
| Health | `GET /api/health` |
| Dashboard | `GET /api/dashboard` |
| Catalogs | `GET /api/models`, `/api/regions`, `/api/datasets`, `/api/crops` |
| Runs | `GET /api/runs`, `POST /api/runs` |
| Methodology | `GET /api/methodology` |
| Weather | `GET /api/data/weather/{region_id}`, `POST /api/data/weather/refresh` |
| Data sources | `GET /api/data/sources`, `GET /api/data/readiness` |
| Farmer advisory | `GET /api/farmer/advisory` |
| Evaluations | `POST /api/evaluations/jobs`, `POST /api/evaluations/jobs/{id}/execute`, `GET /api/evaluations/jobs` |

Evaluation jobs remain blocked until manifest and asset validation succeeds.

---

## 8. Validation and quality status

### 8.1 Latest recorded validation

| Check | Recorded result |
|---|---|
| Evaluation unit tests | 6 passed |
| API integration suite | 22 passed |
| Playwright UI suite | 10 passed |
| Next.js production build | Passed |
| Python compile check | Passed |
| Git diff whitespace check | Passed |

Earlier recorded full validation also included:

- API suite: 14 passed.
- UI suite: 10 passed.
- Next.js build: passed.
- Vite compatibility build: passed.
- Production dependency audit: 0 vulnerabilities.
- Full dependency audit: 0 vulnerabilities after dependency resolution.
- VS Code Problems: no errors found.
- Personal-name scan: no named personal details found.

### 8.2 Test coverage areas

API tests cover:

- Health and catalog routes.
- Provenance validation and persistence.
- Legacy SQLite migrations.
- Live-data and weather behavior.
- Region validation.
- Evaluation-job blocking.
- Metric helper behavior.
- Invalid comparison inputs.
- CSV/export behavior.
- Upload absence.

Playwright tests cover:

- Desktop and responsive navigation.
- Comparison controls.
- Model selection.
- Saved-run restoration.
- Blocked evaluation display.
- Demo and disclaimer copy.
- CSV download.
- API error recovery.
- Farmer advisory rendering.

---

## 9. Local setup

### 9.1 Frontend and API

Requirements:

- Node.js 18+
- Python 3.10+

Install dependencies:

```powershell
npm install
python -m pip install -r requirements.txt
```

Start the API:

```powershell
uvicorn apps.api.main:app --reload
```

Start the frontend:

```powershell
npm run dev
```

Local URLs:

- Frontend: `http://localhost:3000`
- API: `http://127.0.0.1:8000`
- API documentation: `http://127.0.0.1:8000/docs`

### 9.2 Test commands

```powershell
npm run test:api
npm run test:ui
npm run build
npm run build:vite
```

For ML utilities:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_evaluation.py -v
```

### 9.3 Asset fetch

Set the asset root and inspect the plan:

```powershell
$env:AGRIFM_ASSET_ROOT = "D:\AgriFM-assets"
python scripts/fetch_assets.py --dry-run
```

Fetch one approved asset:

```powershell
python scripts/fetch_assets.py --download --only resnet50-a1-in1k
```

The fetcher does not download Sentinel imagery.

---

## 10. Remaining blockers

Before adding a candidate dataset to the manifest, verify the actual license, label schema, field/feature geometry, region coverage, acquisition dates, and mapping to the approved six classes. Do not treat a public download, a competition page, or a paper description as verification of ground truth.

The project must not claim or publish model performance until all of the following are resolved:

1. Authorized Sentinel imagery or another verified task-compatible imagery source.
2. Exact approved AOIs for all five study regions.
3. A task-compatible, licensed crop label dataset.
4. A verified mapping to Wheat, Rice, Cotton, Sugarcane, Maize, and Other.
5. Stable spatial-block assignments for every sample.
6. A final imagery/label chip manifest with source provenance.
7. Canonical train/validation/test split files and hashes.
8. A validated frozen-encoder adapter for each checkpoint.
9. A real-chip inference smoke test.
10. A complete evaluation run and independently reviewed metrics.

Until these are complete:

- All result fields remain null or unevaluated.
- Evaluation jobs remain blocked.
- Comparison runs remain context-only.
- Provenance declarations remain unverified.
- No ranking or winner is reported.

---

## 11. Current project status

| Area | Status |
|---|---|
| Application structure | Implemented |
| Next.js dashboard | Implemented |
| FastAPI API | Implemented |
| SQLite/PostgreSQL support | Implemented |
| Comparison persistence | Implemented |
| Provenance declarations | Implemented, unverified |
| Weather/live data | Implemented |
| Farmer advisory | Implemented |
| Pinned checkpoint assets | Downloaded and hash-verified |
| ML runtime foundation | CPU-only; no CUDA |
| Multiclass metrics | Implemented |
| Spatial split utilities | Implemented |
| Evaluation job framework | Implemented and gated |
| Inference adapters | Not implemented |
| Authorized task labels | Missing or not aligned |
| Exact AOIs | Missing/correction required |
| Real model evaluation | Blocked |
| Performance ranking | Not available |

---

## 12. Evidence and source documents

The consolidated document is based on the repository's implementation and these project records:

- `README.md`
- `docs/QA_LEDGER.md`
- `docs/gaps/FIX_LOG.md`
- `docs/gaps/AUDIT.md`
- `docs/gaps/AUDIT_2026-11-18.md`
- `docs/gaps/FIX_PROMPTS.md`
- `docs/gaps/FIX_PROMPTS_2026-11-18.md`
- `ml/README.md`
- `ml/pipeline/README.md`
- `assets.lock.json`
- `ml/evaluation.py`
- `ml/pipeline/splits.py`
- `tests/test_api.py`
- `tests/test_evaluation.py`
- `tests/e2e/app.spec.js`