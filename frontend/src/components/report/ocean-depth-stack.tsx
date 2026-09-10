"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
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

export interface OceanDepthStackProps {
  selectedIndex?: number;
  onSelectIndex?: (index: number) => void;
  /** Per-depth skill; defaults to the static descriptions when no report is loaded. */
  layers?: OceanDepthLayer[];
}

export function OceanDepthStack({
  selectedIndex: controlledIndex,
  onSelectIndex,
  layers: layersProp,
}: OceanDepthStackProps = {}) {
  const layers = layersProp ?? OCEAN_DEPTH_LAYERS;
  const prefersReducedMotion = useReducedMotion();
  const [internalIndex, setInternalIndex] = useState<number>(7); // Default to 100m (thermocline / D20)
  const isControlled = controlledIndex !== undefined;
  const selectedIndex = isControlled ? controlledIndex : internalIndex;

  const setSelectedIndex = useCallback(
    (updater: number | ((prev: number) => number)) => {
      const nextVal = typeof updater === "function" ? updater(selectedIndex) : updater;
      if (onSelectIndex) {
        onSelectIndex(nextVal);
      }
      if (!isControlled) {
        setInternalIndex(nextVal);
      }
    },
    [isControlled, selectedIndex, onSelectIndex]
  );

  const [viewMode, setViewMode] = useState<ViewMode>("stack");
  const [metricMode, setMetricMode] = useState<MetricMode>("temp");
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  const selectedLayer = layers[selectedIndex];
  const rmseScale = Math.max(1.5, selectedLayer.rmseVaruna, selectedLayer.rmseGbm, selectedLayer.rmseClimatology);

  // Auto-play animation: step through layers sequentially
  useEffect(() => {
    if (!isPlaying) return;
    const interval = window.setInterval(() => {
      setSelectedIndex((prev) => (prev + 1) % layers.length);
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
      const errorRatio = (layer.rmseVaruna - 0.15) / (0.52 - 0.15);
      const color = errorRatio < 0.3 
        ? "rgba(34, 211, 238, 0.7)" 
        : errorRatio < 0.7 
          ? "rgba(59, 130, 246, 0.7)" 
          : "rgba(168, 85, 247, 0.7)";
      return {
        fill: color,
        stroke: "rgba(255, 255, 255, 0.4)",
        badgeText: `±${layer.rmseVaruna.toFixed(2)}°C`,
      };
    }
    // Bias mode: the model's mean error at this depth
    const isPositive = layer.bias >= 0;
    return {
      fill: isPositive ? "rgba(249, 115, 22, 0.65)" : "rgba(14, 165, 233, 0.65)",
      stroke: "rgba(255, 255, 255, 0.4)",
      badgeText: `${isPositive ? "+" : ""}${layer.bias.toFixed(2)}°C`,
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

    const total = layers.length;
    // Center the z-offset around the middle layer (index 7, 100m D20)
    const spacing = 11;
    const centerIndex = (total - 1) / 2;
    const zOffset = (centerIndex - index) * spacing;
    const isSelected = index === selectedIndex;

    let opacity = 0.9;
    let filter = "none";
    let pointerEvents: "auto" | "none" = "auto";

    if (isSelected) {
      opacity = 1;
      filter = "none";
    } else if (index < selectedIndex) {
      // Layers ABOVE the selected layer (going up towards surface 0m)
      // Progressively increase transparency (lower opacity) and increase blur as we go higher up
      const stepsAbove = selectedIndex - index;
      const progress = selectedIndex > 1 ? (stepsAbove - 1) / (selectedIndex - 1) : 0;

      // Opacity drops from ~0.28 down to ~0.06 as we reach the topmost surface layer
      opacity = Math.max(0.06, 0.28 - progress * 0.22);

      // Blur increases progressively as layers sit further above the focus plane (from 2px to 6px)
      const blurPx = 2 + progress * 4;
      filter = `blur(${blurPx.toFixed(1)}px)`;

      // Pass through clicks on highly transparent upper layers so focused layer is easily interactive
      if (opacity < 0.15) {
        pointerEvents = "none";
      }
    } else {
      // Layers BELOW the selected layer (deeper ocean abyss)
      const stepsBelow = index - selectedIndex;
      const maxBelow = (total - 1) - selectedIndex;
      const progressBelow = maxBelow > 0 ? stepsBelow / maxBelow : 0;
      opacity = Math.max(0.68, 0.92 - progressBelow * 0.24);
      filter = "none";
    }

    return {
      transform: `translateZ(${zOffset}px)`,
      opacity,
      filter,
      pointerEvents,
      zIndex: isSelected ? 40 : total - index,
    };
  }, [viewMode, selectedIndex]);

  const skillGain = useMemo(() => {
    const baseline = selectedLayer.rmseClimatology;
    const model = selectedLayer.rmseVaruna;
    return Math.round(((baseline - model) / baseline) * 100);
  }, [selectedLayer]);

  return (
    <div className="flex flex-col gap-6">
      {/* Top Controls Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
        {/* Left: View Modes (Limelight Icon Navbar) */}
        <div className="relative inline-flex items-center gap-1 rounded-2xl border border-white/15 bg-white/[0.02] p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.12)] backdrop-blur-xl">
          {([
            { id: "stack" as ViewMode, label: "3D Stack", icon: Layers },
            { id: "flat" as ViewMode, label: "Flat Slice", icon: Eye },
          ] as const).map((tab) => {
            const Icon = tab.icon;
            const active = viewMode === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setViewMode(tab.id)}
                title={tab.label}
                aria-label={tab.label}
                className="relative z-10 grid size-10 place-items-center rounded-xl outline-none transition-colors focus-visible:ring-2 focus-visible:ring-white/50"
                type="button"
              >
                {active && (
                  <motion.span
                    aria-hidden="true"
                    className="pointer-events-none absolute inset-x-1.5 top-0 h-1 rounded-full bg-white shadow-[0_10px_20px_rgba(255,255,255,0.95),0_0_12px_rgba(255,255,255,0.85)]"
                    layoutId="limelight-view-beam"
                    transition={prefersReducedMotion ? { duration: 0 } : { type: "spring", stiffness: 380, damping: 30 }}
                  >
                    <span className="absolute left-[-30%] top-1 h-8 w-[160%] bg-gradient-to-b from-white/35 via-white/10 to-transparent [clip-path:polygon(10%_100%,28%_0,72%_0,90%_100%)]" />
                  </motion.span>
                )}
                <Icon
                  size={18}
                  className={active ? "text-white drop-shadow-[0_0_10px_rgba(255,255,255,0.8)]" : "text-white/50 transition-colors hover:text-white/80"}
                  strokeWidth={active ? 2.2 : 1.8}
                />
                <span className="sr-only">{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Center: Metric display mode (Limelight Icon Navbar) */}
        <div className="relative inline-flex items-center gap-1 rounded-2xl border border-white/15 bg-white/[0.02] p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.12)] backdrop-blur-xl">
          {([
            { id: "temp" as MetricMode, label: "Temperature", icon: Thermometer },
            { id: "rmse" as MetricMode, label: "RMSE Skill", icon: BarChart2 },
            { id: "anomaly" as MetricMode, label: "Bias", icon: TrendingUp },
          ] as const).map((tab) => {
            const Icon = tab.icon;
            const active = metricMode === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setMetricMode(tab.id)}
                title={tab.label}
                aria-label={tab.label}
                className="relative z-10 grid size-10 place-items-center rounded-xl outline-none transition-colors focus-visible:ring-2 focus-visible:ring-white/50"
                type="button"
              >
                {active && (
                  <motion.span
                    aria-hidden="true"
                    className="pointer-events-none absolute inset-x-1.5 top-0 h-1 rounded-full bg-white shadow-[0_10px_20px_rgba(255,255,255,0.95),0_0_12px_rgba(255,255,255,0.85)]"
                    layoutId="limelight-metric-beam"
                    transition={prefersReducedMotion ? { duration: 0 } : { type: "spring", stiffness: 380, damping: 30 }}
                  >
                    <span className="absolute left-[-30%] top-1 h-8 w-[160%] bg-gradient-to-b from-white/35 via-white/10 to-transparent [clip-path:polygon(10%_100%,28%_0,72%_0,90%_100%)]" />
                  </motion.span>
                )}
                <Icon
                  size={18}
                  className={active ? "text-white drop-shadow-[0_0_10px_rgba(255,255,255,0.8)]" : "text-white/50 transition-colors hover:text-white/80"}
                  strokeWidth={active ? 2.2 : 1.8}
                />
                <span className="sr-only">{tab.label}</span>
              </button>
            );
          })}
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
        <div className="relative lg:col-span-8 flex min-h-[480px] items-center justify-center overflow-hidden rounded-2xl border border-white/20 bg-black/25 px-6 pt-12 pb-16 shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)] backdrop-blur-xl">
          {/* Subtle Stage Grid and Coordinate Overlay */}
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(34,211,238,0.06),transparent_70%)]" />
          <div className="pointer-events-none absolute left-5 top-4 font-mono text-[10px] text-white/40">
            <span>ARABIAN SEA AND BAY OF BENGAL (5 TO 30 N, 45 TO 105 E)</span>
          </div>
          <div className="pointer-events-none absolute right-5 top-4 font-mono text-[10px] text-cyan-300/80">
            <span>15 RECONSTRUCTED DEPTH LAYERS</span>
          </div>

          {/* Perspective 3D Container */}
          <div
            className="relative mb-auto mt-6 flex items-center justify-center w-[300px] h-[210px] sm:w-[380px] sm:h-[250px]"
            style={{
              perspective: "1200px",
              perspectiveOrigin: "50% 45%",
            }}
          >
            <div
              className="relative w-full h-full transition-transform duration-700 ease-out"
              style={{
                transformStyle: "preserve-3d",
                transform:
                  viewMode === "flat"
                    ? "translateY(-12px)"
                    : "rotateX(58deg) rotateZ(-28deg) translateY(-22px)",
              }}
            >
              {layers.map((layer, index) => {
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
                    className={`group absolute inset-0 rounded-xl cursor-pointer transition-[opacity,filter,transform,border-color,box-shadow] duration-300 ease-out border ${
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

          {/* Bottom Stage Depth Scrollbar / Slider */}
          <div className="pointer-events-auto absolute bottom-3.5 inset-x-6 flex flex-col gap-2 border-t border-white/10 pt-3">
            <div className="flex items-center justify-between text-[11px] font-mono">
              <span className="text-white/40">Surface (0m)</span>
              <div className="flex items-center gap-2 font-semibold">
                <span className="text-white/60">Depth:</span>
                <span className="rounded-md border border-cyan-400/40 bg-cyan-500/20 px-2 py-0.5 font-bold text-cyan-100 shadow-[0_0_10px_rgba(34,211,238,0.3)]">
                  {selectedLayer.depth} m
                </span>
                {selectedLayer.isD20Isotherm && (
                  <span className="rounded border border-amber-400/40 bg-amber-500/20 px-1.5 py-0.5 text-[9px] text-amber-200">
                    D20
                  </span>
                )}
                {selectedLayer.isMLD && (
                  <span className="rounded border border-amber-400/40 bg-amber-500/20 px-1.5 py-0.5 text-[9px] text-amber-200">
                    MLD
                  </span>
                )}
              </div>
              <span className="text-white/40">Abyss (1000m)</span>
            </div>

            {/* Interactive Smooth Slider Track */}
            <div className="relative flex items-center w-full h-6">
              {/* Track Background */}
              <div className="relative w-full h-2 rounded-full bg-white/10 overflow-hidden shadow-inner">
                {/* Active Progress Fill */}
                <motion.div
                  className="h-full bg-gradient-to-r from-cyan-500/50 via-cyan-400 to-cyan-300 shadow-[0_0_12px_rgba(34,211,238,0.7)]"
                  style={{ width: `${(selectedIndex / (layers.length - 1)) * 100}%` }}
                  transition={prefersReducedMotion ? { duration: 0 } : { type: "spring", stiffness: 350, damping: 28 }}
                />
              </div>

              {/* Discrete Tick Nodes for all 15 depths */}
              <div className="pointer-events-none absolute inset-x-0 flex items-center justify-between px-1">
                {layers.map((layer, idx) => (
                  <div
                    key={layer.depth}
                    className={`size-1.5 rounded-full transition-all duration-200 ${
                      idx <= selectedIndex
                        ? "bg-cyan-200 shadow-[0_0_6px_rgba(34,211,238,0.8)] scale-110"
                        : "bg-white/20"
                    }`}
                  />
                ))}
              </div>

              {/* Animated Glowing Thumb with spring physics */}
              <motion.div
                className="pointer-events-none absolute top-1/2 -translate-y-1/2 size-5 -ml-2.5 rounded-full border-2 border-white bg-gradient-to-tr from-cyan-400 to-cyan-200 shadow-[0_0_16px_rgba(34,211,238,0.9),0_2px_6px_rgba(0,0,0,0.5)] flex items-center justify-center z-10"
                style={{
                  left: `${(selectedIndex / (layers.length - 1)) * 100}%`,
                }}
                transition={prefersReducedMotion ? { duration: 0 } : { type: "spring", stiffness: 450, damping: 30 }}
              >
                <div className="size-1.5 rounded-full bg-slate-950" />
              </motion.div>

              {/* Native Range Input for smooth sliding, scrubbing, and drag */}
              <input
                type="range"
                min={0}
                max={layers.length - 1}
                step={1}
                value={selectedIndex}
                onChange={(e) => handleLayerClick(Number(e.target.value))}
                aria-label="Ocean depth scrubber slider"
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-20"
              />
            </div>
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
                    Typical Temperature
                  </span>
                  <p className="mt-1 font-mono text-xl font-semibold text-white">
                    {selectedLayer.tempMean.toFixed(1)} °C
                  </p>
                  <span className="text-[10px] text-white/40">
                    Usually {selectedLayer.tempMin.toFixed(1)} to {selectedLayer.tempMax.toFixed(1)} °C
                  </span>
                </div>

                <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
                  <span className="text-[10px] uppercase tracking-wider text-white/45 font-mono">
                    Varuna RMSE
                  </span>
                  <p className="mt-1 font-mono text-xl font-semibold text-cyan-300">
                    ±{selectedLayer.rmseVaruna.toFixed(2)} °C
                  </p>
                  <span className="text-[10px] text-emerald-400 font-medium">
                    {skillGain >= 0 ? "+" : ""}{skillGain}% vs Climatology
                  </span>
                </div>
              </div>

              {/* Baseline Comparison Bars */}
              <div className="flex flex-col gap-2 rounded-xl border border-white/10 bg-white/[0.02] p-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-white/60">Benchmark Skill vs Baselines</span>
                  <span className="font-mono text-[10px] text-cyan-300">test days 2019 and 2020</span>
                </div>

                {/* Varuna bar */}
                <div className="flex flex-col gap-1">
                  <div className="flex justify-between text-[10px] font-mono">
                    <span className="text-cyan-200">Varuna (AI)</span>
                    <span className="text-cyan-200 font-semibold">{selectedLayer.rmseVaruna.toFixed(2)}°C</span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-blue-500"
                      style={{ width: `${Math.min(100, (selectedLayer.rmseVaruna / rmseScale) * 100)}%` }}
                    />
                  </div>
                </div>

                {/* GBM bar */}
                <div className="flex flex-col gap-1">
                  <div className="flex justify-between text-[10px] font-mono">
                    <span className="text-white/50">GBM baseline</span>
                    <span className="text-white/60">{selectedLayer.rmseGbm.toFixed(2)}°C</span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full bg-white/30"
                      style={{ width: `${Math.min(100, (selectedLayer.rmseGbm / rmseScale) * 100)}%` }}
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
                      style={{ width: `${Math.min(100, (selectedLayer.rmseClimatology / rmseScale) * 100)}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Correlation and bias pill */}
              <div className="flex items-center justify-between border-t border-white/10 pt-2 text-xs font-mono">
                <span className="text-white/50">Correlation:</span>
                <span className="font-semibold text-emerald-400">R = {selectedLayer.correlation.toFixed(2)}</span>
                <span className="text-white/30">|</span>
                <span className="text-white/50">Bias:</span>
                <span className={selectedLayer.bias >= 0 ? "text-amber-300" : "text-sky-300"}>
                  {selectedLayer.bias >= 0 ? "+" : ""}{selectedLayer.bias.toFixed(2)} °C
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
          Click a layer, or drag the slider below, to move from the surface down to 1000 m. The bars on the right show the error at that depth.
        </span>
      </div>
    </div>
  );
}
