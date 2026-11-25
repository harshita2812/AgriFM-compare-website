from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import rasterio
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "ml" / "data" / "sentinel2_samples"
DEFAULT_ARTIFACT = ROOT / "ml" / "artifacts" / "sentinel_autoencoder.pt"


class SentinelAutoencoder(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv2d(4, 16, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.ConvTranspose2d(64, 32, 2, stride=2),
            nn.ReLU(),
            nn.ConvTranspose2d(32, 16, 2, stride=2),
            nn.ReLU(),
            nn.Conv2d(16, 4, 3, padding=1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.decoder(self.encoder(x))


def extract_patches(
    input_root: Path,
    patch_size: int,
    patch_count: int,
    seed: int,
) -> tuple[np.ndarray, dict[str, list[float]]]:
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)
    files = sorted(input_root.glob("*/*.tif"))
    if not files:
        raise FileNotFoundError(f"No Sentinel GeoTIFF chips found under {input_root}")

    selected: list[np.ndarray] = []
    raw_values: list[np.ndarray] = []
    for path in files:
        with rasterio.open(path) as source:
            data = source.read().astype(np.float32)
        valid = np.transpose(data, (1, 2, 0)).reshape(-1, 4)
        valid = valid[np.any(valid > 0, axis=1)]
        if valid.size:
            raw_values.append(valid[np_rng.choice(valid.shape[0], size=min(valid.shape[0], 100_000), replace=False)])

    raw = np.concatenate(raw_values, axis=0)
    percentiles = {
        "low": np.percentile(raw, 1, axis=0).tolist(),
        "high": np.percentile(raw, 99, axis=0).tolist(),
    }
    low = np.asarray(percentiles["low"], dtype=np.float32)[:, None, None]
    high = np.asarray(percentiles["high"], dtype=np.float32)[:, None, None]

    attempts = 0
    while len(selected) < patch_count and attempts < patch_count * 20:
        attempts += 1
        path = rng.choice(files)
        with rasterio.open(path) as source:
            data = source.read().astype(np.float32)
        _, height, width = data.shape
        if height < patch_size or width < patch_size:
            continue
        top = rng.randint(0, height - patch_size)
        left = rng.randint(0, width - patch_size)
        patch = data[:, top:top + patch_size, left:left + patch_size]
        if np.mean(patch == 0) > 0.25:
            continue
        normalized = np.clip((patch - low) / np.maximum(high - low, 1.0), 0.0, 1.0)
        if np.std(normalized) < 0.01:
            continue
        selected.append(normalized)

    if not selected:
        raise RuntimeError("Could not extract usable Sentinel patches.")
    return np.stack(selected).astype(np.float32), percentiles


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a Sentinel-2 patch autoencoder")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--patch-size", type=int, default=64)
    parser.add_argument("--patch-count", type=int, default=1500)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    patches, normalization = extract_patches(
        args.input, args.patch_size, args.patch_count, args.seed
    )
    dataset = TensorDataset(torch.from_numpy(patches))
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
        generator=torch.Generator().manual_seed(args.seed),
    )

    model = SentinelAutoencoder()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_function = nn.MSELoss()
    history: list[dict[str, float]] = []
    model.train()
    for epoch in range(args.epochs):
        total_loss = 0.0
        for (batch,) in loader:
            optimizer.zero_grad(set_to_none=True)
            reconstructed = model(batch)
            loss = loss_function(reconstructed, batch)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(batch)
        epoch_loss = total_loss / len(dataset)
        history.append({"epoch": epoch + 1, "reconstruction_mse": epoch_loss})
        print(f"epoch={epoch + 1}/{args.epochs} mse={epoch_loss:.6f}")

    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "model_state_dict": model.state_dict(),
        "normalization": normalization,
        "patch_size": args.patch_size,
        "bands": ["B02", "B03", "B04", "B08"],
        "seed": args.seed,
        "input_root": str(args.input),
        "patch_count": len(dataset),
        "history": history,
    }, args.artifact)
    metadata = {
        "model_type": "sentinel-convolutional-autoencoder",
        "bands": ["B02", "B03", "B04", "B08"],
        "patch_count": len(dataset),
        "patch_size": args.patch_size,
        "epochs": args.epochs,
        "seed": args.seed,
        "normalization": normalization,
        "final_reconstruction_mse": history[-1]["reconstruction_mse"],
        "artifact": str(args.artifact),
        "purpose": "unsupervised representation learning only",
        "not_supervised_crop_training": True,
    }
    args.artifact.with_suffix(".json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
