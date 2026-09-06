"use client";

import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { OCEAN_DEPTHS_M, OCEAN_LAYER_COUNT } from "@/lib/depths";

const INITIAL_LAYER_INDEX = 7;
const MAX_BLURRED_SHALLOW_LAYERS = 9;

function clampLayerIndex(index: number) {
  return Math.min(Math.max(index, 0), OCEAN_LAYER_COUNT - 1);
}

function layerIndexFromLocation() {
  const depth = Number(new URLSearchParams(window.location.search).get("z"));
  const index = OCEAN_DEPTHS_M.indexOf(depth as (typeof OCEAN_DEPTHS_M)[number]);
  return index >= 0 ? index : INITIAL_LAYER_INDEX;
}

function getLayerAppearance(index: number, selectedIndex: number) {
  const relativeIndex = index - selectedIndex;

  if (relativeIndex < -MAX_BLURRED_SHALLOW_LAYERS) return { blur: 0, hidden: true, opacity: 0, y: 0, z: 0 };
  if (relativeIndex < 0) {
    const distance = Math.abs(relativeIndex);
    return { blur: Math.min(3.7, 0.5 + (distance - 1) * 0.4), hidden: false, opacity: 0.8, y: -distance * 5, z: distance * 9 };
  }
  if (relativeIndex > 0) return { blur: 0, hidden: false, opacity: 0.76, y: relativeIndex * 5, z: -relativeIndex * 9 };
  return { blur: 0, hidden: false, opacity: 1, y: 0, z: 12 };
}

