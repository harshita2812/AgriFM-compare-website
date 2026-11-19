from __future__ import annotations

import hashlib
import json
import os
from contextlib import closing
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from apps.api.db import ROOT, connect


LOCK_PATH = ROOT / "assets.lock.json"
MODEL_ASSETS = {
    "prithvi-300m": "prithvi",
    "satmae-vit-base": "satmae",
    "croma-base": "croma",
    "resnet50-a1-in1k": "resnet",
}
LABEL_ASSET_ID = "cropharvest-labels"


def load_asset_lock() -> dict[str, Any]:
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


def get_asset_root(configured_root: Path | str | None = None) -> Path:
    value = configured_root or os.environ.get("AGRIFM_ASSET_ROOT") or ROOT
    return Path(value).expanduser().resolve()


def asset_path(asset: dict[str, Any], asset_root: Path) -> Path:
    target = (asset_root / asset["target"]).resolve()
    if not target.is_relative_to(asset_root.resolve()):
        raise ValueError(f"Asset target must remain under AGRIFM_ASSET_ROOT: {asset['target']}")
    return target


@lru_cache(maxsize=128)
def _cached_sha256(path_text: str, size: int, modified_ns: int) -> str:
    digest = hashlib.sha256()
    with Path(path_text).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_asset_file(asset: dict[str, Any], asset_root: Path) -> dict[str, Any]:
    path = asset_path(asset, asset_root)
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "hash_verified": False,
        "status": "missing",
        "reason": None,
        "actual_sha256": None,
    }
    if not result["exists"]:
        result["reason"] = f"Asset file is missing: {path}"
        return result

    try:
        stat = path.stat()
    except OSError as error:
        result["status"] = "failed"
        result["reason"] = f"Could not inspect asset file {path}: {error}"
        return result

    expected_size = asset.get("size_bytes")
    if expected_size is not None and stat.st_size != expected_size:
        result["status"] = "failed"
        result["reason"] = f"Size mismatch: expected {expected_size} bytes, found {stat.st_size}."
        return result

    expected_sha256 = asset.get("sha256")
    if not expected_sha256:
        result["status"] = "unverified"
        result["reason"] = "No SHA-256 checksum is recorded in assets.lock.json."
        return result

    try:
        actual_sha256 = _cached_sha256(str(path), stat.st_size, stat.st_mtime_ns)
    except OSError as error:
        result["status"] = "failed"
        result["reason"] = f"Could not hash asset file {path}: {error}"
        return result

    result["actual_sha256"] = actual_sha256
    if actual_sha256.lower() != expected_sha256.lower():
        result["status"] = "failed"
        result["reason"] = f"SHA-256 mismatch: expected {expected_sha256}, found {actual_sha256}."
        return result

    result.update({
        "hash_verified": True,
        "status": "present",
        "reason": None,
    })
    return result


def _source_id(asset: dict[str, Any]) -> str:
    return f"asset-{asset['id']}"


def _source_values(asset: dict[str, Any], status: str, updated_at: str) -> tuple[Any, ...]:
    host = urlparse(asset["url"]).hostname or "Public source"
    coverage = asset.get("coverage", {})
    coverage_text = "; ".join(
        f"{key}: {value}" for key, value in coverage.items()
    ) if isinstance(coverage, dict) else str(coverage)
    return (
        _source_id(asset),
        asset["id"].replace("-", " ").title(),
        host,
        asset.get("kind", "reference"),
        coverage_text,
        status,
        f"Public; {asset.get('license', 'license not verified')}",
        asset["url"],
        updated_at,
    )


def _upsert_source(conn: Any, asset: dict[str, Any], status: str, updated_at: str) -> None:
    conn.execute(
        """INSERT INTO data_sources
           (id, name, provider, kind, coverage, status, access_type, source_url, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             name = excluded.name,
             provider = excluded.provider,
             kind = excluded.kind,
             coverage = excluded.coverage,
             status = excluded.status,
             access_type = excluded.access_type,
             source_url = excluded.source_url,
             updated_at = excluded.updated_at""",
        _source_values(asset, status, updated_at),
    )


