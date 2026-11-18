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

Open the Next.js URL (normally `http://localhost:3000`). FastAPI docs are available at `http://127.0.0.1:8000/docs`; API health check: `/api/health`. The Next.js development server proxies `/api/*` to FastAPI at `http://127.0.0.1:8000`; set `AGRIFM_API_ORIGIN` to override that origin. SQLite is created and seeded at `backend/agrifm.db` on first API startup. The database file is excluded from Git.

The Next.js application is in `apps/web/app/`, and the FastAPI implementation is in `apps/api/`. The prior Vite entry point remains available through `npm run dev:vite` and `npm run build:vite` for compatibility.

## What works

- Overview dashboard with summary metrics, latest-run chart, and saved comparison history.
- Comparison workspace with model selection, region, crop, season, and imagery-source controls. Comparison setups are persisted in SQLite and exportable as CSV; no inference is run.
- Model registry for Prithvi-EO-2.0, SatMAE, CROMA, and a ResNet-50 supervised baseline.
- Dataset catalog and study methodology pages.
- FastAPI endpoints for dashboard data, model/region/dataset catalogs, runs, crops, and methodology.
- Responsive layouts for desktop and mobile, served by Next.js.
- Public Open-Meteo weather refresh for the five study regions, with cached SQLite assets and ingestion job status.
- Bilingual farmer advisory API with explicit planning-only and certified-advice disclaimers.

## Data and scope decisions

This repository starts from a UI/product brief that did not include a complete list of model candidates, datasets, or evaluation protocol. The app uses four representative models, five Indian study regions, five crops, and a small source catalog as sensible starter defaults. They can be changed in `backend/main.py`.

**No model performance scores are available.** Model/result records and catalog entries are explicitly marked `is_demo: true`, and the UI displays an amber demo-data banner. Empty metric cells show “Not yet evaluated — Phase-II”. Comparison runs save context only; they do not generate or imply model rankings. Each run reports evaluation status `blocked` and an explanation of the missing prerequisites.

Runs can optionally store typed provenance declarations (such as dataset/label versions, acquisition dates, split details, model revisions, preprocessing, metric configuration, code revision, and runtime). These are user-supplied declarations, not independently verified evidence; the UI and CSV label them `declared_unverified`. Runs without declarations report `not_recorded`. Because no inference pipeline is connected, provenance cannot currently be verified against an actual evaluation.

The app does not download satellite imagery, store uploads, train or load models, perform inference, or calculate metrics from ground-truth labels. Dataset catalog entries are marked `Metadata only` or `Reference`; none is currently available to this app for evaluation. The catalog is descriptive only, not an ingestion pipeline.

The app compares 2–4 candidate models under the same selected region and crop context, but no ML pipeline is included in this repository. Add a documented, held-out evaluation pipeline before reporting performance results.

## QA scope

The delivered web application is Next.js in `apps/web/`; the FastAPI service is in `apps/api/`. The `ml/` directory documents, but does not implement, the blocked evaluation pipeline. No authorized model checkpoints, ground-truth agricultural labels, documented split protocol, or supported ML runtime are included in this repository. Do not report performance results until those inputs and a documented evaluation protocol are provided.

The API tests start an isolated temporary SQLite database and exercise real HTTP routes, including provenance validation/persistence and migrations of the former demo-score schema. The Playwright tests exercise the live Next.js frontend and backend, including blocked evaluation/provenance display, comparison persistence, error recovery, and CSV download. The prior Vite build remains available for compatibility; it is development tooling and is not used by the Next.js app.
