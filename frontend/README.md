This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

## Precomputed data (no backend needed)

The section and report pages read static files from `public/fallback`, written by
`backend/scripts/run_all.py` (stage `precompute`, module `backend/eval/precompute.py`):

- `meta.json` — model version, grid, `curated_days` (the only dates the section page offers).
- `report.json` — evaluation on the held-out 2019–2020 days: per-depth RMSE / bias / correlation /
  skill for lite, GBM and climatology, Argo matchup stats, calibration coverage.
- `days/<date>/fields.bin` + `fields.json` — float16 mean, sigma and GLORYS temperature on the 15
  standard depths over the whole grid (about 2 MB per day); `src/lib/fallback.ts` cuts a vertical
  section along any transect in the browser with the backend's nearest-cell, D20 and MLD rules.
- `days/<date>/argo.json` — Argo float positions within ±2 days, matched within 55 km of the line.
- `days/<date>/sections/<preset>.json`, `day.json`, `profile.json`, `tiles/` — the API's own
  responses for the same day, kept for parity checks and the depth-plane tiles.

Regenerate after retraining; the bundle is committed so a static deploy (`npm run build`) is self-contained.