def _payload(asset: dict[str, Any], file_status: dict[str, Any]) -> str:
    return json.dumps({
        "asset_id": asset["id"],
        "kind": asset["kind"],
        "url": asset["url"],
        "license": asset["license"],
        "revision": asset["revision"],
        "path": file_status["path"],
        "size_bytes": asset["size_bytes"],
        "expected_sha256": asset.get("sha256"),
        "actual_sha256": file_status["actual_sha256"],
        "hash_verified": file_status["hash_verified"],
        "coverage": asset.get("coverage", {}),
        "verification_reason": file_status["reason"],
    })


def _upsert_data_asset(
    conn: Any,
    asset: dict[str, Any],
    region_id: str,
    file_status: dict[str, Any],
    fetched_at: str,
) -> str:
    asset_row_id = f"locked-{asset['id']}-{region_id}"
    status = (
        "ready" if file_status["hash_verified"]
        else "running" if file_status.get("status") == "running"
        else "failed"
    )
    conn.execute(
        """INSERT INTO data_assets
           (id, source_id, region_id, asset_type, payload_json, fetched_at, status)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             source_id = excluded.source_id,
             region_id = excluded.region_id,
             asset_type = excluded.asset_type,
             payload_json = excluded.payload_json,
             fetched_at = excluded.fetched_at,
             status = excluded.status""",
        (
            asset_row_id,
            _source_id(asset),
            region_id,
            asset["kind"],
            _payload(asset, file_status),
            fetched_at,
            status,
        ),
    )
    return asset_row_id


def _upsert_historical_job(
    conn: Any,
    asset: dict[str, Any],
    region_id: str,
    asset_row_id: str,
    file_status: dict[str, Any],
    fetched_at: str,
    verified_at: str,
) -> None:
    job_id = f"locked-{asset['id']}-{region_id}"
    status = "ready" if file_status["hash_verified"] else "failed"
    detail = (
        "Fetched asset passed SHA-256 verification."
        if status == "ready"
        else file_status["reason"]
    )
    conn.execute(
        """INSERT INTO ingestion_jobs
           (id, source_id, region_id, asset_id, status, created_at, completed_at, detail)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             asset_id = excluded.asset_id,
             status = excluded.status,
             completed_at = excluded.completed_at,
             detail = excluded.detail""",
        (
            job_id,
            _source_id(asset),
            region_id,
            asset_row_id,
            status,
            fetched_at,
            verified_at,
            detail,
        ),
    )


def sync_locked_assets(asset_root: Path | str | None = None) -> None:
    if asset_root is None and not os.environ.get("AGRIFM_ASSET_ROOT"):
        return
    root = get_asset_root(asset_root)
    lock = load_asset_lock()
    now = datetime.now(timezone.utc).isoformat()
    fetched_assets = [asset for asset in lock["assets"] if asset.get("fetched_at")]
    if not fetched_assets:
        return

    with closing(connect()) as conn:
        regions = [row["id"] for row in conn.execute("SELECT id FROM regions").fetchall()]
        for asset in fetched_assets:
            file_status = verify_asset_file(asset, root)
            source_status = "Verified asset" if file_status["hash_verified"] else "Asset verification failed"
            _upsert_source(conn, asset, source_status, now)
            for region_id in regions:
                fetched_at = asset["fetched_at"]
                asset_row_id = _upsert_data_asset(conn, asset, region_id, file_status, fetched_at)
                existing_job = conn.execute(
                    "SELECT id FROM ingestion_jobs WHERE asset_id = ? LIMIT 1",
                    (asset_row_id,),
                ).fetchone()
                if not existing_job:
                    _upsert_historical_job(
                        conn, asset, region_id, asset_row_id, file_status, fetched_at, now
                    )

            if asset["id"] == LABEL_ASSET_ID:
                dataset_status = "Downloaded & verified" if file_status["hash_verified"] else "Metadata only"
                conn.execute(
                    "UPDATE datasets SET status = ? WHERE id = 'cropharvest'",
                    (dataset_status,),
                )
        conn.commit()


