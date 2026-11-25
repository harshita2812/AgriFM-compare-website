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

When `AGRIFM_ASSET_ROOT` is configured, API startup registers fetched files in `data_sources`, `data_assets`, and `ingestion_jobs`. `GET /api/data/readiness` reports hash-verified checkpoints and missing/blocked inputs for each model, region, and crop; the Overview page displays the same status. APScheduler refreshes weather daily and re-verifies asset hashes weekly. The task and broad split protocol are approved, but no evaluation manifest is activated until compatible imagery and labels, exact AOIs, and spatial-block assignments exist; evaluation remains blocked.

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

The app compares 2–4 candidate models under the same selected region and crop context. Multiclass metric and deterministic split utilities are implemented, but no end-to-end inference pipeline or model-specific adapters are connected. Do not report performance results until verified imagery, task-compatible labels, spatial splits, and supported adapters exist.

### SICKLE dataset reference

The [SICKLE repository](https://github.com/Depanshu-Sani/SICKLE) describes a multi-sensor satellite dataset for the Cauvery Delta in Tamil Nadu, covering January 2018–March 2021. Its paper reports 388 surveyed plots, 2,370 time-series samples, about 209,000 satellite images, 21 crop types, and annotations at 3 m, 10 m, and 30 m. It combines Landsat-8, Sentinel-1, and Sentinel-2 data and includes crop type, variety, growing season, and yield information. The repository's benchmark code evaluates binary paddy-vs-non-paddy mapping as well as sowing, transplanting, harvest-date, and yield tasks.

The repository does not contain the dataset files. Access to the full and toy data is requested through the authors' [dataset access form](https://docs.google.com/forms/d/e/1FAIpQLSdq7Dcj5FF1VmlKozrQ7XNoq006iVKrUIMTK2jReBJDuO1N2g/viewform). AgriFM Compare lists SICKLE as a reference only; it is not downloaded, and its availability, license for the acquired files, and label alignment have not been independently verified. Its single Tamil Nadu study area and binary paddy benchmark do not satisfy this project's five-region, six-class task (Wheat, Rice, Cotton, Sugarcane, Maize, and other). Do not use it as evaluation ground truth or report comparative scores without obtaining authorized files and documenting a suitable, compatible label mapping and spatial split.

Citation: Depanshu Sani et al., “SICKLE: A Multi-Sensor Satellite Imagery Dataset Annotated With Multiple Key Cropping Parameters,” WACV 2024, pp. 5995–6004. See the [paper](https://openaccess.thecvf.com/content/WACV2024/html/Sani_SICKLE_A_Multi-Sensor_Satellite_Imagery_Dataset_Annotated_With_Multiple_Key_WACV_2024_paper.html) and the repository's citation block for the full BibTeX entry.

## QA scope

The delivered web application is Next.js in `apps/web/`; the FastAPI service is in `apps/api/`. The `ml/` directory contains multiclass metric and geographic split utilities, but the end-to-end evaluation pipeline remains blocked. The four pinned checkpoints and CPU runtime are available locally; task-compatible ground-truth labels, imagery chips, exact AOIs/spatial-block assignments, and model-specific adapters are not. Do not report performance results until those inputs and a documented evaluation protocol are verified.

The API tests start an isolated temporary SQLite database and exercise real HTTP routes, including provenance validation/persistence and migrations of the former demo-score schema. The Playwright tests exercise the live Next.js frontend and backend, including blocked evaluation/provenance display, comparison persistence, error recovery, and CSV download. The prior Vite build remains available for compatibility; it is development tooling and is not used by the Next.js app.

## Trained crop recommendation model

The 2,200-row [crop dataset](/c:/Users/HARSHITA/Downloads/crop_dataset_rag_ready.json) was converted from RAG text records into seven numeric features: nitrogen, phosphorus, potassium, temperature, humidity, soil pH, and rainfall. `ml/train_crop_recommendation.py` trains a seeded Random Forest pipeline with an 80/20 stratified split and writes the model artifact to `ml/artifacts/`.

The held-out test accuracy is 99.32%. This is a soil-and-climate recommendation model, not a plant-disease classifier; the saved Plant Disease Detection HTML contains no model or image dataset and was not used for training.

Retrain after changing the dataset:

```powershell
.\\.venv\\Scripts\\python.exe ml\\train_crop_recommendation.py
```

The trained result is available through `POST /api/crop/recommend` and in the Farmer Guide.

## Sentinel-2 public benchmark samples

Five approximate 25 km square Sentinel-2 L2A chips are available under `ml/data/sentinel2_samples/` for Punjab, Western Uttar Pradesh, Maharashtra, Karnataka, and Bihar. The 2025-10-01 to 2026-04-30 search selected one low-cloud scene per region with B02, B03, B04, and B08 bands.

The acquisition manifest is `ml/data/sentinel2_samples/sentinel2_public_samples_manifest.json`, and the manifest checksum is stored beside it.

These chips are **public benchmark imagery samples only**. They are not approved study AOIs, task-compatible crop ground truth, spatially assigned training examples, or evidence of model performance. The Western Uttar Pradesh sample is explicitly approximate.

`ml/train_sentinel_autoencoder.py` trains an unsupervised convolutional autoencoder on 1,500 random 64×64 patches from the five chips. It is a representation-learning smoke test, not supervised crop or disease training. It completed with final reconstruction MSE 0.009199 after 8 epochs on CPU. The artifact and metadata are stored in `ml/artifacts/`.

Search or retrain the sample set with:

```powershell
.\\.venv\\Scripts\\python.exe ml\\pipeline\\acquire_sentinel_samples.py
.\\.venv\\Scripts\\python.exe ml\\pipeline\\acquire_sentinel_samples.py --download
```

## Implementation status

The latest implementation adds:

- Live Open-Meteo weather ingestion, SQLite caching, ingestion job state, and data-source status APIs.
- A farmer-facing weather guide with English/Hindi copy and planning-only disclaimers.
- Verified asset inventory, readiness reporting, and scheduled asset re-verification.
- Asset-gated evaluation jobs, multiclass metrics, block-bootstrap confidence intervals, and geographic split utilities.
- Explicit blocked results while task-compatible labels, imagery, AOIs, split files, and supported inference adapters remain unavailable.
