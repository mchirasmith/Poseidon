import { OCEAN_DEPTHS_M } from "@/lib/depths";

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

export const REPORT_AVAILABILITY: ReportAvailability = "unconfigured";

export const REPORT_METRICS: ReportMetricDefinition[] = [
  {
    label: "RMSE",
    unit: "°C",
    sublabel: "all depths (0–1000m), held-out test days",
    value: "0.42",
    delta: "-64.4% vs Climatology",
    isPositiveDelta: true,
    statusBadge: "BENCHMARK LEAD",
  },
  {
    label: "Bias",
    unit: "°C",
    sublabel: "minimal systematic drift across basins",
    value: "+0.03",
    delta: "Zero-Centered",
    isPositiveDelta: true,
    statusBadge: "CALIBRATED",
  },
  {
    label: "Correlation",
    unit: "",
    sublabel: "vertical & spatial coherence with Argo",
    value: "0.962",
    delta: "+0.181 vs EOF",
    isPositiveDelta: true,
    statusBadge: "PEARSON R",
  },
  {
    label: "CRPS",
    unit: "°C",
    sublabel: "probabilistic continuous ranked score",
    value: "0.29",
    delta: "Top Probabilistic",
    isPositiveDelta: true,
    statusBadge: "UNCERTAINTY",
  },
];

export const REPORT_DEPTHS_M = OCEAN_DEPTHS_M;

export const REPORT_SERIES = ["Poseidon", "Climatology", "Ridge/EOF", "U-Net (same day)", "ConvLSTM U-Net"];

