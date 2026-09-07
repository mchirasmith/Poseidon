# Poseidon backend: handover for the Windows machine

Operations note for the data download, training and frontend bundle on the Windows laptop
(RTX 5070 Laptop GPU, 8 GB VRAM, 32 GB RAM, 24 logical cores). Updated 2026-09-07 after the
first end-to-end run there.

## Where things stand

- Branch `backend` now contains the merged `frontend` branch. The frontend reads everything from
  the static bundle in `frontend/public/fallback`, so it can be hosted without the API.
- The 2016 to 2020 store, both models, the evaluation report and the bundle were produced on this
  machine on 2026-09-07. Exported weights and the bundle are committed; datasets, caches and
  checkpoints stay out of git.
- The real download was paused part-way. SST, SSS and sea level are complete. Currents (16
  months), wind (12) and GLORYS (20) are real through 2016 for every product and partly through
  2017; every later month of those three products is a **replayed copy** of the same calendar
  month from the latest real year (`data/interim/<product>/manifest.json` lists them under
  `faked_missing`; `manifest.real.json` next to it is the true download state). Training used
  2016 only, so the models are trained on real data, but the 2018 calibration and the 2019 to
  2020 GLORYS "truth" are replayed years. The Argo comparison is against real, independent
  profiles and is the honest skill number.

| Held-out 2019 to 2020 | vs Argo profiles (62,382 pairs) | vs replayed GLORYS (thermocline RMSE) |
|---|---|---|
| Poseidon lite | 1.18 °C RMSE, bias +0.05, r 0.983 | 1.30 °C |
| GBM baseline | 1.04 °C RMSE, bias +0.10, r 0.987 | 1.45 °C |
| Harmonic climatology | 1.30 °C RMSE | 1.31 °C |
| GLORYS field itself | 1.43 °C RMSE | — |

Calibration coverage after the 2018 temperature scaling: 54, 81, 89 and 93 percent at nominal
50, 80, 90 and 95 percent; CRPS 0.42 °C.

## Setting up on Windows

1. Install `uv`, Git and Node 24. Clone the repository and open PowerShell in `backend`.
2. `uv sync` installs Python 3.12 and the **CUDA 12.8** build of torch (the RTX 5070 is compute
   capability 12.0; the cu124 wheel has no kernels for it). Check with
   `uv run python -c "import torch; print(torch.cuda.get_arch_list())"`, which must list `sm_120`.
3. Copy `.env.example` to `.env` and fill in the Copernicus Marine and NASA Earthdata credentials.
4. `uv run python -m pipeline.download --check` must print `credentials ok`.
5. `cd ../frontend && npm ci` for the frontend.

## Running

```powershell
uv run python scripts/run_all.py --years 2016-2020 --cfg configs/lite.yaml
```

Stages: credential and disk check, download and regrid (one process per product), assemble the
Zarr store (worker pool, all cores but three, capped by free RAM), Argo matchups (threaded
download, pooled parsing), GBM, lite, calibrate, export, evaluate, precompute. Each stage is
skipped when its output exists; `--force` reruns it, `--only stage,stage` selects stages. The
precompute stage writes the frontend bundle for the five days in `configs/curated_days.json`.

Frontend: `npm run build` in `frontend` produces a fully static site; `npm run dev` for local work.

## What to expect on this machine

| Stage | Time observed |
|---|---|
| Assemble store, 21 workers | under 3 min (masks 35 s, climatology 25 s, stats 20 s, write 100 s) |
| Argo: 35k profile downloads, 16 threads; parse and match | ~40 min download, ~2 min parse |
| GBM, 15 boosters | 100 s |
| Lite, 10,000 steps, batch 32 | 73 min at 6 GB VRAM, GPU fully busy |
| Evaluate, 731 test days | 17 min |
| Precompute cache and bundle, 731 days, both models | 25 min |

## Findings from the first real run

- Real Copernicus salinity carries a size-1 depth axis and OSCAR currents use a Julian calendar;
  both are normalised at regrid time now. Argo QC flag strings must not be stripped, or the flags
  drift off their pressure levels.
- The coast-distance static channel is in kilometres; fed raw into the head it drove the initial
  NLL into the millions and log-sigma onto its hard clamp, after which the uncertainty never
  recovered (dev NLL 6.919 for all 10k steps, calibration alphas on the floor). The model now
  scales that channel by 1/1000 internally and bounds log-sigma with a smooth tanh.
- The per-step `torch.cuda.empty_cache()` held the GPU at about 25 percent utilisation; it is
  MPS-only now.

## To finish the real dataset

Restore `manifest.real.json` over `manifest.json` for `cur`, `wnd` and `glorys`, delete the
files listed under `faked_missing`, delete `data/poseidon.zarr` (the assembly-done check keys only
on products, years and grid), run the download, then rerun training, evaluate and precompute.
GLORYS is the long pole at about 1.3 GB per month.

## Still open

- The full model, quantile boosters and the 1993 to 2020 range remain deferred.
- `best.pt` is chosen by dev NLL, which peaks early (step 1000) while dev RMSE keeps improving to
  step 3000; selecting on RMSE, or on NLL after calibration, may give a better exported model.
