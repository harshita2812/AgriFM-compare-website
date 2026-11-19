import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "assets.lock.json"
load_dotenv(ROOT / ".env")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CHUNK_SIZE = 1024 * 1024
LARGE_DOWNLOAD_BYTES = 2_000_000_000
RETRIES = 4
DOWNLOADABLE_STATUSES = {"planned", "downloaded_verified"}


def format_size(size: int) -> str:
    return f"{size:,} bytes ({size / 1024**3:.2f} GiB)"


def load_lock(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def asset_path(asset_root: Path, relative_path: str) -> Path:
    target = (asset_root / relative_path).resolve()
    if not target.is_relative_to(asset_root.resolve()):
        raise ValueError(f"Asset target must stay under the asset root: {relative_path}")
    return target


def checksum(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def pending_assets(assets: list[dict], asset_root: Path) -> list[tuple[dict, Path]]:
    pending = []
    for asset in assets:
        if asset.get("status") not in DOWNLOADABLE_STATUSES:
            continue
        destination = asset_path(asset_root, asset["target"])
        if destination.is_file() and destination.stat().st_size == asset["size_bytes"] and asset.get("sha256"):
            if checksum(destination, "sha256").lower() == asset["sha256"].lower():
                continue
        pending.append((asset, destination))
    return pending


def disk_budget(asset_root: Path) -> tuple[int, int]:
    probe = asset_root
    while not probe.exists():
        probe = probe.parent
    free = shutil.disk_usage(probe).free
    return free, int(free * 0.8)


def print_plan(assets: list[dict], asset_root: Path) -> list[tuple[dict, Path]]:
    selected = pending_assets(assets, asset_root)
    total = sum(asset["size_bytes"] for asset, _ in selected)
    free, budget = disk_budget(asset_root)
    print(f"Asset root: {asset_root}")
    print(f"Available disk: {format_size(free)}; 80% download budget: {format_size(budget)}")
    print("Planned files:")
    for asset, destination in selected:
        print(
            f"  {asset['id']}: {format_size(asset['size_bytes'])}; "
            f"license={asset['license']}; destination={destination}"
        )
    existing = len(assets) - len(selected)
    print(f"Already present or not downloadable: {existing}")
    print(f"Selected total: {format_size(total)}")
    if total > budget:
        print("Disk guard: FAIL (planned downloads exceed the 80% free-space budget)")
    else:
        print("Disk guard: PASS")
    oversized = [asset["id"] for asset, _ in selected if asset["size_bytes"] >= LARGE_DOWNLOAD_BYTES]
    if oversized:
        print("Downloads over 2 GB require explicit --allow-large-downloads: " + ", ".join(oversized))
    return selected


def download(asset: dict, destination: Path) -> tuple[str, bool]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.stat().st_size != asset["size_bytes"]:
            raise RuntimeError(
                f"Existing file has the wrong size for {asset['id']}; it was left untouched: {destination}"
            )
        source_checksum = asset.get("source_checksum")
        if source_checksum:
            algorithm, expected = source_checksum.split(":", 1)
            actual = checksum(destination, algorithm)
            if actual.lower() != expected.lower():
                raise RuntimeError(
                    f"Existing file {algorithm} mismatch for {asset['id']}; it was left untouched."
                )
        sha256 = checksum(destination, "sha256")
        expected_sha256 = asset.get("sha256")
        if expected_sha256 and sha256.lower() != expected_sha256.lower():
            raise RuntimeError(f"Existing file SHA-256 mismatch for {asset['id']}; it was left untouched.")
        if not expected_sha256 and not source_checksum:
            raise RuntimeError(f"Cannot verify existing file for {asset['id']}; it was left untouched.")
        return sha256, False

    partial = destination.with_name(destination.name + ".part")
    last_error: Exception | None = None

    for attempt in range(RETRIES):
        offset = partial.stat().st_size if partial.exists() else 0
        if asset["size_bytes"] is not None and offset > asset["size_bytes"]:
            raise RuntimeError(f"Partial download is larger than expected for {asset['id']}.")
        if asset["size_bytes"] is not None and offset == asset["size_bytes"]:
            break
        headers = {"User-Agent": "AgriFM-Compare/1.0"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = Request(asset["url"], headers=headers)
        try:
            with urlopen(request, timeout=60) as response:
                append = offset > 0 and response.status == 206
                mode = "ab" if append else "wb"
                with partial.open(mode) as stream:
                    while chunk := response.read(CHUNK_SIZE):
                        stream.write(chunk)
            if asset["size_bytes"] is not None and partial.stat().st_size != asset["size_bytes"]:
                raise RuntimeError(
                    f"Size mismatch for {asset['id']}: expected {asset['size_bytes']}, "
                    f"received {partial.stat().st_size} bytes."
                )
            break
        except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as error:
            last_error = error
            if attempt + 1 == RETRIES:
                raise RuntimeError(f"Download failed for {asset['id']}: {error}") from error
            time.sleep(min(2**attempt, 30))
    else:
        raise RuntimeError(f"Download failed for {asset['id']}: {last_error}")

    source_checksum = asset.get("source_checksum")
    if source_checksum:
        algorithm, expected = source_checksum.split(":", 1)
        actual = checksum(partial, algorithm)
        if actual.lower() != expected.lower():
            partial.unlink(missing_ok=True)
            raise RuntimeError(f"{algorithm} mismatch for {asset['id']}: expected {expected}, got {actual}.")

    sha256 = checksum(partial, "sha256")
    expected_sha256 = asset.get("sha256")
    if expected_sha256 and sha256.lower() != expected_sha256.lower():
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"SHA-256 mismatch for {asset['id']}: expected {expected_sha256}, got {sha256}.")
    partial.replace(destination)
    return sha256, True


def write_lock(path: Path, lock: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch only pinned, approved AgriFM assets.")
    parser.add_argument("--dry-run", action="store_true", help="Print plan only (the default).")
    parser.add_argument("--download", action="store_true", help="Fetch planned assets; otherwise dry-run.")
    parser.add_argument("--only", nargs="+", help="Limit to asset IDs; accepts spaces or comma-separated IDs.")
    parser.add_argument("--allow-large-downloads", action="store_true", help="Permit an individual file of 2 GB or more.")
    parser.add_argument("--asset-root", type=Path, help="Override the data/models root; defaults to AGRIFM_ASSET_ROOT or the repository.")
    parser.add_argument("--lockfile", type=Path, default=LOCK_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    lock = load_lock(args.lockfile)
    selected_ids = {
        value
        for item in (args.only or [])
        for value in item.split(",")
        if value
    }
    known_ids = {asset["id"] for asset in lock["assets"]}
    known_ids.update(source["id"] for source in lock.get("reference_sources", []))
    unknown_ids = selected_ids - known_ids
    if unknown_ids:
        raise ValueError(f"Unknown asset IDs: {', '.join(sorted(unknown_ids))}")
    chosen = [
        asset for asset in lock["assets"] + lock.get("reference_sources", [])
        if not selected_ids or asset["id"] in selected_ids
    ]
    blocked = [asset["id"] for asset in chosen if asset.get("status") not in DOWNLOADABLE_STATUSES]
    if selected_ids and blocked:
        reasons = [
            f"{asset['id']}: {asset.get('reason', asset.get('status'))}"
            for asset in chosen if asset.get("status") not in DOWNLOADABLE_STATUSES
        ]
        raise ValueError("Selected assets are not downloadable: " + "; ".join(reasons))
    assets = [asset for asset in chosen if asset.get("status") in DOWNLOADABLE_STATUSES]

    asset_root = args.asset_root or Path(os.environ.get("AGRIFM_ASSET_ROOT", ROOT))
    asset_root = asset_root.resolve()
    plan = print_plan(assets, asset_root)
    total = sum(asset["size_bytes"] for asset, _ in plan)
    free, budget = disk_budget(asset_root)
    if total > budget:
        raise RuntimeError("Download stopped by the 80% free-space guard.")
    oversized = [asset for asset, _ in plan if asset["size_bytes"] >= LARGE_DOWNLOAD_BYTES]
    if oversized and not args.allow_large_downloads:
        raise RuntimeError("Download stopped: an individual asset is at least 2 GB.")
    if not args.download:
        print("Dry-run only; no files were downloaded and the lock file was not changed.")
        return 0

    os.environ["AGRIFM_ASSET_ROOT"] = str(asset_root)
    from apps.api.asset_inventory import begin_asset_ingestion, finish_asset_ingestion
    from apps.api.main import init_db

    init_db()
    for asset, destination in plan:
        entries = begin_asset_ingestion(asset, asset_root)
        try:
            sha256, fetched = download(asset, destination)
            asset["sha256"] = sha256
            timestamp = datetime.now(timezone.utc).isoformat()
            asset["status"] = "downloaded_verified"
            if fetched:
                asset["fetched_at"] = timestamp
            else:
                asset["verified_at"] = timestamp
            write_lock(args.lockfile, lock)
            finish_asset_ingestion(asset, asset_root, entries, succeeded=True, sha256=sha256)
            print(f"Verified {asset['id']}: sha256={sha256}")
        except (OSError, ValueError, RuntimeError) as error:
            finish_asset_ingestion(
                asset,
                asset_root,
                entries,
                succeeded=False,
                error=str(error),
            )
            raise
    print("All selected assets downloaded and verified.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"Asset fetch stopped: {error}", file=sys.stderr)
        raise SystemExit(1) from error
