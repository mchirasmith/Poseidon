/**
 * Offline data path: everything the pages need is served as static files from
 * `public/fallback`, written by `backend/eval/precompute.py`. No API server is
 * required to browse the curated test days.
 *
 * Per curated day the bundle holds `fields.bin` (float16 mean, sigma and GLORYS
 * temperature on the 15 standard depths over the whole grid) plus the Argo
 * profiles of that day, so a vertical section along ANY transect is cut here in
 * the browser with the same nearest-cell rule the backend uses.
 */
import type { ArgoMarker, SectionData, TransectCoordinate } from "@/lib/section";

export const FALLBACK_BASE = "/fallback";

/** Same matchup radius as the backend's `argo_max_km` setting. */
const ARGO_MAX_KM = 55;
const MLD_DELTA_C = 0.2;
const MLD_REF_DEPTH_M = 10;
const EARTH_RADIUS_KM = 6371;

export interface CuratedDay {
  date: string;
  label: string;
}

export interface FallbackMeta {
  model_version: string;
  test_range: [string, string];
  depths_m: number[];
  grid: { lat_min: number; lat_max: number; lon_min: number; lon_max: number; step: number; ny: number; nx: number };
  curated_days: CuratedDay[];
  cached_days: string[];
  models_available: string[];
}

interface FieldsHeader {
  order: string[];
  dtype: "float16";
  shape: [number, number, number, number];
  lat: number[];
  lon: number[];
  depths_m: number[];
}

export interface ArgoPosition {
  wmo: string;
  lat: number;
  lon: number;
  day_offset: number;
}

