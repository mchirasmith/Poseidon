# Poseidon: Project and Backend Guide

For: frontend teammate
Companion doc: `poseidon_frontend_spec.md` (page-by-page UI spec)
Hackathon: SIH 2026, PS SIH26066, INCOIS (Ministry of Earth Sciences)

---

## 1. What we are building

A web app that predicts ocean temperature below the surface, every day, for the whole North Indian Ocean, using only satellite data.

- Input: five daily satellite maps of the ocean surface.
- Output: temperature at 15 depths (0 m to 1000 m) for every 0.25 deg grid cell, with an uncertainty on each value.
- Region: 5 N to 30 N, 45 E to 105 E. That's the Arabian Sea and the Bay of Bengal. 100 rows x 240 columns of cells.
- The dashboard shows the test results and lets a judge pick a day, run the model live, and explore the 3D result.

Deliverables INCOIS listed in the problem statement, and how they map to our work:

| INCOIS asks for | We build |
|---|---|
| Preprocessing pipeline | Python scripts that download, clean and regrid all datasets |
| Satellite embedding engine | The encoder half of the model |
| Reconstruction model | The decoder half of the model |
| Daily 0.25 deg output | NetCDF files, one per day |
| Validation with Argo | Evaluation scripts + Report page |
| Proof of concept over BoB / Arabian Sea | The Explorer and Section pages |

## 2. Why it matters (the pitch)

Ships and floats measure the deep ocean but they are rare. Argo floats give roughly one profile per 300 km x 300 km every 10 days. Satellites cover everything daily but only see the top few millimetres.

Heat stored below the surface is what powers cyclones. If INCOIS knows the subsurface heat every day, cyclone intensity forecasts improve. That's the disaster-management angle. Same data also feeds fisheries advisories and marine heatwave monitoring.

So: cheap daily satellite data in, expensive-to-measure subsurface field out.

## 3. The science, in plain English

You don't need this to build the frontend, but it helps you explain the demo.

- Sea surface height (SSH): warm water expands. If the water column is warmer, the surface bulges up by a few centimetres. Satellites measure this. So SSH is a summary of how much heat is below.
- Sea surface temperature (SST) plus wind: wind stirs the top 20 to 80 m into a uniform layer. If you know SST and wind, you know the temperature of that whole top layer.
- Sea surface salinity (SSS): in the Bay of Bengal, river water sits on top and blocks mixing. Low salinity is a warning that the surface no longer tells you about deeper water. Without SSS the model would get the Bay wrong.
- Currents: mostly derived from SSH, gives the model the shape of eddies.
- 9 days of history: the ocean responds to wind over days, so one snapshot isn't enough.

The model learns these relationships from data rather than us coding the equations.

Key words you will see in the UI:
- Thermocline: the depth band (roughly 50 to 150 m here) where temperature drops fast. The most interesting part of any profile.
- D20: depth of the 20 C isotherm. A standard proxy for thermocline depth.
- MLD: mixed layer depth, the bottom of the wind-stirred top layer.
- Profile: temperature vs depth at one location. A vertical line of 15 numbers.
- Section: a vertical slice along a line on the map. Depth on the y-axis, distance on the x-axis.
- Anomaly: difference from the normal value for that day of year and location.

## 4. Data

### Inputs (all free, public)

| Variable | Product | Native grid | Source |
|---|---|---|---|
| SST | OSTIA | 0.05 deg daily | Copernicus Marine |
| SSS | SMOS/SMAP multi-obs | 0.125 deg daily | Copernicus Marine |
| SSH / SLA | DUACS | 0.25 deg daily | Copernicus Marine |
| Currents U, V | OSCAR | 0.25 deg daily | NASA PO.DAAC |
| Winds U, V | CCMP | 0.25 deg 6-hourly | NASA PO.DAAC |

All are regridded to one 0.25 deg daily grid.

### Training target

GLORYS12V1: a global ocean reanalysis. A physics model run by Copernicus that assimilates real observations and outputs a full 3D ocean field daily at 1/12 deg with 50 depth levels. We regrid it to 0.25 deg and interpolate to our 15 depths. It is "model truth", not measurement, but it's the best gap-free 3D field that exists.

### Validation

Argo floats: real measurements. We never train on them. We compare our output with every Argo profile in the test years and report the error. The Report page shows Poseidon vs Argo and GLORYS vs Argo side by side so judges see how we compare to the reanalysis itself.

### Time split

| Years | Use |
|---|---|
| 1993 to 2016 | training |
| 2017 | development |
| 2018 | calibration |
| 2019 to 2020 | locked test set (this is what the dashboard shows) |

Random splits are forbidden. Adjacent days are nearly identical and would leak.

## 5. The model

