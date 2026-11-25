from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = Path(r"C:\Users\HARSHITA\Downloads")
ARTIFACTS = Path(os.environ.get(
    "AGRIFM_ARTIFACT_ROOT",
    r"D:\AgriFM-assets\models\agrifm",
))


AGRonomic_FEATURES = [
    "Elevation_Data",
    "Canopy_Coverage",
    "NDVI",
    "SAVI",
    "Chlorophyll_Content",
    "Leaf_Area_Index",
    "Crop_Stress_Indicator",
    "Temperature",
    "Humidity",
    "Rainfall",
    "Wind_Speed",
    "Soil_Moisture",
    "Soil_pH",
    "Organic_Matter",
    "Pest_Hotspots",
    "Weed_Coverage",
    "Pest_Damage",
    "Crop_Growth_Stage",
    "Expected_Yield",
    "Crop_Health_Label",
]


def safe_read(path: Path, sep: str = ",") -> pd.DataFrame:
    if not path.exists():
        raise FileError(f"Missing dataset: {path}")
    return pd.read_csv(path, sep=sep, low_memory=False)


class FileError(FileNotFoundError):
    pass


def train_agriculture_model(seed: int) -> dict:
    path = DOWNLOADS / "agriculture_dataset.csv"
    frame = safe_read(path)
    missing_features = [name for name in AGRonomic_FEATURES if name not in frame.columns]
    if missing_features:
        raise ValueError(f"Missing agriculture features: {missing_features}")
    if "Crop_Type" not in frame.columns:
        raise ValueError("agriculture_dataset.csv does not contain Crop_Type")

    x = frame[AGRonomic_FEATURES]
    y = frame["Crop_Type"].astype(str)
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.20,
        random_state=seed,
        stratify=y,
    )
    model = ExtraTreesClassifier(
        n_estimators=200,
        max_depth=28,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=seed,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    accuracy = accuracy_score(y_test, predictions)
    report = classification_report(y_test, predictions, output_dict=True)

    joblib.dump(model, ARTIFACTS / "agriculture_crop_classifier.joblib")
    return {
        "task": "supervised_crop_type",
        "model_type": "ExtraTreesClassifier",
        "dataset": str(path),
        "dataset_rows": len(frame),
        "train_rows": len(x_train),
        "test_rows": len(x_test),
        "seed": seed,
        "features": AGRonomic_FEATURES,
        "classes": sorted(y.unique().tolist()),
        "class_counts": y.value_counts().sort_index().to_dict(),
        "test_accuracy": accuracy,
        "macro_f1": report["macro avg"]["f1-score"],
    }


def train_calendar_prior(seed: int) -> dict:
    monthly_path = DOWNLOADS / "india_crop_calendar_2018_monthly_features.csv"
    long_path = DOWNLOADS / "india_crop_calendar_2018_long.csv"
    frame = safe_read(monthly_path)
    long_frame = safe_read(long_path)
    frame = frame.merge(
        long_frame[["record_id", "crop_mapping_confidence"]],
        on="record_id",
        how="left",
    )

    eligible = frame[
        (frame["season_source"].eq("pdf"))
        & (frame["crop_mapping_confidence"].eq("high"))
        & (frame["row_quality"].eq("parsed"))
    ].copy()
    month_features = [name for name in frame.columns if name.startswith("sow_m") or name.startswith("harv_m")]
    categorical = ["state", "district", "season"]
    usable = eligible.dropna(subset=["crop"] + categorical)
    class_counts = usable["crop"].value_counts()
    usable = usable[usable["crop"].isin(class_counts[class_counts >= 2].index)]

    x = usable[categorical + month_features]
    y = usable["crop"].astype(str)
    if len(y) < 100:
        raise RuntimeError("Too few eligible district crop-calendar rows")

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.20,
        random_state=seed,
        stratify=y,
    )
    preprocessor = ColumnTransformer([
        ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical),
    ], remainder="passthrough")
    model = Pipeline([
        ("preprocess", preprocessor),
        ("classifier", RandomForestClassifier(
            n_estimators=300,
            max_depth=24,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
        )),
    ])
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    accuracy = accuracy_score(y_test, predictions)
    report = classification_report(y_test, predictions, output_dict=True, zero_division=0)

    joblib.dump(model, ARTIFACTS / "india_crop_calendar_prior.joblib")
    return {
        "task": "district_crop_calendar_prior",
        "model_type": "RandomForestClassifier",
        "dataset": str(monthly_path),
        "eligible_rows": len(usable),
        "train_rows": len(x_train),
        "test_rows": len(x_test),
        "seed": seed,
        "features": categorical + month_features,
        "classes": sorted(y.unique().tolist()),
        "test_accuracy": accuracy,
        "macro_f1": report["macro avg"]["f1-score"],
        "filters": [
            "season_source == pdf",
            "crop_mapping_confidence == high",
            "row_quality == parsed",
        ],
    }


def build_manifest(seed: int) -> dict:
    agriculture = train_agriculture_model(seed)
    calendar = train_calendar_prior(seed)
    sources = safe_read(DOWNLOADS / "sources_and_references.csv")
    qa = json.loads((DOWNLOADS / "qa_summary.json").read_text(encoding="utf-8"))
    return {
        "schema_version": 1,
        "seed": seed,
        "supervised_models": [agriculture, calendar],
        "provenance": {
            "source_registry": str(DOWNLOADS / "sources_and_references.csv"),
            "source_rows": len(sources),
            "qa_summary": qa,
            "supplementary_not_used_as_training_labels": [
                str(DOWNLOADS / "crop_dataset_rag_ready.json"),
                str(DOWNLOADS / "ifa_india_crop_calendar_monthly.csv"),
                str(DOWNLOADS / "ccfi_india_seasonal_activities.csv"),
            ],
            "duplicates_or_reference_only": [
                str(DOWNLOADS / "india_crop_calendar_2018_long.csv"),
                str(DOWNLOADS / "india_crop_calendar_2018_long.jsonl"),
                str(DOWNLOADS / "india_crop_calendar_2018_monthly_features.csv"),
                str(DOWNLOADS / "crop_calendar_gaul1.csv"),
            ],
            "gaul1_reason": "Global unit-level reference; not an India training file.",
            "crop_calendar_reason": "Calendar windows are priors, not observed phenology.",
            "agriculture_dataset_note": "Synthetic/field-feature dataset; validate with independent field observations before operational use.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the integrated agriculture models")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(args.seed)
    manifest_path = ARTIFACTS / "integrated_training_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
