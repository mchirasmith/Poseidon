"use client";

import { motion, useReducedMotion } from "framer-motion";
import {
  Activity,
  Layers,
  Radio,
  ShieldCheck,
  Thermometer,
  Waves,
  Minus,
} from "lucide-react";
import type { SectionMode } from "@/lib/section";

interface SectionControlsProps {
  mode: SectionMode;
  onModeChange: (mode: SectionMode) => void;
  showD20: boolean;
  onToggleD20: () => void;
  showMLD: boolean;
  onToggleMLD: () => void;
  showArgo: boolean;
  onToggleArgo: () => void;
  meanD20: number;
  meanMLD: number;
  argoCount?: number;
}

export function SectionControls({
  mode,
  onModeChange,
  showD20,
  onToggleD20,
  showMLD,
  onToggleMLD,
  showArgo,
  onToggleArgo,
  meanD20,
  meanMLD,
  argoCount = 3,
}: SectionControlsProps) {
  const prefersReducedMotion = useReducedMotion();

  const modes: { id: SectionMode; label: string; icon: typeof Activity; badge: string }[] = [
    { id: "poseidon", label: "Poseidon Model", icon: Thermometer, badge: "Reconstructed" },
    { id: "glorys", label: "GLORYS Baseline", icon: Layers, badge: "Reanalysis" },
    { id: "diff", label: "Difference", icon: Activity, badge: "Poseidon − GLORYS" },
    { id: "sigma", label: "Uncertainty (1σ)", icon: ShieldCheck, badge: "Confidence Spread" },
  ];

  return (
    <div className="flex flex-wrap items-center gap-2.5 rounded-2xl border border-white/15 bg-white/[0.02] p-2 shadow-[inset_0_1px_1px_rgba(255,255,255,0.12)] backdrop-blur-xl">
      {/* Mode Switcher: Compact Limelight Navbar */}
      <div
        role="tablist"
        aria-label="Section visualization modes"
        className="relative inline-flex items-center gap-0.5 rounded-xl border border-white/15 bg-slate-950/70 p-1 shadow-[0_8px_20px_rgba(0,0,0,0.35),inset_0_1px_0_rgba(255,255,255,0.16)] backdrop-blur-xl"
      >
        {modes.map((m) => {
          const Icon = m.icon;
          const isActive = mode === m.id;
          return (
            <div key={m.id} className="relative group/tooltip flex items-center justify-center">
              <button
                type="button"
                role="tab"
                onClick={() => onModeChange(m.id)}
                aria-label={m.label}
                aria-selected={isActive}
                className="relative z-10 grid size-8.5 sm:size-9 place-items-center rounded-lg transition-colors outline-none focus-visible:ring-2 focus-visible:ring-white/50"
              >
                {isActive && (
                  <motion.span
                    aria-hidden="true"
                    className="pointer-events-none absolute inset-x-1 top-0 h-0.5 rounded-full bg-white shadow-[0_8px_16px_rgba(255,255,255,0.95)]"
                    layoutId="section-mode-limelight-beam"
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
                <span className="sr-only">{m.label}</span>
              </button>

              {/* Instant floating hover tooltip */}
              <div className="pointer-events-none absolute bottom-full mb-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-lg border border-white/20 bg-slate-950/95 px-2.5 py-1 text-[11px] font-mono font-semibold text-white opacity-0 shadow-[0_8px_20px_rgba(0,0,0,0.5)] backdrop-blur-xl transition-all duration-150 group-hover/tooltip:opacity-100 group-hover/tooltip:-translate-y-0.5 z-40">
                <span>{m.label}</span>
                <div className="absolute left-1/2 -bottom-1 -translate-x-1/2 size-2 rotate-45 border-b border-r border-white/20 bg-slate-950" />
              </div>
            </div>
          );
        })}
      </div>

      {/* Subtle vertical separator */}
      <div className="hidden sm:block h-6 w-px bg-white/15 mx-0.5" />

      {/* Oceanographic Overlays directly after navbar (MLD Line, D20 Isotherm, Argo Floats) */}
      <div className="flex flex-wrap items-center gap-2">
        {/* 1. MLD Line Toggle Pill */}
        <button
          type="button"
          onClick={onToggleMLD}
          aria-pressed={showMLD}
          className={`group flex items-center gap-2 rounded-xl border px-3 py-1.5 font-mono text-xs transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50 ${
            showMLD
              ? "border-white/40 bg-white/15 text-white shadow-[0_0_18px_rgba(255,255,255,0.2),inset_0_1px_1px_rgba(255,255,255,0.25)]"
              : "border-white/10 bg-white/[0.02] text-white/45 hover:border-white/20 hover:text-white/70"
          }`}
          title="Toggle Mixed Layer Depth line (temperature criterion ΔT = 0.2°C)"
        >
          <div className="flex items-center gap-1.5">
            <Minus
              size={14}
              className={showMLD ? "text-white drop-shadow-[0_0_8px_rgba(255,255,255,0.7)]" : "text-white/40"}
              strokeWidth={3}
            />
            <span className="font-semibold">MLD Line</span>
          </div>

          <span
            className={`rounded-md px-1.5 py-0.5 text-[10px] font-bold ${
              showMLD
                ? "bg-white/20 text-white border border-white/30"
                : "bg-white/5 text-white/40"
            }`}
          >
            ~{meanMLD} m
          </span>

          {/* Micro Switch Knob */}
          <div
            className={`relative h-4 w-7 rounded-full transition-colors duration-200 ${
              showMLD ? "bg-white/40" : "bg-white/15"
            }`}
          >
            <div
              className={`absolute top-0.5 size-3 rounded-full transition-all duration-200 ${
                showMLD
                  ? "left-3.5 bg-white shadow-[0_0_8px_rgba(255,255,255,0.95)]"
                  : "left-0.5 bg-white/40"
              }`}
            />
          </div>
        </button>

        {/* 2. D20 Isotherm Toggle Pill */}
        <button
          type="button"
          onClick={onToggleD20}
          aria-pressed={showD20}
          className={`group flex items-center gap-2 rounded-xl border px-3 py-1.5 font-mono text-xs transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50 ${
            showD20
              ? "border-white/40 bg-white/15 text-white shadow-[0_0_18px_rgba(255,255,255,0.2),inset_0_1px_1px_rgba(255,255,255,0.25)]"
              : "border-white/10 bg-white/[0.02] text-white/45 hover:border-white/20 hover:text-white/70"
          }`}
          title="Toggle 20°C Isotherm contour (thermocline proxy)"
        >
          <div className="flex items-center gap-1.5">
            <Waves
              size={14}
              className={showD20 ? "text-white drop-shadow-[0_0_8px_rgba(255,255,255,0.7)]" : "text-white/40"}
            />
            <span className="font-semibold">D20 Isotherm</span>
          </div>

          <span
            className={`rounded-md px-1.5 py-0.5 text-[10px] font-bold ${
              showD20
                ? "bg-white/20 text-white border border-white/30"
                : "bg-white/5 text-white/40"
            }`}
          >
            ~{meanD20} m
          </span>

          {/* Micro Switch Knob */}
          <div
            className={`relative h-4 w-7 rounded-full transition-colors duration-200 ${
              showD20 ? "bg-white/40" : "bg-white/15"
            }`}
          >
            <div
              className={`absolute top-0.5 size-3 rounded-full transition-all duration-200 ${
                showD20
                  ? "left-3.5 bg-white shadow-[0_0_8px_rgba(255,255,255,0.95)]"
                  : "left-0.5 bg-white/40"
              }`}
            />
          </div>
        </button>

        {/* 3. Argo Floats Toggle Pill */}
        <button
          type="button"
          onClick={onToggleArgo}
          aria-pressed={showArgo}
          className={`group flex items-center gap-2 rounded-xl border px-3 py-1.5 font-mono text-xs transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50 ${
            showArgo
              ? "border-white/40 bg-white/15 text-white shadow-[0_0_18px_rgba(255,255,255,0.2),inset_0_1px_1px_rgba(255,255,255,0.25)]"
              : "border-white/10 bg-white/[0.02] text-white/45 hover:border-white/20 hover:text-white/70"
          }`}
          title="Toggle collocated independent Argo float validation profiles"
        >
          <div className="flex items-center gap-1.5">
            <Radio
              size={14}
              className={showArgo ? "text-white drop-shadow-[0_0_8px_rgba(255,255,255,0.7)]" : "text-white/40"}
            />
            <span className="font-semibold">Argo Floats</span>
          </div>

          <span
            className={`rounded-md px-1.5 py-0.5 text-[10px] font-bold ${
              showArgo
                ? "bg-white/20 text-white border border-white/30"
                : "bg-white/5 text-white/40"
            }`}
          >
            {argoCount} collocated
          </span>

          {/* Micro Switch Knob */}
          <div
            className={`relative h-4 w-7 rounded-full transition-colors duration-200 ${
              showArgo ? "bg-white/40" : "bg-white/15"
            }`}
          >
            <div
              className={`absolute top-0.5 size-3 rounded-full transition-all duration-200 ${
                showArgo
                  ? "left-3.5 bg-white shadow-[0_0_8px_rgba(255,255,255,0.95)]"
                  : "left-0.5 bg-white/40"
              }`}
            />
          </div>
        </button>
      </div>
    </div>
  );
}
