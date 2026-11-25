import json
from collections.abc import Callable, Sequence
from contextlib import closing
from typing import Any

from apps.api.db import connect


DATA_SOURCES = [
    ("open-meteo", "Open-Meteo", "Open-Meteo Contributors", "Weather forecast",
     "Selected region", "Live public data", "No key required", "https://open-meteo.com/"),
    ("copernicus-sentinel", "Sentinel-2 / Sentinel-1", "Copernicus / ESA",
     "Satellite imagery", "Global satellite archive", "Catalog only", "Credentials may be required",
     "https://dataspace.copernicus.eu/"),
    ("crop-calendar", "Regional crop calendar", "Illustrative project metadata",
     "Seasonal context", "India", "Reference only", "No live service",
     None),
    ("sickle", "SICKLE", "SICKLE authors / IIIT-Delhi",
     "Satellite imagery and crop annotations", "Cauvery Delta, Tamil Nadu, India",
     "Access-gated reference", "Dataset access request required",
     "https://github.com/Depanshu-Sani/SICKLE"),
]


def seed_database(
    models: Sequence[dict[str, Any]],
    regions: Sequence[dict[str, Any]],
    datasets: Sequence[dict[str, Any]],
    unevaluated_results: Callable[[list[str]], list[dict[str, Any]]],
) -> None:
    with closing(connect()) as conn:
        conn.execute("UPDATE models SET values_json = '{}', is_demo = TRUE")
        conn.execute("UPDATE regions SET is_demo = TRUE")
        conn.execute("UPDATE datasets SET is_demo = TRUE")
        for model in models:
            conn.execute(
                """INSERT INTO models
                   (id, name, provider, family, parameters, modality, description, color, values_json, is_demo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}', TRUE)
                   ON CONFLICT DO NOTHING""",
                tuple(model[key] for key in ("id", "name", "provider", "family", "parameters", "modality", "description", "color")),
            )
        for region in regions:
            conn.execute(
                """INSERT INTO regions (id, name, state, lat, lon, is_demo)
                   VALUES (?, ?, ?, ?, ?, TRUE) ON CONFLICT DO NOTHING""",
                tuple(region[key] for key in ("id", "name", "state", "lat", "lon")),
            )
        for dataset in datasets:
            conn.execute(
                """INSERT INTO datasets
                   (id, name, provider, resolution, coverage, type, status, is_demo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, TRUE)
                   ON CONFLICT DO NOTHING""",
                tuple(dataset[key] for key in ("id", "name", "provider", "resolution", "coverage", "type", "status")),
            )
            conn.execute("UPDATE datasets SET status = ? WHERE id = ?", (dataset["status"], dataset["id"]))
        for source in DATA_SOURCES:
            conn.execute(
                """INSERT INTO data_sources
                   (id, name, provider, kind, coverage, status, access_type, source_url, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                   ON CONFLICT DO NOTHING""",
                source,
            )
        for run in conn.execute("SELECT id, model_ids FROM runs").fetchall():
            conn.execute(
                "UPDATE runs SET results_json = ?, is_demo = TRUE WHERE id = ?",
                (json.dumps(unevaluated_results(json.loads(run["model_ids"]))), run["id"]),
            )
        if conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0:
            model_ids = ["prithvi", "satmae", "croma", "resnet"]
            conn.execute(
                """INSERT INTO runs
                   (id, created_at, region_id, crop, season, dataset_id, model_ids, results_json, is_demo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, TRUE)""",
                ("seed-2026", "2026-10-12T10:30:00+00:00", "punjab", "Wheat", "Rabi 2025–26", "sentinel2",
                 json.dumps(model_ids), json.dumps(unevaluated_results(model_ids))),
            )
        conn.commit()
