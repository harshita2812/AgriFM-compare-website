# AgriFM Compare Gap Fix Log

| Gap | Status Fixed/Partial/Blocked | Commits | Tests added | Evidence | Remaining blockers |
|---|---|---|---|---|---|
| GAP-01 — Required application structure | Fixed | Unavailable: this workspace has no Git repository and Git is not available, so per-gap commits could not be created. | `tests/test_api.py`; `tests/e2e/app.spec.js` | `apps/web/` builds with Next.js, `apps/api/` runs the API, `npm run build` and `npm run test:ui` pass. The Vite compatibility build also passes with `npm run build:vite`. | None for the available app structure. Git repository/tooling must be supplied to create commits. |
| GAP-02 — Real imagery-to-metrics evaluation | Blocked | Unavailable: this workspace has no Git repository and Git is not available. | API regression coverage in `tests/test_api.py`; browser coverage in `tests/e2e/app.spec.js` asserts that a saved run stays blocked and metrics remain unevaluated. | API returns `evaluation_status: blocked`, the exact missing-input reason, and null metric fields. `ml/README.md` records the blocked pipeline and required inputs. | Provide authorized checkpoints, imagery and ground-truth labels, label/task definition, held-out geographic split and protocol, preprocessing/metric definitions, and supported compute/runtime. |
| GAP-03 — Reproducible evaluation provenance | Partial | Unavailable: this workspace has no Git repository and Git is not available. | `tests/test_api.py` — provenance persistence, validation, and migration; `tests/e2e/app.spec.js` — provenance display and CSV export. | Typed provenance fields persist in SQLite. User declarations are explicitly `declared_unverified`; absent provenance is `not_recorded`. | No actual evaluation is possible while GAP-02 is blocked, so no provenance can be verified against inference or reported results. |
| GAP-04 — Research-integrity copy | Fixed | Unavailable: this workspace has no Git repository and Git is not available. | `tests/test_api.py` — methodology wording; `tests/e2e/app.spec.js` — methodology, disclaimer, blocked status, Phase-II placeholders. | UI/API say no inference ran, performance results are unavailable, and F1 is proposed rather than an active ranking metric. | None for the verified copy; keep the boundary until a real evaluation is available. |
| GAP-05 — Dataset readiness labels | Fixed | Unavailable: this workspace has no Git repository and Git is not available. | `tests/test_api.py` — catalog status and legacy migration; `tests/e2e/app.spec.js` — catalog status. | Catalog uses `Metadata only` or `Reference`; database startup migration updates stored legacy statuses. | Source ingestion and evaluation availability remain blocked by GAP-02. |
| Current audit GAP-03 — Development dependency advisory | Blocked (mitigated, not fixed) | No Git repository/tooling is available for commits. | Existing API/UI suites and both builds rerun after the toolchain change. | Vite 6.4.6 + `@vitejs/plugin-react` 4.7.0 retain a passing compatibility build. Vite dev server now binds `127.0.0.1`. Latest `npm audit --json`: 4 high advisories via `picomatch <=4.0.7`, exit 1; `npm audit --omit=dev`: 0 vulnerabilities, exit 0. | No patched `picomatch` release was available in registry at audit time. Keep Vite compatibility server local-only; update once a compatible fixed dependency is published. |

## Validation evidence

Latest local validation rerun: 2026-11-18.

- `npm run test:api`: 9 passed, 0 failed, exit code 0.
- `npm run test:ui`: 9 passed, 0 failed, exit code 0.
- `npm run build`: Next.js build succeeded, exit code 0.
- `npm run build:vite`: Vite 6.4.6 transformed 1,578 modules and built successfully, exit code 0.
- `npm audit --omit=dev`: 0 vulnerabilities, exit code 0.

The latest full `npm audit --json` reports 4 high advisories in development-only Vite/picomatch dependencies, exit code 1. The production dependency audit is clean. The remaining advisories trace to `picomatch <=4.0.7`; no compatible patched release was available from the configured npm registry at validation time.