def begin_asset_ingestion(
    asset: dict[str, Any],
    asset_root: Path,
    operation: str = "download",
) -> list[dict[str, str]]:
    started_at = datetime.now(timezone.utc).isoformat()
    root = asset_root.resolve()
    file_status = {
        "path": str(asset_path(asset, root)),
        "actual_sha256": None,
        "hash_verified": False,
        "reason": "Asset download is in progress.",
        "status": "running",
    }
    entries = []
    with closing(connect()) as conn:
        regions = [row["id"] for row in conn.execute("SELECT id FROM regions").fetchall()]
        if not regions:
            raise RuntimeError("Cannot register asset ingestion: no study regions are seeded.")
        _upsert_source(conn, asset, f"{operation.title()} running", started_at)
        for region_id in regions:
            asset_fetched_at = asset.get("fetched_at") if operation == "verification" else started_at
            asset_row_id = _upsert_data_asset(
                conn, asset, region_id, file_status, asset_fetched_at or started_at
            )
            job_id = str(uuid4())
            conn.execute(
                """INSERT INTO ingestion_jobs
                   (id, source_id, region_id, asset_id, status, created_at, completed_at, detail)
                   VALUES (?, ?, ?, ?, 'running', ?, NULL, ?)""",
                (
                    job_id,
                    _source_id(asset),
                    region_id,
                    asset_row_id,
                    started_at,
                    f"{operation.title()} in progress; SHA-256 verification is pending.",
                ),
            )
            entries.append({"asset_row_id": asset_row_id, "job_id": job_id, "region_id": region_id})
        conn.commit()
    return entries


def finish_asset_ingestion(
    asset: dict[str, Any],
    asset_root: Path,
    entries: list[dict[str, str]],
    succeeded: bool,
    sha256: str | None = None,
    error: str | None = None,
    preserve_fetched_at: bool = False,
    success_detail: str = "Downloaded asset passed SHA-256 verification.",
) -> None:
    completed_at = datetime.now(timezone.utc).isoformat()
    path = asset_path(asset, asset_root)
    if succeeded:
        if not path.is_file() or path.stat().st_size != asset["size_bytes"]:
            raise RuntimeError(f"Downloaded asset is missing or has the wrong size: {path}")
        if not sha256 or sha256.lower() != asset.get("sha256", "").lower():
            raise RuntimeError("Downloaded asset SHA-256 does not match assets.lock.json.")
        file_status = {
            "path": str(path),
            "exists": True,
            "hash_verified": True,
            "status": "present",
            "reason": None,
            "actual_sha256": sha256,
        }
    else:
        file_status = {
            "path": str(path),
            "exists": path.is_file(),
            "hash_verified": False,
            "status": "failed",
            "actual_sha256": sha256,
            "reason": error,
        }
    status = "ready" if succeeded else "failed"
    with closing(connect()) as conn:
        for entry in entries:
            if preserve_fetched_at:
                conn.execute(
                    "UPDATE data_assets SET payload_json = ?, status = ? WHERE id = ?",
                    (_payload(asset, file_status), status, entry["asset_row_id"]),
                )
            else:
                conn.execute(
                    """UPDATE data_assets SET payload_json = ?, fetched_at = ?, status = ?
                       WHERE id = ?""",
                    (_payload(asset, file_status), completed_at, status, entry["asset_row_id"]),
                )
            conn.execute(
                """UPDATE ingestion_jobs SET status = ?, completed_at = ?, detail = ?
                   WHERE id = ?""",
                (
                    status,
                    completed_at,
                    success_detail if succeeded else error,
                    entry["job_id"],
                ),
            )
        source_status = "Verified asset" if succeeded else "Asset verification failed"
        _upsert_source(conn, asset, source_status, completed_at)
        if asset["id"] == LABEL_ASSET_ID:
            dataset_status = "Downloaded & verified" if succeeded else "Metadata only"
            conn.execute(
                "UPDATE datasets SET status = ? WHERE id = 'cropharvest'",
                (dataset_status,),
            )
        conn.commit()


