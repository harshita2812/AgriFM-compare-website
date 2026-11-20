import hashlib
import tempfile
import unittest
from pathlib import Path

from ml.evaluation import (
    block_bootstrap_confidence_intervals,
    multiclass_segmentation_metrics,
)
from ml.pipeline.splits import (
    build_leave_one_region_out_splits,
    split_sha256,
    write_split_file,
)


class MulticlassMetricTests(unittest.TestCase):
    def test_multiclass_metrics_include_per_class_scores_and_macro_averages(self):
        metrics = multiclass_segmentation_metrics(
            predictions=[0, 1, 2, 2],
            labels=[0, 1, 1, 2],
            class_ids=[0, 1, 2],
            class_names=["Other", "Wheat", "Rice"],
        )

        self.assertAlmostEqual(metrics["overall_accuracy"], 0.75)
        self.assertAlmostEqual(metrics["mIoU"], 2 / 3)
        self.assertAlmostEqual(metrics["macro_f1"], 7 / 9)
        self.assertEqual(
            [item["class_name"] for item in metrics["class_metrics"]],
            ["Other", "Wheat", "Rice"],
        )
        self.assertAlmostEqual(metrics["class_metrics"][1]["iou"], 0.5)

    def test_multiclass_metrics_reject_values_outside_the_label_schema(self):
        with self.assertRaisesRegex(ValueError, "not a declared class ID"):
            multiclass_segmentation_metrics(
                predictions=[0, 3],
                labels=[0, 1],
                class_ids=[0, 1, 2],
            )

    def test_block_bootstrap_is_reproducible_and_reports_all_resamples(self):
        blocks = {
            "block-a": ([0, 1, 2], [0, 1, 2]),
            "block-b": ([0, 2, 2], [0, 1, 2]),
        }
        first = block_bootstrap_confidence_intervals(
            blocks,
            class_ids=[0, 1, 2],
            class_names=["Other", "Wheat", "Rice"],
            n_resamples=1000,
            seed=42,
        )
        second = block_bootstrap_confidence_intervals(
            blocks,
            class_ids=[0, 1, 2],
            class_names=["Other", "Wheat", "Rice"],
            n_resamples=1000,
            seed=42,
        )

        self.assertEqual(first, second)
        self.assertEqual(first["confidence_intervals"]["mIoU"]["valid_resamples"], 1000)
        self.assertEqual(first["seed"], 42)


class GeographicSplitTests(unittest.TestCase):
    REGIONS = ["punjab", "up", "maharashtra", "karnataka", "bihar"]

    def make_samples(self):
        return [
            {
                "sample_id": f"{region}-{block}-{tile}",
                "region_id": region,
                "spatial_block_id": block,
            }
            for region in self.REGIONS
            for block in ("block-a", "block-b", "block-c")
            for tile in (1, 2)
        ]

    def test_region_holdout_and_spatial_folds_have_no_group_leakage(self):
        samples = self.make_samples()
        split = build_leave_one_region_out_splits(
            samples,
            self.REGIONS,
            spatial_folds=3,
            seed=42,
        )
        by_id = {sample["sample_id"]: sample for sample in samples}

        self.assertEqual(len(split["outer_folds"]), len(self.REGIONS))
        for outer in split["outer_folds"]:
            self.assertFalse(set(outer["train_ids"]) & set(outer["test_ids"]))
            self.assertEqual(
                {by_id[sample_id]["region_id"] for sample_id in outer["test_ids"]},
                {outer["held_out_region"]},
            )
            self.assertNotIn(
                outer["held_out_region"],
                {by_id[sample_id]["region_id"] for sample_id in outer["train_ids"]},
            )
            for fold in outer["spatial_cv"]:
                train_groups = {
                    (by_id[sample_id]["region_id"], by_id[sample_id]["spatial_block_id"])
                    for sample_id in fold["train_ids"]
                }
                validation_groups = {
                    (by_id[sample_id]["region_id"], by_id[sample_id]["spatial_block_id"])
                    for sample_id in fold["validation_ids"]
                }
                self.assertFalse(train_groups & validation_groups)

    def test_split_hash_and_saved_file_are_deterministic(self):
        split = build_leave_one_region_out_splits(
            self.make_samples(),
            self.REGIONS,
            spatial_folds=3,
            seed=42,
        )
        self.assertEqual(
            split_sha256(split),
            split_sha256(build_leave_one_region_out_splits(
                self.make_samples(),
                self.REGIONS,
                spatial_folds=3,
                seed=42,
            )),
        )

        with self.subTest("file hash matches saved bytes"):
            with tempfile.TemporaryDirectory(prefix="agrifm-split-test-") as directory:
                path = Path(directory) / "split.json"
                digest = write_split_file(path, split)
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_split_requires_spatial_block_ids(self):
        sample = {"sample_id": "tile-1", "region_id": "punjab"}
        with self.assertRaisesRegex(ValueError, "spatial_block_id"):
            build_leave_one_region_out_splits(
                [sample],
                self.REGIONS,
                spatial_folds=2,
            )


if __name__ == "__main__":
    unittest.main()
