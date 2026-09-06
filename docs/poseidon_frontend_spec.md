# Poseidon Dashboard: Frontend Specification

Version 0.1, SIH 2026, PS SIH26066
Status: draft for team review

---

## 1. Purpose

A web dashboard that (a) presents the held-out test-set report and (b) lets a judge pick any test-set day, run the model live on that day's satellite inputs, and explore the resulting 15-depth temperature field visually.

The dashboard is a client. The NetCDF output and the validation report are the scientific authority. Nothing in the UI computes science; it displays what the backend returns.

## 2. Users and goals

| User | Goal | Time budget |
|---|---|---|
| SIH evaluator (non-oceanographer) | See that it works, see numbers, see it run once | 3 minutes |
| INCOIS scientist (domain expert) | Check skill by depth and basin, inspect a profile against Argo, look at a section | 10 minutes |
| Team (demo video) | Scripted walkthrough that never breaks | 2 to 3 minute video |

Design rule: every page must make sense to the first user in 10 seconds and satisfy the second user on scroll or click.

## 3. Scope

In scope
- Three pages: Report, Explorer, Section.
- Test-set days only (locked test years, e.g. 2019-01-01 to 2020-12-31).
- Live model run on request, cached results otherwise.
- Read-only. No auth, no user accounts, no uploads.

Out of scope for the PoC
- Near-real-time ingest of today's satellite data.
- Editing, annotation, export beyond NetCDF download link.
- Mobile layout (must not break on tablet, is not optimised).

## 4. Information architecture

```
/                 -> redirect to /report
/report           Report page (default)
/explore          Explorer page
/explore?d=YYYY-MM-DD&lat=15.125&lon=88.125&z=100   deep-linkable state
/section          Section page
/section?d=YYYY-MM-DD&a=lat,lon&b=lat,lon
/about            One screen: PS, team, data sources, model version, links
```

All Explorer and Section state lives in the URL query string so any view can be shared and reopened.

## 5. Global shell

- Top bar, 56 px, full width: logo text "Poseidon", tab links (Report, Explorer, Section, About), right side shows `model vX.Y` and `test set 2019 to 2020` as muted chips, plus a status dot (green = backend reachable, amber = fallback mode, see section 12).
- No sidebar. Content width max 1440 px, centred, 24 px padding.
- Footer, one line: data sources with links, GitHub, NetCDF download for the current day (Explorer and Section only).
- Fonts: system sans. Two weights, 400 and 500.
- Light mode only for the PoC. Colour scales are picked to work on white.

## 6. Page: Report

Purpose: prove skill on the locked test set. Static data, loaded once from `/api/report`.

### 6.1 Layout, top to bottom

1. Headline row, four metric cards (grid 4 x 1)
   - RMSE (deg C), Bias (deg C), Correlation, CRPS (deg C)
   - Each card: label, big number (2 decimals), one-line sublabel "all depths, all test days, ocean cells only"
2. Skill by depth chart (full width, 380 px tall)
   - X: RMSE (deg C). Y: depth (m), inverted, 15 ticks at the standard depths, non-linear spacing (plot depth on a `symlog` or piecewise axis so 0 to 200 m gets half the height).
   - Series (fixed colours, fixed order in legend): Poseidon, Climatology, Ridge/EOF, U-Net (same day), ConvLSTM U-Net.
   - Toggle: RMSE / Bias / Correlation / Anomaly correlation (segmented control above chart).
   - Toggle: Basin: All / Bay of Bengal / Arabian Sea.
   - Toggle: Season: All / DJF / MAM / JJAS / ON.
   - Hover tooltip: depth, value per series.
3. Spatial error map (two panels side by side, each 45% width)
   - Left: RMSE map at a selected depth (dropdown, default 100 m), 0.25 deg grid, sequential colour scale, coastline overlay.
   - Right: Bias map at the same depth, diverging colour scale centred at 0.
   - Shared depth dropdown.
