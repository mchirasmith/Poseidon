# Poseidon backend: handover for the Windows machine

Temporary operations note for continuing the data download and lite training on the Windows laptop
(NVIDIA GPU with 8 GB VRAM, 32 GB RAM, fast ethernet). Delete once the real run has finished there.

## Where things stand

- Branch `backend`. Four commits deliver the API scaffold and contract, the data pipeline with a
  synthetic twin, the GBM baseline and lite network with calibration, ONNX export and evaluation,
  and live serving with NetCDF, cache precompute and the one-shot runner.
- The working tree holds one more batch of verified, uncommitted changes: CF attribute fixes,
  streaming synthetic generator and evaluator, the MPS training memory fix, the lighter
  depth-attention head, the full-domain ONNX parity fix, env-file credentials, parallel downloads,
  automatic device selection with a CUDA wheel on Windows, and the ignore rules that keep datasets
  out of git. It is committed as soon as the last test run finishes; if you pull and do not see a
  commit after `875bd9a`, ask before starting.
- Test suite: about 160 tests, all offline on synthetic data, roughly ten minutes end to end. The
  memory tests are Unix-only and skip on Windows.
- Docker image for the API builds and runs without torch (1.46 GB).
- Data on the Mac: salinity complete, sea level 47, SST 36, currents 12, wind 11, GLORYS 3 of 60
  months each, all resumable from per-product manifests. Downloads are paused there.

## Setting up on Windows

1. Install `uv` and Git. Clone the repository and open PowerShell in `backend`.
2. `uv sync` installs Python 3.12, all dependencies, and the CUDA 12.4 build of torch through the
   platform-marked source in `pyproject.toml`. Check with
   `uv run python -c "import torch; print(torch.cuda.is_available())"`, which must print `True`.
3. Copy `.env.example` to `.env` and fill in the four values: the Copernicus Marine username and
   password (free account at data.marine.copernicus.eu) and the NASA Earthdata username and
   password (free account at urs.earthdata.nasa.gov). The file is git-ignored and Docker-ignored.
   The pipeline reads it directly; no `.netrc` or toolbox login is needed.
4. Confirm both services are detected: `uv run python -m pipeline.download --check`.

## Running

One command does everything, skipping any stage whose output already exists:

```powershell
uv run python scripts/run_all.py --years 2016-2020 --cfg configs/lite.yaml
```

Stages in order: credential and disk check, download and regrid (one process per product in
parallel), assemble the Zarr store, train GBM, train lite, calibrate, export both, evaluate, and
precompute the cache plus the frontend fallback bundle. Rerunning after an interruption resumes.

Only the exported weights are meant to enter git: `artifacts/lite/poseidon-lite.onnx` and its
model card, and `artifacts/gbm/depth_*.txt` with its feature spec and card. Datasets, checkpoints
and caches are ignored by rule.

Optional head start: copying the Mac's `backend/data/interim` folder (1.7 GB) and the
`manifest.json` files under `backend/data/raw/<product>/` lets the Windows run skip the months
already regridded. Without it, the run downloads everything; on fast ethernet GLORYS (about 1.3 GB
per month) dominates and the six parallel streams should finish within a few hours.

## What to expect

| Stage | Memory | Time on the Windows machine (expected) |
|---|---|---|
| Download and regrid, six parallel streams | ~3 GB total | a few hours, bandwidth bound |
| Assemble store | under 1 GB (streams in 32-day chunks) | ~15 min |
| GBM, 15 boosters | ~1 GB | ~5 min |
| Lite, 10,000 steps, batch 32 | 3.4 GB VRAM chunked head, 5.5 GB unchunked | 10 to 20 min on the GPU |
| Evaluate and precompute, 731 test days | ~2 GB | ~30 to 40 min |

Config knobs that matter in `configs/lite.yaml`: `device: auto` picks CUDA; `head_chunk: 16384`
trades 25 percent speed for the lower VRAM figure and can be set to 0 on an 8 GB card; `steps`
and `batch` set the training budget. On the Mac the same step costs about one second, which is why
training was never completed there.

## Findings worth knowing

- Out-of-memory earlier came from three sources, all fixed: the synthetic generator and evaluator
  held whole-period arrays; the MPS trainer's evaluation batch differed in shape from training
  batches and the caching allocator was never emptied; the attention head expanded queries and
  concatenated them per pixel. Memory guard tests now cover each.
- The training step is dominated by the per-pixel attention head. A CUDA GPU fixes the wall-clock;
  RAM does not.
- Full-domain ONNX parity compares mean and log-sigma rather than sigma because float32
  reduction order differs between PyTorch and ONNX Runtime at 25,000 attention rows.
- The DUACS sea level product from the problem statement's DOI is 0.125 degrees and is block-meaned;
  GLORYS is the 0.25 degree ensemble member `thetao_glor`, chosen for download size.

## Still open

- A full-scale synthetic rehearsal on the Mac (100 x 240, five years, 600 lite steps) was in its
  evaluation stage at handover with a 2.7 GB peak; the real run on Windows supersedes it.
- The implementation spec `backend_mvp_implementation_spec.md` is kept for now by request.
- The full model, quantile boosters and the 1993 to 2020 range remain deferred.
