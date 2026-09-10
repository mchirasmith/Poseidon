/**
 * Validation report data. `report.json` is written by `backend/eval/evaluate.py`
 * (held-out 2019-2020 test days, Argo matchups, calibration) and served from the
 * static fallback bundle, so the report page never needs the API.
 */
import { FALLBACK_BASE } from "@/lib/fallback";
import { OCEAN_DEPTH_LAYERS, type OceanDepthLayer } from "@/lib/ocean-layers-data";

export type ReportAvailability = "unconfigured" | "loading" | "error";

export interface ReportMetricDefinition {
  label: string;
  unit: string;
  sublabel: string;
  value: string;
  delta?: string;
  isPositiveDelta?: boolean;
  statusBadge?: string;
}

export type ReportModel = "lite" | "gbm" | "climatology";
export type ReportRegion = "overall" | "arabian_sea" | "bay_of_bengal";
export type ReportSeason = "all" | "DJF" | "MAM" | "JJAS" | "ON";
export type DepthMetric = "rmse" | "mae" | "bias" | "r" | "anomaly_correlation" | "skill_score";

type Nullable = number | null;

export interface ReportJson {
  headline: Partial<Record<ReportModel, { thermocline_rmse: Nullable }>>;
  by_depth: Partial<Record<ReportModel, Partial<Record<DepthMetric, Record<ReportRegion, Record<ReportSeason, Nullable[]>>>>>>;
  tables: Partial<Record<ReportModel, Record<string, Record<ReportRegion, Record<ReportSeason, Nullable>>>>>;
  argo_scatter: Partial<Record<ReportModel | "glorys", { rmse: Nullable; bias: Nullable; r: Nullable; n: number }>>;
  calibration: { nll?: Nullable; crps?: Nullable; coverage?: Record<string, Nullable>; mean_interval_width_90?: Nullable };
  learning_curve: { step: number; dev_nll: number; dev_rmse_100m: number }[];
  maps: Record<string, { rmse: string; bias: string }>;
}

export const MODEL_LABELS: Record<ReportModel, string> = {
  lite: "Varuna lite",
  gbm: "Gradient-boosted baseline",
  climatology: "Harmonic climatology",
};

export const REGION_LABELS: Record<ReportRegion, string> = {
  overall: "North Indian Ocean",
  arabian_sea: "Arabian Sea",
  bay_of_bengal: "Bay of Bengal",
};

export const SEASON_LABELS: Record<ReportSeason, string> = {
  all: "Annual",
  DJF: "NE Monsoon (Dec-Feb)",
  MAM: "Pre-monsoon (Mar-May)",
  JJAS: "SW Monsoon (Jun-Sep)",
  ON: "Post-monsoon (Oct-Nov)",
};

export async function loadReport(): Promise<ReportJson> {
  const res = await fetch(`${FALLBACK_BASE}/report.json`);
  if (!res.ok) throw new Error(`report.json: ${res.status}`);
  return (await res.json()) as ReportJson;
}

/** One depth's value of a per-depth metric, or NaN when the report lacks it. */
export function depthMetric(
  report: ReportJson,
  model: ReportModel,
  metric: DepthMetric,
  depthIndex: number,
  region: ReportRegion = "overall",
  season: ReportSeason = "all"
): number {
  const v = report.by_depth[model]?.[metric]?.[region]?.[season]?.[depthIndex];
  return typeof v === "number" && Number.isFinite(v) ? v : NaN;
}

/** The static layer descriptions (zones, colours, typical temperatures) with the measured skill filled in. */
export interface DepthLayerSkill extends OceanDepthLayer {
  rmseGbm: number;
  skillScore: number;
}

export function buildDepthLayers(report: ReportJson): DepthLayerSkill[] {
  return OCEAN_DEPTH_LAYERS.map((layer, i) => ({
    ...layer,
    rmseVaruna: depthMetric(report, "lite", "rmse", i),
    rmseClimatology: depthMetric(report, "climatology", "rmse", i),
    rmseGbm: depthMetric(report, "gbm", "rmse", i),
    correlation: depthMetric(report, "lite", "r", i),
    bias: depthMetric(report, "lite", "bias", i),
    skillScore: depthMetric(report, "lite", "skill_score", i),
  }));
}

export function fmt(value: number | null | undefined, digits = 2, suffix = ""): string {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(digits)}${suffix}` : "n/a";
}

export function fmtSigned(value: number | null | undefined, digits = 2, suffix = ""): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "n/a";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}${suffix}`;
}
