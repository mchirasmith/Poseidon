"use client";

import { useCallback, useRef, useState, useMemo } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Moon, Move, Navigation, Satellite, Sliders, Waves } from "lucide-react";
import { OCEAN_DEPTHS_M } from "@/lib/depths";
import {
  TRANSECT_PRESETS,
  type TransectCoordinate,
  type TransectPreset,
} from "@/lib/section";

interface TransectMapProps {
  a: TransectCoordinate;
  b: TransectCoordinate;
  depthM: number;
  totalDistanceKm: number;
  onCoordinatesChange: (a: TransectCoordinate, b: TransectCoordinate) => void;
  onDepthChange: (depth: number) => void;
  onPresetSelect?: (preset: TransectPreset) => void;
}

type BasemapType = "bathymetry" | "satellite" | "dark";

const BASEMAPS: { id: BasemapType; label: string; icon: typeof Waves }[] = [
  { id: "bathymetry", label: "Ocean Bathymetry", icon: Waves },
  { id: "satellite", label: "Satellite Earth", icon: Satellite },
  { id: "dark", label: "Dark Tactical", icon: Moon },
];

// Precision Web Mercator Projection for the North Indian Ocean
// Bounding box: 45°E - 105°E, 4°N - 30°N
const SVG_WIDTH = 960;
const SVG_HEIGHT = 440;
const ZOOM = 5;
const WORLD_SIZE = 256 * (1 << ZOOM);

function lon2px(lon: number): number {
  return ((lon + 180.0) / 360.0) * WORLD_SIZE;
}

function lat2px(lat: number): number {
  const latRad = (lat * Math.PI) / 180.0;
  return (
    ((1.0 - Math.log(Math.tan(latRad) + 1.0 / Math.cos(latRad)) / Math.PI) / 2.0) *
    WORLD_SIZE
  );
}

function px2lon(px: number): number {
  return (px / WORLD_SIZE) * 360.0 - 180.0;
}

function py2lat(py: number): number {
  const n = Math.PI - (2.0 * Math.PI * py) / WORLD_SIZE;
  return (Math.atan(Math.sinh(n)) * 180.0) / Math.PI;
}

const X_MIN = lon2px(45.0);
const X_MAX = lon2px(105.0);
const Y_MIN = lat2px(30.0);
const Y_MAX = lat2px(4.0);

function coord2svg(lat: number, lon: number): { x: number; y: number } {
  const x = ((lon2px(lon) - X_MIN) / (X_MAX - X_MIN)) * SVG_WIDTH;
  const y = ((lat2px(lat) - Y_MIN) / (Y_MAX - Y_MIN)) * SVG_HEIGHT;
  return { x, y };
}

function svg2coord(x: number, y: number): TransectCoordinate {
  const worldX = X_MIN + (x / SVG_WIDTH) * (X_MAX - X_MIN);
  const worldY = Y_MIN + (y / SVG_HEIGHT) * (Y_MAX - Y_MIN);
  const lat = Math.max(4.0, Math.min(30.0, Number(py2lat(worldY).toFixed(2))));
  const lon = Math.max(45.0, Math.min(105.0, Number(px2lon(worldX).toFixed(2))));
  return { lat, lon };
}

// Extended Web Mercator tile coverage for North Indian Ocean at Zoom 5 (covers 33°E-112°E, -4°S-37°N)
const TILE_X_START = 19;
const TILE_X_END = 26;
const TILE_Y_START = 12;
const TILE_Y_END = 16;

interface TileInfo {
  tx: number;
  ty: number;
  x: number;
  y: number;
  w: number;
  h: number;
}

const TILES: TileInfo[] = [];
for (let ty = TILE_Y_START; ty <= TILE_Y_END; ty++) {
  for (let tx = TILE_X_START; tx <= TILE_X_END; tx++) {
    TILES.push({
      tx,
      ty,
      x: ((tx * 256 - X_MIN) / (X_MAX - X_MIN)) * SVG_WIDTH,
      y: ((ty * 256 - Y_MIN) / (Y_MAX - Y_MIN)) * SVG_HEIGHT,
      w: (256.0 / (X_MAX - X_MIN)) * SVG_WIDTH,
      h: (256.0 / (Y_MAX - Y_MIN)) * SVG_HEIGHT,
    });
  }
}

