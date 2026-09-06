"use client";

import { useCallback, useRef, useState } from "react";
import { Move, Navigation, Sliders } from "lucide-react";
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
}

// Map projection settings (Equirectangular)
const LON_MIN = 45.0;
const LON_MAX = 105.0;
const LAT_MIN = 4.0;
const LAT_MAX = 30.0;
const SVG_WIDTH = 900;
const SVG_HEIGHT = 440;

function lonToX(lon: number): number {
  return ((lon - LON_MIN) / (LON_MAX - LON_MIN)) * SVG_WIDTH;
}

function latToY(lat: number): number {
  return ((LAT_MAX - lat) / (LAT_MAX - LAT_MIN)) * SVG_HEIGHT;
}

function xToLon(x: number): number {
  const lon = LON_MIN + (x / SVG_WIDTH) * (LON_MAX - LON_MIN);
  return Math.max(LON_MIN + 1, Math.min(LON_MAX - 1, Number(lon.toFixed(2))));
}

function yToLat(y: number): number {
  const lat = LAT_MAX - (y / SVG_HEIGHT) * (LAT_MAX - LAT_MIN);
  return Math.max(LAT_MIN + 1, Math.min(LAT_MAX - 1, Number(lat.toFixed(2))));
}

export function TransectMap({
  a,
  b,
  depthM,
  totalDistanceKm,
  onCoordinatesChange,
  onDepthChange,
}: TransectMapProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [activeHandle, setActiveHandle] = useState<"A" | "B" | null>(null);

  const ax = lonToX(a.lon);
  const ay = latToY(a.lat);
  const bx = lonToX(b.lon);
  const by = latToY(b.lat);

  // Check if current line matches any preset
  const matchedPreset = TRANSECT_PRESETS.find(
    (p) =>
      Math.abs(p.a.lat - a.lat) < 0.2 &&
      Math.abs(p.a.lon - a.lon) < 0.2 &&
      Math.abs(p.b.lat - b.lat) < 0.2 &&
      Math.abs(p.b.lon - b.lon) < 0.2
  );

  const applyPreset = (preset: TransectPreset) => {
    onCoordinatesChange(preset.a, preset.b);
  };

  const handlePointerDown = (handle: "A" | "B", e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setActiveHandle(handle);
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<SVGSVGElement>) => {
      if (!activeHandle || !svgRef.current) return;
      const rect = svgRef.current.getBoundingClientRect();
      const clientX = e.clientX - rect.left;
      const clientY = e.clientY - rect.top;

      const scaleX = SVG_WIDTH / rect.width;
      const scaleY = SVG_HEIGHT / rect.height;

      const svgX = clientX * scaleX;
      const svgY = clientY * scaleY;

      const newCoord: TransectCoordinate = {
        lon: xToLon(svgX),
        lat: yToLat(svgY),
      };

      if (activeHandle === "A") {
        onCoordinatesChange(newCoord, b);
      } else {
        onCoordinatesChange(a, newCoord);
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

  // Graticule ticks
  const latTicks = [5, 10, 15, 20, 25];
  const lonTicks = [50, 60, 70, 80, 90, 100];

  return (
    <div className="space-y-4">
      {/* Top Map Action Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-white/10">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs uppercase tracking-wider text-cyan-200">
            Transect Line:
          </span>
          <span className="rounded-lg border border-cyan-500/20 bg-cyan-500/10 px-2.5 py-1 font-mono text-[11px] text-cyan-300 shadow-[inset_0_1px_1px_rgba(255,255,255,0.2)]">
            A ({a.lat}°N, {a.lon}°E) → B ({b.lat}°N, {b.lon}°E)
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* Presets dropdown */}
          <div className="flex items-center gap-1.5 rounded-xl border border-white/15 bg-white/[0.04] px-3 py-1.5 text-xs shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)] backdrop-blur-md">
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
          <div className="flex items-center gap-1.5 rounded-xl border border-white/15 bg-white/[0.04] px-3 py-1.5 text-xs shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)] backdrop-blur-md">
            <Navigation size={13} className="text-cyan-300" />
            <span className="font-mono text-white/50 text-[11px]">Depth Slice:</span>
            <select
              aria-label="Map slice depth"
              value={depthM}
              onChange={(e) => onDepthChange(Number(e.target.value))}
              className="bg-transparent font-mono text-xs font-semibold text-cyan-200 focus:outline-none cursor-pointer"
            >
              {OCEAN_DEPTHS_M.map((d) => (
                <option key={d} value={d} className="bg-slate-900 text-white">
                  {d} m {d === 100 ? "(D20 Thermocline)" : d === 20 ? "(MLD Base)" : ""}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* SVG Map Container */}
      <div className="relative w-full select-none overflow-hidden rounded-xl border border-white/15 bg-[#030b18] shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)]">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
          className="w-full h-auto max-h-[360px] cursor-crosshair"
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
        >
          <defs>
            {/* Ambient water gradient */}
            <radialGradient id="waterGlow" cx="65%" cy="60%" r="55%">
              <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0.14" />
              <stop offset="50%" stopColor="#0284c7" stopOpacity="0.06" />
              <stop offset="100%" stopColor="#020617" stopOpacity="0.55" />
            </radialGradient>

            {/* Land pattern */}
            <linearGradient id="landGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#334155" />
              <stop offset="100%" stopColor="#1e293b" />
            </linearGradient>

            {/* Transect line pulse glow */}
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Water background fill */}
          <rect width={SVG_WIDTH} height={SVG_HEIGHT} fill="url(#waterGlow)" />

          {/* Graticule Grid Lines & Labels */}
          {latTicks.map((lat) => {
            const y = latToY(lat);
            return (
              <g key={`lat-${lat}`}>
                <line
                  x1={0}
                  y1={y}
                  x2={SVG_WIDTH}
                  y2={y}
                  stroke="rgba(255,255,255,0.08)"
                  strokeDasharray="2 3"
                />
                <text
                  x={12}
                  y={y - 4}
                  fill="rgba(255,255,255,0.4)"
                  fontSize="10"
                  fontFamily="monospace"
                >
                  {lat}°N
                </text>
              </g>
            );
          })}

          {lonTicks.map((lon) => {
            const x = lonToX(lon);
            return (
              <g key={`lon-${lon}`}>
                <line
                  x1={x}
                  y1={0}
                  x2={x}
                  y2={SVG_HEIGHT}
                  stroke="rgba(255,255,255,0.08)"
                  strokeDasharray="2 3"
                />
                <text
                  x={x + 4}
                  y={SVG_HEIGHT - 8}
                  fill="rgba(255,255,255,0.4)"
                  fontSize="10"
                  fontFamily="monospace"
                >
                  {lon}°E
                </text>
              </g>
            );
          })}

          {/* Basin Name Labels */}
          <text
            x={lonToX(64)}
            y={latToY(16)}
            fill="rgba(255,255,255,0.22)"
            fontSize="14"
            fontWeight="bold"
            letterSpacing="0.25em"
            textAnchor="middle"
            fontFamily="monospace"
          >
            ARABIAN SEA
          </text>
          <text
            x={lonToX(89)}
            y={latToY(15)}
            fill="rgba(255,255,255,0.22)"
            fontSize="14"
            fontWeight="bold"
            letterSpacing="0.25em"
            textAnchor="middle"
            fontFamily="monospace"
          >
            BAY OF BENGAL
          </text>
          <text
            x={lonToX(77)}
            y={latToY(6)}
            fill="rgba(255,255,255,0.18)"
            fontSize="12"
            letterSpacing="0.3em"
            textAnchor="middle"
            fontFamily="monospace"
          >
            EQUATORIAL INDIAN OCEAN
          </text>

          {/* Landmass Outlines */}
          {/* 1. Indian Subcontinent */}
          <polygon
            points={`
              ${lonToX(68.5)},${latToY(23.5)}
              ${lonToX(70.0)},${latToY(21.0)}
              ${lonToX(72.8)},${latToY(19.0)}
              ${lonToX(73.8)},${latToY(15.5)}
              ${lonToX(76.2)},${latToY(10.0)}
              ${lonToX(77.5)},${latToY(8.1)}
              ${lonToX(79.8)},${latToY(10.5)}
              ${lonToX(80.3)},${latToY(13.2)}
              ${lonToX(83.3)},${latToY(17.8)}
              ${lonToX(86.5)},${latToY(20.0)}
              ${lonToX(88.8)},${latToY(21.8)}
              ${lonToX(91.0)},${latToY(22.8)}
              ${lonToX(89.0)},${latToY(26.5)}
              ${lonToX(78.0)},${latToY(30.0)}
              ${lonToX(71.0)},${latToY(26.0)}
              ${lonToX(68.0)},${latToY(24.5)}
            `}
            fill="url(#landGrad)"
            stroke="rgba(255,255,255,0.25)"
            strokeWidth="1.2"
          />

          {/* 2. Sri Lanka */}
          <polygon
            points={`
              ${lonToX(79.8)},${latToY(9.8)}
              ${lonToX(81.8)},${latToY(7.5)}
              ${lonToX(80.5)},${latToY(5.9)}
              ${lonToX(79.6)},${latToY(7.0)}
            `}
            fill="url(#landGrad)"
            stroke="rgba(255,255,255,0.25)"
            strokeWidth="1.2"
          />

          {/* 3. Arabian Peninsula & Middle East */}
          <polygon
            points={`
              ${lonToX(45.0)},${latToY(12.5)}
              ${lonToX(51.0)},${latToY(15.0)}
              ${lonToX(54.0)},${latToY(17.0)}
              ${lonToX(59.5)},${latToY(22.5)}
              ${lonToX(56.5)},${latToY(26.0)}
              ${lonToX(53.0)},${latToY(24.0)}
              ${lonToX(45.0)},${latToY(27.0)}
            `}
            fill="url(#landGrad)"
            stroke="rgba(255,255,255,0.25)"
            strokeWidth="1.2"
          />

          {/* 4. Pakistan & Makran Coast */}
          <polygon
            points={`
              ${lonToX(59.5)},${latToY(25.5)}
              ${lonToX(62.0)},${latToY(25.2)}
              ${lonToX(67.0)},${latToY(24.8)}
              ${lonToX(68.5)},${latToY(24.0)}
              ${lonToX(70.0)},${latToY(30.0)}
              ${lonToX(59.0)},${latToY(30.0)}
            `}
            fill="url(#landGrad)"
            stroke="rgba(255,255,255,0.25)"
            strokeWidth="1.2"
          />

          {/* 5. Myanmar & Malay Peninsula */}
          <polygon
            points={`
              ${lonToX(92.5)},${latToY(21.0)}
              ${lonToX(94.2)},${latToY(16.5)}
              ${lonToX(97.5)},${latToY(16.0)}
              ${lonToX(98.5)},${latToY(10.0)}
              ${lonToX(100.0)},${latToY(5.0)}
              ${lonToX(105.0)},${latToY(5.0)}
              ${lonToX(105.0)},${latToY(30.0)}
              ${lonToX(95.0)},${latToY(30.0)}
            `}
            fill="url(#landGrad)"
            stroke="rgba(255,255,255,0.25)"
            strokeWidth="1.2"
          />

          {/* 6. Andaman & Nicobar Ridge */}
          <ellipse
            cx={lonToX(92.8)}
            cy={latToY(12.0)}
            rx="5"
            ry="20"
            fill="#64748b"
            stroke="rgba(255,255,255,0.3)"
          />
          <ellipse
            cx={lonToX(93.8)}
            cy={latToY(7.5)}
            rx="4"
            ry="14"
            fill="#64748b"
            stroke="rgba(255,255,255,0.3)"
          />

          {/* 7. Maldives Ridge */}
          <line
            x1={lonToX(73.0)}
            y1={latToY(7.5)}
            x2={lonToX(73.5)}
            y2={latToY(4.5)}
            stroke="#94a3b8"
            strokeWidth="2.5"
            strokeDasharray="2 6"
          />

          {/* Great-circle transect line A -> B */}
          <line
            x1={ax}
            y1={ay}
            x2={bx}
            y2={by}
            stroke="#22d3ee"
            strokeWidth="5"
            opacity="0.35"
            filter="url(#glow)"
          />
          <line
            x1={ax}
            y1={ay}
            x2={bx}
            y2={by}
            stroke="#22d3ee"
            strokeWidth="2.5"
            strokeDasharray="6 4"
          />

          {/* Midpoint Distance Badge */}
          <g transform={`translate(${(ax + bx) / 2}, ${(ay + by) / 2 - 14})`}>
            <rect
              x="-44"
              y="-12"
              width="88"
              height="22"
              rx="6"
              fill="rgba(15, 23, 42, 0.9)"
              stroke="#38bdf8"
              strokeWidth="1"
            />
            <text
              x="0"
              y="3"
              textAnchor="middle"
              fill="#bae6fd"
              fontSize="11"
              fontWeight="bold"
              fontFamily="monospace"
            >
              {totalDistanceKm} km
            </text>
          </g>

          {/* Endpoint A Handle */}
          <g
            className="cursor-grab active:cursor-grabbing"
            transform={`translate(${ax}, ${ay})`}
            onPointerDown={(e) => handlePointerDown("A", e)}
          >
            <circle r="18" fill="rgba(34, 211, 238, 0.2)" />
            <circle r="9" fill="#0891b2" stroke="#67e8f9" strokeWidth="2.5" />
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
            <g transform="translate(14, -14)">
              <rect
                x="0"
                y="0"
                width="84"
                height="20"
                rx="5"
                fill="rgba(8, 51, 68, 0.92)"
                stroke="rgba(103, 232, 249, 0.5)"
              />
              <text x="6" y="14" fill="#e0f2fe" fontSize="9" fontFamily="monospace">
                A: {a.lat}°N, {a.lon}°E
              </text>
            </g>
          </g>

          {/* Endpoint B Handle */}
          <g
            className="cursor-grab active:cursor-grabbing"
            transform={`translate(${bx}, ${by})`}
            onPointerDown={(e) => handlePointerDown("B", e)}
          >
            <circle r="18" fill="rgba(244, 63, 94, 0.2)" />
            <circle r="9" fill="#e11d48" stroke="#fda4af" strokeWidth="2.5" />
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
            <g transform="translate(14, -14)">
              <rect
                x="0"
                y="0"
                width="84"
                height="20"
                rx="5"
                fill="rgba(76, 5, 25, 0.92)"
                stroke="rgba(253, 164, 175, 0.5)"
              />
              <text x="6" y="14" fill="#ffe4e6" fontSize="9" fontFamily="monospace">
                B: {b.lat}°N, {b.lon}°E
              </text>
            </g>
          </g>
        </svg>

        {/* Instructions pill */}
        <div className="absolute bottom-2.5 right-3 hidden rounded-lg border border-white/10 bg-slate-950/80 px-2.5 py-1 text-[10px] font-mono text-cyan-200/80 backdrop-blur-md sm:flex items-center gap-1.5">
          <Move size={11} />
          <span>Drag handles A or B to reposition transect</span>
        </div>
      </div>
    </div>
  );
}
