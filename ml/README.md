# ML evaluation pipeline status

## Approved protocol

- Task: six-class semantic segmentation for Wheat, Rice, Cotton, Sugarcane, Maize, and other.
- Outer evaluation: leave one of the five study regions out for testing, rotating the held-out region.
- Inner validation: spatial-block cross-validation within each outer training set. Every sample manifest must provide a stable `spatial_block_id`; exact AOIs and block assignments are still pending.
- Default mode: frozen encoder with a lightweight linear/UPerNet-lite segmentation head.
- Shared seed: 42. Proposed metrics are per-class IoU/F1, mIoU, macro-F1, overall accuracy, 1,000-resample block-bootstrap 95% confidence intervals, and measured compute cost.
- Model ranking is not permitted unless uncertainty intervals support a meaningful difference.

## Current asset and runtime status

The four pinned checkpoint files and CropHarvest label archive are present on the configured D: asset drive and passed SHA-256 verification. The local runtime has CPU-only PyTorch; no CUDA GPU is available. CropHarvest's generalized/binary labels do not establish ground truth for the five crop classes, and its exact overlap with study AOIs is unknown. No Sentinel imagery chips or approved split file are available. The Western Uttar Pradesh coordinate still needs correction to the intended study AOI.

Accordingly, no `ml/manifest.json` is generated and `AGRIFM_EVALUATION_MANIFEST` remains unset. A verified file hash proves file identity only; it does not prove that the file is a suitable label source for this task.

## Implemented components

- `evaluation.py` retains the binary metrics API and adds multiclass per-class IoU/F1, mIoU, macro-F1, overall accuracy, and deterministic spatial-block bootstrap confidence intervals.
- `pipeline/splits.py` builds deterministic leave-one-region-out folds with inner spatial-block folds, checks group separation, and writes a canonical split file whose SHA-256 can be recorded.
- API evaluation jobs remain blocked until a task-compatible imagery/label manifest and split exist. No model is loaded, inference is not run, and all saved performance metrics remain null.

## Still blocked

- Resolve the Sentinel catalog license declaration and obtain exact study AOIs, including the intended Western Uttar Pradesh location.
- Obtain appropriately licensed, spatially aligned labels for the approved six classes.
- Build and validate the imagery/label chip manifest and spatial-block IDs; only then can the split file and its hash be generated.
- Implement and verify one consistent frozen-encoder adapter for each checkpoint. The current repository does not yet include model-specific inference adapters.
- Run a real-chip smoke test and full evaluation only after all assets, hashes, adapter inputs, and runtime constraints are verified.
