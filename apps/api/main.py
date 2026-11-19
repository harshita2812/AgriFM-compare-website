from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager, closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypedDict
from uuid import uuid4
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.api.asset_inventory import sync_locked_assets
from apps.api.db import connect, migrate_legacy_schema
from apps.api.seed import seed_database


ROOT = Path(__file__).resolve().parents[2]
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

DatasetStatus = Literal["Metadata only", "Reference", "Downloaded & verified"]


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
    {"id": "cropharvest", "name": "CropHarvest labels (candidate)", "provider": "CropHarvest contributors", "resolution": "Mixed-source polygons", "coverage": "Global; exact study-region overlap unverified", "type": "Binary and generalized crop labels", "status": "Metadata only"},
]

EVALUATION_BLOCK_REASON = (
    "This checkout has no wired inference pipeline. No authorized model checkpoints, "
    "ground-truth agricultural labels, or documented split protocol were found; inference was not run."
)


def init_db() -> None:
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    migrate_legacy_schema()
    seed_database(MODELS, REGIONS, DATASETS, unevaluated_results)
    sync_locked_assets()


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


def get_region_or_404(region_id: str) -> Any:
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


from apps.api.routers import catalog, data, evaluations


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    from apps.api.scheduling import start_scheduler

    scheduler = start_scheduler()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="AgriFM Compare API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(catalog.router)
app.include_router(data.router)
app.include_router(evaluations.router)
