"use client";

import { CheckSquare, Square, Layers, Activity, ShieldCheck, Thermometer } from "lucide-react";
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
}: SectionControlsProps) {
  const modes: { id: SectionMode; label: string; icon: typeof Activity; badge: string }[] = [
    { id: "poseidon", label: "Poseidon Model", icon: Thermometer, badge: "Reconstructed" },
    { id: "glorys", label: "GLORYS Baseline", icon: Layers, badge: "Reanalysis" },
    { id: "diff", label: "Difference", icon: Activity, badge: "Poseidon − GLORYS" },
    { id: "sigma", label: "Uncertainty (1σ)", icon: ShieldCheck, badge: "Confidence Spread" },
  ];

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-white/15 bg-white/[0.02] p-3.5 shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)] backdrop-blur-xl lg:flex-row lg:items-center lg:justify-between">
      {/* Mode Switcher Segmented Control */}
      <div className="flex flex-wrap items-center gap-1.5">
        {modes.map((m) => {
          const Icon = m.icon;
          const isActive = mode === m.id;
          return (
            <button
              key={m.id}
              type="button"
              onClick={() => onModeChange(m.id)}
              className={`flex items-center gap-2 rounded-lg px-3 py-1.5 font-mono text-xs transition-all ${
                isActive
                  ? "border border-cyan-400/40 bg-cyan-500/15 font-semibold text-cyan-200 shadow-[inset_0_1px_1px_rgba(255,255,255,0.2)]"
                  : "border border-transparent text-white/60 hover:border-white/10 hover:bg-white/[0.04] hover:text-white"
              }`}
            >
              <Icon size={14} className={isActive ? "text-cyan-300" : "text-white/40"} />
              <span>{m.label}</span>
            </button>
          );
        })}
      </div>

      {/* Oceanographic Overlays & Diagnostics */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Overlays Checkboxes */}
        <div className="flex items-center gap-3 border-white/15 lg:border-l lg:pl-4">
          <span className="text-[11px] font-mono uppercase tracking-wider text-white/50 hidden sm:inline">
            Overlays:
          </span>

          {/* D20 Contour */}
          <button
            type="button"
            onClick={onToggleD20}
            className={`flex items-center gap-1.5 font-mono text-xs transition-colors ${
              showD20 ? "text-cyan-200" : "text-white/40 hover:text-white/70"
            }`}
          >
            {showD20 ? (
              <CheckSquare size={14} className="text-cyan-300" />
            ) : (
              <Square size={14} className="text-white/40" />
            )}
            <span className="flex items-center gap-1">
              <span className="inline-block size-2 rounded-full bg-cyan-400" />
              D20 Contour
            </span>
          </button>

          {/* MLD Line */}
          <button
            type="button"
            onClick={onToggleMLD}
            className={`flex items-center gap-1.5 font-mono text-xs transition-colors ${
              showMLD ? "text-white font-medium" : "text-white/40 hover:text-white/70"
            }`}
          >
            {showMLD ? (
              <CheckSquare size={14} className="text-white" />
            ) : (
              <Square size={14} className="text-white/40" />
            )}
            <span className="flex items-center gap-1">
              <span className="inline-block h-0.5 w-2.5 bg-white" />
              MLD Line
            </span>
          </button>

          {/* Argo Matchups */}
          <button
            type="button"
            onClick={onToggleArgo}
            className={`flex items-center gap-1.5 font-mono text-xs transition-colors ${
              showArgo ? "text-amber-200" : "text-white/40 hover:text-white/70"
            }`}
          >
            {showArgo ? (
              <CheckSquare size={14} className="text-amber-300" />
            ) : (
              <Square size={14} className="text-white/40" />
            )}
            <span className="flex items-center gap-1">
              <span className="inline-block size-2 rounded-full bg-amber-400" />
              Argo Floats
            </span>
          </button>
        </div>

        {/* Diagnostic Badges */}
        <div className="hidden xl:flex items-center gap-2 border-l border-white/15 pl-4 font-mono text-xs">
          <div className="rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1">
            <span className="text-white/45">Mean D20: </span>
            <span className="font-semibold text-cyan-300">{meanD20} m</span>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1">
            <span className="text-white/45">Mean MLD: </span>
            <span className="font-semibold text-white">{meanMLD} m</span>
          </div>
        </div>
      </div>
    </div>
  );
}