export interface DayFields {
  date: string;
  lat: number[];
  lon: number[];
  depths: number[];
  /** Each is (D, H, W) flattened row-major. */
  mean: Float32Array;
  sigma: Float32Array;
  glorys: Float32Array;
  argo: ArgoPosition[];
}

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${FALLBACK_BASE}${path}`);
  if (!res.ok) throw new Error(`fallback ${path}: ${res.status}`);
  return (await res.json()) as T;
}

export function loadMeta(): Promise<FallbackMeta> {
  return fetchJson<FallbackMeta>("/meta.json");
}

/** IEEE half precision, little-endian, to float32. */
function decodeFloat16(bytes: ArrayBuffer): Float32Array {
  const view = new DataView(bytes);
  const n = bytes.byteLength / 2;
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const h = view.getUint16(i * 2, true);
    const sign = h & 0x8000 ? -1 : 1;
    const exp = (h >> 10) & 0x1f;
    const frac = h & 0x3ff;
    if (exp === 0) out[i] = sign * Math.pow(2, -14) * (frac / 1024);
    else if (exp === 0x1f) out[i] = frac ? NaN : sign * Infinity;
    else out[i] = sign * Math.pow(2, exp - 15) * (1 + frac / 1024);
  }
  return out;
}

export async function loadDayFields(date: string): Promise<DayFields> {
  const [header, argo, binRes] = await Promise.all([
    fetchJson<FieldsHeader>(`/days/${date}/fields.json`),
    fetchJson<ArgoPosition[]>(`/days/${date}/argo.json`),
    fetch(`${FALLBACK_BASE}/days/${date}/fields.bin`),
  ]);
  if (!binRes.ok) throw new Error(`fallback fields.bin for ${date}: ${binRes.status}`);
  const all = decodeFloat16(await binRes.arrayBuffer());
  const [, D, H, W] = header.shape;
  const per = D * H * W;
  const slice = (name: string) => {
    const k = header.order.indexOf(name);
    if (k < 0) throw new Error(`fallback fields.bin for ${date} lacks ${name}`);
    return all.subarray(k * per, (k + 1) * per);
  };
  return {
    date,
    lat: header.lat,
    lon: header.lon,
    depths: header.depths_m,
    mean: slice("mean"),
    sigma: slice("sigma"),
    glorys: slice("glorys"),
    argo,
  };
}

function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dphi = ((lat2 - lat1) * Math.PI) / 180;
  const dlmb = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(dphi / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dlmb / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(a));
}

function nearestIndex(axis: number[], value: number): number {
  let best = 0;
  let bestDist = Infinity;
  for (let i = 0; i < axis.length; i++) {
    const d = Math.abs(axis[i] - value);
    if (d < bestDist) {
      bestDist = d;
      best = i;
    }
  }
  return best;
}

/** First depth, going down, where the profile crosses below `iso`; NaN when it never does. */
function isothermDepth(depths: number[], temps: number[], iso: number): number {
  if (!(temps[0] >= iso)) return NaN;
  const idx = temps.findIndex((t) => t < iso);
  if (idx <= 0) return NaN;
  const t0 = temps[idx - 1];
  const t1 = temps[idx];
  if (!Number.isFinite(t0) || !Number.isFinite(t1)) return NaN;
  const frac = t1 !== t0 ? (iso - t0) / (t1 - t0) : 0;
  return depths[idx - 1] + frac * (depths[idx] - depths[idx - 1]);
}

/** Depth where temperature drops MLD_DELTA_C below its value at MLD_REF_DEPTH_M. */
function mixedLayerDepth(depths: number[], temps: number[]): number {
  const refIdx = nearestIndex(depths, MLD_REF_DEPTH_M);
  const refT = temps[refIdx];
  if (!Number.isFinite(refT)) return NaN;
  const threshold = refT - MLD_DELTA_C;
  let d0 = depths[refIdx];
  let t0 = refT;
  for (let i = refIdx + 1; i < depths.length; i++) {
    const t1 = temps[i];
    if (!Number.isFinite(t1)) continue;
    const d1 = depths[i];
    if (t1 <= threshold) {
      const frac = t1 !== t0 ? Math.min(1, Math.max(0, (threshold - t0) / (t1 - t0))) : 0;
      return d0 + frac * (d1 - d0);
    }
    d0 = d1;
    t0 = t1;
  }
  return NaN;
}

/**
 * Vertical section along the straight lat/lon line A -> B, sampled at `n` points on the
 * nearest grid cell of each, exactly as the backend's `/section` route does.
 */
export function computeSection(fields: DayFields, a: TransectCoordinate, b: TransectCoordinate, n = 60): SectionData {
  const { lat: latAxis, lon: lonAxis, depths } = fields;
  const D = depths.length;
  const H = latAxis.length;
  const W = lonAxis.length;

  const lats: number[] = [];
  const lons: number[] = [];
  const distances_km: number[] = [0];
  for (let k = 0; k < n; k++) {
    const f = n > 1 ? k / (n - 1) : 0;
    lats.push(a.lat + (b.lat - a.lat) * f);
    lons.push(a.lon + (b.lon - a.lon) * f);
    if (k > 0) distances_km.push(distances_km[k - 1] + haversineKm(lats[k - 1], lons[k - 1], lats[k], lons[k]));
  }

  const column = (arr: Float32Array, j: number, i: number) => {
    const out = new Array<number>(D);
    for (let d = 0; d < D; d++) out[d] = arr[d * H * W + j * W + i];
    return out;
  };

  const poseidon: number[][] = [];
  const glorys: number[][] = [];
  const sigma: number[][] = [];
  const diff: number[][] = [];
  const d20_m: number[] = [];
  const mld_m: number[] = [];
  const closestByWmo = new Map<string, { floatKm: number; marker: ArgoMarker }>();

  for (let k = 0; k < n; k++) {
    const j = nearestIndex(latAxis, lats[k]);
    const i = nearestIndex(lonAxis, lons[k]);
    const mean = column(fields.mean, j, i);
    const truth = column(fields.glorys, j, i);
    poseidon.push(mean);
    glorys.push(truth);
    sigma.push(column(fields.sigma, j, i));
    diff.push(mean.map((v, d) => v - truth[d]));
    d20_m.push(isothermDepth(depths, mean, 20));
    mld_m.push(mixedLayerDepth(depths, mean));

    let best: ArgoPosition | null = null;
    let bestKm = Infinity;
    for (const row of fields.argo) {
      const km = haversineKm(lats[k], lons[k], row.lat, row.lon);
      if (km < bestKm) {
        bestKm = km;
        best = row;
      }
    }
    if (best && bestKm <= ARGO_MAX_KM) {
      const prev = closestByWmo.get(best.wmo);
      if (!prev || bestKm < prev.floatKm) {
        closestByWmo.set(best.wmo, {
          floatKm: bestKm,
          marker: { distance_km: Math.round(distances_km[k]), wmo: best.wmo, day_offset: best.day_offset },
        });
      }
    }
  }

  return {
    distances_km: distances_km.map((v) => Math.round(v)),
    lats: lats.map((v) => Number(v.toFixed(3))),
    lons: lons.map((v) => Number(v.toFixed(3))),
    depths_m: depths,
    poseidon,
    glorys,
    diff,
    sigma,
    d20_m,
    mld_m,
    argo_markers: [...closestByWmo.values()].map((v) => v.marker).sort((x, y) => x.distance_km - y.distance_km),
    totalDistanceKm: Math.round(distances_km[n - 1] ?? 0),
  };
}

/** The bundled day closest in time to `target` (ISO `YYYY-MM-DD`). */
export function nearestAvailableDate(available: string[], target: string): string {
  if (available.length === 0) return target;
  const t = Date.parse(target);
  let best = available[0];
  let bestGap = Infinity;
  for (const d of available) {
    const gap = Math.abs(Date.parse(d) - t);
    if (gap < bestGap) {
      bestGap = gap;
      best = d;
    }
  }
  return best;
}
