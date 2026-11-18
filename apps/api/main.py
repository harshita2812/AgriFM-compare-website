from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypedDict
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, model_validator


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.environ.get("AGRIFM_DB_PATH", ROOT / "backend" / "agrifm.db"))

MODELS = [
    {
        "id": "prithvi",
        "name": "Prithvi-EO-2.0",
        "provider": "IBM / NASA",
        "family": "EO foundation model",
        "parameters": "600M",
        "modality": "Multispectral",
        "description": "A geospatial foundation model pretrained on Harmonized Landsat Sentinel-2 data.",
        "color": "#2e7257",
    },
    {
        "id": "satmae",
        "name": "SatMAE",
        "provider": "Harvard / MIT",
        "family": "Masked autoencoder",
        "parameters": "ViT-L",
        "modality": "Multispectral",
        "description": "A self-supervised transformer designed to learn representations from satellite imagery.",
        "color": "#d99b42",
    },
    {
        "id": "croma",
        "name": "CROMA",
        "provider": "University of Oxford",
        "family": "Contrastive multimodal",
        "parameters": "Base",
        "modality": "SAR + optical",
        "description": "A multimodal representation model trained with radar and optical satellite imagery.",
        "color": "#6978b8",
    },
    {
        "id": "resnet",
        "name": "ResNet-50",
        "provider": "Baseline",
        "family": "Supervised baseline",
        "parameters": "25.6M",
        "modality": "Multispectral",
        "description": "A conventional supervised baseline for contextualizing foundation-model performance.",
        "color": "#909b8e",
    },
]

REGIONS = [
    {"id": "punjab", "name": "Punjab", "state": "Punjab", "lat": 31.1471, "lon": 75.3412},
    {"id": "up", "name": "Western Uttar Pradesh", "state": "Uttar Pradesh", "lat": 28.6139, "lon": 77.2090},
    {"id": "maharashtra", "name": "Maharashtra", "state": "Maharashtra", "lat": 19.7515, "lon": 75.7139},
    {"id": "karnataka", "name": "Karnataka", "state": "Karnataka", "lat": 15.3173, "lon": 75.7139},
    {"id": "bihar", "name": "Bihar", "state": "Bihar", "lat": 25.0961, "lon": 85.3131},
]

CROPS = ["Wheat", "Rice", "Cotton", "Sugarcane", "Maize"]

DatasetStatus = Literal["Metadata only", "Reference"]


class DatasetRecord(TypedDict):
    id: str
    name: str
    provider: str
    resolution: str
    coverage: str
    type: str
    status: DatasetStatus


DATASETS: list[DatasetRecord] = [
    {"id": "sentinel2", "name": "Sentinel-2 L2A", "provider": "Copernicus / ESA", "resolution": "10 m", "coverage": "2017–present", "type": "Multispectral imagery", "status": "Metadata only"},
    {"id": "sen1floods", "name": "Sen1Floods11", "provider": "NASA / ESA", "resolution": "10 m", "coverage": "Multi-region", "type": "SAR labels", "status": "Reference"},
    {"id": "s1s2", "name": "Sentinel-1 + Sentinel-2", "provider": "Copernicus / ESA", "resolution": "10 m", "coverage": "2017–present", "type": "SAR + optical", "status": "Metadata only"},
    {"id": "crop-calendar", "name": "Regional crop calendar", "provider": "Illustrative project metadata", "resolution": "District-level", "coverage": "India", "type": "Seasonal context", "status": "Reference"},
]

EVALUATION_BLOCK_REASON = (
    "This checkout has no wired inference pipeline. No authorized model checkpoints, "
    "ground-truth agricultural labels, or documented split protocol were found; inference was not run."
)

