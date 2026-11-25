from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = Path(r"C:\Users\HARSHITA\Downloads\crop_dataset_rag_ready.json")
DEFAULT_ARTIFACT = ROOT / "ml" / "artifacts" / "crop_recommendation.joblib"

PATTERNS = {
    "nitrogen": r"nitrogen is ([+-]?(?:\d+(?:\.\d*)?|\.\d+))",
    "phosphorus": r"phosphorus is ([+-]?(?:\d+(?:\.\d*)?|\.\d+))",
    "potassium": r"potassium is ([+-]?(?:\d+(?:\.\d*)?|\.\d+))",
    "temperature": r"temperature is around ([+-]?(?:\d+(?:\.\d*)?|\.\d+))",
    "humidity": r"humidity ([+-]?(?:\d+(?:\.\d*)?|\.\d+))",
    "ph": r"Soil pH should be around ([+-]?(?:\d+(?:\.\d*)?|\.\d+))",
    "rainfall": r"rainfall about ([+-]?(?:\d+(?:\.\d*)?|\.\d+))",
}


def load_dataset(path: Path) -> tuple[list[list[float]], list[str]]:
    records = json.loads(path.read_text(encoding="utf-8"))
    features: list[list[float]] = []
    labels: list[str] = []

    for record in records:
        text = record["text"]
        values: dict[str, float] = {}
        for name, pattern in PATTERNS.items():
            match = re.search(pattern, text)
            if not match:
                raise ValueError(f"Could not parse {name} from record: {text}")
            values[name] = float(match.group(1))

        crop = record["metadata"]["crop"]
        features.append([values[name] for name in PATTERNS])
        labels.append(crop)

    return features, labels


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a crop recommendation classifier")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    features, labels = load_dataset(args.dataset)
    x_train, x_test, y_train, y_test = train_test_split(
        features, labels, test_size=0.2, random_state=args.seed, stratify=labels
    )

    model = Pipeline([
        ("scale", StandardScaler()),
        ("classifier", RandomForestClassifier(
            n_estimators=300,
            random_state=args.seed,
            n_jobs=-1,
            class_weight="balanced",
        )),
    ])
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    accuracy = accuracy_score(y_test, predictions)

    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.artifact)
    metadata = {
        "model_type": "RandomForestClassifier",
        "feature_names": list(PATTERNS),
        "classes": sorted(set(labels)),
        "dataset": str(args.dataset),
        "dataset_rows": len(labels),
        "test_rows": len(y_test),
        "seed": args.seed,
        "accuracy": accuracy,
    }
    args.artifact.with_suffix(".json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    print(json.dumps(metadata, indent=2))
    print(classification_report(y_test, predictions))


if __name__ == "__main__":
    main()
