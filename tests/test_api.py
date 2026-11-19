import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from apps.api.asset_inventory import verify_asset_file


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


class ApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory(prefix="agrifm-api-test-")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        env = os.environ.copy()
        database_url = env.get("DATABASE_URL", "")
        if database_url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
            if database_url.startswith("postgres://"):
                database_url = "postgresql+psycopg://" + database_url[len("postgres://"):]
            elif database_url.startswith("postgresql://"):
                database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
            cls.postgres_engine = create_engine(database_url, pool_pre_ping=True)
            cls.postgres_schema = f"agrifm_test_{uuid4().hex}"
            with cls.postgres_engine.begin() as connection:
                connection.execute(text(f'CREATE SCHEMA "{cls.postgres_schema}"'))
            env.pop("AGRIFM_DB_PATH", None)
            env["AGRIFM_DB_SCHEMA"] = cls.postgres_schema
        else:
            cls.postgres_engine = None
            cls.postgres_schema = None
            env.pop("AGRIFM_DB_SCHEMA", None)
            env["AGRIFM_DB_PATH"] = str(Path(cls.temp_dir.name) / "test.sqlite3")
        env.pop("AGRIFM_ASSET_ROOT", None)
        cls.server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "apps.api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(cls.port),
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(100):
            if cls.server.poll() is not None:
                raise RuntimeError(f"API server exited with code {cls.server.returncode}")
            try:
                cls.request("GET", "/api/health")
                break
            except (URLError, TimeoutError):
                time.sleep(0.1)
        else:
            cls.server.terminate()
            raise RuntimeError("API server did not start within 10 seconds")

    @classmethod
    def tearDownClass(cls):
        if cls.server.poll() is None:
            cls.server.terminate()
            try:
                cls.server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.server.kill()
                cls.server.wait(timeout=5)
        if cls.postgres_engine is not None:
            with cls.postgres_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{cls.postgres_schema}" CASCADE'))
            cls.postgres_engine.dispose()
        cls.temp_dir.cleanup()

    @classmethod
    def request(cls, method, path, body=None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            f"{cls.base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

    def test_seeded_catalogs_are_marked_as_demo_and_have_no_scores(self):
        for path in ("/api/models", "/api/regions", "/api/datasets"):
            status, records = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertTrue(records)
            for record in records:
                self.assertIs(record.get("is_demo"), True, path)
        _, models = self.request("GET", "/api/models")
        for model in models:
            self.assertNotIn("values", model)
            for metric in ("accuracy", "f1", "iou", "kappa", "latency"):
                self.assertNotIn(metric, model)
        dataset_statuses = {dataset["status"] for dataset in self.request("GET", "/api/datasets")[1]}
        self.assertIn("Metadata only", dataset_statuses)
        self.assertNotIn("Ready", dataset_statuses)

    def test_seeded_runs_and_dashboard_do_not_claim_evaluated_metrics(self):
        status, runs = self.request("GET", "/api/runs")
        self.assertEqual(status, 200)
        self.assertTrue(runs)
        for run in runs:
            self.assertIs(run.get("is_demo"), True)
            self.assertEqual(run.get("evaluation_status"), "blocked")
            self.assertIn("No authorized model checkpoints", run.get("evaluation_reason", ""))
            expected_provenance_status = "declared_unverified" if run.get("provenance") else "not_recorded"
            self.assertEqual(run.get("provenance_status"), expected_provenance_status)
            for result in run["results"]:
                self.assertIs(result.get("is_demo"), True)
                for metric in ("accuracy", "f1", "iou", "kappa", "latency"):
                    self.assertIsNone(result.get(metric), f"{metric} must be unevaluated")
        _, dashboard = self.request("GET", "/api/dashboard")
        self.assertIs(dashboard.get("is_demo"), True)
        self.assertIsNone(dashboard["top_f1"])

    def test_crop_catalog_is_marked_as_demo(self):
        status, crops = self.request("GET", "/api/crops")
        self.assertEqual(status, 200)
        self.assertIs(crops.get("is_demo"), True)
        self.assertIn("Wheat", crops["items"])
        status, methodology = self.request("GET", "/api/methodology")
        self.assertEqual(status, 200)
        self.assertIs(methodology.get("is_demo"), True)
        self.assertTrue(any("unevaluated until Phase-II" in step for step in methodology["protocol"]))
        self.assertTrue(any("proposed" in metric["description"].lower() for metric in methodology["metrics"]))
        self.assertFalse(any("used here as the primary ranking metric" in metric["description"] for metric in methodology["metrics"]))

    def test_api_does_not_accept_or_store_uploads(self):
        status, _ = self.request("GET", "/api/uploads")
        self.assertEqual(status, 404)

    def test_data_sources_and_ingestion_jobs_are_explicit(self):
        status, data = self.request("GET", "/api/data/sources")
        self.assertEqual(status, 200)
        self.assertIs(data["is_demo"], False)
        self.assertIn("assets", data)
        sources = {source["id"]: source for source in data["sources"]}
        self.assertIn("open-meteo", sources)
        self.assertIn("copernicus-sentinel", sources)
        self.assertEqual(sources["copernicus-sentinel"]["status"], "Catalog only")
        self.assertIsInstance(data["jobs"], list)

    def test_readiness_explains_blocked_inputs_per_model_region_and_crop(self):
        status, readiness = self.request("GET", "/api/data/readiness")
        self.assertEqual(status, 200)
        self.assertEqual(len(readiness["items"]), 4 * 5 * 5)
        item = readiness["items"][0]
        self.assertEqual(
            set(item["components"]),
            {"checkpoint", "imagery", "labels", "split", "runtime"},
        )
        self.assertFalse(item["ready"])
        self.assertEqual(item["components"]["imagery"]["status"], "missing")
        self.assertTrue(item["components"]["imagery"]["reason"])
        self.assertEqual(item["components"]["labels"]["status"], "blocked")
        self.assertTrue(item["components"]["labels"]["reason"])

    def test_weather_asset_absence_is_explicit_and_region_validation_applies(self):
        status, body = self.request("GET", "/api/data/weather/punjab")
        self.assertEqual(status, 404)
        self.assertIn("No weather asset", body["detail"])
        status, _ = self.request("POST", "/api/data/weather/refresh", {
            "region_id": "unknown",
            "forecast_days": 7,
        })
        self.assertEqual(status, 404)

    def test_evaluation_job_remains_blocked_without_manifest_and_assets(self):
        status, job = self.request("POST", "/api/evaluations/jobs", {
            "region_id": "punjab",
            "crop": "Wheat",
            "dataset_id": "sentinel2",
            "model_ids": ["prithvi", "satmae"],
        })
        self.assertEqual(status, 200)
        self.assertEqual(job["status"], "blocked")
        self.assertTrue(all(result["f1"] is None for result in job["results"]))
        execute_status, executed = self.request("POST", f"/api/evaluations/jobs/{job['id']}/execute")
        self.assertEqual(execute_status, 200)
        self.assertEqual(executed["status"], "blocked")
        self.assertIn("AGRIFM_EVALUATION_MANIFEST", executed["detail"])
        list_status, jobs = self.request("GET", "/api/evaluations/jobs")
        self.assertEqual(list_status, 200)
        self.assertIn(job["id"], [item["id"] for item in jobs])

    def test_new_comparison_persists_without_fabricated_scores(self):
        body = {
            "region_id": "punjab",
            "crop": "Wheat",
            "season": "Rabi 2025–26",
            "dataset_id": "sentinel2",
            "model_ids": ["prithvi", "satmae"],
        }
        status, run = self.request("POST", "/api/runs", body)
        self.assertEqual(status, 200)
        self.assertIs(run.get("is_demo"), True)
        self.assertEqual(len(run["results"]), 2)
        for result in run["results"]:
            self.assertIs(result.get("is_demo"), True)
            for metric in ("accuracy", "f1", "iou", "kappa", "latency"):
                self.assertIsNone(result.get(metric))
        _, saved_runs = self.request("GET", "/api/runs")
        self.assertIn(run["id"], [saved["id"] for saved in saved_runs])

    def test_run_provenance_persists_as_unverified_declaration(self):
        body = {
            "region_id": "punjab",
            "crop": "Wheat",
            "dataset_id": "sentinel2",
            "model_ids": ["prithvi", "satmae"],
            "provenance": {
                "dataset_release": "declared-release",
                "label_source_version": "declared-labels",
                "acquisition_start": "2025-01-01",
                "acquisition_end": "2025-03-31",
                "split_id": "declared-split",
                "split_method": "declared-method",
                "model_revisions": {"prithvi": "revision-a", "satmae": "revision-b"},
                "preprocessing": "declared preprocessing",
                "input_resolution": "10 m",
                "metric_config": "declared metric configuration",
                "random_seed": 7,
                "code_revision": "declared-code",
                "hardware_runtime": "declared-runtime",
            },
        }
        status, run = self.request("POST", "/api/runs", body)
        self.assertEqual(status, 200)
        self.assertEqual(run["evaluation_status"], "blocked")
        self.assertEqual(run["provenance_status"], "declared_unverified")
        self.assertEqual(run["provenance"], body["provenance"])
        self.assertTrue(all(result["f1"] is None for result in run["results"]))

        _, saved_runs = self.request("GET", "/api/runs")
        saved = next(item for item in saved_runs if item["id"] == run["id"])
        self.assertEqual(saved["provenance"], body["provenance"])
        self.assertEqual(saved["provenance_status"], "declared_unverified")

    def test_invalid_run_provenance_is_rejected(self):
        valid = {
            "region_id": "punjab",
            "crop": "Wheat",
            "dataset_id": "sentinel2",
            "model_ids": ["prithvi", "satmae"],
        }
        for provenance in (
            {},
            {"acquisition_start": "2025-05-01", "acquisition_end": "2025-01-01"},
            {"model_revisions": {"unknown-model": "revision"}},
        ):
            status, _ = self.request("POST", "/api/runs", {**valid, "provenance": provenance})
            self.assertEqual(status, 422, provenance)

    def test_invalid_comparison_inputs_return_explicit_errors(self):
        valid = {
            "region_id": "punjab",
            "crop": "Wheat",
            "dataset_id": "sentinel2",
            "model_ids": ["prithvi", "satmae"],
        }
        for changes, expected_status in (
            ({"model_ids": ["prithvi"]}, 422),
            ({"model_ids": ["prithvi", "satmae", "croma", "resnet", "extra"]}, 422),
            ({"model_ids": ["prithvi", "prithvi"]}, 422),
            ({"model_ids": ["unknown", "satmae"]}, 404),
            ({"region_id": "unknown"}, 404),
            ({"crop": "Unknown"}, 422),
            ({"dataset_id": "unknown"}, 404),
        ):
            payload = {**valid, **changes}
            status, body = self.request("POST", "/api/runs", payload)
            self.assertEqual(status, expected_status, (changes, body))


class AssetVerificationTests(unittest.TestCase):
    def test_hash_verification_uses_file_contents_and_reports_mismatch(self):
        import hashlib

        with tempfile.TemporaryDirectory(prefix="agrifm-asset-test-") as directory:
            path = Path(directory) / "asset.bin"
            path.write_bytes(b"verified")
            asset = {
                "target": "asset.bin",
                "size_bytes": path.stat().st_size,
                "sha256": hashlib.sha256(b"verified").hexdigest(),
            }
            verified = verify_asset_file(asset, Path(directory))
            self.assertTrue(verified["exists"])
            self.assertTrue(verified["hash_verified"])
            self.assertEqual(verified["status"], "present")

            asset["sha256"] = "0" * 64
            mismatch = verify_asset_file(asset, Path(directory))
            self.assertFalse(mismatch["hash_verified"])
            self.assertEqual(mismatch["status"], "failed")
            self.assertIn("SHA-256 mismatch", mismatch["reason"])


class SegmentationMetricTests(unittest.TestCase):
    def test_binary_metrics_are_calculated_from_predictions_and_labels(self):
        from ml.evaluation import segmentation_metrics

        metrics = segmentation_metrics(
            predictions=[[1, 1], [0, 1]],
            labels=[[1, 0], [0, 1]],
        )
        self.assertAlmostEqual(metrics["accuracy"], 0.75)
        self.assertAlmostEqual(metrics["f1"], 0.8)
        self.assertAlmostEqual(metrics["iou"], 2 / 3)
        self.assertGreaterEqual(metrics["kappa"], 0.0)

    def test_mismatched_arrays_are_rejected(self):
        from ml.evaluation import segmentation_metrics

        with self.assertRaises(ValueError):
            segmentation_metrics([1, 0], [1])


class LegacyDatabaseMigrationTests(unittest.TestCase):
    def test_existing_demo_scores_are_removed_on_startup(self):
        with tempfile.TemporaryDirectory(prefix="agrifm-legacy-test-") as directory:
            db_path = Path(directory) / "legacy.sqlite3"
            with closing(sqlite3.connect(db_path)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE models (
                        id TEXT PRIMARY KEY, name TEXT NOT NULL, provider TEXT NOT NULL,
                        family TEXT NOT NULL, parameters TEXT NOT NULL, modality TEXT NOT NULL,
                        description TEXT NOT NULL, color TEXT NOT NULL, values_json TEXT NOT NULL
                    );
                    CREATE TABLE regions (
                        id TEXT PRIMARY KEY, name TEXT NOT NULL, state TEXT NOT NULL,
                        lat REAL NOT NULL, lon REAL NOT NULL
                    );
                    CREATE TABLE datasets (
                        id TEXT PRIMARY KEY, name TEXT NOT NULL, provider TEXT NOT NULL,
                        resolution TEXT NOT NULL, coverage TEXT NOT NULL, type TEXT NOT NULL,
                        status TEXT NOT NULL
                    );
                    CREATE TABLE runs (
                        id TEXT PRIMARY KEY, created_at TEXT NOT NULL, region_id TEXT NOT NULL,
                        crop TEXT NOT NULL, season TEXT NOT NULL, dataset_id TEXT NOT NULL,
                        model_ids TEXT NOT NULL, results_json TEXT NOT NULL
                    );
                    INSERT INTO models VALUES (
                        'prithvi', 'Prithvi-EO-2.0', 'provider', 'family', '600M',
                        'Multispectral', 'description', '#2e7257',
                        '{"accuracy":99.9,"f1":99.9,"iou":99.9,"kappa":0.99,"latency":1}'
                    );
                    INSERT INTO regions VALUES ('punjab', 'Punjab', 'Punjab', 31.1, 75.3);
                    INSERT INTO datasets VALUES (
                        'sentinel2', 'Sentinel-2 L2A', 'provider', '10 m',
                        '2017-present', 'Multispectral', 'Ready'
                    );
                    INSERT INTO runs VALUES (
                        'legacy-run', '2026-01-01T00:00:00+00:00', 'punjab',
                        'Wheat', 'Rabi 2025-26', 'sentinel2',
                        '["prithvi"]',
                        '[{"model_id":"prithvi","model_name":"Prithvi-EO-2.0","accuracy":99.9,"f1":99.9,"iou":99.9,"kappa":0.99,"latency":1}]'
                    );
                    """
                )
                connection.commit()

            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            env = os.environ.copy()
            env["AGRIFM_DB_PATH"] = str(db_path)
            env.pop("AGRIFM_DB_SCHEMA", None)
            server = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "backend.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                base_url = f"http://127.0.0.1:{port}"
                for _ in range(100):
                    if server.poll() is not None:
                        self.fail(f"API server exited with code {server.returncode}")
                    try:
                        with urlopen(f"{base_url}/api/health", timeout=1):
                            break
                    except (URLError, TimeoutError):
                        time.sleep(0.1)
                else:
                    self.fail("Migrated API server did not start within 10 seconds")

                with urlopen(f"{base_url}/api/models", timeout=3) as response:
                    models = json.loads(response.read().decode("utf-8"))
                with urlopen(f"{base_url}/api/runs", timeout=3) as response:
                    runs = json.loads(response.read().decode("utf-8"))
                with urlopen(f"{base_url}/api/datasets", timeout=3) as response:
                    datasets = json.loads(response.read().decode("utf-8"))
                self.assertEqual(models[0]["is_demo"], True)
                self.assertNotIn("values", models[0])
                self.assertEqual(runs[0]["id"], "legacy-run")
                self.assertEqual(runs[0]["is_demo"], True)
                self.assertEqual(runs[0]["evaluation_status"], "blocked")
                self.assertEqual(runs[0]["provenance_status"], "not_recorded")
                self.assertNotIn("Ready", [dataset["status"] for dataset in datasets])
                for metric in ("accuracy", "f1", "iou", "kappa", "latency"):
                    self.assertIsNone(runs[0]["results"][0][metric])
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
