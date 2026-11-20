import hashlib
import json
import os
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from apps.api import main as core
from apps.api.db import connect
from apps.api.routers.catalog import create_run


router = APIRouter()


@router.post("/api/evaluations/jobs")
def create_evaluation_job(request: core.RunRequest) -> dict[str, Any]:
    run = create_run(request)
    job_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    detail = (
        "Evaluation blocked: no verified evaluation manifest, task-compatible labels, imagery chips, "
        "or saved spatial split are available. No model was loaded and no metrics were calculated."
    )
    provenance = request.provenance.model_dump(mode="json", exclude_none=True) if request.provenance else None
    with closing(connect()) as conn:
        conn.execute(
            """INSERT INTO evaluation_jobs
               (id, run_id, status, created_at, completed_at, manifest_json, result_json, detail, provenance_json)
               VALUES (?, ?, 'blocked', ?, NULL, NULL, ?, ?, ?)""",
            (
                job_id,
                run["id"],
                created_at,
                json.dumps(core.unevaluated_results(request.model_ids)),
                detail,
                json.dumps(provenance) if provenance else None,
            ),
        )
        conn.commit()
    return {
        "id": job_id,
        "run_id": run["id"],
        "status": "blocked",
        "created_at": created_at,
        "completed_at": None,
        "manifest": None,
        "results": core.unevaluated_results(request.model_ids),
        "detail": detail,
        "provenance_status": "declared_unverified" if provenance else "not_recorded",
    }


@router.get("/api/evaluations/jobs")
def get_evaluation_jobs() -> list[dict[str, Any]]:
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM evaluation_jobs ORDER BY created_at DESC"
        ).fetchall()
    return [
        {
            "id": row["id"],
            "run_id": row["run_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
            "manifest": json.loads(row["manifest_json"]) if row["manifest_json"] else None,
            "results": json.loads(row["result_json"]) if row["result_json"] else [],
            "detail": row["detail"],
            "provenance_status": "declared_unverified" if row["provenance_json"] else "not_recorded",
        }
        for row in rows
    ]


@router.post("/api/evaluations/jobs/{job_id}/execute")
def execute_evaluation_job(job_id: str) -> dict[str, Any]:
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM evaluation_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Evaluation job not found.")

    manifest_path = os.environ.get("AGRIFM_EVALUATION_MANIFEST")
    if not manifest_path:
        detail = (
            "Evaluation blocked: AGRIFM_EVALUATION_MANIFEST is not configured. "
            "Task-compatible labels, imagery chips, and a saved spatial split are unavailable."
        )
    else:
        path = Path(manifest_path)
        if not path.is_absolute():
            path = core.ROOT / path
        if not path.is_file():
            detail = f"Evaluation blocked: manifest not found at {path}."
        else:
            try:
                manifest = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                detail = f"Evaluation blocked: manifest could not be read: {error}"
                manifest = None
            if manifest is not None:
                required = {
                    "dataset_path",
                    "labels_path",
                    "split_path",
                    "models",
                    "metric_config",
                    "code_revision",
                    "hardware_runtime",
                }
                missing = sorted(required - set(manifest))
                if missing:
                    detail = f"Evaluation blocked: manifest fields missing: {', '.join(missing)}."
                else:
                    asset_paths = [
                        manifest["dataset_path"],
                        manifest["labels_path"],
                        manifest["split_path"],
                        *[value for value in manifest["models"].values() if isinstance(value, str)],
                    ]
                    missing_assets = []
                    for asset in asset_paths:
                        candidate = Path(asset)
                        if not candidate.is_absolute():
                            candidate = path.parent / candidate
                        if not candidate.is_file():
                            missing_assets.append(asset)
                    if missing_assets:
                        detail = (
                            "Evaluation blocked: authorized assets missing: "
                            + ", ".join(missing_assets)
                        )
                    else:
                        detail = (
                            "Evaluation blocked: assets and manifest passed inventory validation, "
                            "but no supported model inference backend is implemented in this checkout."
                        )
                        manifest["manifest_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                        manifest["observed_status"] = "inventory_validated"

    completed_at = datetime.now(timezone.utc).isoformat()
    manifest_json = json.dumps(manifest) if "manifest" in locals() and manifest is not None else None
    with closing(connect()) as conn:
        conn.execute(
            """UPDATE evaluation_jobs
               SET status = 'blocked', completed_at = ?, manifest_json = ?, detail = ?
               WHERE id = ?""",
            (completed_at, manifest_json, detail, job_id),
        )
        conn.commit()
    return {
        "id": job_id,
        "run_id": row["run_id"],
        "status": "blocked",
        "created_at": row["created_at"],
        "completed_at": completed_at,
        "manifest": json.loads(manifest_json) if manifest_json else None,
        "results": json.loads(row["result_json"]) if row["result_json"] else [],
        "detail": detail,
        "provenance_status": "declared_unverified" if row["provenance_json"] else "not_recorded",
    }
