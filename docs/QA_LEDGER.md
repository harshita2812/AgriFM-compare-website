# AgriFM Compare QA Ledger

## Scope and evidence

### Phase 4 — approved protocol and evaluation foundations (2026-11-20)

- Approved six-class task: Wheat, Rice, Cotton, Sugarcane, Maize, and other.
- Approved outer leave-one-region-out split with inner spatial-block cross-validation; shared seed 42.
- Added multiclass per-class IoU/F1, mIoU, macro-F1, overall accuracy, and deterministic block-bootstrap 95% confidence intervals.
- Added deterministic split generation, group-leakage checks, canonical serialization, and split SHA-256 support.
- Updated API, methodology, and documentation to describe the actual blockers rather than claiming checkpoints or runtime are absent.
- No evaluation manifest, model inference, or performance result was generated; imagery, compatible labels, AOIs/block assignments, and adapters remain unavailable.

Latest Phase 4 validation:

| Command | Result | Exit code |
|---|---:|---:|
| `.venv\Scripts\python.exe -m unittest discover -s tests -p test_evaluation.py -v` | 6 passed, 0 failed | 0 |
| `npm.cmd run test:api` | 22 passed, 0 failed/errors | 0 |
| `npm.cmd run test:ui` | 10 passed, 0 failed | 0 |
| `npm.cmd run build` | Next.js production build passed | 0 |
| `.venv\Scripts\python.exe -m compileall ml\evaluation.py ml\pipeline apps\api` | Passed | 0 |
| `git diff --check` | Passed | 0 |

### Phase 1 — automatic data foundation (2026-11-19)

Implemented the first live-data integration slice:

- Added source and ingestion-job APIs at `/api/data/sources`.
- Added cached weather assets at `/api/data/weather/{region_id}`.
- Added live Open-Meteo refresh at `/api/data/weather/refresh`.
- Added bilingual farmer advisory infrastructure at `/api/farmer/advisory`.
- Added SQLite `data_sources`, `data_assets`, and `ingestion_jobs` tables with startup seeding.
- Recorded network and provider errors as ingestion failures instead of fabricated data.
- Added API tests for source metadata, ingestion-job status, cached-weather absence, and region validation.

Latest phase validation:

| Command | Result | Exit code |
|---|---:|---:|
| API integration suite | 11 passed, 0 failed/errors | 0 |
| Playwright UI suite | 9 passed, 0 failed | 0 |
| Next.js production build | Passed | 0 |

### Phase 4 — final QA and dependency hardening (2026-11-19)

- API and metric suite: 14 passed, 0 failed/errors.
- Playwright suite: 10 passed, 0 failed.
- Next.js production build: passed.
- Vite compatibility build: passed, 1,578 modules transformed.
- Full `npm audit`: 0 vulnerabilities.
- Production-only `npm audit --omit=dev`: 0 vulnerabilities.
- The earlier 4 high development-tool advisories are no longer reported by the current registry/lockfile resolution.
- Sequential build and browser validation avoid `.next` state contention with the running Next development server.

### Phase 3 — evaluation job framework (2026-11-19)

Implemented:

- SQLite evaluation-job persistence.
- `POST /api/evaluations/jobs` for creating asset-gated blocked jobs.
- `POST /api/evaluations/jobs/{id}/execute` for explicit manifest and asset validation.
- `GET /api/evaluations/jobs` for job history and status.
- SHA-256 manifest capture only after a supplied manifest passes field and asset-path validation.
- Pure binary metrics remain supported in `ml/evaluation.py`; multiclass metrics and spatial-block bootstrap are also implemented.
- Tests proving blocked jobs remain blocked, arrays are validated, and metric helpers do not fabricate model results.

Latest phase validation:

| Command | Result | Exit code |
|---|---:|---:|
| API and metric integration suite | 14 passed, 0 failed/errors | 0 |
| Playwright UI suite | 10 passed, 0 failed | 0 |
| Next.js production build | Passed | 0 |

### Phase 2 — farmer-facing weather guide (2026-11-19)

Implemented:

- A responsive `Farmer guide` navigation section.
- Region, crop, and English/Hindi controls.
- 7-day weather summary cards for hot-day and rainfall indicators.
- Simple planning advisories with a visible planning-only disclaimer.
- Playwright coverage for Hindi rendering and advisory display.

Latest phase validation:

| Command | Result | Exit code |
|---|---:|---:|
| API integration suite | 11 passed, 0 failed/errors | 0 |
| Playwright UI suite | 10 passed, 0 failed | 0 |
| Next.js production build | Passed | 0 |

This ledger covers the repository as updated for the audited gaps: Next.js (`apps/web/`), FastAPI (`apps/api/`), and the retained Vite compatibility entry point (`src/`). `ml/` contains metric and geographic-split foundations; an end-to-end inference pipeline and compatible evaluation data are still unavailable.

