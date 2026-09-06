# Poseidon product and frontend roadmap

## What we are building

Poseidon is the SIH 2026 (PS SIH26066) dashboard for reconstructing North Indian Ocean subsurface temperature from surface satellite observations. It must present held-out test-set evidence and let a reviewer run a selected test day, inspect the predicted 15-depth temperature field, inspect a point profile, and view a vertical section.

The frontend is a scientific-data client: the backend NetCDF outputs and validation report are the authority. The UI must display returned values and not calculate scientific results independently.

## Audiences and primary workflows

| Audience | Primary workflow |
| --- | --- |
| SIH evaluator | In about three minutes, see the validation evidence and one successful reconstruction. |
| INCOIS scientist | Compare skill by depth/basin, inspect a predicted profile against Argo/GLORYS, then inspect a depth-versus-distance section. |
| Demo team | Use curated test dates and fallback data for a repeatable two-to-three-minute video. |

The product specification is [poseidon_frontend_spec.md](./poseidon_frontend_spec.md). It defines the intended Report, Explorer, Section, and About experiences, the backend contract, fallback behavior, accessibility, and acceptance criteria. It is a draft, not evidence that those features already exist.

## Current implementation inventory

The current frontend is a Next.js landing page plus an honest `/report` availability scaffold and the `/section` route; shared route navigation is implemented, but the data-backed dashboard is not built yet:

- [`frontend/src/app/page.tsx`](../frontend/src/app/page.tsx) implements the Poseidon hero and route links for `/section` and `/report`, plus the landing feature-card entry point.
- [`frontend/src/components/landing/feature-cards.tsx`](../frontend/src/components/landing/feature-cards.tsx) makes the landing cards explanatory triggers for a reusable glass modal. The Validation Report and Ocean Section modals offer `/report` and `/section` CTAs.
- [`frontend/src/components/ui/feature-modal.tsx`](../frontend/src/components/ui/feature-modal.tsx) provides that reusable card-trigger dialog with close controls, Escape handling, scroll locking, and focus return.
- [`frontend/src/app/report/page.tsx`](../frontend/src/app/report/page.tsx) implements an availability-only Report scaffold: headline metric labels, skill-by-depth controls and comparison-series labels, spatial error/bias, Argo/reference consistency, calibration, summary, and baseline/ablation regions. Every region explicitly says its report data is unavailable; no scientific values are rendered and no data connection exists.
- [`frontend/src/app/layout.tsx`](../frontend/src/app/layout.tsx) applies product metadata and fonts, wraps the app in the implemented site-wide `KineticGrid`, and mounts the shared navigation.
- [`frontend/src/components/ui/limelight-nav.tsx`](../frontend/src/components/ui/limelight-nav.tsx) provides the shared Home (`/`), Validation report (`/report`), and Ocean section (`/section`) route links. Its active-route limelight uses Framer Motion and resolves to an immediate state for reduced-motion users.
- [`frontend/src/components/ui/kinetic-grid.tsx`](../frontend/src/components/ui/kinetic-grid.tsx) implements the globally mounted canvas surface, exact five-stop vertical gradient, depth-aware grid contrast, pointer warp/ripples, reduced-motion handling, visibility pausing, and device-pixel-ratio cap.
- [`frontend/src/components/ui/the-infinite-grid.tsx`](../frontend/src/components/ui/the-infinite-grid.tsx) is retained legacy code; only its card-level `SubtleGridBackground` mounts were removed from the landing page.
- [`frontend/src/lib/utils.ts`](../frontend/src/lib/utils.ts) supplies the shadcn-compatible `cn` helper.

`/report` exists, but it is not a scientific-data view until an approved payload is connected. About remains unbuilt. There are no API clients/hooks, charts, fallback payloads, tiles, `report.schema.json`, or model data in this repository. The static public files are the default Next starter assets.

## Delivery phases

### Phase 0 — architecture, visual foundation, and fixtures

Deliverables:

- Record the resolved framework/environment decision and update the API environment variable for Next.js.
- In progress: create the app-route skeleton and shared shell/navigation. Shared Home, Report, and Section navigation is complete; `/about` remains unbuilt.
- Completed: replace the full-page drifting grid with globally mounted `KineticGrid` and remove the legacy card-level `SubtleGridBackground` mounts from the landing page.
- Completed: have `KineticGrid` render the global five-stop vertical surface `#FFDDB0` → `#E3F2FD` → `#90CAF9` → `#2196F3` → `#0D47A1`, with depth-aware grid contrast.
- Completed: make landing feature cards open a reusable glass modal that links to the available Report scaffold and describes Section as a planned experience.
- Completed: give the Validation Report and Ocean Section modals their `/report` and `/section` CTAs while retaining `Got it`.
- Define TypeScript API payload types, shared depth-axis/scales utilities, and an explicit fallback file layout.
- Obtain representative, non-scientific fixture payloads only if clearly labelled as fixtures.

