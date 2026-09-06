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

export const REPORT_DEPTHS_M = [0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000];

export const REPORT_SERIES = ["Poseidon", "Climatology", "Ridge/EOF", "U-Net (same day)", "ConvLSTM U-Net"];