Final validation (all commands run from the project root):

Latest rerun: 2026-11-19.

| Command | Result | Exit code |
|---|---:|---:|
| `npm run test:api` (latest rerun) | 14 passed, 0 failed/errors (`unittest`, including provenance, live-data, legacy SQLite migrations, and metric helpers) | 0 |
| `npm run test:ui` (latest rerun) | 10 passed, 0 failed (`Playwright` / Chromium against Next.js and FastAPI) | 0 |
| `npm run build` (latest rerun) | Next.js production build succeeded; routes `/` and `/_not-found` generated | 0 |
| `npm run build:vite` (latest rerun) | Vite 6.4.6 transformed 1,578 modules and emitted production assets | 0 |
| `npm audit --omit=dev` (latest rerun) | 0 vulnerabilities | 0 |
| `npm audit` (latest rerun) | 0 vulnerabilities across the full dependency tree | 0 |
| VS Code Problems | No errors found | — |
| Personal-name scan over app, backend, README, and tests | No named personal details found | 0 |

During test-first work, the new API assertions first failed against the pre-fix API (3 failures and 1 error in 5 tests; exit 1), exposing missing demo flags, fabricated result values, and the crops response shape. Fixes were applied and the full suites above were rerun successfully.

## Interactive elements and API ledger