Exit criteria: `/`, `/report`, `/section`, and `/about` have intentional route behavior; the app has a documented API base configuration and no route implies unavailable data is real.

## Next phase — Report-first vertical slice

Continue the Report-first vertical slice next. The availability scaffold is implemented; it answers no scientific question until it receives one approved read-only payload. The Explorer route has been removed; if it returns it still has larger upstream dependencies: job polling, tiles, profiles, cached dates, and fallback data.

1. Define Report payload types and a Next-compatible API boundary, with loading, error, and explicitly labelled unavailable states; do not invent scientific values.
2. Connect the first approved backend or bundled payload to headline metrics, skill-by-depth series, and the two summary tables, preserving the current availability state for missing fields.
3. Add the approved map, Argo/reference, and calibration visualisations through the selected chart wrapper, with table alternatives.
4. Reuse the implemented shared dashboard navigation and verify keyboard access, error handling, and loading performance before extending the Report.

Before wiring real data, decide whether the frontend uses `NEXT_PUBLIC_API_BASE` with CORS or a Next route-handler proxy; obtain the approved, versioned report schema/payload (including filters, series, units, tiles, empty/error rules, and cache expectations); confirm the chart library and bundle strategy; and decide whether the Report uses the global branded visual surface or the specification's light scientific canvas.

### Phase 1 — report

Status: availability-only scaffold complete. It includes the metric, skill-by-depth, spatial error/bias, Argo/reference, calibration, summary, and baseline/ablation regions, but contains no scientific values and has no data connection.

Next increment blockers: choose the API boundary; obtain the approved versioned schema/payload and fallback policy; choose the chart bundle and shared depth/scale conventions; decide the Report visual surface.

Remaining deliverables: report loading/error/fallback states; connected metric cards; skill-by-depth chart controls; spatial, Argo, calibration, and summary/baseline views through one chart convention.

Exit criteria: a backend or explicitly labelled fallback payload renders every Report element needed for acceptance criterion 1, with keyboard access and table alternatives.

### Phase 2 — explorer

Status: not started. The former no-data `/explore` scaffold and its `OceanLayerExplorer` component were removed; no Explorer route exists.

Deliverables: meta/day fetching and cache; test-day picker; run polling/status; inputs; 15-layer/flat-map modes; depth controls; profile fetch/cache; deep-link state.

Exit criteria: a curated date can be reconstructed or loaded from cache, the selected cell retrieves a profile, modes update client-side, and the documented Explorer deep link reproduces state.

### Phase 3 — section

Deliverables: shared flat-map line editor, presets, debounced section request, heatmap modes, and D20/MLD/Argo overlays.

Exit criteria: the 88 E Bay of Bengal preset produces a labelled section from a real or clearly labelled fallback response.

### Phase 4 — resilience and demo readiness

Deliverables: five curated fallback days and three sections supplied by the scientific/backend team; backend timeout/switchover; accessibility summaries/data tables; performance checks; demo script/video.

Exit criteria: all specification acceptance criteria pass, including a backend-off reload that visibly enters fallback mode.

## Mismatches and decisions needed before data work

| Topic | Specification | Repository reality | Decision needed |
| --- | --- | --- | --- |
| Frontend platform | Vite, React 18, React Router | Next 16.3, React 19, App Router | Keep Next and translate route/state guidance to App Router, or intentionally migrate. Keeping Next is the lower-churn path. |
| API configuration | `VITE_API_BASE` | Next exposes browser variables only with `NEXT_PUBLIC_` prefix | Adopt `NEXT_PUBLIC_API_BASE` for client fetches, or proxy backend calls through Next route handlers. |
| Root route | `/` redirects to `/report` | `/` is a marketing landing page | Retain the landing page as an intentional entry point, or implement the specified redirect. |
| Visual system | Light-only; no chrome gradients or shadows | Globally mounted `KineticGrid` renders `#FFDDB0` → `#E3F2FD` → `#90CAF9` → `#2196F3` → `#0D47A1` with depth-aware contrast; the landing retains some gradient/shadow styling | Decide whether the dashboard uses the scientific light system while the branded global treatment remains, or revise the spec. |
| Charts | Plotly basic bundle | Plotly is not installed | Confirm Plotly and bundle strategy before Phase 1. |
| Fallback/schema assets | Required by the spec | Absent | Backend/science team must supply validated payloads, tiles, and schema before resilience claims. |

Open scientific/product decisions remain those listed in the specification: tile resolution, shared depth-axis function, discrete versus interpolated section rendering, and the curated day set.
