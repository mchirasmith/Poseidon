"use client";

import { ArrowRight, BarChart3, Layers, type LucideIcon } from "lucide-react";
import { useCallback, useState } from "react";
import { FeatureModal } from "@/components/ui/feature-modal";

interface Feature {
  title: string;
  summary: string;
  detail: string;
  action: string;
  icon: LucideIcon;
  accent: string;
  actionHref?: string;
  modalActionLabel?: string;
}

const features: Feature[] = [
  {
    title: "Validation Report",
    summary: "Rigorous locked test set benchmarks (2019-2020) with Argo float comparisons and baseline models.",
    detail: "Review benchmark performance across the locked 2019–2020 test set, including Argo float comparisons and baseline-model results.",
    action: "View Metrics",
    icon: BarChart3,
    accent: "text-blue-400 border-blue-500/20 bg-blue-500/10",
    actionHref: "/report",
    modalActionLabel: "Open validation report",
  },
  {
    title: "3D Depth Stack",
    summary: "Interactive peeling of 15 depth layers (0m to 1000m) with live point temperature profile extraction.",
    detail: "Explore the planned 15-layer subsurface reconstruction, from the surface to 1000m, and inspect a live point temperature profile.",
    action: "Open Explorer",
    icon: Layers,
    accent: "text-cyan-400 border-cyan-500/20 bg-cyan-500/10",
    actionHref: "/explore",
    modalActionLabel: "Open layer explorer",
  },
  {
    title: "Ocean Section",
    summary: "Slice across custom ocean coordinates to view thermocline depth, D20 contour, and mixed layer depth.",
    detail: "Draw a planned ocean transect across custom coordinates to inspect thermocline depth, D20 contours, and mixed-layer depth.",
    action: "Draw Section",
    icon: Layers,
    accent: "text-cyan-400 border-cyan-500/20 bg-cyan-500/10",
  },
];

export function FeatureCards() {
  const [activeFeature, setActiveFeature] = useState<Feature | null>(null);
  const closeModal = useCallback(() => setActiveFeature(null), []);

  return (
    <>
      <div id="feature-previews" className="pointer-events-auto mt-16 grid w-full grid-cols-1 gap-5 text-left md:grid-cols-3">
        {features.map((feature) => {
          const Icon = feature.icon;
          return (
            <button
              key={feature.title}
              aria-haspopup="dialog"
              className="group relative overflow-hidden rounded-2xl border border-white/20 bg-white/[0.03] p-6 text-left shadow-[inset_0_1px_1px_rgba(255,255,255,0.35),0_8px_32px_rgba(0,0,0,0.25)] backdrop-blur-2xl transition-all duration-300 hover:-translate-y-1.5 hover:border-white/40 hover:bg-white/[0.07] hover:shadow-[inset_0_1px_1px_rgba(255,255,255,0.55),0_16px_48px_rgba(0,0,0,0.35)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200 focus-visible:ring-offset-2 focus-visible:ring-offset-black"
              type="button"
              onClick={() => setActiveFeature(feature)}
            >
              {/* Liquid glass light sheen & top edge reflection */}
              <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-white/[0.12] via-transparent to-transparent opacity-70 transition-opacity group-hover:opacity-100" />
              <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/40 to-transparent" />

              <div className="relative z-10 flex h-full flex-col justify-between space-y-4">
                <div className={`w-fit rounded-xl border p-3 ${feature.accent} shadow-[inset_0_1px_1px_rgba(255,255,255,0.25)] backdrop-blur-md transition-all group-hover:scale-105`}>
                  <Icon aria-hidden="true" size={24} />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white transition-colors group-hover:text-cyan-300">
                    {feature.title}
                  </h3>
                  <p className="mt-1 text-sm leading-relaxed text-neutral-200/90">{feature.summary}</p>
                </div>
                <div className="flex items-center gap-1.5 pt-2 font-mono text-xs text-cyan-300 transition-transform group-hover:translate-x-1">
                  <span>{feature.action}</span>
                  <ArrowRight aria-hidden="true" size={12} />
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <FeatureModal
        description={activeFeature?.detail ?? ""}
        isOpen={activeFeature !== null}
        title={activeFeature?.title ?? ""}
        actionHref={activeFeature?.actionHref}
        actionLabel={activeFeature?.modalActionLabel}
        onOpenChange={(open) => {
          if (!open) closeModal();
        }}
      />
    </>
  );
}
