"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import Link from "next/link";
import { ArrowLeft, Waves } from "lucide-react";
import { MetricShell, ReportPanel } from "@/components/report/report-primitives";
import { OceanDepthStack } from "@/components/report/ocean-depth-stack";
import { OCEAN_DEPTH_LAYERS, type OceanDepthLayer } from "@/lib/ocean-layers-data";
import { TrackShiftSpinner } from "@/components/ui/trackshift-spinner";
import {
  MODEL_LABELS,
  REGION_LABELS,
  SEASON_LABELS,
  buildDepthLayers,
  depthMetric,
  fmt,
  fmtSigned,
  loadReport,
  type DepthLayerSkill,
  type ReportJson,
  type ReportModel,
  type ReportRegion,
  type ReportSeason,
} from "@/lib/report";

function ReportHeader({ layer, report }: { layer: OceanDepthLayer; report: ReportJson | null }) {
  const n = report?.argo_scatter.lite?.n;
  return (
    <header className="flex flex-col gap-5 border-b border-white/15 pb-5 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex items-center gap-4">
        <Link
          aria-label="Back to Varuna home"
          className="grid size-10 place-items-center rounded-full border border-white/20 bg-white/[0.05] text-white/80 shadow-[inset_0_1px_1px_rgba(255,255,255,0.35)] backdrop-blur-xl transition-all duration-200 hover:scale-105 hover:border-white/40 hover:bg-white/[0.10] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200"
          href="/"
        >
          <ArrowLeft aria-hidden="true" size={18} />
        </Link>
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.22em] text-cyan-200/80">
            Varuna / report · {layer.depth} m ({layer.zone})
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Validation report</h1>
        </div>
      </div>
      <p className="max-w-xl text-sm leading-relaxed text-white/60">
        This page is not a single day. Every number is an average over the 731 test days of 2019 and 2020,
        which the model never trained on, compared with the GLORYS ocean analysis
        {typeof n === "number" ? ` and with ${n.toLocaleString()} independent Argo float readings` : ""}.
      </p>
    </header>
  );
}

function SkillByDepthShell({
  layers,
  selectedIndex,
  onSelectIndex,
}: {
  layers: OceanDepthLayer[];
  selectedIndex: number;
  onSelectIndex: (index: number) => void;
}) {
  return (
    <ReportPanel
      title="Accuracy by depth"
      description="Pick a depth layer to see how well the model did there. The bars compare Varuna with the gradient-boosted baseline and the seasonal climatology on the same days. Lower error is better."
    >
      <OceanDepthStack layers={layers} selectedIndex={selectedIndex} onSelectIndex={onSelectIndex} />
    </ReportPanel>
  );
}

const NOMINAL_LEVELS = [0.5, 0.8, 0.9, 0.95];