| ID | Page/Component | Element | Expected | Actual | Status (PASS/FIXED/BLOCKED) | Test file |
|---|---|---|---|---|---|---|
| NAV-01 | Sidebar | Overview | Opens the overview page | Opens dashboard | PASS | `tests/e2e/app.spec.js` — overview entry points |
| NAV-02 | Sidebar | Compare models | Opens comparison workspace | Opens comparison workspace | PASS | `tests/e2e/app.spec.js` — model library add actions |
| NAV-03 | Sidebar | Model library | Opens model registry | Opens registry; add actions select the chosen model | FIXED | `tests/e2e/app.spec.js` — model library add actions |
| NAV-04 | Sidebar | Datasets | Opens dataset catalog | Opens catalog with five rows | PASS | `tests/e2e/app.spec.js` — all primary sections |
| NAV-05 | Sidebar | Methodology | Opens methodology/About content | Opens methodology with project disclaimer | PASS | `tests/e2e/app.spec.js` — all primary sections |
| NAV-06 | Responsive sidebar | Open navigation | Sidebar is off-canvas at smaller widths and opens from the menu button | Hidden at 900px and 390px; opens on demand | PASS | `tests/e2e/app.spec.js` — responsive navigation |
| NAV-07 | Responsive sidebar | Close navigation | Closes the drawer and keeps it off-canvas | Closes and remains hidden at 900px and 390px | PASS | `tests/e2e/app.spec.js` — responsive navigation |
| NAV-08 | Header | Help | Opens methodology help | Opens methodology | PASS | `tests/e2e/app.spec.js` — all primary sections |
| NAV-09 | API error banner | Retry | Refetches failed API data and clears error | Recovers after transient dashboard failure | PASS | `tests/e2e/app.spec.js` — retry recovers |
| NAV-10 | Notice banner | Dismiss | Clears the notice | Clears completed-run notice | PASS | `tests/e2e/app.spec.js` — comparison controls |
| NAV-11 | Sidebar context cards | Project/profile cards | Static cards must not imply a working dropdown | Removed inactive chevrons; cards are non-interactive | FIXED | `tests/e2e/app.spec.js` — all primary sections |
| OVR-01 | Overview | New comparison | Opens comparison workspace | Opens comparison workspace | PASS | `tests/e2e/app.spec.js` — overview entry points |
| OVR-02 | Overview hero | Set up a run | Opens comparison workspace | Opens comparison workspace | PASS | `tests/e2e/app.spec.js` — overview entry points |
| OVR-03 | Latest comparison panel | Compare models | Opens comparison workspace | Opens comparison workspace | PASS | `tests/e2e/app.spec.js` — overview entry points |
| OVR-04 | Empty chart | Set up a comparison | Opens comparison workspace | Opens comparison workspace | PASS | `tests/e2e/app.spec.js` — overview entry points |
| OVR-05 | Recent comparisons | View all | Opens saved-comparison selector | Opens comparison workspace | PASS | `tests/e2e/app.spec.js` — overview entry points |
| OVR-06 | Recent comparisons | Run ID button | Opens that run and restores its context | Opens selected run | PASS | `tests/e2e/app.spec.js` — overview history controls |
| OVR-07 | Recent comparisons | View run icon | Opens that run and restores its context | Opens selected run | PASS | `tests/e2e/app.spec.js` — overview history controls |
| CMP-01 | Comparison setup | Study region select | Updates comparison region | Region changes and persists with run | PASS | `tests/e2e/app.spec.js` — comparison controls |
| CMP-02 | Comparison setup | Target crop select | Updates target crop | Crop changes and persists with run | PASS | `tests/e2e/app.spec.js` — comparison controls |
| CMP-03 | Comparison setup | Growing season select | Updates season | Season changes and persists with run | PASS | `tests/e2e/app.spec.js` — comparison controls |
| CMP-04 | Comparison setup | Imagery/dataset select | Updates dataset | Dataset changes and persists with run | PASS | `tests/e2e/app.spec.js` — comparison controls |
| CMP-05 | Comparison results | Saved runs select | Loads saved results and restores all run controls | Restores region/crop and associated context | FIXED | `tests/e2e/app.spec.js` — comparison controls |
| CMP-06 | Model selection | Select all | Selects all available models (maximum four) | Selects all four | PASS | `tests/e2e/app.spec.js` — comparison controls |
| CMP-07 | Model selection | Prithvi-EO-2.0 toggle | Adds/removes only that model | Toggle is reflected in selection state | PASS | `tests/e2e/app.spec.js` — model library add actions |
| CMP-08 | Model selection | SatMAE toggle | Adds/removes only that model | Toggle is reflected in selection state | PASS | `tests/e2e/app.spec.js` — model library add actions |
| CMP-09 | Model selection | CROMA toggle | Adds/removes only that model | Toggle is reflected in selection state | PASS | `tests/e2e/app.spec.js` — model library add actions |
| CMP-10 | Model selection | ResNet-50 toggle | Adds/removes only that model | Toggle is reflected in selection state | PASS | `tests/e2e/app.spec.js` — model library add actions |
| CMP-11 | Comparison setup | Save comparison setup | Requires at least two models; persists context and explicitly says no inference ran | Disabled with one model; saved context has null metrics and explicit no-inference notice | FIXED | `tests/e2e/app.spec.js` — comparison controls; `tests/test_api.py` — new comparison |
| CMP-12 | Empty comparison results | Save current setup | Persists selected setup when there is no prior run | Creates context-only run and shows Phase-II placeholders | PASS | `tests/e2e/app.spec.js` — empty results state |
| CMP-13 | Comparison results | Download results as CSV | Downloads context/results and marks demo data; no fabricated numbers | CSV downloads and contains Phase-II placeholders and `is_demo` | PASS | `tests/e2e/app.spec.js` — comparison controls |
| ML-01 | Model library | Compare models CTA | Opens comparison workspace | Opens comparison workspace | PASS | `tests/e2e/app.spec.js` — all primary sections |
| ML-02 | Prithvi model card | Add to a comparison | Selects Prithvi and opens comparison workspace | Model is selected | FIXED | `tests/e2e/app.spec.js` — model library add actions |
| ML-03 | SatMAE model card | Add to a comparison | Selects SatMAE and opens comparison workspace | Model is selected | FIXED | `tests/e2e/app.spec.js` — model library add actions |
| ML-04 | CROMA model card | Add to a comparison | Selects CROMA and opens comparison workspace | Model is selected | FIXED | `tests/e2e/app.spec.js` — model library add actions |
| ML-05 | ResNet-50 model card | Add to a comparison | Selects ResNet-50 and opens comparison workspace | Model is selected | FIXED | `tests/e2e/app.spec.js` — model library add actions |
| DEMO-01 | All pages | Amber demo banner | Always explains no ground-truth evaluation is available | Visible with `DEMO DATA` label on every primary page and comparison workspace | FIXED | `tests/e2e/app.spec.js` — all primary sections; comparison controls |
| DEMO-02 | Overview and charts | F1 score, winner, and chart | No ranking or chart when metrics are unevaluated | Shows `Not yet evaluated — Phase-II`; no winner/bar chart | FIXED | `tests/e2e/app.spec.js` — comparison controls |
| DEMO-03 | Comparison result table | Accuracy, F1, IoU, kappa, latency cells | Empty metrics show `Not yet evaluated — Phase-II` | Every metric cell uses the required placeholder | FIXED | `tests/e2e/app.spec.js` — comparison controls |
| DEMO-04 | Footer/About | Research disclaimer | Warns demo values are not validated results | Disclaimer present in footer and About/methodology page | FIXED | `tests/e2e/app.spec.js` — all primary sections |
| PRIV-01 | App/API | Personal names | No personal names in app, docs, or saved demo data | Names omitted; source scan and UI assertion pass | FIXED | `tests/e2e/app.spec.js` — all primary sections; final source scan |
| PRIV-02 | App/API | File uploads | No upload UI, endpoint, or stored uploads | No file input; `/api/uploads` returns 404 | PASS | `tests/e2e/app.spec.js` — all primary sections; `tests/test_api.py` — upload absence |
| API-01 | FastAPI | `GET /api/health` | Returns healthy status | HTTP 200; used by test server readiness probe | PASS | `tests/test_api.py` — integration setup |
| API-02 | FastAPI | `GET /api/models` | Catalog metadata only, `is_demo=true`, no score fields | Demo flags present; legacy values cleared and omitted | FIXED | `tests/test_api.py` — seeded catalogs; legacy migration |
| API-03 | FastAPI | `GET /api/regions` | Catalog records carry `is_demo=true` | All region records marked demo | PASS | `tests/test_api.py` — seeded catalogs |
| API-04 | FastAPI | `GET /api/datasets` | Catalog records carry `is_demo=true` | All dataset records marked demo | PASS | `tests/test_api.py` — seeded catalogs |
| API-05 | FastAPI | `GET /api/crops` | Response includes items and `is_demo=true` | Returns marked object, not an unmarked list | FIXED | `tests/test_api.py` — crop catalog |
| API-06 | FastAPI | `GET /api/runs` | Persisted runs and results are demo-marked; metric values null | Seeded and saved runs return null metrics and `is_demo=true` | FIXED | `tests/test_api.py` — runs/dashboard |
| API-07 | FastAPI | `POST /api/runs` | Validates context, persists run, returns no fabricated metrics | HTTP success and persisted run with null metrics/demo flags | FIXED | `tests/test_api.py` — new comparison |
| API-08 | FastAPI | `POST /api/runs` validation | Invalid model counts, duplicate/unknown models, crop, region, dataset return errors | 422/404 responses asserted | PASS | `tests/test_api.py` — invalid comparison inputs |
| API-09 | FastAPI | `GET /api/dashboard` | Counts work; no unmeasured top score/ranking | Dashboard has demo flag and null top score/model | FIXED | `tests/test_api.py` — runs/dashboard |
| API-10 | FastAPI | `GET /api/methodology` | Protocol/metrics definitions are demo-marked and accurately caveated | `is_demo=true`; Phase-II protocol returned | PASS | `tests/test_api.py` — crop/methodology |
| API-11 | FastAPI/SQLite | Startup migration | Wipes old demo scores while preserving run context | Legacy database is migrated; all metric fields null | FIXED | `tests/test_api.py` — legacy migration |
| QA-01 | Test runner | `npm run test:api` | Uses local venv Python when Python is not on PATH | Node wrapper selects `.venv` interpreter; suite passes | FIXED | `scripts/test-api.mjs` |
| STR-01 | Repository layout | Next.js `apps/web`, FastAPI `apps/api` | Required application structure is present and runnable | Next app and API are in the requested directories; Vite compatibility entry point remains available | FIXED | `npm run build`; `npm run test:ui`; `npm run build:vite` |
| GAP-02 | ML pipeline | Imagery-to-metrics evaluation | Run models on authorized labels and report reproducible metrics | Evaluation is explicitly `blocked`; API returns null metrics and an exact prerequisite reason | BLOCKED | `tests/test_api.py` — seeded runs/dashboard; `tests/e2e/app.spec.js` — comparison controls; `ml/README.md` |
| GAP-03 | Comparison provenance | Typed metadata, persistence, display, CSV export | Capture reproducibility declarations without implying they are verified | Provenance infrastructure is implemented and tested; declarations are labeled unverified. Verified provenance tied to a real evaluation is unavailable because GAP-02 is blocked. | BLOCKED | `tests/test_api.py` — provenance persistence/validation; `tests/e2e/app.spec.js` — comparison controls |
| GAP-04 | Methodology and evaluation copy | No fabricated performance/ranking claims | Copy matches the no-inference, null-metric behavior | UI/API describe F1 as proposed and explicitly state no inference/results are available | FIXED | `tests/test_api.py` — crop/methodology; `tests/e2e/app.spec.js` — all primary sections |
| GAP-05 | Dataset catalog | Availability labels | Do not imply sources are ready for app evaluation | Rows use `Metadata only` or `Reference`; startup migration corrects persisted legacy labels | FIXED | `tests/test_api.py` — seeded catalogs; legacy migration; `tests/e2e/app.spec.js` — all primary sections |

### Blocked items — required input

To unblock GAP-02 and complete verified evaluation provenance for GAP-03, provide/resolve licensed Sentinel imagery and exact study AOIs, task-compatible five-crop ground-truth labels with versions and permissions, stable spatial-block assignments, and validated adapters for the pinned checkpoints. The task, broad split protocol, metric defaults, seed 42, checkpoint hashes, and CPU runtime are now recorded. No inference or model performance claim is made by this workspace.
