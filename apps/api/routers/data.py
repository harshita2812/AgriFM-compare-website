import json
from contextlib import closing
from typing import Any

from fastapi import APIRouter, HTTPException

from apps.api import main as core
from apps.api.asset_inventory import build_readiness
from apps.api.db import connect


router = APIRouter()


@router.get("/api/data/sources")
def get_data_sources() -> dict[str, Any]:
    with closing(connect()) as conn:
        sources = [dict(row) for row in conn.execute(
            "SELECT * FROM data_sources ORDER BY name"
        ).fetchall()]
        jobs = [dict(row) for row in conn.execute(
            "SELECT * FROM ingestion_jobs ORDER BY created_at DESC LIMIT 20"
        ).fetchall()]
        assets = []
        for row in conn.execute(
            "SELECT * FROM data_assets ORDER BY fetched_at DESC"
        ).fetchall():
            asset = dict(row)
            asset["payload"] = json.loads(asset.pop("payload_json"))
            assets.append(asset)
    return {"sources": sources, "assets": assets, "jobs": jobs, "is_demo": False}


@router.get("/api/data/readiness")
def get_data_readiness() -> dict[str, Any]:
    return build_readiness(core.MODELS, core.REGIONS, core.CROPS)


@router.post("/api/data/weather/refresh")
def refresh_region_weather(request: core.WeatherRefreshRequest) -> dict[str, Any]:
    return core.refresh_weather(request.region_id, request.forecast_days)


@router.get("/api/data/weather/{region_id}")
def get_cached_weather(region_id: str) -> dict[str, Any]:
    core.get_region_or_404(region_id)
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


@router.post("/api/farmer/advisory")
def get_farmer_advisory(request: core.FarmerAdvisoryRequest) -> dict[str, Any]:
    if request.crop not in core.CROPS:
        raise HTTPException(status_code=422, detail="Select a supported crop.")
    region = core.get_region_or_404(request.region_id)
    refresh = core.refresh_weather(request.region_id, request.forecast_days)

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
        rain_en = "Heavy rain may reduce spraying opportunities; plan drainage and delay fertilizer application if runoff is likely."
        rain_hi = "भारी बारिश से छिड़काव प्रभावित हो सकता है। जल निकासी देखें और बहाव की संभावना हो तो उर्वरक रोकें।"
    elif total_rain is not None and total_rain >= 15:
        rain_en = "Some rain is expected; consider naturally available soil moisture before irrigation."
        rain_hi = "कुछ बारिश की संभावना है। सिंचाई से पहले मिट्टी की प्राकृतिक नमी देखें।"
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
            "condition": core.WEATHER_CODE_TEXT.get(code, "Not reported"),
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