4. Argo consistency (two panels)
   - Left: scatter, observed (x) vs predicted (y), one point per Argo matchup at all depths, coloured by depth (same depth colour ramp used everywhere), 1:1 line, N shown.
   - Right: same scatter for GLORYS vs Argo at identical matchups.
   - Under both: small table with RMSE, bias, R for Poseidon and GLORYS side by side.
5. Uncertainty calibration (full width, 260 px)
   - Line chart: nominal coverage (x: 50, 80, 90, 95) vs empirical coverage (y). Diagonal reference line. Second axis or small table: mean interval width per level.
6. Per-basin and per-season table (markdown-style table rendered in HTML)
   - Rows: All, BoB, AS, DJF, MAM, JJAS, ON. Columns: RMSE, Bias, Corr, CRPS. Sortable not required.
7. Baseline and ablation table
   - Rows: Climatology, Coordinate-only, Ridge/EOF, U-Net, ConvLSTM, Poseidon mean-only, Poseidon. Columns: RMSE, Corr, CRPS, params, inference time.

### 6.2 States

- Loading: skeleton cards and grey chart boxes. No spinner text.
- Error: one inline banner at top, "Couldn't load the report. Retry", with retry button. Below it, cached copy of the report if one is bundled (see section 12).

## 7. Page: Explorer

Purpose: pick a day, run the model, look at 15 depths, click a cell, see a profile.

### 7.1 Layout

Three-column grid: 140 px | flexible | 280 px. Min content width 1100 px.

Header strip (full width above the grid)
- Date picker. Only test-set days selectable. Keyboard arrows step by one day. Left/right buttons step by one day. Quick picks dropdown: "Cyclone Amphan, 2020-05-18", "Pre-monsoon, 2019-04-15", "Missing SSS example, 2019-08-03", plus 3 to 5 more curated dates.
- Reconstruct button. Primary style. Disabled only while a run is in flight.
- Run status pill, right of the button. Shows one of:
  - idle: "Pick a day"
  - stages during run: "Loading inputs" -> "Encoding" -> "Embedding" -> "Decoding" -> "Rendering", each with elapsed ms
  - done: "Done in 3.2 s" (green) or "Loaded from cache, 0.1 s" (grey)
  - error: "Run failed. Retry" (red)
- Model chip: `poseidon vX.Y, ckpt abc123`.

Left column: Inputs
- Label "Inputs, t-8 to t".
- Five thumbnails, 120 x 60 px each, stacked: SST, SSS, SLA, Currents (speed, with sparse arrows), Winds (speed with sparse arrows).
- Each thumbnail shows day t. Hover shows a small colour-bar and value range. Click opens a modal with the full-size map and a 9-step scrubber (t-8 to t), keyboard left/right.
- Missing-data cells are hatched grey. If a modality is fully missing on a day, thumbnail shows "not available, model ran with mask".

Centre column: Depth stack
- Mode segmented control: Mean | Uncertainty | Anomaly | Error vs GLORYS.
- View toggle (icon button, top right of panel): 3D stack | Flat map.
- 3D stack view
  - 15 layers rendered as pre-coloured PNG tiles from the backend, positioned with CSS 3D transforms (rotateX 58 deg, rotateZ -28 deg, translateZ per layer, spacing 14 px).
  - Depth slider below (15 discrete steps, labelled with metres). Selected layer at full opacity with a 2 px outline; layers above it at 15% opacity; layers below at 92%.
  - Depth labels on the right edge of each layer.
  - Hover on the selected layer shows lat, lon, value in a tooltip.
  - Click on the selected layer sets the profile point (updates URL `lat`, `lon`, and the right column).
  - Land is drawn as a flat neutral grey with coastline; below-bottom cells (e.g. 1000 m over shelf) are hatched.
- Flat map view
  - Single layer at the selected depth, larger (fills panel), same slider, same click behaviour, lat/lon graticule every 5 deg, basin labels "Arabian Sea" and "Bay of Bengal".