export function OceanLayerExplorer() {
  const [selectedIndex, setSelectedIndex] = useState(INITIAL_LAYER_INDEX);
  const prefersReducedMotion = useReducedMotion();
  const selectedDepth = OCEAN_DEPTHS_M[selectedIndex];

  useEffect(() => {
    const syncFromLocation = () => setSelectedIndex(layerIndexFromLocation());
    syncFromLocation();
    window.addEventListener("popstate", syncFromLocation);
    return () => window.removeEventListener("popstate", syncFromLocation);
  }, []);

  const selectLayer = (index: number) => {
    const nextIndex = clampLayerIndex(index);
    setSelectedIndex(nextIndex);
    const params = new URLSearchParams(window.location.search);
    params.set("z", String(OCEAN_DEPTHS_M[nextIndex]));
    window.history.pushState(null, "", `${window.location.pathname}?${params.toString()}`);
  };

  return (
    <section aria-labelledby="depth-stack-title" className="mt-6 rounded-[28px] border border-white/20 bg-neutral-950/70 p-4 shadow-[inset_0_1px_1px_rgba(255,255,255,0.24),0_18px_48px_rgba(0,0,0,0.38)] backdrop-blur-2xl sm:p-6">
      <div className="flex flex-col gap-3 border-b border-white/15 pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-cyan-200/80">Interactive visual scaffold</p>
          <h2 id="depth-stack-title" className="mt-1 text-xl font-semibold tracking-tight sm:text-2xl">15-layer depth structure</h2>
        </div>
        <p className="max-w-sm text-sm leading-relaxed text-white/65">No model run or scientific data is connected. This compact volume only provides navigation across the approved depth axis.</p>
      </div>

      <div className="relative mt-5 min-h-[22rem] overflow-hidden rounded-2xl border border-cyan-100/15 bg-slate-950/45 sm:min-h-[28rem] lg:min-h-[34rem]" style={{ perspective: "1200px" }}>
        <div aria-hidden="true" className="absolute inset-0 bg-[radial-gradient(circle_at_50%_36%,rgba(34,211,238,0.15),transparent_46%)]" />
        <div aria-hidden="true" className="absolute inset-x-5 top-4 flex justify-between text-[10px] uppercase tracking-[0.16em] text-cyan-100/50 sm:inset-x-8 sm:top-7"><span>surface · 0 m</span><span>bottom · 1000 m</span></div>
        <div aria-hidden="true" className="absolute left-1/2 top-[47%] h-48 w-[80%] max-w-3xl" style={{ transformStyle: "preserve-3d" }}>
          {OCEAN_DEPTHS_M.map((depth, index) => {
            const appearance = getLayerAppearance(index, selectedIndex);
            const isSelected = index === selectedIndex;
            return (
              <motion.div animate={{ filter: appearance.blur ? `blur(${appearance.blur}px)` : "blur(0px)", opacity: appearance.opacity, x: "-50%", y: appearance.y, z: appearance.z }} className="absolute left-1/2 top-1/2 h-28 w-full" initial={false} key={depth} style={{ pointerEvents: "none", transformStyle: "preserve-3d", visibility: appearance.hidden ? "hidden" : "visible" }} transition={prefersReducedMotion ? { duration: 0 } : { type: "spring", stiffness: 180, damping: 24, mass: 0.7 }}>
                <div className="relative h-full w-full rounded-xl border sm:h-36" style={{ borderColor: isSelected ? "rgba(103, 232, 249, 0.95)" : "rgba(186, 230, 253, 0.28)", boxShadow: isSelected ? "0 0 0 2px rgba(34, 211, 238, 0.28), 0 0 32px rgba(34, 211, 238, 0.22)" : "none", transform: "rotateX(58deg) rotateZ(-26deg)" }}>
                  <div className="absolute inset-0 rounded-[inherit] bg-[linear-gradient(rgba(186,230,253,0.14)_1px,transparent_1px),linear-gradient(90deg,rgba(186,230,253,0.14)_1px,transparent_1px)] bg-[size:24px_24px]" />
                  {isSelected ? <span className="absolute right-3 top-2 rounded bg-slate-950/70 px-2 py-1 text-[10px] text-cyan-50">Layer {index + 1} · {depth} m</span> : null}
                </div>
              </motion.div>
            );
          })}
        </div>
        <div className="absolute inset-x-4 bottom-4 rounded-xl border border-cyan-100/15 bg-slate-950/75 px-3 py-2 text-xs text-cyan-50/80 backdrop-blur-md sm:inset-x-6 sm:bottom-6"><span className="font-semibold text-cyan-100">Layer {selectedIndex + 1}</span> · {selectedDepth} m · selected slice</div>
      </div>

      <div className="mt-5 rounded-2xl border border-white/15 bg-black/20 p-4">
        <div className="flex items-baseline justify-between gap-4"><label className="font-medium text-white" htmlFor="depth-slider">Depth selector</label><output className="text-sm text-cyan-100" htmlFor="depth-slider">Layer {selectedIndex + 1} · {selectedDepth} m</output></div>
        <input id="depth-slider" aria-describedby="depth-selection-status" aria-label="Selected ocean depth layer" aria-valuetext={`Layer ${selectedIndex + 1} of ${OCEAN_LAYER_COUNT}, ${selectedDepth} metres`} className="mt-4 h-3 w-full cursor-pointer accent-cyan-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200 focus-visible:ring-offset-4 focus-visible:ring-offset-slate-950" max={OCEAN_LAYER_COUNT - 1} min={0} onChange={(event) => selectLayer(Number(event.target.value))} onKeyDown={(event) => { if (event.key === "Home") { event.preventDefault(); selectLayer(0); } if (event.key === "End") { event.preventDefault(); selectLayer(OCEAN_LAYER_COUNT - 1); } }} step={1} type="range" value={selectedIndex} />
        <div aria-hidden="true" className="mt-2 grid text-[10px] text-white/45" style={{ gridTemplateColumns: `repeat(${OCEAN_LAYER_COUNT}, minmax(0, 1fr))` }}>{OCEAN_DEPTHS_M.map((depth, index) => <span className={index === selectedIndex ? "text-center text-cyan-100" : "text-center"} key={depth}>{index + 1}</span>)}</div>
        <div aria-hidden="true" className="mt-1 flex justify-between text-[10px] uppercase tracking-[0.14em] text-white/45"><span>0 m</span><span>1000 m</span></div>
        <p id="depth-selection-status" className="sr-only" role="status">Layer {selectedIndex + 1} of {OCEAN_LAYER_COUNT}, {selectedDepth} metres selected. Visual scaffold; no data connected.</p>
      </div>
    </section>
  );
}
