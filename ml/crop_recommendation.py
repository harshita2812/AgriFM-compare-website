from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib


ARTIFACT = Path(__file__).resolve().parent / "artifacts" / "crop_recommendation.joblib"
METADATA = ARTIFACT.with_suffix(".json")
_MODEL: Any = None


def predict(values: dict[str, float]) -> dict[str, Any]:
    global _MODEL
    if not ARTIFACT.exists():
        return {
            "available": False,
            "error": "Crop recommendation model artifact has not been trained.",
        }

    if _MODEL is None:
        _MODEL = joblib.load(ARTIFACT)

    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    feature_names = metadata["feature_names"]
    feature_row = [[values[name] for name in feature_names]]
    probabilities = _MODEL.predict_proba(feature_row)[0]
    ranked = sorted(
        zip(_MODEL.classes_, probabilities),
        key=lambda item: item[1],
        reverse=True,
    )

    return {
        "available": True,
        "recommended_crop": ranked[0][0],
        "confidence": round(float(ranked[0][1]), 4),
        "alternatives": [
            {"crop": crop, "confidence": round(float(probability), 4)}
            for crop, probability in ranked[1:4]
        ],
        "model": {
            "type": metadata["model_type"],
            "dataset_rows": metadata["dataset_rows"],
            "test_accuracy": metadata["accuracy"],
            "seed": metadata["seed"],
        },
    }
