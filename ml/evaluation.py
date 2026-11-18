from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any


def flatten_values(values: Iterable[Any]) -> list[Any]:
    flattened: list[Any] = []
    for value in values:
        if isinstance(value, (list, tuple)):
            flattened.extend(flatten_values(value))
        else:
            flattened.append(value)
    return flattened


def segmentation_metrics(
    predictions: Sequence[Any] | Iterable[Any],
    labels: Sequence[Any] | Iterable[Any],
    positive: Any = 1,
) -> dict[str, float]:
    predicted = flatten_values(predictions)
    expected = flatten_values(labels)
    if len(predicted) != len(expected):
        raise ValueError("Prediction and label arrays must contain the same number of cells.")
    if not predicted:
        raise ValueError("Prediction and label arrays must not be empty.")

    classes = list(dict.fromkeys([*predicted, *expected]))
    confusion = {
        actual: {predicted_class: 0 for predicted_class in classes}
        for actual in classes
    }
    for actual, prediction in zip(expected, predicted):
        confusion[actual][prediction] += 1

    tp = sum(1 for actual, prediction in zip(expected, predicted)
             if actual == positive and prediction == positive)
    fp = sum(1 for actual, prediction in zip(expected, predicted)
             if actual != positive and prediction == positive)
    fn = sum(1 for actual, prediction in zip(expected, predicted)
             if actual == positive and prediction != positive)
    tn = sum(1 for actual, prediction in zip(expected, predicted)
             if actual != positive and prediction != positive)

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    accuracy = (tp + tn) / len(expected)

    total = len(expected)
    actual_positive = tp + fn
    actual_negative = tn + fp
    predicted_positive = tp + fp
    predicted_negative = tn + fn
    expected_agreement = (
        (actual_positive * predicted_positive)
        + (actual_negative * predicted_negative)
    ) / (total * total)
    kappa = (
        (accuracy - expected_agreement) / (1 - expected_agreement)
        if 1 - expected_agreement
        else 1.0
    )
    return {
        "accuracy": accuracy,
        "f1": f1,
        "iou": iou,
        "kappa": kappa,
    }
