from __future__ import annotations

import argparse
import hashlib
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds


ROOT = Path(__file__).resolve().parents[2]
SEARCH_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
SIGN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"

REGIONS = {
    "punjab": {
        "name": "Punjab",
        "bbox": [75.10, 31.00, 75.35, 31.25],
    },
    "up": {
        "name": "Western Uttar Pradesh",
        "bbox": [77.10, 28.50, 77.35, 28.75],
        "warning": "Approximate location only; the project AOI remains unapproved.",
    },
    "maharashtra": {
        "name": "Maharashtra",
        "bbox": [74.65, 19.20, 74.90, 19.45],
    },
    "karnataka": {
        "name": "Karnataka",
        "bbox": [75.20, 15.20, 75.45, 15.45],
    },
    "bihar": {
        "name": "Bihar",
        "bbox": [85.00, 25.25, 85.25, 25.50],
    },
}


def post_json(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "AgriFM-Compare/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def sign_href(href: str) -> str:
    response = post_json(
        SIGN_URL + "?href=" + urllib.parse.quote(href, safe="")
    )
    return response["href"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def search_item(
    region_id: str,
    region: dict[str, Any],
    start: str,
    end: str,
    max_cloud: int,
) -> dict[str, Any]:
    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox": region["bbox"],
        "datetime": f"{start}/{end}",
        "query": {"eo:cloud_cover": {"lt": max_cloud}},
        "limit": 10,
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
    }
    response = post_json(SEARCH_URL, payload)
    features = response.get("features", [])
    if not features:
        raise RuntimeError(f"No Sentinel-2 L2A item found for {region_id} in {start}/{end}.")
    return features[0]


def read_clipped_band(asset_href: str, bounds: list[float]) -> tuple[np.ndarray, Any, dict[str, Any]]:
    signed_href = sign_href(asset_href)
    with rasterio.open(signed_href) as source:
        source_bounds = transform_bounds("EPSG:4326", source.crs, *bounds)
        window = from_bounds(*source_bounds, transform=source.transform)
        window = window.round_offsets().round_lengths()
        data = source.read(1, window=window, boundless=True, fill_value=0)
        transform = source.window_transform(window)
        profile = source.profile
    return data, transform, profile


def acquire(args: argparse.Namespace) -> dict[str, Any]:
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "purpose": "public benchmark sample only",
        "source": "Microsoft Planetary Computer Sentinel-2 L2A",
        "period": {"start": args.start, "end": args.end},
        "cloud_cover_below_percent": args.max_cloud,
        "acquired_at": datetime.now(timezone.utc).isoformat(),
        "items": [],
        "disclaimer": (
            "Approximate regional center samples only. "
            "These files are not approved AOIs, task-compatible labels, or evidence of model performance."
        ),
    }

    selected = [args.region] if args.region else list(REGIONS)
    for region_id in selected:
        region = REGIONS[region_id]
        item = search_item(region_id, region, args.start, args.end, args.max_cloud)
        assets = item["assets"]
        record: dict[str, Any] = {
            "region_id": region_id,
            "region_name": region["name"],
            "approximate_bbox": region["bbox"],
            "stac_item_id": item["id"],
            "datetime": item["properties"]["datetime"],
            "cloud_cover_percent": item["properties"].get("eo:cloud_cover"),
            "stac_link": next(
                (link["href"] for link in item.get("links", []) if link.get("rel") == "self"),
                None,
            ),
            "warning": region.get("warning"),
        }

        if not args.download:
            record["status"] = "search_only"
            manifest["items"].append(record)
            continue

        bands: list[np.ndarray] = []
        transform = None
        profile = None
        for band_name in ("B02", "B03", "B04", "B08"):
            data, transform, profile = read_clipped_band(
                assets[band_name]["href"], region["bbox"]
            )
            bands.append(data)

        height, width = bands[0].shape
        chip = np.stack(bands, axis=0).astype(np.uint16)
        destination = output_root / region_id / f"{item['id']}_B02-B03-B04-B08.tif"
        destination.parent.mkdir(parents=True, exist_ok=True)
        profile.update(
            driver="GTiff",
            dtype="uint16",
            count=4,
            height=height,
            width=width,
            transform=transform,
            compress="deflate",
        )
        with rasterio.open(destination, "w", **profile) as target:
            target.write(chip)
            target.set_band_description(1, "B02 blue")
            target.set_band_description(2, "B03 green")
            target.set_band_description(3, "B04 red")
            target.set_band_description(4, "B08 near-infrared")

        record.update({
            "status": "downloaded",
            "file": str(destination),
            "sha256": sha256(destination),
            "bands": ["B02", "B03", "B04", "B08"],
            "size_bytes": destination.stat().st_size,
        })
        manifest["items"].append(record)

    manifest_path = output_root / "sentinel2_public_samples_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    manifest_path.with_suffix(".json.sha256").write_text(
        sha256(manifest_path) + "  " + manifest_path.name + "\n",
        encoding="ascii",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search or acquire public Sentinel-2 benchmark samples through Microsoft Planetary Computer."
    )
    parser.add_argument("--region", choices=sorted(REGIONS))
    parser.add_argument("--output", type=Path, default=ROOT / "ml" / "data" / "sentinel2_samples")
    parser.add_argument("--start", default="2025-10-01")
    parser.add_argument("--end", default="2026-04-30")
    parser.add_argument("--max-cloud", type=int, default=20)
    parser.add_argument("--download", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    acquire(parse_args())
