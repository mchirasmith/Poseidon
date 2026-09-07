"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Waves } from "lucide-react";
import { MetricShell, ReportPanel } from "@/components/report/report-primitives";
import type { ReportMetricDefinition } from "@/lib/report";
import { SectionHeader } from "@/components/section/section-header";
import { TransectMap } from "@/components/section/transect-map";
import { SectionControls } from "@/components/section/section-controls";
import { SectionHeatmap } from "@/components/section/section-heatmap";
import { TrackShiftSpinner } from "@/components/ui/trackshift-spinner";
import {
  TRANSECT_PRESETS,
  emptySectionData,
  type SectionMode,
  type TransectCoordinate,
  type TransectPreset,
} from "@/lib/section";
import {
  computeSection,
  loadDayFields,
  loadMeta,
  nearestAvailableDate,
  type CuratedDay,
  type DayFields,
} from "@/lib/fallback";

const DEFAULT_DATE = "2020-05-18";

/** Mean of the finite entries, NaN when there are none. */
function finiteMean(values: Iterable<number>): number {
  let sum = 0;
  let count = 0;
  for (const v of values) {
    if (Number.isFinite(v)) {
      sum += v;
      count++;
    }
  }
  return count > 0 ? sum / count : NaN;
}

export function SectionDashboard() {
  const searchParams = useSearchParams();

  // Default initial values from URL query string or BoB preset
  const initialPreset = TRANSECT_PRESETS[0];

  const [date, setDate] = useState<string>(() => {
    return searchParams.get("d") || DEFAULT_DATE;
  });

  const [coordA, setCoordA] = useState<TransectCoordinate>(() => {
    const aParam = searchParams.get("a");
    if (aParam) {
      const [lat, lon] = aParam.split(",").map(Number);
      if (!isNaN(lat) && !isNaN(lon)) return { lat, lon };
    }
    return initialPreset.a;
  });

  const [coordB, setCoordB] = useState<TransectCoordinate>(() => {
    const bParam = searchParams.get("b");
    if (bParam) {
      const [lat, lon] = bParam.split(",").map(Number);
      if (!isNaN(lat) && !isNaN(lon)) return { lat, lon };
    }
    return initialPreset.b;
  });

  const [mode, setMode] = useState<SectionMode>(() => {
    const m = searchParams.get("mode") as SectionMode;
    return m && ["poseidon", "glorys", "diff", "sigma"].includes(m) ? m : "poseidon";
  });

  const [mapDepth, setMapDepth] = useState<number>(() => {
    const z = Number(searchParams.get("depth"));
    return !isNaN(z) && z >= 0 ? z : 100;
  });

  // Precomputed bundle: which days exist, and the selected day's 3D fields
  const [curatedDays, setCuratedDays] = useState<CuratedDay[]>([]);
  const [fields, setFields] = useState<DayFields | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Cosmetic transition spinner for map/mode/depth changes
  const [isTaskLoading, setIsTaskLoading] = useState(false);
  const [loadingTitle, setLoadingTitle] = useState("Computing Vertical Section");
  const [loadingSubtitle, setLoadingSubtitle] = useState(
    "Cutting the slice through the reconstructed ocean..."
  );

  // Overlay visibility states
  const [showD20, setShowD20] = useState(true);
  const [showMLD, setShowMLD] = useState(true);
  const [showArgo, setShowArgo] = useState(true);

  const availableDates = useMemo(() => curatedDays.map((d) => d.date).sort(), [curatedDays]);
  // Only bundled days can be shown: anything else resolves to the nearest one
  const activeDate = useMemo(
    () => (availableDates.length === 0 || availableDates.includes(date) ? date : nearestAvailableDate(availableDates, date)),
    [availableDates, date]
  );
  const dayLabel = useMemo(() => curatedDays.find((d) => d.date === activeDate)?.label, [curatedDays, activeDate]);
  const isFieldsLoading = loadError === null && (fields === null || fields.date !== activeDate);

  // Helper to trigger smooth full-page loading spinner on any user task
  const triggerLoading = useCallback((title: string, subtitle: string, duration = 650) => {
    setLoadingTitle(title);
    setLoadingSubtitle(subtitle);
    setIsTaskLoading(true);
    setTimeout(() => {
      setIsTaskLoading(false);
    }, duration);
  }, []);

  // Bundle index: the curated days that have precomputed fields
  useEffect(() => {
    let cancelled = false;
    loadMeta()
      .then((meta) => {
        if (cancelled) return;
        const days = meta.curated_days.length
          ? meta.curated_days
          : meta.cached_days.map((d) => ({ date: d, label: "" }));
        setCuratedDays(days);
      })
      .catch((err: unknown) => {
        if (!cancelled) setLoadError(`The precomputed bundle is missing (${String(err)}).`);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Fetch the active day's mean / sigma / GLORYS fields and Argo positions
  useEffect(() => {
    if (availableDates.length === 0) return;
    let cancelled = false;
    loadDayFields(activeDate)
      .then((loaded) => {
        if (cancelled) return;
        setFields(loaded);
        setLoadError(null);
      })
      .catch((err: unknown) => {
        if (!cancelled) setLoadError(`Could not load the fields for ${activeDate} (${String(err)}).`);
      });
    return () => {
      cancelled = true;
    };
  }, [activeDate, availableDates]);

  // Sync state back to URL query parameters
  useEffect(() => {
    const params = new URLSearchParams();
    params.set("d", activeDate);
    params.set("a", `${coordA.lat},${coordA.lon}`);
    params.set("b", `${coordB.lat},${coordB.lon}`);
    params.set("mode", mode);
    params.set("depth", String(mapDepth));

    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState(null, "", newUrl);
  }, [activeDate, coordA, coordB, mode, mapDepth]);

  // Cut the section along the transect from the day's fields, in the browser
  const sectionData = useMemo(() => {
    return fields ? computeSection(fields, coordA, coordB) : emptySectionData();
  }, [fields, coordA, coordB]);

  const handleDateChange = useCallback(
    (newDate: string) => {
      if (newDate === activeDate) return;
      setDate(newDate);
    },
    [activeDate]
  );

  // Handle preset selection with animated loading spinner
  const handlePresetSelect = useCallback(
    (preset: TransectPreset) => {
      setCoordA(preset.a);
      setCoordB(preset.b);
      triggerLoading(
        `Loading ${preset.name}`,
        `Moving the line to ${preset.basin} (${preset.a.lat} N, ${preset.a.lon} E to ${preset.b.lat} N, ${preset.b.lon} E)...`,
        650
      );
    },
    [triggerLoading]
  );

  // Handle mode change with animated loading spinner
  const handleModeChange = useCallback(
    (newMode: SectionMode) => {
      if (newMode === mode) return;
      setMode(newMode);
      const modeNames: Record<SectionMode, string> = {
        poseidon: "Poseidon Model Prediction",
        glorys: "GLORYS Reanalysis Baseline",
        diff: "Model vs Baseline Difference",
        sigma: "Ensemble Uncertainty Spread (1σ)",
      };
      triggerLoading(
        `Switching to ${modeNames[newMode]}`,
        "Redrawing the slice...",
        500
      );
    },
    [mode, triggerLoading]
  );

  // Handle depth slice change with animated loading spinner
  const handleDepthChange = useCallback(
    (newDepth: number) => {
      if (newDepth === mapDepth) return;
      setMapDepth(newDepth);
      triggerLoading(
        `Slicing Ocean at ${newDepth} m Depth`,
        `Showing the map at ${newDepth} m...`,
        500
      );
    },
    [mapDepth, triggerLoading]
  );

  // Check matching preset
  const matchedPreset = useMemo(() => {
    return TRANSECT_PRESETS.find(
      (p) =>
        Math.abs(p.a.lat - coordA.lat) < 0.2 &&
        Math.abs(p.a.lon - coordA.lon) < 0.2 &&
        Math.abs(p.b.lat - coordB.lat) < 0.2 &&
        Math.abs(p.b.lon - coordB.lon) < 0.2
    );
  }, [coordA, coordB]);

  // Oceanographic scalar aggregates along the transect line
  const meanD20 = useMemo(() => finiteMean(sectionData.d20_m), [sectionData]);
  const meanMLD = useMemo(() => finiteMean(sectionData.mld_m), [sectionData]);
  const meanUncertainty = useMemo(() => {
    return finiteMean(sectionData.sigma.flat());
  }, [sectionData]);

  const fmtMetres = (v: number) => (Number.isFinite(v) ? `${Math.round(v)}` : "n/a");

  // 4 headline metric cards matching validation report styling exactly
  const dynamicMetrics: ReportMetricDefinition[] = useMemo(() => {
    return [
      {
        label: "Transect Span",
        unit: "km",
        sublabel: `length of the line, sampled at ${sectionData.lats.length} grid cells of 0.25 degrees`,
        value: `${sectionData.totalDistanceKm}`,
        delta: "Great-Circle Arc",
        isPositiveDelta: true,
        statusBadge: matchedPreset ? matchedPreset.basin.toUpperCase() : "CUSTOM LINE",
      },
      {
        label: "D20 Thermocline",
        unit: "m",
        sublabel: `average depth where the water cools to 20 °C along the line on ${activeDate}`,
        value: fmtMetres(meanD20),
        delta: "Subsurface Core",
        isPositiveDelta: true,
        statusBadge: "THERMOCLINE",
      },
      {
        label: "Mixed Layer Depth",
        unit: "m",
        sublabel: "average depth of the well-mixed surface layer along the line",
        value: fmtMetres(meanMLD),
        delta: "Wind-Driven MLD",
        isPositiveDelta: true,
        statusBadge: "MLD BASE",
      },
      {
        label: "Mean Uncertainty",
        unit: "°C",
        sublabel: `how unsure the model is, averaged over the whole slice`,
        value: Number.isFinite(meanUncertainty) ? `±${meanUncertainty.toFixed(2)}` : "n/a",
        delta: "Calibrated on 2018",
        isPositiveDelta: true,
        statusBadge: "1σ",
      },
    ];
  }, [sectionData, matchedPreset, meanD20, meanMLD, meanUncertainty, activeDate]);

  const handleCoordinatesChange = useCallback((newA: TransectCoordinate, newB: TransectCoordinate) => {
    setCoordA(newA);
    setCoordB(newB);
  }, []);

  return (
    <>
      <TrackShiftSpinner
        isLoading={isFieldsLoading || isTaskLoading}
        title={isFieldsLoading ? `Loading ${activeDate}` : loadingTitle}
        subtitle={
          isFieldsLoading
            ? "Loading this day's reconstruction of the ocean..."
            : loadingSubtitle
        }
        isFullPage={true}
      />

      <main className="relative min-h-screen px-4 pb-8 pt-6 text-white sm:px-6 sm:pt-8 lg:px-8">
        <div className="relative mx-auto max-w-7xl">
          {/* Header Strip */}
          <SectionHeader
            date={activeDate}
            availableDates={availableDates}
            dayLabel={dayLabel}
            preset={matchedPreset}
            totalDistanceKm={sectionData.totalDistanceKm}
            isLoading={isTaskLoading}
            onDateChange={handleDateChange}
          />

          {loadError && (
            <div
              role="alert"
              className="mt-5 rounded-xl border border-amber-400/40 bg-amber-500/10 px-4 py-3 font-mono text-xs text-amber-200"
            >
              {loadError} Run <code>backend/scripts/run_all.py</code> to regenerate <code>frontend/public/fallback</code>.
            </div>
          )}

          {/* Section 1: Transect Navigation Map */}
          <section className="mt-5">
            <ReportPanel
              title="Where to cut"
              description="This page shows one day. Drag the A and B handles anywhere in the sea, or pick a preset, and the slice below is cut along that line from the model's 3D reconstruction for the chosen date."
            >
              <TransectMap
                a={coordA}
                b={coordB}
                depthM={mapDepth}
                totalDistanceKm={sectionData.totalDistanceKm}
                onCoordinatesChange={handleCoordinatesChange}
                onDepthChange={handleDepthChange}
                onPresetSelect={handlePresetSelect}
              />
            </ReportPanel>
          </section>

          {/* Section 2: Headline Metric Cards */}
          <section className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Headline metrics">
            {dynamicMetrics.map((metric) => (
              <MetricShell key={metric.label} metric={metric} />
            ))}
          </section>

          {/* Section 3: Vertical Stratification Heatmap */}
          <section className="mt-6">
            <ReportPanel
              title="The slice, surface to 1000 m"
              description="Distance along the line runs left to right, depth runs down. Each column is one 0.25 degree grid cell. Switch between the model, the GLORYS analysis, their difference and the model's uncertainty. Argo floats that surfaced within 55 km and two days are marked."
            >
              <SectionControls
                mode={mode}
                onModeChange={handleModeChange}
                showD20={showD20}
                onToggleD20={() => setShowD20((v) => !v)}
                showMLD={showMLD}
                onToggleMLD={() => setShowMLD((v) => !v)}
                showArgo={showArgo}
                onToggleArgo={() => setShowArgo((v) => !v)}
                meanD20={Number.isFinite(meanD20) ? Math.round(meanD20) : 0}
                meanMLD={Number.isFinite(meanMLD) ? Math.round(meanMLD) : 0}
                argoCount={sectionData.argo_markers.length}
              />
              <SectionHeatmap
                data={sectionData}
                mode={mode}
                showD20={showD20}
                showMLD={showMLD}
                showArgo={showArgo}
              />
            </ReportPanel>
          </section>

          <footer className="flex flex-col gap-3 py-10 text-xs text-white/45 sm:flex-row sm:items-center sm:justify-between">
            <span>
              {availableDates.length} showcase days from the 2019 and 2020 test period, computed once and bundled with the site.
            </span>
            <span className="flex items-center gap-2">
              <Waves aria-hidden="true" size={14} /> Poseidon ocean temperature intelligence
            </span>
          </footer>
        </div>
      </main>
    </>
  );
}
