export type ReportAvailability = "unconfigured" | "loading" | "error";

export interface ReportMetricDefinition {
  label: string;
  unit: string;
  sublabel: string;
}

export const REPORT_AVAILABILITY: ReportAvailability = "unconfigured";

export const REPORT_METRICS: ReportMetricDefinition[] = [
  { label: "RMSE", unit: "°C", sublabel: "all depths, all test days, ocean cells only" },
  { label: "Bias", unit: "°C", sublabel: "all depths, all test days, ocean cells only" },
  { label: "Correlation", unit: "", sublabel: "all depths, all test days, ocean cells only" },
  { label: "CRPS", unit: "°C", sublabel: "all depths, all test days, ocean cells only" },
];

export const REPORT_DEPTHS_M = OCEAN_DEPTHS_M;

export const REPORT_SERIES = ["Poseidon", "Climatology", "Ridge/EOF", "U-Net (same day)", "ConvLSTM U-Net"];
import { OCEAN_DEPTHS_M } from "@/lib/depths";