def verify_registered_assets() -> list[str]:
    _cached_sha256.cache_clear()
    root = get_asset_root()
    lock = load_asset_lock()
    errors = []
    for asset in lock["assets"]:
        if not asset.get("fetched_at"):
            continue
        entries = begin_asset_ingestion(asset, root, operation="verification")
        file_status = verify_asset_file(asset, root)
        succeeded = file_status["hash_verified"]
        error = None if succeeded else file_status["reason"]
        finish_asset_ingestion(
            asset,
            root,
            entries,
            succeeded=succeeded,
            sha256=file_status["actual_sha256"],
            error=error,
            preserve_fetched_at=True,
            success_detail="Scheduled SHA-256 verification passed.",
        )
        if error:
            errors.append(f"{asset['id']}: {error}")
    return errors


def _runtime_status() -> dict[str, Any]:
    required_packages = ("torch", "torchvision", "numpy", "rasterio")
    versions = {}
    missing = []
    from importlib.metadata import PackageNotFoundError, version

    for package in required_packages:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            missing.append(package)
    present = not missing
    cuda_status = (
        "unavailable (CPU-only PyTorch build)"
        if "+cpu" in versions.get("torch", "")
        else "not probed"
    )
    detail = f"Versions: {versions}; CUDA {cuda_status}."
    if missing:
        detail = f"Missing required runtime packages: {', '.join(missing)}."
    return {
        "exists": present,
        "hash_verified": None,
        "status": "present" if present else "missing",
        "reason": detail,
    }


def build_readiness(
    models: list[dict[str, Any]],
    regions: list[dict[str, Any]],
    crops: list[str],
) -> dict[str, Any]:
    lock = load_asset_lock()
    root = get_asset_root()
    by_id = {asset["id"]: asset for asset in lock["assets"]}
    verified = {
        asset_id: verify_asset_file(by_id[asset_id], root)
        for asset_id in (*MODEL_ASSETS.keys(), LABEL_ASSET_ID)
        if asset_id in by_id
    }
    runtime = _runtime_status()
    items = []
    for region in regions:
        for crop in crops:
            for model in models:
                asset_id = next(
                    (item_id for item_id, model_id in MODEL_ASSETS.items() if model_id == model["id"]),
                    None,
                )
                checkpoint = verified.get(asset_id, {
                    "exists": False,
                    "hash_verified": False,
                    "status": "missing",
                    "reason": f"No locked checkpoint is registered for model {model['id']}.",
                })
                labels = verified.get(LABEL_ASSET_ID, {
                    "exists": False,
                    "hash_verified": False,
                    "status": "missing",
                    "reason": "No locked label asset is registered.",
                })
                labels = {
                    **labels,
                    "status": "blocked",
                    "reason": (
                        "CropHarvest file is checksum-verified, but its generalized/binary labels "
                        "and regional overlap do not validate this five-crop task."
                        if labels["hash_verified"]
                        else "No task-compatible, hash-verified ground-truth labels are available."
                    ),
                }
                components = {
                    "checkpoint": checkpoint,
                    "imagery": {
                        "exists": False,
                        "hash_verified": False,
                        "status": "missing",
                        "reason": (
                            "No imagery was downloaded; Sentinel catalog licensing and the Western-UP "
                            "study AOI remain unresolved."
                        ),
                    },
                    "labels": labels,
                    "split": {
                        "exists": False,
                        "hash_verified": False,
                        "status": "missing",
                        "reason": "No approved task or geographic train/test split file exists.",
                    },
                    "runtime": runtime,
                }
                items.append({
                    "model_id": model["id"],
                    "model_name": model["name"],
                    "region_id": region["id"],
                    "region_name": region["name"],
                    "crop": crop,
                    "components": components,
                    "ready": all(item["status"] == "present" for item in components.values()),
                })
    return {
        "asset_root": str(root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "regions": [{"id": item["id"], "name": item["name"]} for item in regions],
        "crops": crops,
        "items": items,
    }
