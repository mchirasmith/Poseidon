"use client";

import { useEffect, useRef, useState, useMemo, useCallback } from "react";
import { Radio } from "lucide-react";
import { getColorByMode } from "@/lib/color-scales";
import type { ArgoMarker, SectionData, SectionMode } from "@/lib/section";

interface SectionHeatmapProps {
  data: SectionData;
  mode: SectionMode;
  showD20: boolean;
  showMLD: boolean;
  showArgo: boolean;
}

// Key depth ticks on the non-linear piecewise vertical axis
const AXIS_DEPTH_TICKS = [0, 20, 50, 100, 150, 200, 300, 500, 700, 1000];

/** Maps ocean depth (0-1000m) to normalized Y (0 at 0m, 0.5 at 200m, 1.0 at 1000m) */
function depthToNormY(depthM: number): number {
  const d = Math.max(0, Math.min(1000, depthM));
  if (d <= 200) {
    return 0.5 * (d / 200);
  }
  return 0.5 + 0.5 * ((d - 200) / 800);
}

/** Inverse mapping from normalized Y back to depth in meters */
function normYToDepth(normY: number): number {
  const clamped = Math.max(0, Math.min(1, normY));
  if (clamped <= 0.5) {
    return Math.round((clamped / 0.5) * 200);
  }
  return Math.round(200 + ((clamped - 0.5) / 0.5) * 800);
}

