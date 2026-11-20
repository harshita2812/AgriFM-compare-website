from __future__ import annotations

import random
from collections.abc import Iterable, Mapping, Sequence
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


def _confusion_matrix(
    predictions: Sequence[Any] | Iterable[Any],
    labels: Sequence[Any] | Iterable[Any],
    class_ids: Sequence[Any],
) -> list[list[int]]:
    predicted = flatten_values(predictions)
    expected = flatten_values(labels)
    if len(predicted) != len(expected):
        raise ValueError("Prediction and label arrays must contain the same number of cells.")
    if not predicted:
        raise ValueError("Prediction and label arrays must not be empty.")
    try:
        if not class_ids or len(set(class_ids)) != len(class_ids):
            raise ValueError("Class IDs must be a non-empty sequence of unique values.")
    except TypeError as error:
        raise ValueError("Class IDs must be hashable values.") from error

    class_indexes = {class_id: index for index, class_id in enumerate(class_ids)}
    matrix = [[0 for _ in class_ids] for _ in class_ids]
    for actual, prediction in zip(expected, predicted):
        try:
            actual_index = class_indexes[actual]
            prediction_index = class_indexes[prediction]
        except (KeyError, TypeError) as error:
            invalid = error.args[0] if error.args else "unknown value"
            raise ValueError(f"Prediction or label value is not a declared class ID: {invalid!r}.") from error
        matrix[actual_index][prediction_index] += 1
    return matrix


def _metrics_from_confusion(
    matrix: list[list[int]],
    class_ids: Sequence[Any],
    class_names: Sequence[str],
) -> dict[str, Any]:
    total = sum(sum(row) for row in matrix)
    correct = sum(matrix[index][index] for index in range(len(class_ids)))
    per_class = []
    iou_values = []
    f1_values = []

    for index, (class_id, class_name) in enumerate(zip(class_ids, class_names)):
        true_positive = matrix[index][index]
        support = sum(matrix[index])
        predicted_support = sum(row[index] for row in matrix)
        false_positive = predicted_support - true_positive
        false_negative = support - true_positive
        iou_denominator = true_positive + false_positive + false_negative
        f1_denominator = 2 * true_positive + false_positive + false_negative
        iou = true_positive / iou_denominator if iou_denominator else None
        f1 = 2 * true_positive / f1_denominator if f1_denominator else None
        precision = true_positive / predicted_support if predicted_support else None
        recall = true_positive / support if support else None
        if iou is not None:
            iou_values.append(iou)
        if f1 is not None:
            f1_values.append(f1)
        per_class.append({
            "class_id": class_id,
            "class_name": class_name,
            "support": support,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "iou": iou,
        })

    return {
        "overall_accuracy": correct / total if total else None,
        "mIoU": sum(iou_values) / len(iou_values) if iou_values else None,
        "macro_f1": sum(f1_values) / len(f1_values) if f1_values else None,
        "class_metrics": per_class,
        "confusion_matrix": matrix,
    }


def multiclass_segmentation_metrics(
    predictions: Sequence[Any] | Iterable[Any],
    labels: Sequence[Any] | Iterable[Any],
    class_ids: Sequence[Any],
    class_names: Sequence[str] | None = None,
) -> dict[str, Any]:
    names = list(class_names) if class_names is not None else [str(value) for value in class_ids]
    if len(names) != len(class_ids) or len(set(names)) != len(names):
        raise ValueError("Class names must be unique and match the declared class IDs.")
    matrix = _confusion_matrix(predictions, labels, class_ids)
    return _metrics_from_confusion(matrix, class_ids, names)


def _percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _confidence_interval(values: list[float], confidence_level: float) -> dict[str, Any]:
    tail = (1 - confidence_level) / 2
    return {
        "lower": _percentile(values, tail),
        "upper": _percentile(values, 1 - tail),
        "valid_resamples": len(values),
    }


def block_bootstrap_confidence_intervals(
    blocks: Mapping[str, tuple[Sequence[Any] | Iterable[Any], Sequence[Any] | Iterable[Any]]],
    class_ids: Sequence[Any],
    class_names: Sequence[str] | None = None,
    n_resamples: int = 1000,
    seed: int = 42,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    if len(blocks) < 2:
        raise ValueError("Block bootstrap requires at least two spatial blocks.")
    if not isinstance(n_resamples, int) or isinstance(n_resamples, bool) or n_resamples < 1:
        raise ValueError("n_resamples must be a positive integer.")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative integer.")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between 0 and 1.")
    names = list(class_names) if class_names is not None else [str(value) for value in class_ids]
    if len(names) != len(class_ids) or len(set(names)) != len(names):
        raise ValueError("Class names must be unique and match the declared class IDs.")

    block_ids = list(blocks)
    if any(not isinstance(block_id, str) or not block_id.strip() for block_id in block_ids):
        raise ValueError("Spatial block IDs must be non-empty strings.")
    block_ids.sort()
    block_matrices = []
    for block_id in block_ids:
        predictions, labels = blocks[block_id]
        block_matrices.append(_confusion_matrix(predictions, labels, class_ids))

    rng = random.Random(seed)
    sampled_values: dict[str, list[float]] = {
        "overall_accuracy": [],
        "mIoU": [],
        "macro_f1": [],
    }
    per_class_values = {
        name: {"iou": [], "f1": []}
        for name in names
    }
    for _ in range(n_resamples):
        matrix = [[0 for _ in class_ids] for _ in class_ids]
        for block_index in (rng.randrange(len(block_ids)) for _ in block_ids):
            source = block_matrices[block_index]
            for row_index, row in enumerate(source):
                for column_index, count in enumerate(row):
                    matrix[row_index][column_index] += count
        metrics = _metrics_from_confusion(matrix, class_ids, names)
        for key in sampled_values:
            value = metrics[key]
            if value is not None:
                sampled_values[key].append(value)
        for result in metrics["class_metrics"]:
            for key in ("iou", "f1"):
                value = result[key]
                if value is not None:
                    per_class_values[result["class_name"]][key].append(value)

    total_matrix = [[0 for _ in class_ids] for _ in class_ids]
    for source in block_matrices:
        for row_index, row in enumerate(source):
            for column_index, count in enumerate(row):
                total_matrix[row_index][column_index] += count
    return {
        "seed": seed,
        "n_blocks": len(block_ids),
        "n_resamples": n_resamples,
        "confidence_level": confidence_level,
        "point_estimate": _metrics_from_confusion(total_matrix, class_ids, names),
        "confidence_intervals": {
            **{
                key: _confidence_interval(values, confidence_level)
                for key, values in sampled_values.items()
            },
            "per_class": {
                name: {
                    key: _confidence_interval(values, confidence_level)
                    for key, values in metrics.items()
                }
                for name, metrics in per_class_values.items()
            },
        },
    }