- Colour bar, always visible, bottom left of panel. Fixed scale per mode:
  - Mean: fixed across all depths, 2 to 32 deg C, sequential thermal ramp.
  - Uncertainty: 0 to 2 deg C (1 sigma), sequential.
  - Anomaly: -4 to +4 deg C, diverging centred on 0.
  - Error: -3 to +3 deg C, diverging.
  - Toggle "per-depth scale" (checkbox) rescales Mean to each depth's own 2nd to 98th percentile. Label changes to warn that colours no longer compare across layers.
- Animate button: steps the depth slider from 0 to 1000 m over 4 s. Used in the demo video.

Right column: Profile
- Header "Profile at {lat} N, {lon} E" with a small copy-link icon.
- Profile chart, 280 x 240 px: temperature (x) vs depth (y, inverted, same piecewise depth axis as Report). Series: Poseidon mean (solid), 80% interval (filled band), GLORYS (dashed), Argo (points, only if a matchup exists). Legend below.
- Argo matchup note: "Argo float {WMO id}, {distance} km, {days} d offset" or "No Argo within 0.5 deg and 2 days".
- Scalars card: D20, D26, MLD (from the predicted profile), local RMSE vs GLORYS, local RMSE vs Argo (if any).
- Button: "Open section through this point" -> navigates to `/section` with a default east-west line through the point.

### 7.2 Behaviour

- On page load with `?d=` in URL: fetch `/api/day/{d}`. If cached, render immediately. If not, do not auto-run; show the Reconstruct button in an attention state.
- Reconstruct: POST `/api/run`, then poll `/api/run/{job_id}` every 300 ms until done, mapping stage names to the status pill. On done, fetch `/api/day/{d}` and render.
- Depth slider, mode switch, view toggle: client-only, no network.
- Cell click: GET `/api/profile?d=&lat=&lon=`. Cache in memory per (d, lat, lon).
- Date change clears the profile panel but keeps lat/lon in URL; profile refetches after the new day is loaded.

### 7.3 States

- No day loaded: centre panel shows an empty state with the depth stack drawn in grey outline and one line "Pick a test day and reconstruct".
- Run in flight: keep last day's stack visible at 40% opacity with a progress bar across the top of the panel.
- Run failed: banner in panel, keep previous state.
- Backend unreachable: switch to fallback mode (section 12); date picker restricts to the bundled days.

## 8. Page: Section

Purpose: depth-versus-distance slice, the view oceanographers expect.

### 8.1 Layout

Two rows.

Row 1, 40% height: flat map at a chosen depth (reuse Flat map component, default 100 m) with a draggable line A to B. Endpoints are draggable handles; the line is a great-circle approximation drawn as straight in lat/lon. Presets dropdown: "BoB north-south along 88 E", "Arabian Sea east-west along 15 N", "Equatorial edge 5 N".

Row 2, 60% height: section heatmap.
- X: distance along the line in km, with lat/lon ticks at both ends and every 500 km.
- Y: depth 0 to 1000 m, inverted, same piecewise axis.
- Values interpolated from the 15 levels (linear in depth, nearest cell along the line, up to 200 samples).
- Mode segmented control: Poseidon | GLORYS | Difference | Uncertainty.
- Overlays (checkboxes): D20 contour (black), MLD line (white), Argo profiles within 0.5 deg of the line shown as vertical dotted markers.
- Colour scale same as Explorer Mean/Anomaly/Error.

### 8.2 Behaviour

- Changing the line or day: GET `/api/section?d=&a=lat,lon&b=lat,lon&n=200`. Debounce drags at 250 ms; render on drag end.
- Day picker in header identical to Explorer, shares the same URL param.

## 9. Page: About

Single scroll. PS title and ID, one-paragraph description, team, data sources with product versions and DOIs, model card (params, training years, test years, split rules, purge window), links to GitHub, NetCDF sample, demo video. No interactivity.