function UncertaintyCalibrationCard({ report }: { report: ReportJson }) {
  const cal = report.calibration;
  const coverage = cal.coverage ?? {};
  const points = NOMINAL_LEVELS.map((nominal) => {
    const empirical = coverage[String(nominal)];
    return { nominal, empirical: typeof empirical === "number" ? empirical : NaN };
  }).filter((p) => Number.isFinite(p.empirical));

  // plot frame: x 50..390 for 0..100 % nominal, y 180..20 for 0..100 % empirical
  const px = (v: number) => 50 + v * 340;
  const py = (v: number) => 180 - v * 160;
  const polyline = points.map((p) => `${px(p.nominal)},${py(p.empirical)}`).join(" ");
  const cov90 = coverage["0.9"];

  return (
    <ReportPanel
      title="Are the error bars honest?"
      description="The model predicts a range for every value. If it says 90 percent, the truth should fall inside that range about 90 percent of the time. Points on the dashed line mean the ranges are exactly right."
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-center">
        <div className="lg:col-span-8 relative h-64 w-full overflow-hidden rounded-xl border border-white/10 bg-black/40 p-3">
          <svg viewBox="0 0 420 220" className="h-full w-full">
            <line x1="50" y1="180" x2="390" y2="180" stroke="rgba(255,255,255,0.2)" strokeWidth="1" />
            <line x1="50" y1="20" x2="50" y2="180" stroke="rgba(255,255,255,0.2)" strokeWidth="1" />

            <line x1="50" y1="140" x2="390" y2="140" stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <line x1="50" y1="100" x2="390" y2="100" stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <line x1="50" y1="60" x2="390" y2="60" stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <line x1="135" y1="20" x2="135" y2="180" stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <line x1="220" y1="20" x2="220" y2="180" stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <line x1="305" y1="20" x2="305" y2="180" stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />

            {/* perfect calibration */}
            <line x1="50" y1="180" x2="390" y2="20" stroke="rgba(255,255,255,0.3)" strokeWidth="1.2" strokeDasharray="4 4" />

            {points.length > 1 && <polyline points={polyline} fill="none" stroke="#22d3ee" strokeWidth="2.5" />}
            {points.map((p) => (
              <g key={p.nominal}>
                <circle cx={px(p.nominal)} cy={py(p.empirical)} r="4" fill="#0891b2" stroke="#67e8f9" strokeWidth="2" />
                <text
                  x={px(p.nominal)}
                  y={py(p.empirical) - 9}
                  fill="rgba(255,255,255,0.7)"
                  fontSize="9"
                  textAnchor="middle"
                  fontFamily="monospace"
                >
                  {(p.empirical * 100).toFixed(1)}%
                </text>
              </g>
            ))}

            <text x="220" y="205" fill="rgba(255,255,255,0.6)" fontSize="10" textAnchor="middle" fontFamily="monospace">Nominal Credible Interval (%)</text>
            <text x="15" y="100" fill="rgba(255,255,255,0.6)" fontSize="10" textAnchor="middle" transform="rotate(-90 15 100)" fontFamily="monospace">Empirical Coverage (%)</text>

            <text x="45" y="195" fill="rgba(255,255,255,0.4)" fontSize="9" fontFamily="monospace">0%</text>
            <text x="215" y="195" fill="rgba(255,255,255,0.4)" fontSize="9" fontFamily="monospace">50%</text>
            <text x="375" y="195" fill="rgba(255,255,255,0.4)" fontSize="9" fontFamily="monospace">100%</text>
          </svg>
        </div>

        <div className="lg:col-span-4 flex flex-col gap-3">
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
            <span className="text-white/50 text-xs font-mono block">TYPICAL 90% RANGE</span>
            <span className="text-2xl font-bold font-mono text-cyan-300">{fmt(cal.mean_interval_width_90, 2, " °C")}</span>
            <p className="mt-1 text-xs text-neutral-300/70 leading-relaxed">How wide the model&apos;s 90 percent range is on average, over every sea cell and depth on the test days.</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
            <span className="text-white/50 text-xs font-mono block">HOW OFTEN THE 90% RANGE WAS RIGHT</span>
            <span className="text-2xl font-bold font-mono text-emerald-400">
              {typeof cov90 === "number" ? `${(cov90 * 100).toFixed(1)}%` : "n/a"}
            </span>
            <p className="mt-1 text-xs text-neutral-300/70 leading-relaxed">
              Probabilistic scores on the test days: NLL {fmt(cal.nll, 3)}, CRPS {fmt(cal.crps, 3, " °C")}.
            </p>
          </div>
        </div>
      </div>
    </ReportPanel>
  );
}

