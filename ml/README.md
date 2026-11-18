# ML evaluation pipeline status

The evaluation pipeline is blocked and is not implemented. This directory is reserved for the future, documented pipeline; it is not a runnable model package and produces no metrics.

The workspace inventory found no authorized model checkpoints (`.pt`, `.pth`, `.ckpt`, or `.safetensors`), satellite imagery or ground-truth label assets, or documented split files. The project environment also lacks `torch`, `transformers`, `rasterio`, `geopandas`, `numpy`, and `scikit-learn`. The evaluation protocol and target compute requirements have not been supplied or verified.

Before implementing or running inference, provide:

- Authorized checkpoint artifacts or their official, license-compatible source and revisions.
- Corresponding imagery and ground-truth labels, with source, version, acquisition dates, and usage permissions.
- The task definition, label schema, geographically held-out split, preprocessing rules, and metric aggregation protocol.
- The supported runtime/compute environment and model-specific input/output requirements.

Until those prerequisites are available and validated, API runs remain `blocked`, all performance metrics remain `Not yet evaluated — Phase-II`, and no model ranking is produced.