## 10. Components

| Component | Used in | Props (key ones) |
|---|---|---|
| `MetricCard` | Report | label, value, unit, sublabel |
| `DepthAxisChart` | Report, Explorer, Section | series[], metric, depths[], axis mode |
| `DatePicker` | Explorer, Section | value, allowedRange, curatedDates[], onChange |
| `RunStatusPill` | Explorer | state, stage, elapsedMs |
| `InputThumbnail` | Explorer | variable, tileUrl, range, missingFraction, onClick |
| `DepthStack` | Explorer | tiles[15], selectedIndex, mode, onSelectCell |
| `FlatMap` | Explorer, Section | tile, depth, graticule, onClick, line (optional) |
| `DepthSlider` | Explorer | depths[], index, onChange, animate |
| `ColorBar` | Explorer, Section | scale, range, label |
| `ProfileChart` | Explorer | poseidon[], interval[], glorys[], argo[] |
| `ScalarsCard` | Explorer | d20, d26, mld, rmseGlorys, rmseArgo |
| `SectionHeatmap` | Section | matrix, distances[], depths[], overlays |
| `Banner` | all | tone (info, warning, error), message, action |

All charts through one wrapper around Plotly so axis conventions (inverted depth, piecewise spacing, colour scales) are defined once.

## 11. API contract

Base URL from env `NEXT_PUBLIC_API_BASE`. All responses JSON unless noted. All dates `YYYY-MM-DD`. Lat/lon are cell centres on the 0.25 deg grid (x.125 convention).

### `GET /api/meta`
```json
{
  "model_version": "0.3.1",
  "checkpoint": "abc1234",
  "test_range": ["2019-01-01", "2020-12-31"],
  "depths_m": [0,5,10,20,30,50,75,100,125,150,200,300,500,700,1000],
  "grid": {"lat_min": 5.125, "lat_max": 29.875, "lon_min": 45.125, "lon_max": 104.875, "step": 0.25, "ny": 100, "nx": 240},
  "curated_days": [{"date": "2020-05-18", "label": "Cyclone Amphan"}],
  "cached_days": ["2019-01-01", "..."]
}
```

### `GET /api/report`
Returns the full report payload: headline metrics, by-depth arrays per model per metric per basin per season, map arrays (or tile URLs) for RMSE and bias per depth, Argo scatter points, calibration curve, tables. Shape documented in `report.schema.json` in the repo. Size target under 3 MB; maps served as PNG tile URLs, not arrays.

### `POST /api/run`
Body `{"date": "2020-05-18", "force": false}`. Returns `{"job_id": "...", "cached": true|false}`. If cached and `force` is false, no job runs; the client proceeds to `/api/day`.

### `GET /api/run/{job_id}`
```json
{"state": "running|done|error", "stage": "load|encode|embed|decode|render", "elapsed_ms": 1840, "message": null}
```

### `GET /api/day/{date}`
```json
{
  "date": "2020-05-18",
  "cached_at": "2026-09-05T10:00:00Z",
  "runtime_ms": 3210,
  "inputs": {
    "sst": {"tile": "/tiles/2020-05-18/in/sst_t0.png", "range": [24.1, 31.8], "missing_fraction": 0.0, "history": ["/tiles/.../sst_t-8.png", "..."]},
    "sss": {"...": "..."}, "sla": {"...": "..."}, "cur": {"...": "..."}, "wind": {"...": "..."}
  },
  "layers": {
    "mean":  ["/tiles/2020-05-18/mean/z00.png", "..."],
    "sigma": ["/tiles/2020-05-18/sigma/z00.png", "..."],
    "anom":  ["..."],
    "error": ["..."]
  },
  "scales": {"mean": [2, 32], "sigma": [0, 2], "anom": [-4, 4], "error": [-3, 3]},
  "per_depth_scales": {"mean": [[24, 32], [23.5, 31.9], "..."]},
  "netcdf_url": "/download/poseidon_2020-05-18.nc"
}
```
Tiles are 240 x 100 px PNG (one pixel per cell), rendered by the backend with the agreed colour scales, land transparent. Frontend upsamples with `image-rendering: pixelated`.

