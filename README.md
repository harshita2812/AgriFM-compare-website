# AgriFM Compare

**Which foundation model actually works for Indian precision agriculture? A region-controlled comparative study.**

A local research-dashboard prototype for the B.Tech Major Project **“Foundation Model for Precision Agriculture: A Comparative Study”** at IILM University, Greater Noida, School of CSE, Session 2026–27. Personal names are intentionally omitted from the application and its saved data.

## Run locally

Requirements: Node.js 18+ and Python 3.10+.

In the project root, install frontend packages once:

```powershell
npm install
```

In one terminal, create/activate a virtual environment as desired, install Python dependencies, and start the FastAPI service from the repository root:

```powershell
python -m pip install -r requirements.txt
uvicorn apps.api.main:app --reload
```

In a second terminal:

```powershell
npm run dev
```

Run the API integration suite from the repository root:

```powershell
npm run test:api
```

The UI suite uses Playwright Chromium against the running local app. Install its browser once, then start both services before running it:

```powershell
npx playwright install chromium
npm run test:ui
```

Open the Next.js URL (normally `http://localhost:3000`). FastAPI docs are available at `http://127.0.0.1:8000/docs`; API health check: `/api/health`. The Next.js development server proxies `/api/*` to FastAPI at `http://127.0.0.1:8000`; set `AGRIFM_API_ORIGIN` to override that origin. SQLite is created and seeded at `backend/agrifm.db` on first API startup. The database file is excluded from Git. Copy `.env.example` to `.env` to configure the D: drive asset root; the database remains SQLite by default.

The Next.js application is in `apps/web/app/`; FastAPI startup is in `apps/api/main.py`, its SQLAlchemy schema and connection layer are in `apps/api/models.py` and `apps/api/db.py`, and route groups are in `apps/api/routers/`. The prior Vite entry point remains available through `npm run dev:vite` and `npm run build:vite` for compatibility.

### Database

The default database is SQLite at `backend/agrifm.db`; the API creates, migrates, and seeds it on startup. SQLAlchemy 2 and Alembic manage the schema, and the same API continues to work with SQLite. The database file is local and excluded from Git. Edit `DATABASE_URL` in `.env` only if you want a non-default database URL.

For PostgreSQL 16, install and initialize PostgreSQL separately, create an `agrifm` database, and set this value in `.env`:

```text
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/agrifm
```

Apply the schema with `python -m alembic upgrade head`. To copy the existing local SQLite records, set the PostgreSQL URL in `.env` and run `python scripts/migrate_sqlite_to_postgres.py`. The migration is transactional, safe to rerun, checks each table's row count, and leaves `backend/agrifm.db` untouched. Do not use the example credentials as real credentials.

### ML assets (Phase II)

The optional CPU-compatible ML environment is defined in `requirements-ml.txt`. In Python 3.12, install it into the project virtual environment with `python -m pip install -r requirements-ml.txt`. This does not install GPU/CUDA packages.

Asset URLs, pinned revisions, licenses, source checksums, and planned destinations are recorded in `assets.lock.json`. The CPU ML dependencies use several gigabytes on this laptop, so keep the model/data files on the larger D: drive. Review the complete plan and disk budget before downloading:

```powershell
$env:AGRIFM_ASSET_ROOT = "D:\AgriFM-assets"
python scripts/fetch_assets.py --dry-run
```

The complete checkpoint-and-label plan was 3,615,967,939 bytes (3.37 GiB). The approved assets are now stored on D: and all five files passed SHA-256 verification; no checkpoint is copied into Git. The fetcher remains dry-run by default, enforces an 80%-of-free-disk guard, and registers future downloads as ingestion jobs. To fetch a later planned asset, review the dry run and then use `--download`, optionally with `--only`:

```powershell
python scripts/fetch_assets.py --download --only resnet50-a1-in1k
```

The locked CropHarvest labels are only a candidate: a streaming scan found 95,186 polygons and 2,742 feature centers in a coarse India bounding box, but that box includes neighboring countries. Its labels are binary plus generalized classes, not verified labels for the five study crops; exact regional overlap needs defined AOIs. Sentinel catalog entries currently declare a proprietary license and the Western-UP AOI needs correction, so no imagery is planned for download. WorldCover is land-cover reference data, not five-crop ground truth; Dynamic World requires Earth Engine access and is model-derived.