def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(connect()) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS models (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, provider TEXT NOT NULL,
                family TEXT NOT NULL, parameters TEXT NOT NULL, modality TEXT NOT NULL,
                description TEXT NOT NULL, color TEXT NOT NULL, values_json TEXT NOT NULL,
                is_demo INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS regions (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, state TEXT NOT NULL,
                lat REAL NOT NULL, lon REAL NOT NULL, is_demo INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS datasets (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, provider TEXT NOT NULL,
                resolution TEXT NOT NULL, coverage TEXT NOT NULL, type TEXT NOT NULL,
                status TEXT NOT NULL, is_demo INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, region_id TEXT NOT NULL,
                crop TEXT NOT NULL, season TEXT NOT NULL, dataset_id TEXT NOT NULL,
                model_ids TEXT NOT NULL, results_json TEXT NOT NULL,
                is_demo INTEGER NOT NULL DEFAULT 1, provenance_json TEXT
            );
            """
        )
        for table in ("models", "regions", "datasets", "runs"):
            columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            if "is_demo" not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 1")
        run_columns = {row["name"] for row in conn.execute("PRAGMA table_info(runs)")}
        if "provenance_json" not in run_columns:
            conn.execute("ALTER TABLE runs ADD COLUMN provenance_json TEXT")

        conn.execute("UPDATE models SET values_json = '{}', is_demo = 1")
        conn.execute("UPDATE regions SET is_demo = 1")
        conn.execute("UPDATE datasets SET is_demo = 1")
        for model in MODELS:
            conn.execute(
                """INSERT OR IGNORE INTO models
                   (id, name, provider, family, parameters, modality, description, color, values_json, is_demo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}', 1)""",
                tuple(model[key] for key in ("id", "name", "provider", "family", "parameters", "modality", "description", "color")),
            )
        for region in REGIONS:
            conn.execute(
                "INSERT OR IGNORE INTO regions (id, name, state, lat, lon, is_demo) VALUES (?, ?, ?, ?, ?, 1)",
                tuple(region[key] for key in ("id", "name", "state", "lat", "lon")),
            )
        for dataset in DATASETS:
            conn.execute(
                """INSERT OR IGNORE INTO datasets
                   (id, name, provider, resolution, coverage, type, status, is_demo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                tuple(dataset[key] for key in ("id", "name", "provider", "resolution", "coverage", "type", "status")),
            )
            conn.execute("UPDATE datasets SET status = ? WHERE id = ?", (dataset["status"], dataset["id"]))
        for run in conn.execute("SELECT id, model_ids FROM runs").fetchall():
            conn.execute(
                "UPDATE runs SET results_json = ?, is_demo = 1 WHERE id = ?",
                (json.dumps(unevaluated_results(json.loads(run["model_ids"]))), run["id"]),
            )
        if conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0:
            model_ids = ["prithvi", "satmae", "croma", "resnet"]
            conn.execute(
                """INSERT INTO runs
                   (id, created_at, region_id, crop, season, dataset_id, model_ids, results_json, is_demo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                ("seed-2026", "2026-10-12T10:30:00+00:00", "punjab", "Wheat", "Rabi 2025–26", "sentinel2",
                 json.dumps(model_ids), json.dumps(unevaluated_results(model_ids))),
            )
        conn.commit()


def unevaluated_results(model_ids: list[str]) -> list[dict[str, Any]]:
    model_map = {model["id"]: model for model in MODELS}
    return [
        {
            "model_id": model_id,
            "model_name": model_map[model_id]["name"],
            "color": model_map[model_id]["color"],
            "accuracy": None,
            "f1": None,
            "iou": None,
            "kappa": None,
            "latency": None,
            "is_demo": True,
        }
        for model_id in model_ids
    ]


class EvaluationProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    dataset_release: str | None = None
    label_source_version: str | None = None
    acquisition_start: date | None = None
    acquisition_end: date | None = None
    split_id: str | None = None
    split_method: str | None = None
    model_revisions: dict[str, str] | None = None
    preprocessing: str | None = None
    input_resolution: str | None = None
    metric_config: str | None = None
    random_seed: int | None = Field(default=None, ge=0)
    code_revision: str | None = None
    hardware_runtime: str | None = None

    @model_validator(mode="after")
    def validate_provenance(self) -> "EvaluationProvenance":
        supplied = [value for value in self.model_dump().values() if value is not None and value != {}]
        if not supplied:
            raise ValueError("Provide at least one provenance value or omit provenance.")
        if self.acquisition_start and self.acquisition_end and self.acquisition_start > self.acquisition_end:
            raise ValueError("acquisition_start must not be after acquisition_end.")
        return self


class RunRequest(BaseModel):
    region_id: str
    crop: str
    season: str = "Rabi 2025–26"
    dataset_id: str = "sentinel2"
    model_ids: list[str] = Field(min_length=2, max_length=4)
    provenance: EvaluationProvenance | None = None


def run_disclosure_fields(provenance: dict[str, Any] | None) -> dict[str, Any]:
    if provenance:
        provenance_status = "declared_unverified"
        provenance_reason = "These values were declared with the setup and have not been independently verified."
    else:
        provenance_status = "not_recorded"
        provenance_reason = "No provenance values were recorded because inference was not run."
    return {
        "evaluation_status": "blocked",
        "evaluation_reason": EVALUATION_BLOCK_REASON,
        "provenance": provenance,
        "provenance_status": provenance_status,
        "provenance_reason": provenance_reason,
    }


app = FastAPI(title="AgriFM Compare API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/models")
def get_models() -> list[dict[str, Any]]:
    with closing(connect()) as conn:
        rows = conn.execute("SELECT * FROM models ORDER BY CASE id WHEN 'prithvi' THEN 0 WHEN 'satmae' THEN 1 WHEN 'croma' THEN 2 ELSE 3 END").fetchall()
    return [
        {
            key: row[key]
            for key in ("id", "name", "provider", "family", "parameters", "modality", "description", "color")
        } | {"is_demo": True}
        for row in rows
    ]


@app.get("/api/regions")
def get_regions() -> list[dict[str, Any]]:
    with closing(connect()) as conn:
        return [
            {**dict(row), "is_demo": True}
            for row in conn.execute("SELECT * FROM regions ORDER BY name")
        ]


@app.get("/api/datasets")
def get_datasets() -> list[dict[str, Any]]:
    with closing(connect()) as conn:
        return [
            {**dict(row), "is_demo": True}
            for row in conn.execute("SELECT * FROM datasets ORDER BY name")
        ]


@app.get("/api/crops")
def get_crops() -> dict[str, Any]:
    return {"items": CROPS, "is_demo": True}


@app.get("/api/runs")
def get_runs() -> list[dict[str, Any]]:
    with closing(connect()) as conn:
        rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
    return [
        ({
            **dict(row),
            "model_ids": json.loads(row["model_ids"]),
            "results": json.loads(row["results_json"]),
            "is_demo": True,
        } | run_disclosure_fields(json.loads(row["provenance_json"]) if row["provenance_json"] else None))
        for row in rows
    ]


@app.post("/api/runs")
def create_run(request: RunRequest) -> dict[str, Any]:
    if len(set(request.model_ids)) != len(request.model_ids):
        raise HTTPException(status_code=422, detail="Choose each model only once.")
    if request.crop not in CROPS:
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

    results = unevaluated_results(request.model_ids)
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
        **run_disclosure_fields(provenance),
    }
    with closing(connect()) as conn:
        conn.execute(
            """INSERT INTO runs
               (id, created_at, region_id, crop, season, dataset_id, model_ids, results_json, is_demo, provenance_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (run["id"], run["created_at"], run["region_id"], run["crop"], run["season"], run["dataset_id"],
             json.dumps(run["model_ids"]), json.dumps(results), json.dumps(provenance) if provenance else None),
        )
        conn.commit()
    return run


@app.get("/api/dashboard")
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


@app.get("/api/methodology")
def get_methodology() -> dict[str, Any]:
    return {
        "is_demo": True,
        "metrics": [
            {"name": "F1 score", "unit": "%", "description": "Harmonic mean of precision and recall; proposed as a primary ranking metric after a documented evaluation, but not currently calculated or used to rank models."},
            {"name": "Intersection over Union", "unit": "%", "description": "Overlap between predicted and reference crop masks."},
            {"name": "Overall accuracy", "unit": "%", "description": "Fraction of correctly classified pixels across the evaluation sample."},
            {"name": "Cohen's kappa", "unit": "0–1", "description": "Chance-corrected agreement between predictions and reference labels."},
            {"name": "Inference time", "unit": "ms / tile", "description": "Report only after measuring with documented hardware, batch size, and runtime conditions."},
        ],
        "protocol": [
            "Choose a region, crop, season, dataset, and at least two candidate models.",
            "The same region and crop context is applied to every selected model for a within-run comparison.",
            "This prototype does not execute models; performance metrics remain unevaluated until Phase-II.",
            "For a publishable result, calculate metrics on a documented, held-out, ground-truth-labelled dataset.",
        ],
    }