### `GET /api/profile?d=&lat=&lon=`
```json
{
  "lat": 15.125, "lon": 88.125,
  "depths_m": [0, "..."],
  "poseidon_mean": [29.4, "..."], "poseidon_p10": ["..."], "poseidon_p90": ["..."],
  "glorys": [29.3, "..."],
  "argo": {"wmo": "2902123", "distance_km": 31, "day_offset": -1, "depths_m": ["..."], "temp": ["..."]} ,
  "scalars": {"d20_m": 112, "d26_m": 71, "mld_m": 31, "rmse_glorys": 0.41, "rmse_argo": 0.48}
}
```
`argo` is `null` when no matchup within 0.5 deg and 2 days.

### `GET /api/section?d=&a=lat,lon&b=lat,lon&n=200`
```json
{
  "distances_km": ["..."], "lats": ["..."], "lons": ["..."],
  "depths_m": ["..."],
  "poseidon": [[...15 values...], "..."], "glorys": ["..."], "sigma": ["..."],
  "d20_m": ["..."], "mld_m": ["..."],
  "argo_markers": [{"distance_km": 640, "wmo": "..."}]
}
```

### Errors
Non-2xx returns `{"error": "short message", "detail": "optional"}`. Frontend shows `error` in a banner, logs `detail` to console.

## 12. Fallback mode

The demo must survive a dead backend.

- Repo ships `public/fallback/` containing: `meta.json`, `report.json`, report tiles, and full `day` payloads plus tiles and profiles for 5 curated days, plus 3 precomputed sections.
- On load, `/api/meta` is fetched with a 3 s timeout. On failure, the app sets `fallback = true`, shows an amber status dot with tooltip "Running from bundled results", restricts the date picker to the 5 bundled days, and serves everything from `public/fallback/`.
- Reconstruct in fallback mode plays the stage animation for 1.2 s then loads the bundled payload. The status pill says "Loaded bundled result".
- Fallback is never silent. The amber dot and the pill text always reveal it.

## 13. Visual design

- Colour scales (define once in `scales.ts`, used by backend tile renderer too, shared JSON):
  - Thermal (Mean): perceptually uniform, e.g. `cmocean.thermal` sampled to 256 stops.
  - Diverging (Anomaly, Error, Bias): `cmocean.balance`.
  - Sequential (Uncertainty, RMSE): `cmocean.amp` or `viridis`.
  - Depth categorical ramp (Argo scatter, legends): 15 stops from warm to cold following the thermal ramp.
- Series colours: Poseidon blue `#378ADD`, GLORYS grey `#888780` dashed, Argo coral `#D85A30`, baselines in muted purple/teal/amber, fixed and documented.
- Typography: 13 px labels, 14 px body, 24 px metric numbers, 500 weight for numbers and headings only.
- Land: `#E8E6DF`. Coastline: 0.75 px `#5F5E5A`. Graticule: 0.5 px `#D3D1C7`.
- No shadows, no gradients in chrome. Charts have hairline borders.

## 14. State management

- URL is the source of truth for `d`, `lat`, `lon`, `z` (depth index), `mode`, `view`, `a`, `b`.
- One `useDay(date)` hook wraps fetch + cache (in-memory Map keyed by date, max 30 entries).
- One `useRun()` hook wraps POST + polling and exposes `{state, stage, elapsedMs, start, cancel}`.
- Profile and section fetches are keyed by their full query string and cached the same way.
- No global store beyond React context for `meta` and `fallback`.

## 15. Performance targets