function TableShell({
  title,
  description,
  columns,
  rows,
  highlightFirstRow = false,
}: {
  title: string;
  description: string;
  columns: string[];
  rows: string[][];
  highlightFirstRow?: boolean;
}) {
  return (
    <ReportPanel title={title} description={description}>
      <div className="relative overflow-hidden rounded-2xl border border-white/20 bg-white/[0.02] shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)] backdrop-blur-xl">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/30 to-transparent" />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[34rem] text-left text-sm">
            <caption className="sr-only">{title}</caption>
            <thead className="border-b border-white/15 bg-white/[0.04] text-xs font-mono uppercase tracking-wider text-white/60">
              <tr>
                {columns.map((column, idx) => (
                  <th
                    key={column}
                    className={`px-4 py-3.5 font-medium ${idx > 0 ? "text-right font-mono" : ""}`}
                  >
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10 font-mono text-xs">
              {rows.map((row, rIdx) => {
                const isHighlight = highlightFirstRow && rIdx === 0;
                return (
                  <tr
                    key={rIdx}
                    className={`transition-colors ${
                      isHighlight
                        ? "bg-cyan-500/10 font-semibold text-cyan-200"
                        : "text-neutral-300/90 hover:bg-white/[0.04]"
                    }`}
                  >
                    {row.map((cell, cIdx) => (
                      <td
                        key={cIdx}
                        className={`px-4 py-3.5 ${
                          cIdx === 0
                            ? "font-sans font-medium text-white flex items-center gap-2"
                            : "text-right font-mono"
                        }`}
                      >
                        {cIdx === 0 && isHighlight && (
                          <span className="rounded bg-cyan-400/20 px-1.5 py-0.5 text-[9px] font-mono font-bold text-cyan-300 uppercase tracking-wide border border-cyan-400/40">
                            Current
                          </span>
                        )}
                        {cell}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </ReportPanel>
  );
}

const SLICES: { region: ReportRegion; season: ReportSeason }[] = [
  { region: "arabian_sea", season: "JJAS" },
  { region: "arabian_sea", season: "DJF" },
  { region: "bay_of_bengal", season: "ON" },
  { region: "bay_of_bengal", season: "MAM" },
  { region: "overall", season: "all" },
];

const BASELINES: ReportModel[] = ["lite", "gbm", "climatology"];

export function ReportDashboard() {
  const [report, setReport] = useState<ReportJson | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLayerLoading, setIsLayerLoading] = useState(false);
  const [loadingTitle, setLoadingTitle] = useState("Loading Validation Report");
  const [loadingSubtitle, setLoadingSubtitle] = useState(
    "Reading the test results for 2019 and 2020..."
  );
  const [selectedIndex, setSelectedIndex] = useState<number>(7); // Default to 100m

  useEffect(() => {
    let cancelled = false;
    loadReport()
      .then((r) => {
        if (!cancelled) setReport(r);
      })
      .catch((err: unknown) => {
        if (!cancelled) setLoadError(`The precomputed report is missing (${String(err)}).`);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const layers: DepthLayerSkill[] = useMemo(
    () => (report ? buildDepthLayers(report) : OCEAN_DEPTH_LAYERS.map((l) => ({ ...l, rmseGbm: NaN, skillScore: NaN }))),
    [report]
  );
  const selectedLayer = layers[selectedIndex];
  const isLoading = report === null && loadError === null;

  const handleSelectIndex = useCallback(
    (index: number) => {
      if (index === selectedIndex) return;
      const targetLayer = layers[index];
      setLoadingTitle(`Evaluating ${targetLayer.depth} m Depth Tier`);
      setLoadingSubtitle(
        `Reading the test results at ${targetLayer.depth} m (${targetLayer.zone})...`
      );
      setIsLayerLoading(true);
      setSelectedIndex(index);
      setTimeout(() => {
        setIsLayerLoading(false);
      }, 550);
    },
    [selectedIndex, layers]
  );

  const dynamicMetrics = useMemo(() => {
    const baseline = selectedLayer.rmseClimatology;
    const model = selectedLayer.rmseVaruna;
    const skillPct = Number.isFinite(baseline) && Number.isFinite(model) && baseline > 0 ? Math.round(((baseline - model) / baseline) * 100) : NaN;
    const crps = report?.calibration.crps;

    return [
      {
        label: "RMSE",
        unit: "°C",
        sublabel: `typical error at ${selectedLayer.depth} m over the 731 test days`,
        value: fmt(model),
        delta: Number.isFinite(skillPct) ? `${skillPct >= 0 ? "-" : "+"}${Math.abs(skillPct)}% vs Climatology` : "n/a",
        isPositiveDelta: Number.isFinite(skillPct) && skillPct >= 0,
        statusBadge: selectedLayer.isD20Isotherm ? "D20 ISOTHERM" : selectedLayer.isMLD ? "MLD BASE" : "LAYER EVAL",
      },
      {
        label: "Bias",
        unit: "°C",
        sublabel: `average error at ${selectedLayer.depth} m: positive means too warm`,
        value: fmtSigned(selectedLayer.bias),
        delta: Number.isFinite(selectedLayer.bias) && Math.abs(selectedLayer.bias) < 0.25 ? "Zero-Centered" : "Systematic",
        isPositiveDelta: Number.isFinite(selectedLayer.bias) && Math.abs(selectedLayer.bias) < 0.25,
        statusBadge: "MEAN ERROR",
      },
      {
        label: "Correlation",
        unit: "",
        sublabel: `how well the map pattern matches GLORYS at ${selectedLayer.depth} m`,
        value: fmt(selectedLayer.correlation, 3),
        delta: "Pearson R",
        isPositiveDelta: Number.isFinite(selectedLayer.correlation) && selectedLayer.correlation > 0.5,
        statusBadge: selectedLayer.correlation >= 0.9 ? "EXCELLENT" : "HIGH FIDELITY",
      },
      {
        label: "CRPS",
        unit: "°C",
        sublabel: "score for the whole predicted range, all depths and test days",
        value: fmt(crps),
        delta: `skill score ${fmt(selectedLayer.skillScore, 2)} at ${selectedLayer.depth} m`,
        isPositiveDelta: Number.isFinite(selectedLayer.skillScore) && selectedLayer.skillScore > 0,
        statusBadge: "UNCERTAINTY",
      },
    ];
  }, [selectedLayer, report]);

  const basinSeasonRows = useMemo(() => {
    if (!report) return [];
    return SLICES.map(({ region, season }) => [
      `${REGION_LABELS[region]} · ${SEASON_LABELS[season]}`,
      fmt(depthMetric(report, "lite", "rmse", selectedIndex, region, season), 2, " °C"),
      fmtSigned(depthMetric(report, "lite", "bias", selectedIndex, region, season), 2, " °C"),
      fmt(depthMetric(report, "lite", "r", selectedIndex, region, season), 3),
      fmt(depthMetric(report, "lite", "skill_score", selectedIndex, region, season), 2),
    ]);
  }, [report, selectedIndex]);

  const baselinesRows = useMemo(() => {
    if (!report) return [];
    return BASELINES.map((model) => [
      `${MODEL_LABELS[model]} (${selectedLayer.depth} m)`,
      fmt(depthMetric(report, model, "rmse", selectedIndex), 2, " °C"),
      fmtSigned(depthMetric(report, model, "bias", selectedIndex), 2, " °C"),
      fmt(depthMetric(report, model, "r", selectedIndex), 3),
      fmt(depthMetric(report, model, "skill_score", selectedIndex), 2),
    ]);
  }, [report, selectedIndex, selectedLayer.depth]);

  return (
    <>
      <TrackShiftSpinner
        isLoading={isLoading || isLayerLoading}
        title={isLoading ? "Loading Validation Report" : loadingTitle}
        subtitle={
          isLoading
            ? "Reading the test results for 2019 and 2020..."
            : loadingSubtitle
        }
        isFullPage={true}
      />

      <main className="relative min-h-screen px-4 pb-8 pt-6 text-white sm:px-6 sm:pt-8 lg:px-8">
      <div className="relative mx-auto max-w-7xl">
        <ReportHeader layer={selectedLayer} report={report} />
        {loadError && (
          <div
            role="alert"
            className="mt-5 rounded-xl border border-amber-400/40 bg-amber-500/10 px-4 py-3 font-mono text-xs text-amber-200"
          >
            {loadError} Run <code>backend/scripts/run_all.py</code> to regenerate <code>frontend/public/fallback</code>.
          </div>
        )}
        <section className="mt-5">
          <SkillByDepthShell layers={layers} selectedIndex={selectedIndex} onSelectIndex={handleSelectIndex} />
        </section>
        <section className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Headline metrics">
          {dynamicMetrics.map((metric) => (
            <MetricShell key={metric.label} metric={metric} />
          ))}
        </section>
        {report && (
          <>
            <section className="mt-6">
              <UncertaintyCalibrationCard report={report} />
            </section>
            <section className="mt-6 grid gap-6 lg:grid-cols-2">
              <TableShell
                title={`By basin and season, ${selectedLayer.depth} m`}
                description={`The same accuracy split by sea and by monsoon season. Skill is how much of the climatology's error the model removes: 1 is perfect, 0 is no better than climatology.`}
                columns={["Slice", "RMSE", "Bias", "Correlation", "Skill"]}
                rows={basinSeasonRows}
              />
              <TableShell
                title={`Compared with the baselines, ${selectedLayer.depth} m`}
                description={`The three models scored on exactly the same days and cells at ${selectedLayer.depth} m.`}
                columns={["Method", "RMSE", "Bias", "Correlation", "Skill"]}
                rows={baselinesRows}
                highlightFirstRow={true}
              />
            </section>
          </>
        )}
        <footer className="flex flex-col gap-3 py-10 text-xs text-white/45 sm:flex-row sm:items-center sm:justify-between">
          <span>Averages over 731 test days on the 0.25 degree grid. Computed once and bundled with the site, so nothing runs live.</span>
          <span className="flex items-center gap-2">
            <Waves aria-hidden="true" size={14} /> Varuna ocean temperature intelligence
          </span>
        </footer>
      </div>
    </main>
    </>
  );
}
