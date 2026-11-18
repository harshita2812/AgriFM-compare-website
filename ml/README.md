# ML evaluation pipeline status

The evaluation pipeline is blocked and only a manifest/job framework is implemented. This directory is not a runnable model package and produces no model metrics.

The workspace inventory found no authorized model checkpoints (`.pt`, `.pth`, `.ckpt`, or `.safetensors`), satellite imagery or ground-truth label assets, or documented split files. The project environment also lacks `torch`, `transformers`, `rasterio`, `geopandas`, `numpy`, and `scikit-learn`. The evaluation protocol and target compute requirements have not been supplied or verified.

Before implementing or running inference, provide:

- Authorized checkpoint artifacts or their official, license-compatible source and revisions.
- Corresponding imagery and ground-truth labels, with source, version, acquisition dates, and usage permissions.
- The task definition, label schema, geographically held-out split, preprocessing rules, and metric aggregation protocol.
- The supported runtime/compute environment and model-specific input/output requirements.

Until those prerequisites are available and validated, API runs remain `blocked`, all performance metrics remain `Not yet evaluated — Phase-II`, and no model ranking is produced.

## Implemented framework

- FastAPI evaluation-job endpoints create and track blocked jobs.
- `evaluation.py` provides pure binary segmentation metric calculations for future, externally validated predictions and labels.
- Supplied evaluation manifests may include dataset, labels, split, model artifact, metric, code, and runtime declarations.
- Job execution validates manifest fields and asset paths and records a manifest SHA-256 when inventory is valid.
- No model artifact is loaded and no inference is run by this framework.
- Missing assets, runtime, backend, or manifest produce explicit blocked status and never a success-shaped result.
