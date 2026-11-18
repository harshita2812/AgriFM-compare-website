from __future__ import annotations

import json
import os
import sqlite3
import hashlib
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypedDict
from uuid import uuid4
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, model_validator


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.environ.get("AGRIFM_DB_PATH", ROOT / "backend" / "agrifm.db"))
WEATHER_API_BASE = os.environ.get(
    "AGRIFM_WEATHER_API_URL",
    "https://api.open-meteo.com/v1/forecast",
)

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
            CREATE TABLE IF NOT EXISTS data_sources (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                kind TEXT NOT NULL,
                coverage TEXT NOT NULL,
                status TEXT NOT NULL,
                access_type TEXT NOT NULL,
                source_url TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS data_assets (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                region_id TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES data_sources(id)
            );
            CREATE TABLE IF NOT EXISTS ingestion_jobs (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                region_id TEXT,
                asset_id TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                detail TEXT,
                FOREIGN KEY(source_id) REFERENCES data_sources(id)
            );
            CREATE TABLE IF NOT EXISTS evaluation_jobs (
                id TEXT PRIMARY KEY,
                run_id TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                manifest_json TEXT,
                result_json TEXT,
                detail TEXT,
                provenance_json TEXT
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
        data_sources = [
            ("open-meteo", "Open-Meteo", "Open-Meteo Contributors", "Weather forecast",
             "Selected region", "Live public data", "No key required", "https://open-meteo.com/"),
            ("copernicus-sentinel", "Sentinel-2 / Sentinel-1", "Copernicus / ESA",
             "Satellite imagery", "Global satellite archive", "Catalog only", "Credentials may be required",
             "https://dataspace.copernicus.eu/"),
            ("crop-calendar", "Regional crop calendar", "Illustrative project metadata",
             "Seasonal context", "India", "Reference only", "No live service",
             None),
        ]
        for source in data_sources:
            conn.execute(
                """INSERT OR IGNORE INTO data_sources
                   (id, name, provider, kind, coverage, status, access_type, source_url, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
                source,
            )
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


class WeatherRefreshRequest(BaseModel):
    region_id: str
    forecast_days: int = Field(default=7, ge=1, le=16)


class FarmerAdvisoryRequest(BaseModel):
    region_id: str
    crop: str
    forecast_days: int = Field(default=7, ge=1, le=16)
    language: Literal["en", "hi"] = "en"


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


WEATHER_CODE_TEXT = {
    0: "Clear",
    1: "Mostly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    71: "Light snow",
    80: "Rain showers",
    81: "Rain showers",
    82: "Heavy rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Severe thunderstorm",
}


def get_region_or_404(region_id: str) -> sqlite3.Row:
    with closing(connect()) as conn:
        region = conn.execute("SELECT * FROM regions WHERE id = ?", (region_id,)).fetchone()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found.")
    return region


def refresh_weather(region_id: str, forecast_days: int) -> dict[str, Any]:
    region = get_region_or_404(region_id)
    job_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    with closing(connect()) as conn:
        conn.execute(
            """INSERT INTO ingestion_jobs
               (id, source_id, region_id, asset_id, status, created_at, completed_at, detail)
               VALUES (?, 'open-meteo', ?, NULL, 'running', ?, NULL, NULL)""",
            (job_id, region_id, created_at),
        )
        conn.commit()

    query = urlencode({
        "latitude": region["lat"],
        "longitude": region["lon"],
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum,weather_code",
        "forecast_days": forecast_days,
        "timezone": "Asia/Kolkata",
    })
    try:
        request = Request(f"{WEATHER_API_BASE}?{query}", headers={"User-Agent": "AgriFM-Compare/1.0"})
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        detail = f"Weather source request failed: {error}"
        with closing(connect()) as conn:
            conn.execute(
                """UPDATE ingestion_jobs
                   SET status = 'failed', completed_at = ?, detail = ?
                   WHERE id = ?""",
                (datetime.now(timezone.utc).isoformat(), detail, job_id),
            )
            conn.commit()
        raise HTTPException(status_code=502, detail=detail)

    fetched_at = datetime.now(timezone.utc).isoformat()
    asset_id = str(uuid4())
    normalized = {
        "source": "Open-Meteo",
        "source_url": "https://open-meteo.com/",
        "timezone": payload.get("timezone", "Asia/Kolkata"),
        "latitude": payload.get("latitude", region["lat"]),
        "longitude": payload.get("longitude", region["lon"]),
        "daily": payload.get("daily", {}),
        "forecast_days": forecast_days,
        "fetched_at": fetched_at,
    }
    with closing(connect()) as conn:
        conn.execute(
            """INSERT INTO data_assets
               (id, source_id, region_id, asset_type, payload_json, fetched_at, status)
               VALUES (?, 'open-meteo', ?, 'weather_forecast', ?, ?, 'ready')""",
            (asset_id, region_id, json.dumps(normalized), fetched_at),
        )
        conn.execute(
            """UPDATE data_sources SET status = 'Live public data', updated_at = ?
               WHERE id = 'open-meteo'""",
            (fetched_at,),
        )
        conn.execute(
            """UPDATE ingestion_jobs
               SET status = 'ready', asset_id = ?, completed_at = ?, detail = ?
               WHERE id = ?""",
            (asset_id, fetched_at, "Weather forecast downloaded and cached.", job_id),
        )
        conn.commit()
    return {
        "job_id": job_id,
        "asset_id": asset_id,
        "region_id": region_id,
        "region_name": region["name"],
        "status": "ready",
        "asset": normalized,
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


@app.get("/api/data/sources")
def get_data_sources() -> dict[str, Any]:
    with closing(connect()) as conn:
        sources = [dict(row) for row in conn.execute(
            "SELECT * FROM data_sources ORDER BY name"
        ).fetchall()]
        jobs = [dict(row) for row in conn.execute(
            "SELECT * FROM ingestion_jobs ORDER BY created_at DESC LIMIT 20"
        ).fetchall()]
    return {"sources": sources, "jobs": jobs, "is_demo": False}


@app.post("/api/data/weather/refresh")
def refresh_region_weather(request: WeatherRefreshRequest) -> dict[str, Any]:
    return refresh_weather(request.region_id, request.forecast_days)


@app.get("/api/data/weather/{region_id}")
def get_cached_weather(region_id: str) -> dict[str, Any]:
    get_region_or_404(region_id)
    with closing(connect()) as conn:
        row = conn.execute(
            """SELECT * FROM data_assets
               WHERE region_id = ? AND asset_type = 'weather_forecast' AND status = 'ready'
               ORDER BY fetched_at DESC LIMIT 1""",
            (region_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No weather asset has been ingested for this region.")
    return {
        "asset_id": row["id"],
        "region_id": row["region_id"],
        "status": row["status"],
        "asset": json.loads(row["payload_json"]),
    }


@app.post("/api/farmer/advisory")
def get_farmer_advisory(request: FarmerAdvisoryRequest) -> dict[str, Any]:
    if request.crop not in CROPS:
        raise HTTPException(status_code=422, detail="Select a supported crop.")
    region = get_region_or_404(request.region_id)
    try:
        refresh = refresh_weather(request.region_id, request.forecast_days)
    except HTTPException:
        raise

    daily = refresh["asset"].get("daily", {})
    dates = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    rain_values = daily.get("precipitation_sum", [])
    codes = daily.get("weather_code", [])
    valid_temps = [value for value in max_temps if isinstance(value, (int, float))]
    valid_rain = [value for value in rain_values if isinstance(value, (int, float))]
    hottest = max(valid_temps) if valid_temps else None
    total_rain = round(sum(valid_rain), 1) if valid_rain else None

    if hottest is not None and hottest >= 38:
        heat_en = "High heat is forecast. Schedule irrigation or field work early morning or evening."
        heat_hi = "अधिक गर्मी का पूर्वानुमान है। सिंचाई या खेत का काम सुबह जल्दी या शाम को करें।"
    elif hottest is not None and hottest >= 34:
        heat_en = "Warm conditions are forecast. Check soil moisture before irrigation."
        heat_hi = "गरम मौसम का पूर्वानुमान है। सिंचाई से पहले मिट्टी में नमी देखें।"
    else:
        heat_en = "No unusually high temperature is forecast in this period."
        heat_hi = "इस अवधि में सामान्य से अधिक गर्मी का पूर्वानुमान नहीं है।"

    if total_rain is not None and total_rain >= 40:
        rain_en = f"Heavy rain may reduce spraying opportunities; plan drainage and delay fertilizer application if runoff is likely."
        rain_hi = f"भारी बारिश से छिड़काव प्रभावित हो सकता है। जल निकासी देखें और बहाव की संभावना हो तो उर्वरक रोकें।"
    elif total_rain is not None and total_rain >= 15:
        rain_en = f"Some rain is expected; consider naturally available soil moisture before irrigation."
        rain_hi = f"कुछ बारिश की संभावना है। सिंचाई से पहले मिट्टी की प्राकृतिक नमी देखें।"
    else:
        rain_en = "Low rainfall is forecast; monitor soil moisture and follow local irrigation guidance."
        rain_hi = "कम बारिश का पूर्वानुमान है। मिट्टी की नमी जांचें और स्थानीय सिंचाई सलाह लें।"

    summaries = []
    for index, date_value in enumerate(dates):
        code = codes[index] if index < len(codes) else None
        summaries.append({
            "date": date_value,
            "temperature_max_c": max_temps[index] if index < len(max_temps) else None,
            "temperature_min_c": min_temps[index] if index < len(min_temps) else None,
            "precipitation_mm": rain_values[index] if index < len(rain_values) else None,
            "condition": WEATHER_CODE_TEXT.get(code, "Not reported"),
        })

    return {
        "region_id": region["id"],
        "region_name": region["name"],
        "crop": request.crop,
        "language": request.language,
        "source": "Open-Meteo",
        "asset_id": refresh["asset_id"],
        "fetched_at": refresh["asset"]["fetched_at"],
        "forecast_days": request.forecast_days,
        "summary": {
            "hottest_day_c": hottest,
            "total_rainfall_mm": total_rain,
        },
        "advisories": [
            heat_en if request.language == "en" else heat_hi,
            rain_en if request.language == "en" else rain_hi,
            ("Keep inputs within the label, and consult a local agriculture officer for crop-specific decisions."
             if request.language == "en"
             else "इनपुट लेबल के अनुसार रखें और फसल-विशिष्ट निर्णय के लिए स्थानीय कृषि अधिकारी से सलाह लें."),
        ],
        "disclaimer": (
            "Planning aid based on a public weather forecast, not a certified agronomic recommendation."
            if request.language == "en"
            else "यह सार्वजनिक मौसम पूर्वानुमान पर आधारित योजना सहायता है, प्रमाणित कृषि सलाह नहीं।"
        ),
        "daily": summaries,
    }


@app.post("/api/evaluations/jobs")
def create_evaluation_job(request: RunRequest) -> dict[str, Any]:
    run = create_run(request)
    job_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    detail = (
        "Evaluation blocked: no supplied manifest or authorized assets were found. "
        "No model was loaded and no metrics were calculated."
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
                json.dumps(unevaluated_results(request.model_ids)),
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
        "results": unevaluated_results(request.model_ids),
        "detail": detail,
        "provenance_status": "declared_unverified" if provenance else "not_recorded",
    }


@app.get("/api/evaluations/jobs")
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


@app.post("/api/evaluations/jobs/{job_id}/execute")
def execute_evaluation_job(job_id: str) -> dict[str, Any]:
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM evaluation_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Evaluation job not found.")

    manifest_path = os.environ.get("AGRIFM_EVALUATION_MANIFEST")
    if not manifest_path:
        detail = (
            "Evaluation blocked: AGRIFM_EVALUATION_MANIFEST is not configured. "
            "No authorized checkpoints or labels were supplied."
        )
    else:
        path = Path(manifest_path)
        if not path.is_absolute():
            path = ROOT / path
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
