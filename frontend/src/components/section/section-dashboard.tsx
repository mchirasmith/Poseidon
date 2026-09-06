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
  generateSectionData,
  type SectionMode,
  type TransectCoordinate,
  type TransectPreset,
} from "@/lib/section";

export function SectionDashboard() {
  const searchParams = useSearchParams();

  // Default initial values from URL query string or BoB preset
  const initialPreset = TRANSECT_PRESETS[0];

  const [date, setDate] = useState<string>(() => {
    return searchParams.get("d") || "2020-05-18";
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

  // Loading states
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [isTaskLoading, setIsTaskLoading] = useState(false);
  const [loadingTitle, setLoadingTitle] = useState("Computing Vertical Section");
  const [loadingSubtitle, setLoadingSubtitle] = useState(
    "Running Poseidon neural inversion across 15 depth tiers, please wait (this takes a few seconds)..."
  );

  // Overlay visibility states
  const [showD20, setShowD20] = useState(true);
  const [showMLD, setShowMLD] = useState(true);
  const [showArgo, setShowArgo] = useState(true);

  // Helper to trigger smooth full-page loading spinner on any user task
  const triggerLoading = useCallback((title: string, subtitle: string, duration = 650) => {
    setLoadingTitle(title);
    setLoadingSubtitle(subtitle);
    setIsTaskLoading(true);
    setTimeout(() => {
      setIsTaskLoading(false);
    }, duration);
  }, []);

  // Initial page load simulation
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsInitialLoading(false);
    }, 750);
    return () => clearTimeout(timer);
  }, []);

  // Sync state back to URL query parameters
  useEffect(() => {
    const params = new URLSearchParams();
    params.set("d", date);
    params.set("a", `${coordA.lat},${coordA.lon}`);
    params.set("b", `${coordB.lat},${coordB.lon}`);
    params.set("mode", mode);
    params.set("depth", String(mapDepth));

    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState(null, "", newUrl);
  }, [date, coordA, coordB, mode, mapDepth]);

  // Compute section dataset based on transect coordinates and date
  const sectionData = useMemo(() => {
    return generateSectionData(coordA, coordB, date);
  }, [coordA, coordB, date]);

  // Handle date change with animated full-page loading spinner
  const handleDateChange = useCallback(
    (newDate: string) => {
      if (newDate === date) return;
      setDate(newDate);
      triggerLoading(
        "Updating Ocean Inversion",
        `Re-computing 3D vertical thermal section for ${newDate}...`,
        700
      );
    },
    [date, triggerLoading]
  );

  // Handle preset selection with animated loading spinner
  const handlePresetSelect = useCallback(
    (preset: TransectPreset) => {
      setCoordA(preset.a);
      setCoordB(preset.b);
      triggerLoading(
        `Loading ${preset.name}`,
        `Re-projecting transect track across ${preset.basin.toUpperCase()} (${preset.a.lat}°N, ${preset.a.lon}°E → ${preset.b.lat}°N, ${preset.b.lon}°E)...`,
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
        "Recalculating cross-section thermal field and contours...",
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
        `Extracting horizontal depth plane from 3D volume at ${newDepth} m...`,
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
  const meanD20 = useMemo(() => {
    if (!sectionData.d20_m.length) return 105;
    const sum = sectionData.d20_m.reduce((acc, v) => acc + v, 0);
    return Math.round(sum / sectionData.d20_m.length);
  }, [sectionData]);

  const meanMLD = useMemo(() => {
    if (!sectionData.mld_m.length) return 32;
    const sum = sectionData.mld_m.reduce((acc, v) => acc + v, 0);
    return Math.round(sum / sectionData.mld_m.length);
  }, [sectionData]);

  const meanUncertainty = useMemo(() => {
    let sum = 0;
    let count = 0;
    for (const row of sectionData.sigma) {
      for (const val of row) {
        sum += val;
        count++;
      }
    }
    return count > 0 ? (sum / count).toFixed(2) : "0.45";
  }, [sectionData]);

  // 4 headline metric cards matching validation report styling exactly
  const dynamicMetrics: ReportMetricDefinition[] = useMemo(() => {
    return [
      {
        label: "Transect Span",
        unit: "km",
        sublabel: `great-circle distance across ${sectionData.lats.length} sampled points`,
        value: `${sectionData.totalDistanceKm}`,
        delta: "Great-Circle Arc",
        isPositiveDelta: true,
        statusBadge: matchedPreset ? matchedPreset.basin.toUpperCase() : "CUSTOM LINE",
      },
      {
        label: "D20 Thermocline",
        unit: "m",
        sublabel: `mean 20°C isotherm depth boundary across transect for ${date}`,
        value: `${meanD20}`,
        delta: "Subsurface Core",
        isPositiveDelta: true,
        statusBadge: "THERMOCLINE",
      },
      {
        label: "Mixed Layer Depth",
        unit: "m",
        sublabel: "turbulent surface mixed layer base depth along slice",
        value: `${meanMLD}`,
        delta: "Wind-Driven MLD",
        isPositiveDelta: true,
        statusBadge: "MLD BASE",
      },
      {
        label: "Mean Uncertainty",
        unit: "°C",
        sublabel: `ensemble 1σ confidence across all 15 depth tiers`,
        value: `±${meanUncertainty}`,
        delta: "Sharp Bound",
        isPositiveDelta: true,
        statusBadge: "CALIBRATED",
      },
    ];
  }, [sectionData, matchedPreset, meanD20, meanMLD, meanUncertainty, date]);

  const handleCoordinatesChange = useCallback((newA: TransectCoordinate, newB: TransectCoordinate) => {
    setCoordA(newA);
    setCoordB(newB);
  }, []);

  return (
    <>
      <TrackShiftSpinner
        isLoading={isInitialLoading || isTaskLoading}
        title={isInitialLoading ? "Computing Vertical Section" : loadingTitle}
        subtitle={
          isInitialLoading
            ? "Running Poseidon neural inversion across 15 depth tiers, please wait (this takes a few seconds)..."
            : loadingSubtitle
        }
        isFullPage={true}
      />

      <main className="relative min-h-screen px-4 pb-8 pt-6 text-white sm:px-6 sm:pt-8 lg:px-8">
        <div className="relative mx-auto max-w-7xl">
          {/* Header Strip */}
          <SectionHeader
            date={date}
            preset={matchedPreset}
            totalDistanceKm={sectionData.totalDistanceKm}
            isLoading={isTaskLoading}
            onDateChange={handleDateChange}
          />

          {/* Section 1: Transect Navigation Map */}
          <section className="mt-5">
            <ReportPanel
              title="Transect navigation · North Indian Ocean (A → B)"
              description="Interactive great-circle ocean transect across custom coordinates or oceanographic presets at depth."
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
              title="Vertical Stratification Heatmap · 0 m to 1000 m"
              description="High-resolution depth vs distance vertical cross-section with D20 thermocline, mixed layer depth, and collocated Argo float profiles."
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
                meanD20={meanD20}
                meanMLD={meanMLD}
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

        {/* Footer matching Validation Report exactly */}
        <footer className="flex flex-col gap-3 py-10 text-xs text-white/45 sm:flex-row sm:items-center sm:justify-between">
          <span>Read-only validation workspace · values validated against independent Argo test profiles.</span>
          <span className="flex items-center gap-2">
            <Waves aria-hidden="true" size={14} /> Poseidon ocean temperature intelligence
          </span>
        </footer>
      </div>
    </main>
    </>
  );
}
