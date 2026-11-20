import json
from contextlib import closing
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from apps.api import main as core
from apps.api.db import connect


router = APIRouter()


@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/models")
def get_models() -> list[dict[str, Any]]:
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM models ORDER BY CASE id WHEN 'prithvi' THEN 0 WHEN 'satmae' THEN 1 WHEN 'croma' THEN 2 ELSE 3 END"
        ).fetchall()
    return [
        {
            key: row[key]
            for key in ("id", "name", "provider", "family", "parameters", "modality", "description", "color")
        } | {"is_demo": True}
        for row in rows
    ]


@router.get("/api/regions")
def get_regions() -> list[dict[str, Any]]:
    with closing(connect()) as conn:
        return [
            {**dict(row), "is_demo": True}
            for row in conn.execute("SELECT * FROM regions ORDER BY name")
        ]


@router.get("/api/datasets")
def get_datasets() -> list[dict[str, Any]]:
    with closing(connect()) as conn:
        return [
            {**dict(row), "is_demo": True}
            for row in conn.execute("SELECT * FROM datasets ORDER BY name")
        ]


@router.get("/api/crops")
def get_crops() -> dict[str, Any]:
    return {"items": core.CROPS, "is_demo": True}


@router.get("/api/runs")
def get_runs() -> list[dict[str, Any]]:
    with closing(connect()) as conn:
        rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
    return [
        ({
            **dict(row),
            "model_ids": json.loads(row["model_ids"]),
            "results": json.loads(row["results_json"]),
            "is_demo": True,
        } | core.run_disclosure_fields(json.loads(row["provenance_json"]) if row["provenance_json"] else None))
        for row in rows
    ]


@router.post("/api/runs")
def create_run(request: core.RunRequest) -> dict[str, Any]:
    if len(set(request.model_ids)) != len(request.model_ids):
        raise HTTPException(status_code=422, detail="Choose each model only once.")
    if request.crop not in core.CROPS:
        raise HTTPException(status_code=422, detail="Select a supported crop.")
    provenance = request.provenance.model_dump(mode="json", exclude_none=True) if request.provenance else None
    unknown_revision_models = set((provenance or {}).get("model_revisions", {})) - set(request.model_ids)
    if unknown_revision_models:
        raise HTTPException(
            status_code=422,
            detail=f"Model revisions must refer only to selected models: {', '.join(sorted(unknown_revision_models))}.",
        )
    with closing(connect()) as conn:
        region = conn.execute("SELECT id, name FROM regions WHERE id = ?", (request.region_id,)).fetchone()
        dataset = conn.execute("SELECT id, name FROM datasets WHERE id = ?", (request.dataset_id,)).fetchone()
        model_rows = conn.execute(
            f"SELECT id FROM models WHERE id IN ({','.join('?' for _ in request.model_ids)})",
            request.model_ids,
        ).fetchall()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found.")
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    if len(model_rows) != len(request.model_ids):
        raise HTTPException(status_code=404, detail="One or more selected models were not found.")

    results = core.unevaluated_results(request.model_ids)
    run = {
        "id": str(uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "region_id": request.region_id,
        "region_name": region["name"],
        "crop": request.crop,
        "season": request.season,
        "dataset_id": request.dataset_id,
        "dataset_name": dataset["name"],
        "model_ids": request.model_ids,
        "results": results,
        "is_demo": True,
        **core.run_disclosure_fields(provenance),
    }
    with closing(connect()) as conn:
        conn.execute(
            """INSERT INTO runs
               (id, created_at, region_id, crop, season, dataset_id, model_ids, results_json, is_demo, provenance_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, TRUE, ?)""",
            (run["id"], run["created_at"], run["region_id"], run["crop"], run["season"], run["dataset_id"],
             json.dumps(run["model_ids"]), json.dumps(results), json.dumps(provenance) if provenance else None),
        )
        conn.commit()
    return run


@router.get("/api/dashboard")
def get_dashboard() -> dict[str, Any]:
    models = get_models()
    runs = get_runs()
    regions = get_regions()
    datasets = get_datasets()
    latest = runs[0] if runs else None
    return {
        "is_demo": True,
        "model_count": len(models),
        "run_count": len(runs),
        "region_count": len(regions),
        "dataset_count": len(datasets),
        "top_model": None,
        "top_f1": None,
        "latest_run": latest,
        "models": models,
        "regions": regions,
        "runs": runs[:5],
    }


@router.get("/api/methodology")
def get_methodology() -> dict[str, Any]:
    return {
        "is_demo": True,
        "metrics": [
            {"name": "Per-class IoU and mIoU", "unit": "%", "description": "Overlap for each of the five crop classes and other, with mean IoU proposed for the approved segmentation task; not currently calculated or used to rank models."},
            {"name": "Per-class F1 and macro F1", "unit": "%", "description": "Harmonic mean of precision and recall for each class and their macro average; proposed, but not currently calculated or used to rank models."},
            {"name": "Overall accuracy", "unit": "%", "description": "Fraction of correctly classified pixels across the evaluation sample; proposed, but not currently calculated."},
            {"name": "Bootstrap confidence intervals", "unit": "95% CI", "description": "Planned 1,000-resample spatial-block bootstrap intervals; not calculated until verified held-out data are available."},
            {"name": "Compute cost", "unit": "parameters, FLOPs, seconds/hectare", "description": "Planned measured resource cost under the documented CPU runtime; no measurements are currently available."},
            {"name": "Cohen's kappa", "unit": "0–1", "description": "Chance-corrected agreement between predictions and reference labels."},
            {"name": "Inference time", "unit": "ms / tile", "description": "Report only after measuring with documented hardware, batch size, and runtime conditions."},
        ],
        "protocol": [
            "Choose a region, crop, season, dataset, and at least two candidate models.",
            "The same region and crop context is applied to every selected model for a within-run comparison.",
            "The approved task is six-class semantic segmentation: Wheat, Rice, Cotton, Sugarcane, Maize, and other.",
            "The proposed split is leave-one-region-out with spatial-block cross-validation; block assignments and AOIs are not yet available.",
            "The CPU-friendly default is a frozen encoder with a lightweight segmentation head, using shared seed 42.",
            "This prototype does not execute model inference; performance metrics remain unevaluated until Phase-II.",
            "For a publishable result, calculate metrics on a documented, held-out, ground-truth-labelled dataset.",
        ],
    }
