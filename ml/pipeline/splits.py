from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def build_leave_one_region_out_splits(
    samples: list[dict[str, Any]],
    region_ids: list[str],
    spatial_folds: int = 5,
    seed: int = 42,
) -> dict[str, Any]:
    if not isinstance(spatial_folds, int) or spatial_folds < 2:
        raise ValueError("spatial_folds must be an integer of at least two.")
    if not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer.")
    if not region_ids or len(set(region_ids)) != len(region_ids):
        raise ValueError("region_ids must be a non-empty sequence of unique IDs.")

    normalized_samples = []
    sample_ids = set()
    region_set = set(region_ids)
    for sample in samples:
        sample_id = sample.get("sample_id")
        region_id = sample.get("region_id")
        block_id = sample.get("spatial_block_id")
        if not isinstance(sample_id, str) or not sample_id.strip():
            raise ValueError("Every sample must have a non-empty sample_id.")
        if sample_id in sample_ids:
            raise ValueError(f"Duplicate sample_id: {sample_id}.")
        if region_id not in region_set:
            raise ValueError(f"Sample {sample_id} has an unknown region_id: {region_id!r}.")
        if not isinstance(block_id, str) or not block_id.strip():
            raise ValueError(f"Sample {sample_id} must have a non-empty spatial_block_id.")
        sample_ids.add(sample_id)
        normalized_samples.append({
            "sample_id": sample_id,
            "region_id": region_id,
            "spatial_block_id": block_id,
        })

    by_region: dict[str, list[dict[str, str]]] = defaultdict(list)
    for sample in normalized_samples:
        by_region[sample["region_id"]].append(sample)
    missing_regions = [region_id for region_id in region_ids if not by_region[region_id]]
    if missing_regions:
        raise ValueError(f"No samples are available for regions: {', '.join(missing_regions)}.")

    outer_folds = []
    for held_out_region in region_ids:
        outer_train = [
            sample for sample in normalized_samples
            if sample["region_id"] != held_out_region
        ]
        outer_test = [
            sample for sample in normalized_samples
            if sample["region_id"] == held_out_region
        ]
        grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
        for sample in outer_train:
            group = (sample["region_id"], sample["spatial_block_id"])
            grouped[group].append(sample["sample_id"])

        groups = list(grouped)
        if len(groups) < spatial_folds:
            raise ValueError(
                f"Leave-one-region-out fold {held_out_region!r} has {len(groups)} training "
                f"spatial blocks; at least {spatial_folds} are required."
            )
        ranked_groups = sorted(
            groups,
            key=lambda group: (
                -len(grouped[group]),
                hashlib.sha256(
                    f"{seed}\0{group[0]}\0{group[1]}".encode("utf-8")
                ).digest(),
            ),
        )
        validation_groups: list[list[tuple[str, str]]] = [
            [] for _ in range(spatial_folds)
        ]
        fold_sizes = [0 for _ in range(spatial_folds)]
        for group in ranked_groups:
            fold_index = min(range(spatial_folds), key=lambda index: (fold_sizes[index], index))
            validation_groups[fold_index].append(group)
            fold_sizes[fold_index] += len(grouped[group])

        spatial_cv = []
        for fold_index, fold_groups in enumerate(validation_groups):
            validation_group_set = set(fold_groups)
            validation_ids = sorted(
                sample_id
                for group in fold_groups
                for sample_id in grouped[group]
            )
            train_ids = sorted(
                sample_id
                for group, group_sample_ids in grouped.items()
                if group not in validation_group_set
                for sample_id in group_sample_ids
            )
            spatial_cv.append({
                "fold": fold_index,
                "train_ids": train_ids,
                "validation_ids": validation_ids,
                "validation_blocks": [
                    {"region_id": region_id, "spatial_block_id": block_id}
                    for region_id, block_id in sorted(fold_groups)
                ],
            })

        outer_folds.append({
            "held_out_region": held_out_region,
            "train_ids": sorted(sample["sample_id"] for sample in outer_train),
            "test_ids": sorted(sample["sample_id"] for sample in outer_test),
            "spatial_cv": spatial_cv,
        })

    return {
        "schema_version": 1,
        "method": "leave_one_region_out_with_spatial_block_cv",
        "seed": seed,
        "spatial_folds": spatial_folds,
        "region_ids": list(region_ids),
        "sample_count": len(normalized_samples),
        "outer_folds": outer_folds,
    }


def split_file_bytes(split: dict[str, Any]) -> bytes:
    serialized = json.dumps(
        split,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (serialized + "\n").encode("utf-8")


def split_sha256(split: dict[str, Any]) -> str:
    return hashlib.sha256(split_file_bytes(split)).hexdigest()


def write_split_file(path: Path, split: dict[str, Any]) -> str:
    content = split_file_bytes(split)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()
