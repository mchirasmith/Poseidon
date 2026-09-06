"use client";

import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";
import { OCEAN_DEPTHS_M, OCEAN_LAYER_COUNT } from "@/lib/depths";

const INITIAL_LAYER_INDEX = 7;
const MAX_BLURRED_SHALLOW_LAYERS = 9;

function getLayerAppearance(index: number, selectedIndex: number) {
  const relativeIndex = index - selectedIndex;

  if (relativeIndex < -MAX_BLURRED_SHALLOW_LAYERS) {
    return { blur: 0, hidden: true, opacity: 0, y: 0, z: 0 };
  }

  if (relativeIndex < 0) {
    const distance = Math.abs(relativeIndex);
    return {
      hidden: false,
      blur: Math.min(3.7, 0.5 + (distance - 1) * 0.4),
      opacity: 0.92,
      y: -distance * 19,
      z: distance * 24,
    };
  }

  if (relativeIndex > 0) {
    return {
      hidden: false,
      blur: 0,
      opacity: 0.92,
      y: relativeIndex * 19,
      z: -relativeIndex * 24,
    };
  }

  return { blur: 0, hidden: false, opacity: 1, y: 0, z: 18 };
}

export function OceanLayerExplorer() {
  const [selectedIndex, setSelectedIndex] = useState(INITIAL_LAYER_INDEX);
  const prefersReducedMotion = useReducedMotion();
  const layerButtonsRef = useRef<Array<HTMLButtonElement | null>>([]);

  const selectLayer = (index: number) => {
    setSelectedIndex(Math.min(Math.max(index, 0), OCEAN_LAYER_COUNT - 1));
  };

  useEffect(() => {
    layerButtonsRef.current[selectedIndex]?.scrollIntoView({
      behavior: prefersReducedMotion ? "auto" : "smooth",
      block: "nearest",
      inline: "center",
    });
  }, [prefersReducedMotion, selectedIndex]);

  const selectedDepth = OCEAN_DEPTHS_M[selectedIndex];

  return (
    <section aria-labelledby="depth-stack-title" className="mt-6 rounded-[28px] border border-white/20 bg-neutral-950/70 p-4 shadow-[inset_0_1px_1px_rgba(255,255,255,0.24),0_18px_48px_rgba(0,0,0,0.38)] backdrop-blur-2xl sm:p-6">
      <div className="flex flex-col gap-3 border-b border-white/15 pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-cyan-200/80">Interactive visual scaffold</p>
          <h2 id="depth-stack-title" className="mt-1 text-xl font-semibold tracking-tight sm:text-2xl">15-layer depth stack</h2>
        </div>
        <p className="max-w-sm text-sm leading-relaxed text-white/65">No model run or scientific data is connected. Planes only show the navigation structure for the approved depth axis.</p>
      </div>

      <div className="relative mt-5 min-h-[22rem] overflow-hidden rounded-2xl border border-cyan-100/15 bg-slate-950/45 sm:min-h-[28rem] lg:min-h-[34rem]" style={{ perspective: "1200px" }}>
        <div aria-hidden="true" className="absolute inset-0 bg-[radial-gradient(circle_at_50%_36%,rgba(34,211,238,0.15),transparent_46%)]" />
        <div aria-hidden="true" className="absolute inset-x-5 top-4 flex justify-between font-mono text-[10px] uppercase tracking-[0.16em] text-cyan-100/50 sm:inset-x-8 sm:top-7"><span>surface · 0 m</span><span>bottom · 1000 m</span></div>
        <div aria-hidden="true" className="absolute left-1/2 top-[47%] h-48 w-[80%] max-w-3xl" style={{ transformStyle: "preserve-3d" }}>
          {OCEAN_DEPTHS_M.map((depth, index) => {
            const appearance = getLayerAppearance(index, selectedIndex);
            const isSelected = index === selectedIndex;

            return (
              <div
                key={depth}
                className="absolute left-1/2 top-1/2 h-28 w-full -translate-x-1/2 rounded-xl border transition-[transform,opacity,filter,border-color,box-shadow] duration-500 motion-reduce:transition-none sm:h-36"
                style={{
                  borderColor: isSelected ? "rgba(103, 232, 249, 0.95)" : "rgba(186, 230, 253, 0.28)",
                  boxShadow: isSelected ? "0 0 0 2px rgba(34, 211, 238, 0.28), 0 0 32px rgba(34, 211, 238, 0.22)" : "none",
                  filter: appearance.blur ? `blur(${appearance.blur}px)` : undefined,
                  opacity: appearance.opacity,
                  pointerEvents: "none",
                  transform: `translateX(-50%) translateY(${appearance.y}px) translateZ(${appearance.z}px) rotateX(58deg) rotateZ(-26deg)`,
                  visibility: appearance.hidden ? "hidden" : "visible",
                }}
              >
                <div className="absolute inset-0 rounded-[inherit] bg-[linear-gradient(rgba(186,230,253,0.14)_1px,transparent_1px),linear-gradient(90deg,rgba(186,230,253,0.14)_1px,transparent_1px)] bg-[size:24px_24px]" />
                <span className="absolute right-3 top-2 rounded bg-slate-950/70 px-2 py-1 font-mono text-[10px] text-cyan-50">{depth} m</span>
              </div>
            );
          })}
        </div>
        <div className="absolute inset-x-4 bottom-4 rounded-xl border border-cyan-100/15 bg-slate-950/75 px-3 py-2 text-xs text-cyan-50/80 backdrop-blur-md sm:inset-x-6 sm:bottom-6"><span className="font-semibold text-cyan-100">Layer {selectedIndex + 1}</span> · {selectedDepth} m · selected plane</div>
      </div>

      <div className="mt-5 rounded-2xl border border-white/15 bg-black/20 p-4">
        <div className="flex items-baseline justify-between gap-4"><label className="font-medium text-white" htmlFor="depth-slider">Selected depth</label><output className="font-mono text-sm text-cyan-100" htmlFor="depth-slider">Layer {selectedIndex + 1} · {selectedDepth} m</output></div>
        <input
          id="depth-slider"
          aria-describedby="depth-selection-status"
          aria-label="Selected ocean depth layer"
          aria-valuetext={`Layer ${selectedIndex + 1} of ${OCEAN_LAYER_COUNT}, ${selectedDepth} metres`}
          className="mt-4 h-3 w-full cursor-pointer accent-cyan-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200 focus-visible:ring-offset-4 focus-visible:ring-offset-slate-950"
          max={OCEAN_LAYER_COUNT - 1}
          min={0}
          onChange={(event) => selectLayer(Number(event.target.value))}
          onKeyDown={(event) => {
            if (event.key === "Home") { event.preventDefault(); selectLayer(0); }
            if (event.key === "End") { event.preventDefault(); selectLayer(OCEAN_LAYER_COUNT - 1); }
          }}
          step={1}
          type="range"
          value={selectedIndex}
        />
        <p id="depth-selection-status" className="sr-only" role="status">Layer {selectedIndex + 1} of {OCEAN_LAYER_COUNT}, {selectedDepth} metres selected. Visual scaffold; no data connected.</p>
      </div>

      <div aria-label="Ocean depth layer rail" className="mt-4 flex snap-x snap-mandatory gap-2 overflow-x-auto pb-2 [scrollbar-width:thin]">
        {OCEAN_DEPTHS_M.map((depth, index) => {
          const isSelected = index === selectedIndex;
          return (
            <button
              key={depth}
              ref={(element) => { layerButtonsRef.current[index] = element; }}
              aria-pressed={isSelected}
              className={`snap-center shrink-0 rounded-xl border px-3 py-2 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 ${isSelected ? "border-cyan-100/70 bg-cyan-300/20 text-cyan-50" : "border-white/15 bg-white/5 text-white/70 hover:bg-white/10"}`}
              type="button"
              onClick={() => selectLayer(index)}
            >
              <span className="block font-mono text-[10px] uppercase tracking-wide opacity-70">Layer {index + 1}</span>
              <span className="mt-0.5 block text-sm font-semibold">{depth} m</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
