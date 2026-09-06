"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { 
  Play, 
  Pause, 
  Layers, 
  Eye, 
  Compass, 
  Thermometer, 
  BarChart2, 
  TrendingUp,
  Info
} from "lucide-react";
import { OCEAN_DEPTH_LAYERS, type OceanDepthLayer } from "@/lib/ocean-layers-data";

type ViewMode = "stack" | "flat";
type MetricMode = "temp" | "rmse" | "anomaly";

export function OceanDepthStack() {
  const [selectedIndex, setSelectedIndex] = useState<number>(7); // Default to 100m (thermocline / D20)
  const [viewMode, setViewMode] = useState<ViewMode>("stack");
  const [metricMode, setMetricMode] = useState<MetricMode>("temp");
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  const selectedLayer = OCEAN_DEPTH_LAYERS[selectedIndex];

  // Auto-play animation: step through layers sequentially
  useEffect(() => {
    if (!isPlaying) return;
    const interval = window.setInterval(() => {
      setSelectedIndex((prev) => (prev + 1) % OCEAN_DEPTH_LAYERS.length);
    }, 1200);
    return () => window.clearInterval(interval);
  }, [isPlaying]);

  const handleLayerClick = useCallback((index: number) => {
    setSelectedIndex(index);
    if (isPlaying) setIsPlaying(false);
  }, [isPlaying]);

  // Color mapping based on metric mode
  const getLayerColor = useCallback((layer: OceanDepthLayer) => {
    if (metricMode === "temp") {
      return {
        fill: `linear-gradient(135deg, ${layer.thermalColors.arabianSea}cc 0%, ${layer.thermalColors.equator}bb 50%, ${layer.thermalColors.bayOfBengal}cc 100%)`,
        stroke: layer.thermalColors.contourStroke,
        badgeText: `${layer.tempMean.toFixed(1)}°C`,
      };
    }
    if (metricMode === "rmse") {
      // Lower RMSE is better (cyan to dark blue)
      const errorRatio = (layer.rmsePoseidon - 0.15) / (0.52 - 0.15);
      const color = errorRatio < 0.3 
        ? "rgba(34, 211, 238, 0.7)" 
        : errorRatio < 0.7 
          ? "rgba(59, 130, 246, 0.7)" 
          : "rgba(168, 85, 247, 0.7)";
      return {
        fill: color,
        stroke: "rgba(255, 255, 255, 0.4)",
        badgeText: `±${layer.rmsePoseidon.toFixed(2)}°C`,
      };
    }
    // Anomaly mode (-0.4°C to +0.6°C)
    const isPositive = layer.anomaly >= 0;
    return {
      fill: isPositive ? "rgba(249, 115, 22, 0.65)" : "rgba(14, 165, 233, 0.65)",
      stroke: "rgba(255, 255, 255, 0.4)",
      badgeText: `${isPositive ? "+" : ""}${layer.anomaly.toFixed(1)}°C`,
    };
  }, [metricMode]);

  // Transform styles for each layer in 3D
  const getLayerTransform = useCallback((index: number) => {
    if (viewMode === "flat") {
      const isCurrent = index === selectedIndex;
      return {
        transform: "none",
        display: isCurrent ? "block" : "none",
        opacity: 1,
        zIndex: 10,
      };
    }

    const total = OCEAN_DEPTH_LAYERS.length;
    // Layer 0 at top, Layer 14 at bottom
    const spacing = 12;
    const zOffset = (total - 1 - index) * spacing;
    const isSelected = index === selectedIndex;
    const isAbove = index < selectedIndex;

    let opacity = 0.85;
    if (isSelected) opacity = 1;
    else if (isAbove) opacity = 0.45;

    return {
      transform: `translateZ(${zOffset}px)`,
      opacity,
      zIndex: isSelected ? 30 : index,
    };
  }, [viewMode, selectedIndex]);

  const skillGain = useMemo(() => {
    const baseline = selectedLayer.rmseClimatology;
    const model = selectedLayer.rmsePoseidon;
    return Math.round(((baseline - model) / baseline) * 100);
  }, [selectedLayer]);

  return (
    <div className="flex flex-col gap-6">
      {/* Top Controls Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
        {/* Left: View Modes */}
        <div className="flex items-center gap-1 rounded-xl border border-white/15 bg-white/[0.03] p-1 backdrop-blur-md">
          <button
            onClick={() => setViewMode("stack")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
              viewMode === "stack"
                ? "bg-cyan-500/20 text-cyan-200 shadow-sm border border-cyan-400/30"
                : "text-white/60 hover:text-white hover:bg-white/5"
            }`}
            type="button"
          >
            <Layers size={13} />
            <span>3D Stack</span>
          </button>
          <button
            onClick={() => setViewMode("flat")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
              viewMode === "flat"
                ? "bg-cyan-500/20 text-cyan-200 shadow-sm border border-cyan-400/30"
                : "text-white/60 hover:text-white hover:bg-white/5"
            }`}
            type="button"
          >
            <Eye size={13} />
            <span>Flat Slice</span>
          </button>
        </div>

        {/* Center: Metric display mode */}
        <div className="flex items-center gap-1 rounded-xl border border-white/15 bg-white/[0.03] p-1 backdrop-blur-md">
          <button
            onClick={() => setMetricMode("temp")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
              metricMode === "temp"
                ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/30"
                : "text-white/60 hover:text-white"
            }`}
            type="button"
          >
            <Thermometer size={13} />
            <span>Temperature</span>
          </button>
          <button
            onClick={() => setMetricMode("rmse")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
              metricMode === "rmse"
                ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/30"
                : "text-white/60 hover:text-white"
            }`}
            type="button"
          >
            <BarChart2 size={13} />
            <span>RMSE Skill</span>
          </button>
          <button
            onClick={() => setMetricMode("anomaly")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
              metricMode === "anomaly"
                ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/30"
                : "text-white/60 hover:text-white"
            }`}
            type="button"
          >
            <TrendingUp size={13} />
            <span>Anomaly</span>
          </button>
        </div>

        {/* Right: Auto-play */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsPlaying((prev) => !prev)}
            className="flex items-center gap-1.5 rounded-lg border border-cyan-400/30 bg-cyan-500/15 px-3 py-1.5 text-xs font-semibold text-cyan-100 shadow-sm transition hover:bg-cyan-500/25"
            type="button"
          >
            {isPlaying ? <Pause size={13} /> : <Play size={13} />}
            <span>{isPlaying ? "Pause" : "Auto advance"}</span>
          </button>
        </div>
      </div>

      {/* Main 3D Canvas Stage & Telemetry Panel */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-center">
        {/* 3D Depth Stack Stage (8 cols) */}
        <div className="relative lg:col-span-8 flex min-h-[440px] items-center justify-center overflow-hidden rounded-2xl border border-white/20 bg-black/25 p-6 shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)] backdrop-blur-xl">
          {/* Subtle Stage Grid and Coordinate Overlay */}
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(34,211,238,0.06),transparent_70%)]" />
          <div className="pointer-events-none absolute left-4 top-4 font-mono text-[10px] text-white/40">
            <span>BAY OF BENGAL & ARABIAN SEA (5°N–28°N, 45°E–100°E)</span>
          </div>
          <div className="pointer-events-none absolute right-4 top-4 font-mono text-[10px] text-cyan-300/80">
            <span>15 RECONSTRUCTED DEPTH LAYERS</span>
          </div>

          {/* Perspective 3D Container */}
          <div
            className="relative flex items-center justify-center w-[340px] h-[260px] sm:w-[420px] sm:h-[300px]"
            style={{
              perspective: "1100px",
              perspectiveOrigin: "50% 30%",
            }}
          >
            <div
              className="relative w-full h-full transition-transform duration-700 ease-out"
              style={{
                transformStyle: "preserve-3d",
                transform:
                  viewMode === "flat"
                    ? "none"
                    : "rotateX(60deg) rotateZ(-30deg) translateY(-20px)",
              }}
            >
              {OCEAN_DEPTH_LAYERS.map((layer, index) => {
                const isSelected = index === selectedIndex;
                const layerStyle = getLayerColor(layer);
                const transformStyles = getLayerTransform(index);

                return (
                  <div
                    key={layer.depth}
                    onClick={() => handleLayerClick(index)}
                    style={{
                      ...transformStyles,
                      background: layerStyle.fill,
                    }}
                    className={`group absolute inset-0 rounded-xl cursor-pointer transition-[opacity,border-color,box-shadow] duration-200 border ${
                      isSelected
                        ? "border-cyan-300 ring-2 ring-cyan-400 shadow-[0_0_30px_rgba(34,211,238,0.6)]"
                        : "border-white/20 hover:border-cyan-300/80 hover:ring-1 hover:ring-cyan-300/50 hover:shadow-[0_0_20px_rgba(34,211,238,0.35)]"
                    }`}
                  >
                    {/* SVG Graphic representing North Indian Ocean Contours */}
                    <svg
                      viewBox="0 0 400 280"
                      className="pointer-events-none absolute inset-0 h-full w-full"
                    >
                      {/* Subsurface temperature gradient contour paths */}
                      <path
                        d="M 20 60 Q 90 40 180 60 T 360 80"
                        fill="none"
                        stroke={layerStyle.stroke}
                        strokeWidth="1.2"
                        strokeDasharray={isSelected ? "none" : "3 3"}
                      />
                      <path
                        d="M 40 130 Q 130 110 200 130 T 380 150"
                        fill="none"
                        stroke={layerStyle.stroke}
                        strokeWidth="1.2"
                      />
                      <path
                        d="M 30 200 Q 140 170 220 200 T 370 220"
                        fill="none"
                        stroke={layerStyle.stroke}
                        strokeWidth="1.2"
                      />

                      {/* Land Mass Silhouette (Indian Subcontinent Peninsula) */}
                      <polygon
                        points="150,10 260,10 240,80 205,170 195,190 185,170 160,80"
                        fill="rgba(10, 15, 25, 0.75)"
                        stroke="rgba(255, 255, 255, 0.4)"
                        strokeWidth="1"
                      />
                      {/* Sri Lanka teardrop */}
                      <ellipse
                        cx="220"
                        cy="195"
                        rx="7"
                        ry="12"
                        fill="rgba(10, 15, 25, 0.75)"
                        stroke="rgba(255, 255, 255, 0.4)"
                        strokeWidth="0.8"
                      />

                      {/* Basin Labels */}
                      <text x="50" y="110" fill="rgba(255,255,255,0.4)" fontSize="11" fontFamily="monospace">ARABIAN SEA</text>
                      <text x="270" y="110" fill="rgba(255,255,255,0.4)" fontSize="11" fontFamily="monospace">BAY OF BENGAL</text>
                    </svg>

                    {/* Depth Tag on Edge */}
                    <div
                      className={`pointer-events-none absolute right-2 top-2 flex items-center gap-1.5 rounded-md px-2 py-0.5 font-mono text-[10px] font-semibold transition-colors ${
                        isSelected
                          ? "bg-cyan-400 text-slate-950 shadow-md"
                          : "bg-black/70 text-white/80 border border-white/20 group-hover:border-cyan-400/50 group-hover:bg-cyan-500/20 group-hover:text-cyan-200"
                      }`}
                    >
                      <span>{layer.depth} m</span>
                      <span className="opacity-75">·</span>
                      <span>{layerStyle.badgeText}</span>
                    </div>

                    {/* D20 Special Marker */}
                    {layer.isD20Isotherm && (
                      <div className="pointer-events-none absolute left-3 bottom-2 flex items-center gap-1 rounded-md border border-cyan-400/40 bg-cyan-500/20 px-2 py-0.5 font-mono text-[9px] text-cyan-200">
                        <span className="size-1.5 rounded-full bg-cyan-300 animate-pulse" />
                        <span>D20 Isotherm</span>
                      </div>
                    )}

                    {/* MLD Marker */}
                    {layer.isMLD && (
                      <div className="pointer-events-none absolute left-3 bottom-2 flex items-center gap-1 rounded-md border border-amber-400/40 bg-amber-500/20 px-2 py-0.5 font-mono text-[9px] text-amber-200">
                        <span className="size-1.5 rounded-full bg-amber-300" />
                        <span>MLD Base</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Bottom Stage Depth Quick Jumper / Scrubber */}
          <div className="pointer-events-auto absolute bottom-3 inset-x-6 flex items-center justify-between gap-2 border-t border-white/10 pt-3">
            <span className="font-mono text-[10px] text-white/40 shrink-0">Surface (0m)</span>
            <div className="flex flex-1 items-center justify-between gap-1 overflow-x-auto px-2">
              {OCEAN_DEPTH_LAYERS.map((layer, idx) => (
                <button
                  key={layer.depth}
                  type="button"
                  onClick={() => handleLayerClick(idx)}
                  className={`size-6 rounded-full text-[9px] font-mono transition-all grid place-items-center ${
                    idx === selectedIndex
                      ? "bg-cyan-400 text-slate-950 font-bold scale-125 shadow-[0_0_10px_rgba(34,211,238,0.8)]"
                      : "text-white/50 hover:text-cyan-200 hover:bg-white/10"
                  }`}
                  title={`${layer.depth}m - ${layer.tempMean}°C`}
                >
                  {layer.depth < 100 ? layer.depth : idx}
                </button>
              ))}
            </div>
            <span className="font-mono text-[10px] text-white/40 shrink-0">Abyss (1000m)</span>
          </div>
        </div>

        {/* Selected Layer Telemetry / Scientific Readout Card (4 cols) */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          <div className="relative overflow-hidden rounded-2xl border border-white/20 bg-white/[0.04] p-5 shadow-[inset_0_1px_1px_rgba(255,255,255,0.35),0_8px_32px_rgba(0,0,0,0.25)] backdrop-blur-2xl">
            {/* Liquid glass light sheen */}
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/[0.12] via-transparent to-transparent opacity-70" />
            <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400/50 to-transparent" />

            <div className="relative z-10 flex flex-col gap-4">
              {/* Header: Depth & Zone */}
              <div className="flex items-start justify-between border-b border-white/10 pb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-2xl font-bold tracking-tight text-cyan-200">
                      {selectedLayer.depth} m
                    </span>
                    {selectedLayer.isD20Isotherm && (
                      <span className="rounded-md border border-cyan-400/40 bg-cyan-400/15 px-2 py-0.5 font-mono text-[10px] text-cyan-200 font-semibold">
                        D20
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-xs font-semibold uppercase tracking-wider text-white/70">
                    {selectedLayer.zone}
                  </p>
                </div>
                <div className="rounded-xl border border-white/15 bg-white/[0.06] p-2 text-cyan-300">
                  <Compass size={20} />
                </div>
              </div>

              {/* Physical description */}
              <p className="text-xs leading-relaxed text-neutral-300/75">
                {selectedLayer.zoneDescription}
              </p>

              {/* Primary Stats Grid */}
              <div className="grid grid-cols-2 gap-3 pt-1">
                <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
                  <span className="text-[10px] uppercase tracking-wider text-white/45 font-mono">
                    Mean Temperature
                  </span>
                  <p className="mt-1 font-mono text-xl font-semibold text-white">
                    {selectedLayer.tempMean.toFixed(1)} °C
                  </p>
                  <span className="text-[10px] text-white/40">
                    Range: {selectedLayer.tempMin.toFixed(1)}° – {selectedLayer.tempMax.toFixed(1)}°
                  </span>
                </div>

                <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
                  <span className="text-[10px] uppercase tracking-wider text-white/45 font-mono">
                    Poseidon RMSE
                  </span>
                  <p className="mt-1 font-mono text-xl font-semibold text-cyan-300">
                    ±{selectedLayer.rmsePoseidon.toFixed(2)} °C
                  </p>
                  <span className="text-[10px] text-emerald-400 font-medium">
                    +{skillGain}% vs Climatology
                  </span>
                </div>
              </div>

              {/* Baseline Comparison Bars */}
              <div className="flex flex-col gap-2 rounded-xl border border-white/10 bg-white/[0.02] p-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-white/60">Benchmark Skill vs Baselines</span>
                  <span className="font-mono text-[10px] text-cyan-300">Argo 2019–2020</span>
                </div>

                {/* Poseidon bar */}
                <div className="flex flex-col gap-1">
                  <div className="flex justify-between text-[10px] font-mono">
                    <span className="text-cyan-200">Poseidon (AI)</span>
                    <span className="text-cyan-200 font-semibold">{selectedLayer.rmsePoseidon.toFixed(2)}°C</span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-blue-500"
                      style={{ width: `${Math.min(100, (selectedLayer.rmsePoseidon / 1.5) * 100)}%` }}
                    />
                  </div>
                </div>

                {/* U-Net bar */}
                <div className="flex flex-col gap-1">
                  <div className="flex justify-between text-[10px] font-mono">
                    <span className="text-white/50">U-Net Baseline</span>
                    <span className="text-white/60">{selectedLayer.rmseUNet.toFixed(2)}°C</span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full bg-white/30"
                      style={{ width: `${Math.min(100, (selectedLayer.rmseUNet / 1.5) * 100)}%` }}
                    />
                  </div>
                </div>

                {/* Climatology bar */}
                <div className="flex flex-col gap-1">
                  <div className="flex justify-between text-[10px] font-mono">
                    <span className="text-white/40">Climatology</span>
                    <span className="text-white/50">{selectedLayer.rmseClimatology.toFixed(2)}°C</span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full bg-red-400/40"
                      style={{ width: `${Math.min(100, (selectedLayer.rmseClimatology / 1.5) * 100)}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Correlation and Anomaly Pill */}
              <div className="flex items-center justify-between border-t border-white/10 pt-2 text-xs font-mono">
                <span className="text-white/50">Correlation:</span>
                <span className="font-semibold text-emerald-400">R = {selectedLayer.correlation.toFixed(2)}</span>
                <span className="text-white/30">|</span>
                <span className="text-white/50">Anomaly:</span>
                <span className={selectedLayer.anomaly >= 0 ? "text-amber-300" : "text-sky-300"}>
                  {selectedLayer.anomaly >= 0 ? "+" : ""}{selectedLayer.anomaly.toFixed(1)} °C
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Footnote note */}
      <div className="flex items-center gap-2 text-xs text-white/45">
        <Info size={14} className="text-cyan-300/70 shrink-0" />
        <span>
          Interactive 15-depth oceanographic volume for the North Indian Ocean basin. Click any layer or use the scrubber below to inspect temperature stratifications from the sunlit surface to 1000m.
        </span>
      </div>
    </div>
  );
}
