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
    <div className="flex flex-col gap-4 rounded-2xl border border-white/15 bg-white/[0.02] p-3 shadow-[inset_0_1px_1px_rgba(255,255,255,0.12)] backdrop-blur-xl xl:flex-row xl:items-center xl:justify-between">
      {/* Mode Switcher: Limelight Navbar */}
      <div
        role="tablist"
        aria-label="Section visualization modes"
        className="relative inline-flex flex-wrap items-center gap-1 rounded-2xl border border-white/15 bg-slate-950/60 p-1.5 shadow-[0_12px_32px_rgba(0,0,0,0.3),inset_0_1px_0_rgba(255,255,255,0.16)] backdrop-blur-2xl"
      >
        {modes.map((m) => {
          const Icon = m.icon;
          const isActive = mode === m.id;
          return (
            <button
              key={m.id}
              type="button"
              role="tab"
              onClick={() => onModeChange(m.id)}
              aria-label={m.label}
              aria-selected={isActive}
              className={`relative z-10 flex items-center gap-2 rounded-xl px-3.5 py-2 font-mono text-xs transition-colors outline-none focus-visible:ring-2 focus-visible:ring-cyan-200 ${
                isActive
                  ? "text-white font-semibold drop-shadow-[0_0_10px_rgba(34,211,238,0.7)]"
                  : "text-white/55 hover:text-white/90 hover:bg-white/[0.04]"
              }`}
            >
              {isActive && (
                <motion.span
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-x-2 top-0 h-1 rounded-full bg-cyan-200 shadow-[0_12px_22px_rgba(103,232,249,0.95),0_0_14px_rgba(34,211,238,0.85)]"
                  layoutId="section-mode-limelight-beam"
                  transition={
                    prefersReducedMotion
                      ? { duration: 0 }
                      : { type: "spring", stiffness: 380, damping: 30 }
                  }
                >
                  <span className="absolute left-[-35%] top-1 h-9 w-[170%] bg-gradient-to-b from-cyan-200/25 via-cyan-200/10 to-transparent [clip-path:polygon(10%_100%,28%_0,72%_0,90%_100%)]" />
                </motion.span>
              )}
              <Icon
                size={15}
                className={
                  isActive
                    ? "text-cyan-300 drop-shadow-[0_0_8px_rgba(34,211,238,0.8)]"
                    : "text-white/45"
                }
                strokeWidth={isActive ? 2.2 : 1.8}
              />
              <span>{m.label}</span>
            </button>
          );
        })}
      </div>

      {/* Oceanographic Overlays Selection (D20, MLD, Argo Floaters) */}
      <div className="flex flex-wrap items-center gap-2.5">
        <span className="text-[11px] font-mono uppercase tracking-wider text-white/40 hidden sm:inline mr-1">
          Overlays:
        </span>

        {/* 1. D20 Isotherm Toggle Pill */}
        <button
          type="button"
          onClick={onToggleD20}
          aria-pressed={showD20}
          className={`group flex items-center gap-2.5 rounded-xl border px-3 py-1.5 font-mono text-xs transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 ${
            showD20
              ? "border-cyan-400/50 bg-cyan-500/15 text-cyan-100 shadow-[0_0_18px_rgba(34,211,238,0.25),inset_0_1px_1px_rgba(255,255,255,0.2)]"
              : "border-white/10 bg-white/[0.02] text-white/45 hover:border-white/20 hover:text-white/70"
          }`}
          title="Toggle 20°C Isotherm contour (thermocline proxy)"
        >
          <div className="flex items-center gap-1">
            <Waves
              size={14}
              className={showD20 ? "text-cyan-300 animate-pulse" : "text-white/40"}
            />
            <span className="font-semibold">D20 Isotherm</span>
          </div>

          <span
            className={`rounded-md px-1.5 py-0.5 text-[10px] font-bold ${
              showD20
                ? "bg-cyan-400/25 text-cyan-200 border border-cyan-400/30"
                : "bg-white/5 text-white/40"
            }`}
          >
            ~{meanD20} m
          </span>

          {/* Micro Switch Knob */}
          <div
            className={`relative h-4 w-7 rounded-full transition-colors duration-200 ${
              showD20 ? "bg-cyan-500/50" : "bg-white/15"
            }`}
          >
            <div
              className={`absolute top-0.5 size-3 rounded-full transition-all duration-200 ${
                showD20
                  ? "left-3.5 bg-cyan-200 shadow-[0_0_8px_rgba(34,211,238,0.9)]"
                  : "left-0.5 bg-white/40"
              }`}
            />
          </div>
        </button>

        {/* 2. MLD Line Toggle Pill */}
        <button
          type="button"
          onClick={onToggleMLD}
          aria-pressed={showMLD}
          className={`group flex items-center gap-2.5 rounded-xl border px-3 py-1.5 font-mono text-xs transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50 ${
            showMLD
              ? "border-white/40 bg-white/15 text-white shadow-[0_0_18px_rgba(255,255,255,0.2),inset_0_1px_1px_rgba(255,255,255,0.25)]"
              : "border-white/10 bg-white/[0.02] text-white/45 hover:border-white/20 hover:text-white/70"
          }`}
          title="Toggle Mixed Layer Depth line (temperature criterion ΔT = 0.2°C)"
        >
          <div className="flex items-center gap-1">
            <Minus
              size={14}
              className={showMLD ? "text-white" : "text-white/40"}
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
                  ? "left-3.5 bg-white shadow-[0_0_8px_rgba(255,255,255,0.9)]"
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
          className={`group flex items-center gap-2.5 rounded-xl border px-3 py-1.5 font-mono text-xs transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-300 ${
            showArgo
              ? "border-amber-400/50 bg-amber-500/15 text-amber-100 shadow-[0_0_18px_rgba(251,191,36,0.25),inset_0_1px_1px_rgba(255,255,255,0.2)]"
              : "border-white/10 bg-white/[0.02] text-white/45 hover:border-white/20 hover:text-white/70"
          }`}
          title="Toggle collocated independent Argo float validation profiles"
        >
          <div className="flex items-center gap-1">
            <Radio
              size={14}
              className={showArgo ? "text-amber-300 animate-pulse" : "text-white/40"}
            />
            <span className="font-semibold">Argo Floats</span>
          </div>

          <span
            className={`rounded-md px-1.5 py-0.5 text-[10px] font-bold ${
              showArgo
                ? "bg-amber-400/25 text-amber-200 border border-amber-400/30"
                : "bg-white/5 text-white/40"
            }`}
          >
            {argoCount} collocated
          </span>

          {/* Micro Switch Knob */}
          <div
            className={`relative h-4 w-7 rounded-full transition-colors duration-200 ${
              showArgo ? "bg-amber-500/50" : "bg-white/15"
            }`}
          >
            <div
              className={`absolute top-0.5 size-3 rounded-full transition-all duration-200 ${
                showArgo
                  ? "left-3.5 bg-amber-200 shadow-[0_0_8px_rgba(251,191,36,0.9)]"
                  : "left-0.5 bg-white/40"
              }`}
            />
          </div>
        </button>
      </div>
    </div>
  );
}