export function SectionHeatmap({
  data,
  mode,
  showD20,
  showMLD,
  showArgo,
}: SectionHeatmapProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Selected & Hovered Argo Float profiles
  const [selectedArgo, setSelectedArgo] = useState<ArgoMarker | null>(null);
  const [hoveredArgo, setHoveredArgo] = useState<ArgoMarker | null>(null);

  const [hoverPos, setHoverPos] = useState<{
    x: number;
    y: number;
    containerWidth: number;
    distKm: number;
    depthM: number;
    lat: number;
    lon: number;
    value: number;
    localD20: number;
    localMLD: number;
    isNearD20: boolean;
    isNearMLD: boolean;
  } | null>(null);

  const { distances_km, lats, lons, depths_m, poseidon, glorys, diff, sigma, d20_m, mld_m, totalDistanceKm } = data;

  // Active 2D matrix depending on selected mode
  const activeMatrix = useMemo(() => {
    switch (mode) {
      case "poseidon":
        return poseidon;
      case "glorys":
        return glorys;
      case "diff":
        return diff;
      case "sigma":
        return sigma;
    }
  }, [mode, poseidon, glorys, diff, sigma]);

  // Color scale configuration for active mode
  const scaleInfo = useMemo(() => {
    switch (mode) {
      case "poseidon":
      case "glorys":
        return {
          title: "Temperature scale",
          min: "2.0 °C",
          mid: "18.0 °C",
          max: "32.0 °C",
          unit: "°C",
          gradient: "from-[#0d1126] via-[#2a9d8f] via-[#e49e36] to-[#f52d23]",
        };
      case "diff":
        return {
          title: "Model difference (Poseidon − GLORYS)",
          min: "-3.0 °C",
          mid: "0.0 °C",
          max: "+3.0 °C",
          unit: "°C",
          gradient: "from-[#1b4496] via-[#f2f2f2] to-[#b8221e]",
        };
      case "sigma":
        return {
          title: "Uncertainty spread (1σ)",
          min: "0.0 °C",
          mid: "1.0 °C",
          max: "2.0 °C",
          unit: "°C",
          gradient: "from-[#0f172a] via-[#b43269] to-[#fed766]",
        };
    }
  }, [mode]);

  // Render the 2D vertical cross-section to canvas with piecewise depth interpolation
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = 640;
    const height = 360;
    canvas.width = width;
    canvas.height = height;

    const numDistSteps = activeMatrix.length;
    if (numDistSteps === 0) return;

    const imgData = ctx.createImageData(width, height);
    const pixels = imgData.data;
    const depthNormYs = depths_m.map(depthToNormY);

    for (let x = 0; x < width; x++) {
      const distFraction = x / (width - 1);
      const distIdx = Math.min(numDistSteps - 1, Math.floor(distFraction * numDistSteps));
      const depthValues = activeMatrix[distIdx];

      for (let y = 0; y < height; y++) {
        const normY = y / (height - 1);

        let d1 = 0;
        let d2 = depths_m.length - 1;
        for (let k = 0; k < depthNormYs.length - 1; k++) {
          if (normY >= depthNormYs[k] && normY <= depthNormYs[k + 1]) {
            d1 = k;
            d2 = k + 1;
            break;
          }
        }

        const t =
          depthNormYs[d2] === depthNormYs[d1]
            ? 0
            : (normY - depthNormYs[d1]) / (depthNormYs[d2] - depthNormYs[d1]);
        const val = depthValues[d1] + t * (depthValues[d2] - depthValues[d1]);

        // land and below-seafloor cells carry NaN: paint them as dark basement
        const rgbStr = Number.isFinite(val) ? getColorByMode(val, mode) : "rgb(14, 18, 28)";
        const match = rgbStr.match(/\d+/g);
        const r = match ? Number(match[0]) : 20;
        const g = match ? Number(match[1]) : 30;
        const b = match ? Number(match[2]) : 50;

        const pIdx = (y * width + x) * 4;
        pixels[pIdx] = r;
        pixels[pIdx + 1] = g;
        pixels[pIdx + 2] = b;
        pixels[pIdx + 3] = 255;
      }
    }

    ctx.putImageData(imgData, 0, 0);
  }, [activeMatrix, depths_m, mode]);

  // Handle pointer hover to inspect exact values along the slice
  const handlePointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      const container = containerRef.current;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const clientX = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
      const clientY = Math.max(0, Math.min(rect.height, e.clientY - rect.top));

      const fracX = clientX / rect.width;
      const fracY = clientY / rect.height;

      const numDistSteps = activeMatrix.length;
      const distIdx = Math.min(numDistSteps - 1, Math.floor(fracX * numDistSteps));
      const distKm = distances_km[distIdx];
      const lat = lats[distIdx];
      const lon = lons[distIdx];
      const depthM = normYToDepth(fracY);

      const depthNormYs = depths_m.map(depthToNormY);
      let d1 = 0;
      let d2 = depths_m.length - 1;
      for (let k = 0; k < depthNormYs.length - 1; k++) {
        if (fracY >= depthNormYs[k] && fracY <= depthNormYs[k + 1]) {
          d1 = k;
          d2 = k + 1;
          break;
        }
      }
      const t =
        depthNormYs[d2] === depthNormYs[d1]
          ? 0
          : (fracY - depthNormYs[d1]) / (depthNormYs[d2] - depthNormYs[d1]);
      const depthValues = activeMatrix[distIdx];
      const val = Number((depthValues[d1] + t * (depthValues[d2] - depthValues[d1])).toFixed(2));

      const localD20 = d20_m[distIdx] ?? 0;
      const localMLD = mld_m[distIdx] ?? 0;
      const isNearD20 = Math.abs(depthM - localD20) < 18;
      const isNearMLD = Math.abs(depthM - localMLD) < 10;

      setHoverPos({
        x: clientX,
        y: clientY,
        containerWidth: rect.width,
        distKm,
        depthM,
        lat,
        lon,
        value: val,
        localD20,
        localMLD,
        isNearD20,
        isNearMLD,
      });
    },
    [activeMatrix, distances_km, lats, lons, depths_m, d20_m, mld_m]
  );

  const handlePointerLeave = () => setHoverPos(null);

  // SVG Paths for D20 and MLD contours
  const d20Path = useMemo(() => {
    return d20_m
      .map((d, i) => {
        const x = (i / (d20_m.length - 1)) * 100;
        const y = depthToNormY(d) * 100;
        return `${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
      })
      .join(" ");
  }, [d20_m]);

  const mldPath = useMemo(() => {
    return mld_m
      .map((d, i) => {
        const x = (i / (mld_m.length - 1)) * 100;
        const y = depthToNormY(d) * 100;
        return `${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
      })
      .join(" ");
  }, [mld_m]);

  // Dismiss tooltip when user scrolls the page
  useEffect(() => {
    const handleScroll = () => {
      setHoverPos(null);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Distance ticks along X axis
  const distanceTicks = useMemo(() => {
    const ticks: { distKm: number; normX: number; label: string }[] = [];
    ticks.push({ distKm: 0, normX: 0, label: "0 km (A)" });

    const step = totalDistanceKm > 1500 ? 500 : totalDistanceKm > 800 ? 250 : 100;
    for (let d = step; d < totalDistanceKm - step / 2; d += step) {
      ticks.push({
        distKm: d,
        normX: d / totalDistanceKm,
        label: `${d} km`,
      });
    }

    ticks.push({
      distKm: totalDistanceKm,
      normX: 1.0,
      label: `${totalDistanceKm} km (B)`,
    });
    return ticks;
  }, [totalDistanceKm]);

  return (
    <div className="mt-4 space-y-4">
      {/* Heatmap Container with Axes */}
      <div className="relative flex select-none">
        {/* Y-Axis: Inverted Depth Ticks */}
        <div className="relative w-14 sm:w-16 shrink-0 text-right pr-2">
          {AXIS_DEPTH_TICKS.map((depth) => {
            const normY = depthToNormY(depth);
            const isThermocline = depth === 100;
            const isMLDBound = depth === 20;

            return (
              <div
                key={depth}
                className="absolute right-2 -translate-y-1/2 flex items-center gap-1 font-mono text-[10px]"
                style={{ top: `${(normY * 100).toFixed(2)}%` }}
              >
                <span
                  className={`${
                    isThermocline
                      ? "text-cyan-300 font-bold"
                      : isMLDBound
                      ? "text-emerald-300 font-semibold"
                      : "text-white/60"
                  }`}
                >
                  {depth}m
                </span>
                <span className="h-px w-2 bg-white/30" />
              </div>
            );
          })}
          <span className="absolute top-1/2 -left-6 -translate-y-1/2 -rotate-90 text-[10px] font-mono uppercase tracking-widest text-white/40">
            Depth (m)
          </span>
        </div>

        {/* Heatmap Surface (Canvas + SVG Overlays) */}
        <div
          ref={containerRef}
          className="relative flex-1 h-[340px] sm:h-[400px] overflow-hidden rounded-xl border border-white/15 bg-slate-950 cursor-crosshair shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)]"
          onPointerMove={handlePointerMove}
          onPointerLeave={handlePointerLeave}
        >
          {/* Interpolated Canvas */}
          <canvas ref={canvasRef} className="h-full w-full object-fill" />

          {/* SVG Overlay: Contour lines, MLD, and Argo markers */}
          <svg
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            className="pointer-events-none absolute inset-0 h-full w-full"
          >
            {/* Horizontal Grid lines at depth ticks */}
            {AXIS_DEPTH_TICKS.map((depth) => (
              <line
                key={`grid-${depth}`}
                x1="0"
                y1={depthToNormY(depth) * 100}
                x2="100"
                y2={depthToNormY(depth) * 100}
                stroke="rgba(255,255,255,0.12)"
                strokeDasharray="1 2"
                strokeWidth="0.4"
              />
            ))}

            {/* D20 Isotherm Contour (Cyan continuous curve with reactive highlight) */}
            {showD20 && (
              <>
                <path
                  d={d20Path}
                  fill="none"
                  stroke="#000000"
                  strokeWidth={hoverPos?.isNearD20 ? "4.0" : "2.8"}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity="0.85"
                />
                <path
                  d={d20Path}
                  fill="none"
                  stroke="#22d3ee"
                  strokeWidth={hoverPos?.isNearD20 ? "2.6" : "1.6"}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{
                    filter: hoverPos?.isNearD20
                      ? "drop-shadow(0 0 6px rgba(34, 211, 238, 0.95))"
                      : "drop-shadow(0 0 2px rgba(34, 211, 238, 0.4))",
                  }}
                  className="transition-all duration-150"
                />
              </>
            )}

            {/* MLD Line (White dashed curve with reactive highlight) */}
            {showMLD && (
              <path
                d={mldPath}
                fill="none"
                stroke="#ffffff"
                strokeWidth={hoverPos?.isNearMLD ? "2.6" : "1.6"}
                strokeDasharray="4 2"
                strokeLinecap="round"
                style={{
                  filter: hoverPos?.isNearMLD
                    ? "drop-shadow(0 0 6px rgba(255, 255, 255, 0.95))"
                    : "drop-shadow(0 0 2px rgba(255, 255, 255, 0.35))",
                }}
                className="transition-all duration-150"
              />
            )}

            {/* Argo Float Markers with Interactive Click/Hover Selection */}
            {showArgo &&
              data.argo_markers.map((marker, i) => {
                const normX = (marker.distance_km / totalDistanceKm) * 100;
                const isFloatActive =
                  selectedArgo?.wmo === marker.wmo || hoveredArgo?.wmo === marker.wmo;

                return (
                  <g
                    key={`argo-${i}`}
                    className="cursor-pointer"
                    onPointerEnter={() => setHoveredArgo(marker)}
                    onPointerLeave={() => setHoveredArgo(null)}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedArgo((prev) => (prev?.wmo === marker.wmo ? null : marker));
                    }}
                  >
                    {/* Generous hit area for easy touch/mouse hover */}
                    <line
                      x1={normX}
                      y1="0"
                      x2={normX}
                      y2="100"
                      stroke="transparent"
                      strokeWidth="24"
                    />

                    {/* Vertical profile collocated line */}
                    <line
                      x1={normX}
                      y1="0"
                      x2={normX}
                      y2="100"
                      stroke={isFloatActive ? "#f59e0b" : "#fbbf24"}
                      strokeWidth={isFloatActive ? "2.6" : "1.2"}
                      strokeDasharray={isFloatActive ? "none" : "2 3"}
                      style={{
                        filter: isFloatActive
                          ? "drop-shadow(0 0 8px rgba(245, 158, 11, 0.95))"
                          : "none",
                      }}
                      className="transition-all duration-150"
                    />

                    {/* Surface float beacon ping halo */}
                    <circle
                      cx={normX}
                      cy="4"
                      r={isFloatActive ? 8 : 4}
                      fill={isFloatActive ? "rgba(245, 158, 11, 0.35)" : "rgba(251, 191, 36, 0.18)"}
                      className={isFloatActive ? "animate-pulse" : ""}
                    />

                    {/* Surface float center beacon */}
                    <circle
                      cx={normX}
                      cy="4"
                      r={isFloatActive ? 3.8 : 2.4}
                      fill={isFloatActive ? "#f59e0b" : "#fbbf24"}
                      stroke="#ffffff"
                      strokeWidth={isFloatActive ? "1.2" : "0.5"}
                    />
                  </g>
                );
              })}
          </svg>

          {/* Dedicated Argo Float Inspection Popover */}
          {showArgo && (hoveredArgo || selectedArgo) && (() => {
            const activeFloat = hoveredArgo || selectedArgo;
            if (!activeFloat) return null;
            const normX = (activeFloat.distance_km / totalDistanceKm) * 100;
            const clampedNormX = Math.max(18, Math.min(82, normX));

            return (
              <div
                className="pointer-events-auto absolute top-3 z-30 -translate-x-1/2 rounded-xl border border-amber-400/50 bg-slate-950/95 p-3 text-xs shadow-2xl backdrop-blur-xl animate-in fade-in zoom-in-95 duration-150 font-mono"
                style={{ left: `${clampedNormX}%` }}
              >
                <div className="flex items-center justify-between gap-3 border-b border-amber-400/20 pb-1.5">
                  <div className="flex items-center gap-1.5 font-bold text-amber-200">
                    <Radio size={13} className="text-amber-300 animate-pulse" />
                    <span>Argo Float #{activeFloat.wmo}</span>
                  </div>
                  <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[9px] font-bold text-amber-300">
                    IN-SITU MATCHUP
                  </span>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-white/80">
                  <span>Transect Distance:</span>
                  <span className="text-right text-amber-200 font-semibold">{activeFloat.distance_km} km</span>
                  <span>Match Offset:</span>
                  <span className="text-right text-white">
                    {activeFloat.day_offset === 0
                      ? "Synchronous (0d)"
                      : `${activeFloat.day_offset! > 0 ? "+" : ""}${activeFloat.day_offset} day offset`}
                  </span>
                  <span>Depth Coverage:</span>
                  <span className="text-right text-white/70">0 – 1000 m (15 layers)</span>
                  <span>Collocated Skill:</span>
                  <span className="text-right text-cyan-300 font-bold">RMSE ~0.34 °C</span>
                </div>
              </div>
            );
          })()}

          {/* Hover Crosshairs & Inspector Tooltip */}
          {hoverPos && (
            <>
              {/* Vertical crosshair */}
              <div
                className="pointer-events-none absolute top-0 bottom-0 w-px bg-cyan-300/80 shadow-[0_0_8px_rgba(34,211,238,0.8)]"
                style={{ left: `${hoverPos.x}px` }}
              />
              {/* Horizontal crosshair */}
              <div
                className="pointer-events-none absolute left-0 right-0 h-px bg-cyan-300/80 shadow-[0_0_8px_rgba(34,211,238,0.8)]"
                style={{ top: `${hoverPos.y}px` }}
              />
              {/* Tooltip Badge with dynamic top/bottom flip and horizontal bounds clamping */}
              {(() => {
                const containerWidth = hoverPos.containerWidth || 600;
                const clampedX = Math.max(105, Math.min(hoverPos.x, containerWidth - 105));
                const isNearTop = hoverPos.y < 125;
                const tooltipTop = isNearTop ? hoverPos.y + 14 : hoverPos.y - 14;

                return (
                  <div
                    className={`pointer-events-none absolute z-20 -translate-x-1/2 rounded-xl border border-cyan-400/40 bg-slate-950/95 p-2.5 text-xs shadow-2xl backdrop-blur-xl transition-all ${
                      isNearTop ? "translate-y-0" : "-translate-y-full"
                    }`}
                    style={{
                      left: `${clampedX}px`,
                      top: `${tooltipTop}px`,
                    }}
                  >
                    <div className="flex items-center justify-between gap-3 border-b border-white/10 pb-1.5 font-mono">
                      <span className="font-bold text-white text-sm">
                        {hoverPos.value > 0 && mode === "diff" ? `+${hoverPos.value}` : hoverPos.value}{" "}
                        {scaleInfo.unit}
                      </span>
                      <div className="flex items-center gap-1.5">
                        {hoverPos.isNearD20 && showD20 && (
                          <span className="rounded bg-cyan-500/30 px-1.5 py-0.5 text-[9px] font-bold text-cyan-200 border border-cyan-400/40">
                            D20 BOUNDARY
                          </span>
                        )}
                        {hoverPos.isNearMLD && showMLD && (
                          <span className="rounded bg-white/20 px-1.5 py-0.5 text-[9px] font-bold text-white border border-white/40">
                            MLD BOUNDARY
                          </span>
                        )}
                        <span className="rounded bg-cyan-500/20 px-1.5 py-0.5 text-[10px] text-cyan-300 uppercase">
                          {mode}
                        </span>
                      </div>
                    </div>
                    <div className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono text-[11px] text-white/75">
                      <span>Depth:</span>
                      <span className="text-right text-cyan-200 font-semibold">{hoverPos.depthM} m</span>
                      <span>Distance:</span>
                      <span className="text-right text-white font-semibold">{hoverPos.distKm} km</span>
                      <span>Position:</span>
                      <span className="text-right text-white/60">
                        {hoverPos.lat}°N, {hoverPos.lon}°E
                      </span>
                      {showD20 && (
                        <>
                          <span className="flex items-center gap-1 text-cyan-300/90">
                            <span className="inline-block size-1.5 rounded-full bg-cyan-400" />
                            D20 Isotherm:
                          </span>
                          <span className="text-right text-cyan-200 font-semibold">{hoverPos.localD20} m</span>
                        </>
                      )}
                      {showMLD && (
                        <>
                          <span className="flex items-center gap-1 text-white/90">
                            <span className="inline-block h-0.5 w-2 bg-white" />
                            MLD Mixed Layer:
                          </span>
                          <span className="text-right text-white font-semibold">{hoverPos.localMLD} m</span>
                        </>
                      )}
                    </div>
                  </div>
                );
              })()}
            </>
          )}
        </div>
      </div>

      {/* X-Axis: Distance & Lat/Lon Ticks */}
      <div className="relative ml-14 sm:ml-16 h-8 text-xs font-mono text-white/50">
        {distanceTicks.map((tick, idx) => (
          <div
            key={idx}
            className="absolute -translate-x-1/2 flex flex-col items-center"
            style={{ left: `${(tick.normX * 100).toFixed(2)}%` }}
          >
            <span className="h-1.5 w-px bg-white/30" />
            <span className="mt-0.5 text-[10px] text-neutral-300 font-medium whitespace-nowrap">
              {tick.label}
            </span>
          </div>
        ))}
      </div>

      {/* Color Bar Legend */}
      <div className="flex flex-col gap-2 pt-3 border-t border-white/10 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 text-xs font-mono text-neutral-300">
          <span className="font-semibold text-white">{scaleInfo.title}:</span>
        </div>

        {/* Color Ramp */}
        <div className="flex flex-1 sm:max-w-md items-center gap-3">
          <span className="font-mono text-[11px] text-neutral-400">{scaleInfo.min}</span>
          <div
            className={`h-3.5 flex-1 rounded-full border border-white/20 bg-gradient-to-r ${scaleInfo.gradient}`}
          />
          <span className="font-mono text-[11px] text-neutral-400">{scaleInfo.max}</span>
        </div>
      </div>
    </div>
  );
}