function getTileUrl(tx: number, ty: number, basemap: BasemapType): string {
  switch (basemap) {
    case "bathymetry":
      return `https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/5/${ty}/${tx}`;
    case "satellite":
      return `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/5/${ty}/${tx}`;
    case "dark":
      return `https://a.basemaps.cartocdn.com/dark_all/5/${tx}/${ty}.png`;
  }
}

export function TransectMap({
  a,
  b,
  depthM,
  totalDistanceKm,
  onCoordinatesChange,
  onDepthChange,
  onPresetSelect,
}: TransectMapProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [activeHandle, setActiveHandle] = useState<"A" | "B" | null>(null);
  const [basemap, setBasemap] = useState<BasemapType>("bathymetry");
  const prefersReducedMotion = useReducedMotion();
  const [cursorPos, setCursorPos] = useState<TransectCoordinate | null>(null);

  const { x: ax, y: ay } = coord2svg(a.lat, a.lon);
  const { x: bx, y: by } = coord2svg(b.lat, b.lon);

  // Check if current line matches any preset
  const matchedPreset = TRANSECT_PRESETS.find(
    (p) =>
      Math.abs(p.a.lat - a.lat) < 0.25 &&
      Math.abs(p.a.lon - a.lon) < 0.25 &&
      Math.abs(p.b.lat - b.lat) < 0.25 &&
      Math.abs(p.b.lon - b.lon) < 0.25
  );

  const applyPreset = (preset: TransectPreset) => {
    if (onPresetSelect) {
      onPresetSelect(preset);
    } else {
      onCoordinatesChange(preset.a, preset.b);
    }
  };

  const handlePointerDown = (handle: "A" | "B", e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setActiveHandle(handle);
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<SVGSVGElement>) => {
      if (!svgRef.current) return;
      const rect = svgRef.current.getBoundingClientRect();
      const clientX = e.clientX - rect.left;
      const clientY = e.clientY - rect.top;

      const scaleX = SVG_WIDTH / rect.width;
      const scaleY = SVG_HEIGHT / rect.height;

      const svgX = clientX * scaleX;
      const svgY = clientY * scaleY;

      const coord = svg2coord(svgX, svgY);
      setCursorPos(coord);

      if (!activeHandle) return;

      if (activeHandle === "A") {
        onCoordinatesChange(coord, b);
      } else {
        onCoordinatesChange(a, coord);
      }
    },
    [activeHandle, a, b, onCoordinatesChange]
  );

  const handlePointerUp = (e: React.PointerEvent) => {
    if (activeHandle) {
      setActiveHandle(null);
      (e.target as HTMLElement).releasePointerCapture?.(e.pointerId);
    }
  };

  const handlePointerLeave = () => {
    setCursorPos(null);
  };

  // Graticule ticks
  const latTicks = [5, 10, 15, 20, 25];
  const lonTicks = [50, 60, 70, 80, 90, 100];

  // Intermediate waypoints along transect (every 10%)
  const waypoints = useMemo(() => {
    const pts: { x: number; y: number }[] = [];
    for (let f = 0.1; f < 0.95; f += 0.1) {
      pts.push({
        x: ax + f * (bx - ax),
        y: ay + f * (by - ay),
      });
    }
    return pts;
  }, [ax, ay, bx, by]);

  return (
    <div className="space-y-3.5">
      {/* Top Map Action Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-white/10">
        {/* Left: Transect Line readout */}
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs uppercase tracking-wider text-cyan-200">
            Transect Line:
          </span>
          <span className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 font-mono text-[11px] text-cyan-300 shadow-[inset_0_1px_1px_rgba(255,255,255,0.2)]">
            A ({a.lat}°N, {a.lon}°E) → B ({b.lat}°N, {b.lon}°E) · {totalDistanceKm} km
          </span>
        </div>

        {/* Right: Map Type Switcher & Presets */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Basemap Style Switcher: Compact Limelight Navbar */}
          <div
            role="tablist"
            aria-label="Basemap styles"
            className="relative inline-flex items-center gap-0.5 rounded-xl border border-white/15 bg-slate-950/70 p-1 shadow-[0_8px_20px_rgba(0,0,0,0.35),inset_0_1px_0_rgba(255,255,255,0.16)] backdrop-blur-xl"
          >
            {BASEMAPS.map((item) => {
              const Icon = item.icon;
              const isActive = basemap === item.id;
              return (
                <div key={item.id} className="relative group/tooltip flex items-center justify-center">
                  <button
                    type="button"
                    role="tab"
                    onClick={() => setBasemap(item.id)}
                    aria-label={item.label}
                    aria-selected={isActive}
                    className="relative z-10 grid size-8.5 sm:size-9 place-items-center rounded-lg transition-colors outline-none focus-visible:ring-2 focus-visible:ring-white/50"
                  >
                    {isActive && (
                      <motion.span
                        aria-hidden="true"
                        className="pointer-events-none absolute inset-x-1 top-0 h-0.5 rounded-full bg-white shadow-[0_8px_16px_rgba(255,255,255,0.95)]"
                        layoutId="basemap-limelight-beam"
                        transition={
                          prefersReducedMotion
                            ? { duration: 0 }
                            : { type: "spring", stiffness: 380, damping: 30 }
                        }
                      >
                        <span className="absolute left-[-30%] top-0.5 h-7 w-[160%] bg-gradient-to-b from-white/35 via-white/10 to-transparent [clip-path:polygon(10%_100%,28%_0,72%_0,90%_100%)]" />
                      </motion.span>
                    )}
                    <Icon
                      size={17}
                      className={
                        isActive
                          ? "text-white drop-shadow-[0_0_8px_rgba(255,255,255,0.85)]"
                          : "text-white/50 transition-colors hover:text-white/80"
                      }
                      strokeWidth={isActive ? 2.2 : 1.8}
                    />
                    <span className="sr-only">{item.label}</span>
                  </button>

                  {/* Instant floating hover tooltip */}
                  <div className="pointer-events-none absolute bottom-full mb-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-lg border border-white/20 bg-slate-950/95 px-2.5 py-1 text-[11px] font-mono font-semibold text-white opacity-0 shadow-[0_8px_20px_rgba(0,0,0,0.5)] backdrop-blur-xl transition-all duration-150 group-hover/tooltip:opacity-100 group-hover/tooltip:-translate-y-0.5 z-40">
                    <span>{item.label}</span>
                    <div className="absolute left-1/2 -bottom-1 -translate-x-1/2 size-2 rotate-45 border-b border-r border-white/20 bg-slate-950" />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Presets dropdown */}
          <div className="flex items-center gap-1.5 rounded-xl border border-white/15 bg-white/[0.04] px-2.5 py-1 text-xs shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)] backdrop-blur-md">
            <Sliders size={13} className="text-cyan-300" />
            <span className="font-mono text-white/50 text-[11px]">Preset:</span>
            <select
              aria-label="Oceanographic transect preset"
              value={matchedPreset?.id || ""}
              onChange={(e) => {
                const p = TRANSECT_PRESETS.find((preset) => preset.id === e.target.value);
                if (p) applyPreset(p);
              }}
              className="bg-transparent font-mono text-xs text-white focus:outline-none cursor-pointer"
            >
              <option value="" disabled className="bg-slate-900">
                Oceanographic Presets...
              </option>
              {TRANSECT_PRESETS.map((preset) => (
                <option key={preset.id} value={preset.id} className="bg-slate-900 text-white">
                  {preset.name}
                </option>
              ))}
            </select>
          </div>

          {/* Depth map level */}
          <div className="flex items-center gap-1.5 rounded-xl border border-white/15 bg-white/[0.04] px-2.5 py-1 text-xs shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)] backdrop-blur-md">
            <Navigation size={13} className="text-cyan-300" />
            <span className="font-mono text-white/50 text-[11px]">Depth:</span>
            <select
              aria-label="Map slice depth"
              value={depthM}
              onChange={(e) => onDepthChange(Number(e.target.value))}
              className="bg-transparent font-mono text-xs font-semibold text-cyan-200 focus:outline-none cursor-pointer"
            >
              {OCEAN_DEPTHS_M.map((d) => (
                <option key={d} value={d} className="bg-slate-900 text-white">
                  {d} m {d === 100 ? "(D20)" : d === 20 ? "(MLD)" : ""}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Interactive Real Map Stage */}
      <div className="relative w-full aspect-[960/440] min-h-[360px] sm:min-h-[420px] select-none overflow-hidden rounded-2xl border border-white/15 bg-[#030914] shadow-[0_16px_36px_rgba(0,0,0,0.5),inset_0_1px_1px_rgba(255,255,255,0.15)]">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
          preserveAspectRatio="none"
          className="w-full h-full cursor-crosshair block"
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerLeave={handlePointerLeave}
        >
          <defs>
            {/* Ambient oceanic bathymetry backdrop gradient */}
            <radialGradient id="bathymetryGlow" cx="65%" cy="55%" r="65%">
              <stop offset="0%" stopColor="#0c2d48" stopOpacity="0.8" />
              <stop offset="35%" stopColor="#081f38" stopOpacity="0.9" />
              <stop offset="70%" stopColor="#041226" stopOpacity="0.95" />
              <stop offset="100%" stopColor="#020617" stopOpacity="1" />
            </radialGradient>

            {/* Glowing neon transect beam filter */}
            <filter id="transectGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="blur1" />
              <feGaussianBlur stdDeviation="2" result="blur2" />
              <feMerge>
                <feMergeNode in="blur1" />
                <feMergeNode in="blur2" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            {/* Subtle drop shadow for handles */}
            <filter id="pinShadow" x="-30%" y="-30%" width="160%" height="160%">
              <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#000000" floodOpacity="0.8" />
            </filter>
          </defs>

          {/* Fallback Deep Water Fill */}
          <rect width={SVG_WIDTH} height={SVG_HEIGHT} fill="url(#bathymetryGlow)" />

          {/* Real Map Tiles Layer (Web Mercator at Zoom 5) */}
          <g className="map-tiles" opacity={basemap === "satellite" ? 0.95 : 0.9}>
            {TILES.map((t) => (
              <image
                key={`${basemap}-${t.tx}-${t.ty}`}
                href={getTileUrl(t.tx, t.ty, basemap)}
                x={t.x}
                y={t.y}
                width={t.w + 0.6}
                height={t.h + 0.6}
                preserveAspectRatio="none"
              />
            ))}
          </g>

          {/* Atmospheric / Nautical Vignette for Real Depth Feeling */}
          <rect
            width={SVG_WIDTH}
            height={SVG_HEIGHT}
            fill="none"
            stroke="rgba(0,0,0,0.3)"
            strokeWidth="2"
          />

          {/* Graticule Grid Lines & Labels */}
          {latTicks.map((lat) => {
            const { y } = coord2svg(lat, 45);
            return (
              <g key={`lat-${lat}`}>
                <line
                  x1={0}
                  y1={y}
                  x2={SVG_WIDTH}
                  y2={y}
                  stroke="rgba(255,255,255,0.12)"
                  strokeDasharray="3 4"
                  strokeWidth="0.8"
                />
                <text
                  x={12}
                  y={y - 4}
                  fill="rgba(255,255,255,0.55)"
                  fontSize="10"
                  fontFamily="monospace"
                  fontWeight="600"
                >
                  {lat}°N
                </text>
              </g>
            );
          })}

          {lonTicks.map((lon) => {
            const { x } = coord2svg(4, lon);
            return (
              <g key={`lon-${lon}`}>
                <line
                  x1={x}
                  y1={0}
                  x2={x}
                  y2={SVG_HEIGHT}
                  stroke="rgba(255,255,255,0.12)"
                  strokeDasharray="3 4"
                  strokeWidth="0.8"
                />
                <text
                  x={x + 4}
                  y={SVG_HEIGHT - 10}
                  fill="rgba(255,255,255,0.55)"
                  fontSize="10"
                  fontFamily="monospace"
                  fontWeight="600"
                >
                  {lon}°E
                </text>
              </g>
            );
          })}

          {/* Ocean Basin Typographic Watermarks */}
          <text
            x={coord2svg(16, 64).x}
            y={coord2svg(16, 64).y}
            fill="rgba(255,255,255,0.35)"
            fontSize="14"
            fontWeight="bold"
            letterSpacing="0.25em"
            textAnchor="middle"
            fontFamily="monospace"
            style={{ textShadow: "0 2px 8px rgba(0,0,0,0.8)" }}
          >
            ARABIAN SEA
          </text>
          <text
            x={coord2svg(15, 89).x}
            y={coord2svg(15, 89).y}
            fill="rgba(255,255,255,0.35)"
            fontSize="14"
            fontWeight="bold"
            letterSpacing="0.25em"
            textAnchor="middle"
            fontFamily="monospace"
            style={{ textShadow: "0 2px 8px rgba(0,0,0,0.8)" }}
          >
            BAY OF BENGAL
          </text>
          <text
            x={coord2svg(6.5, 77).x}
            y={coord2svg(6.5, 77).y}
            fill="rgba(255,255,255,0.28)"
            fontSize="12"
            letterSpacing="0.3em"
            textAnchor="middle"
            fontFamily="monospace"
            style={{ textShadow: "0 2px 8px rgba(0,0,0,0.8)" }}
          >
            EQUATORIAL INDIAN OCEAN
          </text>
          <text
            x={coord2svg(11.5, 96).x}
            y={coord2svg(11.5, 96).y}
            fill="rgba(255,255,255,0.22)"
            fontSize="10"
            letterSpacing="0.2em"
            textAnchor="middle"
            fontFamily="monospace"
            style={{ textShadow: "0 2px 6px rgba(0,0,0,0.8)" }}
          >
            ANDAMAN SEA
          </text>

          {/* Great-Circle Transect Line A -> B */}
          {/* Luminous Glow Outer Beam */}
          <line
            x1={ax}
            y1={ay}
            x2={bx}
            y2={by}
            stroke="#22d3ee"
            strokeWidth="6"
            opacity="0.5"
            filter="url(#transectGlow)"
          />

          {/* Sharp Core Dashed Navigation Line */}
          <line
            x1={ax}
            y1={ay}
            x2={bx}
            y2={by}
            stroke="#ffffff"
            strokeWidth="2.2"
            strokeDasharray="6 3"
            strokeLinecap="round"
          />

          {/* Intermediate Sampling Waypoints along the transect line */}
          {waypoints.map((pt, idx) => (
            <circle
              key={`waypoint-${idx}`}
              cx={pt.x}
              cy={pt.y}
              r="2"
              fill="#22d3ee"
              stroke="#ffffff"
              strokeWidth="0.8"
              opacity="0.85"
            />
          ))}

          {/* Midpoint Distance Badge */}
          <g transform={`translate(${(ax + bx) / 2}, ${(ay + by) / 2 - 16})`}>
            <rect
              x="-48"
              y="-12"
              width="96"
              height="24"
              rx="7"
              fill="rgba(2, 6, 23, 0.92)"
              stroke="#38bdf8"
              strokeWidth="1.2"
              filter="url(#pinShadow)"
            />
            <text
              x="0"
              y="4"
              textAnchor="middle"
              fill="#ffffff"
              fontSize="11"
              fontWeight="bold"
              fontFamily="monospace"
            >
              {totalDistanceKm} km
            </text>
          </g>

          {/* Endpoint A Handle (Cyan Theme) */}
          <g
            className="cursor-grab active:cursor-grabbing transition-transform duration-75"
            transform={`translate(${ax}, ${ay})`}
            onPointerDown={(e) => handlePointerDown("A", e)}
            filter="url(#pinShadow)"
          >
            {/* Pulsing Target Halo */}
            <circle r="18" fill="rgba(34, 211, 238, 0.25)" className="animate-pulse" />
            <circle r="10" fill="#06b6d4" stroke="#ffffff" strokeWidth="2.5" />
            <text
              x="0"
              y="3.5"
              textAnchor="middle"
              fill="#ffffff"
              fontSize="10"
              fontWeight="bold"
              fontFamily="sans-serif"
            >
              A
            </text>
            {/* Coordinate Callout Tag */}
            <g transform="translate(14, -14)">
              <rect
                x="0"
                y="0"
                width="94"
                height="22"
                rx="6"
                fill="rgba(6, 44, 66, 0.94)"
                stroke="#22d3ee"
                strokeWidth="1.2"
              />
              <text x="7" y="15" fill="#e0f2fe" fontSize="9.5" fontFamily="monospace" fontWeight="600">
                A: {a.lat}°N, {a.lon}°E
              </text>
            </g>
          </g>

          {/* Endpoint B Handle (Rose/Coral Theme) */}
          <g
            className="cursor-grab active:cursor-grabbing transition-transform duration-75"
            transform={`translate(${bx}, ${by})`}
            onPointerDown={(e) => handlePointerDown("B", e)}
            filter="url(#pinShadow)"
          >
            {/* Pulsing Target Halo */}
            <circle r="18" fill="rgba(244, 63, 94, 0.25)" className="animate-pulse" />
            <circle r="10" fill="#f43f5e" stroke="#ffffff" strokeWidth="2.5" />
            <text
              x="0"
              y="3.5"
              textAnchor="middle"
              fill="#ffffff"
              fontSize="10"
              fontWeight="bold"
              fontFamily="sans-serif"
            >
              B
            </text>
            {/* Coordinate Callout Tag */}
            <g transform="translate(14, -14)">
              <rect
                x="0"
                y="0"
                width="94"
                height="22"
                rx="6"
                fill="rgba(76, 5, 25, 0.94)"
                stroke="#fda4af"
                strokeWidth="1.2"
              />
              <text x="7" y="15" fill="#ffe4e6" fontSize="9.5" fontFamily="monospace" fontWeight="600">
                B: {b.lat}°N, {b.lon}°E
              </text>
            </g>
          </g>
        </svg>

        {/* Nautical Compass Rose (Top Right) */}
        <div className="pointer-events-none absolute top-3 right-3 flex flex-col items-center rounded-xl border border-white/15 bg-slate-950/80 p-2 shadow-xl backdrop-blur-md">
          <div className="relative flex items-center justify-center size-7 rounded-full border border-white/20">
            <span className="font-mono text-[10px] font-bold text-cyan-200 -mt-0.5">N</span>
            <div className="absolute top-1 size-1 bg-cyan-400 rounded-full" />
          </div>
          <span className="mt-1 font-mono text-[8px] uppercase tracking-widest text-white/45">COMPASS</span>
        </div>

        {/* Distance Scale Bar & Real-time Cursor Coordinates (Bottom Left) */}
        <div className="pointer-events-none absolute bottom-3 left-3 flex items-center gap-3 rounded-xl border border-white/15 bg-slate-950/85 px-3 py-1.5 text-[10px] font-mono text-white/80 shadow-xl backdrop-blur-md">
          <div className="flex flex-col gap-0.5">
            <div className="flex justify-between text-[8px] text-white/50">
              <span>0</span>
              <span>250</span>
              <span>500 km</span>
            </div>
            <div className="h-1.5 w-24 rounded-full bg-white/20 overflow-hidden flex border border-white/30">
              <div className="h-full w-1/2 bg-white" />
              <div className="h-full w-1/2 bg-white/40" />
            </div>
          </div>

          {cursorPos && (
            <div className="border-l border-white/15 pl-2.5 flex items-center gap-1.5 text-cyan-200 font-semibold">
              <Move size={11} className="text-cyan-400" />
              <span>
                {cursorPos.lat}°N, {cursorPos.lon}°E
              </span>
            </div>
          )}
        </div>

        {/* Instructions Pill (Bottom Right) */}
        <div className="pointer-events-none absolute bottom-3 right-3 hidden rounded-xl border border-white/15 bg-slate-950/85 px-3 py-1.5 text-[10px] font-mono text-cyan-200/80 shadow-xl backdrop-blur-md sm:flex items-center gap-1.5">
          <Move size={12} className="text-cyan-300" />
          <span>Drag handles A or B to reposition ocean transect</span>
        </div>
      </div>
    </div>
  );
}