Name: Poseidon. Size: about 2 million parameters (small).

```
5 input maps x 9 days
  -> per-variable CNN encoder (one for each of the 5 inputs)
  -> fusion across the 5 inputs (attention, handles missing inputs)
  -> small Transformer over the 9 days (only looks backward in time)
  -> 64-number "embedding" per cell        <- the satellite embedding INCOIS asked for
  -> spatial decoder + coast/bathymetry info
  -> 15 depth "tokens" decoded together with attention
  -> per depth: mean temperature, uncertainty, plus covariance between depths
```

Output per day: two arrays of shape `(15, 100, 240)`, mean and standard deviation, plus the raw covariance factors for computing intervals.

The model predicts anomalies (difference from a seasonal average) and the backend adds the seasonal average back before serving. You never see this; you get temperatures in degrees C.

Inference: full domain in a few seconds on CPU via ONNX. No GPU needed to serve.

## 6. End-to-end pipeline

Four stages. Only the last one is live.

```
[1] Preprocess (offline, once)
    download -> subset to region -> QC -> regrid to 0.25 deg daily
    -> compute climatology and normalisation stats (training years only)
    -> write one Zarr store: inputs (time, channel, lat, lon), targets (time, 15, lat, lon)

[2] Train (offline, GPU, hours)
    -> checkpoint .pt -> export to ONNX

[3] Evaluate (offline)
    run model on all test days -> compare with GLORYS and Argo
    -> report.json, error maps as PNG, Argo matchups as Parquet
    -> precompute all test days into the cache (tiles + NetCDF)

[4] Serve (live, FastAPI)
    on request: read 9-day window from Zarr -> ONNX -> tiles + NetCDF -> cache -> JSON to frontend
```

## 7. Backend architecture

```
frontend (Vercel)
      |  HTTPS, JSON + PNG tiles
      v
FastAPI app (Render or our own box)
  |-- routers/meta, report, run, day, profile, section
  |-- services/
  |     inference.py    loads ONNX once, runs a day
  |     tiles.py        arrays -> PNG using shared scales.json
  |     argo.py         nearest-float lookup from Parquet
  |     section.py      samples along a line, interpolates in depth
  |     cache.py        per-day results on disk
  |-- data/
  |     inputs.zarr     preprocessed test-year inputs + GLORYS truth
  |     climatology.nc  seasonal average to add back
  |     argo_matchups.parquet
  |     report.json + report tiles
  |     cache/<date>/   tiles, netcdf, profile precomputes
  |-- model/
        poseidon.onnx, scales.json, model_card.json
```

### Run flow for `POST /api/run`

1. Check `cache/<date>/`. If present and `force=false`, return `{cached: true}` immediately.
2. Otherwise create a job id, put it in an in-memory dict, start a background task.
3. Background task updates `job.stage` through: `load` (read 9 days from Zarr, ~0.3 s) -> `encode` -> `embed` -> `decode` (ONNX, ~2 to 4 s total) -> `render` (write 60 tiles + NetCDF, ~0.5 s).
4. Frontend polls `GET /api/run/{id}` every 300 ms and shows the stage.
5. On `done`, frontend calls `GET /api/day/<date>`.

Jobs live in memory. One worker. Fine for a demo; not fine for production, and we say so in the README.

### Tiles

Every map the frontend shows is a PNG rendered by the backend:
- Size 240 x 100 pixels, one pixel per grid cell. Frontend scales up with `image-rendering: pixelated`.
- Land is transparent. Below-seafloor cells at deep levels are a hatched pattern baked into the PNG.
- Colours come from `scales.json`, which the frontend also imports so the colour bar matches.

Modes and their fixed ranges:

| Mode | Range | Scale type |
|---|---|---|
| mean | 2 to 32 C | sequential thermal |
| sigma (uncertainty) | 0 to 2 C | sequential |
| anom (anomaly) | -4 to +4 C | diverging |
| error (vs GLORYS) | -3 to +3 C | diverging |

Per-depth ranges for `mean` are also returned so the frontend can offer a "per-depth scale" toggle.

### Static files

`/tiles/...` and `/download/...` are served straight from the cache directory by the same app. In production put them behind a CDN or just let Render serve them.

## 8. API reference

Base URL from env. Dates are `YYYY-MM-DD`. Lat/lon are cell centres (`x.125`, `x.375`, `x.625`, `x.875`).