When `AGRIFM_ASSET_ROOT` is configured, API startup registers fetched files in `data_sources`, `data_assets`, and `ingestion_jobs`. `GET /api/data/readiness` reports hash-verified checkpoints and missing/blocked inputs for each model, region, and crop; the Overview page displays the same status. APScheduler refreshes weather daily and re-verifies asset hashes weekly. An evaluation manifest is intentionally not activated until the task, labels, AOIs, and split protocol are approved; evaluation remains blocked.

## What works

- Overview dashboard with summary metrics, latest-run chart, and saved comparison history.
- Comparison workspace with model selection, region, crop, season, and imagery-source controls. Comparison setups are persisted in SQLite and exportable as CSV; no inference is run.
- Model registry for Prithvi-EO-2.0, SatMAE, CROMA, and a ResNet-50 supervised baseline.
- Dataset catalog and study methodology pages.
- FastAPI endpoints for dashboard data, model/region/dataset catalogs, runs, crops, and methodology.
- Responsive layouts for desktop and mobile, served by Next.js.
- Public Open-Meteo weather refresh for the five study regions, with cached SQLite assets and ingestion job status.
- Bilingual farmer advisory API with explicit planning-only and certified-advice disclaimers.
- Asset-gated evaluation-job APIs and metric helpers that keep real inference blocked until authorized inputs and a supported backend exist.

## Data and scope decisions

This repository starts from a UI/product brief that did not include a complete list of model candidates, datasets, or evaluation protocol. The app uses four representative models, five Indian study regions, five crops, and a small source catalog as sensible starter defaults. They can be changed in `backend/main.py`.

**No model performance scores are available.** Model/result records and catalog entries are explicitly marked `is_demo: true`, and the UI displays an amber demo-data banner. Empty metric cells show “Not yet evaluated — Phase-II”. Comparison runs save context only; they do not generate or imply model rankings. Each run reports evaluation status `blocked` and an explanation of the missing prerequisites.

Runs can optionally store typed provenance declarations (such as dataset/label versions, acquisition dates, split details, model revisions, preprocessing, metric configuration, code revision, and runtime). These are user-supplied declarations, not independently verified evidence; the UI and CSV label them `declared_unverified`. Runs without declarations report `not_recorded`. Because no inference pipeline is connected, provenance cannot currently be verified against an actual evaluation.

The app does not download satellite imagery, store uploads, train models, perform inference, or calculate metrics from ground-truth labels. The standalone fetcher handles only pinned checkpoints and the CropHarvest label archive. Dataset catalog status is based on actual file and checksum verification; a downloaded candidate label file is not thereby considered suitable ground truth.

The app compares 2–4 candidate models under the same selected region and crop context, but no ML pipeline is included in this repository. Add a documented, held-out evaluation pipeline before reporting performance results.

## QA scope

The delivered web application is Next.js in `apps/web/`; the FastAPI service is in `apps/api/`. The `ml/` directory documents, but does not implement, the blocked evaluation pipeline. No authorized model checkpoints, ground-truth agricultural labels, documented split protocol, or supported ML runtime are included in this repository. Do not report performance results until those inputs and a documented evaluation protocol are provided.

The API tests start an isolated temporary SQLite database and exercise real HTTP routes, including provenance validation/persistence and migrations of the former demo-score schema. The Playwright tests exercise the live Next.js frontend and backend, including blocked evaluation/provenance display, comparison persistence, error recovery, and CSV download. The prior Vite build remains available for compatibility; it is development tooling and is not used by the Next.js app.

## Implementation status

The latest implementation adds:

- Live Open-Meteo weather ingestion, SQLite caching, ingestion job state, and data-source status APIs.
- A farmer-facing weather guide with English/Hindi copy and planning-only disclaimers.
- Asset-gated evaluation jobs and a pure segmentation-metric helper module.
- Explicit blocked results while authorized checkpoints, labels, a geographic split, and a supported inference backend remain unavailable.