- First contentful paint under 1.5 s on a laptop over hotel Wi-Fi.
- Report page fully interactive under 3 s (tiles lazy-load below the fold).
- Depth slider and mode switch respond within one frame (all 60 tiles for a day prefetched after `day` payload arrives).
- Reconstruct end to end under 6 s on the demo machine; under 10 s is acceptable with the stage pill visible.
- Bundle under 1.5 MB gzipped excluding fallback assets.

## 16. Accessibility and input

- All controls keyboard reachable. Date picker: arrow keys step days. Depth slider: arrow keys step levels, Home/End jump.
- Every chart has a text summary in an `aria-label` and a "View data as table" link that opens the numbers in a modal.
- Colour is never the only channel: series have distinct dash patterns; missing data is hatched, not just grey.
- Minimum text size 12 px.

## 17. Error and empty states (summary)

| Situation | Behaviour |
|---|---|
| Backend down at load | Fallback mode, amber dot |
| Backend down mid-session | Banner "Lost connection, showing bundled results", switch to fallback |
| Run error | Red pill with Retry, keep previous day visible |
| Day outside test range | Date picker prevents it; deep link shows banner and snaps to nearest valid day |
| No Argo near clicked point | Profile shows Poseidon and GLORYS only, note explains |
| Cell over land or shelf below bottom | Tooltip "land" or "below seafloor", click ignored |
| Modality missing that day | Thumbnail note, model runs with mask, stack renders normally |

## 18. Tech stack

- Next.js 16, App Router, React 19, TypeScript.
- Plotly.js for charts and the section heatmap, as a custom partial bundle: `plotly.js/lib/core` with scatter, scattergl, heatmap and contour registered. The basic bundle is not enough, it has no heatmap or contour trace, and the full and cartesian bundles blow the size budget in section 15.
- Plain CSS 3D for the depth stack. No three.js.
- App Router for routes. URL state through `useSearchParams` and `router.replace`.
- Every page is a client component. Nothing is server-rendered; the app is a static client that talks to FastAPI. Plotly is loaded through `next/dynamic` with `ssr: false` because it touches `window` on import.
- Deploy: Vercel (frontend), backend on Render or a self-managed GPU box; `NEXT_PUBLIC_API_BASE` per environment.

Repo layout
```
frontend/
  src/
    app/
      layout.tsx                              global shell, top bar, footer
      page.tsx                                redirect to /report
      {report,explore,section,about}/page.tsx
    components/...
    hooks/{useMeta,useDay,useRun,useProfile,useSection}.ts
    lib/{api.ts,scales.ts,depthAxis.ts,url.ts}
  public/fallback/...
  scales.json          shared with backend renderer
```

## 19. Acceptance criteria (PoC done when all pass)

1. `/report` loads with real test-set numbers, all five baselines on the depth chart, Argo scatter for both Poseidon and GLORYS.
2. `/explore` with a curated date: Reconstruct runs live, stage pill advances, stack renders 15 layers, slider peels, click gives a profile with GLORYS and at least one Argo matchup on at least 3 curated days.
3. Mode switch to Error vs GLORYS works and the colour bar updates.
4. `/section` preset "BoB north-south along 88 E" renders with D20 contour.
5. Kill the backend, reload: app enters fallback mode within 3 s, all 5 curated days still work end to end.
6. Every page reachable by keyboard, every chart has a data table.
7. Deep link `/explore?d=2020-05-18&lat=15.125&lon=88.125&z=7&mode=anom&view=flat` reproduces the exact view.
8. Demo video recorded from this build, 2 to 3 minutes, covering criteria 1, 2, 4.

## 20. Open decisions

- Tile size: 1 px per cell (240 x 100) upsampled, or 4 px per cell rendered server-side. Start with 1 px; switch if pixelated upsampling looks bad in the video.
- Depth axis spacing function: agree on one and use it in Report, Explorer and Section.
- Whether Section interpolates in depth linearly or shows 15 discrete bands. Start linear, keep a toggle in code.
- Curated day list: pick 5 to 8 with the science team, including at least one failure case.