| Method | Path | Purpose | Returns |
|---|---|---|---|
| GET | `/api/meta` | app config | model version, test date range, depths, grid, curated days, cached days |
| GET | `/api/report` | Report page data | metrics, per-depth series for all baselines, tile URLs for error maps, Argo scatter points, calibration curve, tables |
| POST | `/api/run` | start a run | `{job_id, cached}` |
| GET | `/api/run/{job_id}` | poll | `{state, stage, elapsed_ms, message}` |
| GET | `/api/day/{date}` | everything for one day | input tiles (with 9-day history), 15 tiles per mode, colour ranges, NetCDF URL, runtime |
| GET | `/api/profile?d&lat&lon` | one cell | 15 means, p10/p90, GLORYS, nearest Argo or null, D20/D26/MLD, local RMSE |
| GET | `/api/section?d&a=lat,lon&b=lat,lon&n` | a slice | distances, lats, lons, matrices for Poseidon/GLORYS/sigma, D20 and MLD lines, Argo markers |

Exact JSON shapes with examples are in `poseidon_frontend_spec.md`, section 11. Errors return `{error, detail}` with a 4xx/5xx status.

## 9. Local development for the frontend

You don't need the model or the data to start.

1. Clone the repo. `frontend/public/fallback/` contains `meta.json`, `report.json`, and full payloads plus tiles for five curated days and three sections. This is real model output.
2. Run `npm run dev`. With no `NEXT_PUBLIC_API_BASE` set, the app runs in fallback mode and reads those files. Build every page against this first.
3. When the backend is up, set `NEXT_PUBLIC_API_BASE=https://...` in `.env.local` and the same UI talks to the live API. The only visible difference: the date picker allows all test days, and Reconstruct really runs.
4. A mock server is also available: `cd backend && uvicorn mock:app`. It serves the fallback files through the real routes and fakes the run stages with delays. Use it to test polling and error states (`POST /api/run` with `{"date": "2019-02-30"}` returns a 400).

Fallback mode is also the production safety net. If the live backend is down during judging, the app degrades to the five bundled days and shows an amber dot. Never hide that.

## 10. What the frontend needs to be

Three pages plus About. Full detail in the spec; the short version:

- Report: metric cards, one chart of error vs depth with all baselines, two error maps, Argo scatter for Poseidon and GLORYS, calibration chart, two tables. Static data from `/api/report`.
- Explorer: date picker, Reconstruct button with stage pill, five input thumbnails on the left, 15 stacked depth tiles in the centre (CSS 3D, slider peels layers, click a cell), profile chart on the right with Poseidon, GLORYS and Argo.
- Section: map with a draggable line, heatmap of depth vs distance below it.
- About: static page with sources, model card, links.

Rules:
- URL holds all Explorer and Section state. Deep links must reproduce views.
- No science in the browser. If you're tempted to compute something, ask for an endpoint.
- Colour scales from `scales.json`. Never hardcode.
- Keyboard reachable, every chart has a "view as table" fallback.

## 11. Repo layout

```
poseidon/
  pipeline/        download, regrid, climatology, zarr writer
  model/           architecture, training, onnx export
  eval/            metrics, argo matchups, report.json, cache precompute
  backend/         FastAPI app, mock server, tile renderer, scales.json
  frontend/        Next.js + React + TS, public/fallback/
  data/            gitignored; zarr, parquet, cache
  docs/            this file, the frontend spec, model card
```

## 12. Who does what and when

| Week | Model/backend side | Frontend side |
|---|---|---|
| 1 | Pipeline done for test years, first trained model, ONNX export, `scales.json` frozen | Shell, routing, fallback loader, Report page against `report.json` |
| 2 | Evaluation, `report.json`, cache precompute for all test days, FastAPI routes live | Explorer with stack, slider, profile; Section page |
| 3 | Argo matchups, curated days chosen, deploy backend | Polish, keyboard, deep links, About, demo video |

Hand-off contract: `report.json`, `meta.json`, one full `day` payload and `scales.json` are delivered by end of week 1 so the frontend is never blocked.

## 13. FAQ

**Why only 2019 to 2020 in the date picker?**
Those are the locked test years. Showing other years would be showing training data, which proves nothing.

**Why do we show "Error vs GLORYS" if GLORYS isn't real observation?**
Because on the test set we know the GLORYS field for that day, and GLORYS is the closest thing to a full 3D truth. Argo is real but only exists at a few points; that's why it appears as dots in the profile, not as a map.

**Why is 1000 m the deepest level?**
Below roughly 700 m the surface tells you very little. INCOIS stopped the requirement at 1000 m for that reason.

**What if Reconstruct takes 8 seconds in the demo?**
Fine. The stage pill shows progress. Just never let it look frozen.

**What's the "embedding"?**
The 64 numbers per cell that the encoder produces. INCOIS specifically wants this as a reusable product. The dashboard doesn't visualise it in the PoC; the NetCDF download includes it.

**Can I use three.js for the stack?**
Don't. Fifteen PNGs with CSS `translateZ` gives the same visual in a fraction of the effort and works everywhere.
