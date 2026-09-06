"use client";

import { ArrowRight, BarChart3, Compass, Layers, type LucideIcon } from "lucide-react";
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
  },
  {
    title: "3D Depth Stack",
    summary: "Interactive peeling of 15 depth layers (0m to 1000m) with live point temperature profile extraction.",
    detail: "Explore the planned 15-layer subsurface reconstruction, from the surface to 1000m, and inspect a live point temperature profile.",
    action: "Open Explorer",
    icon: Layers,
    accent: "text-cyan-400 border-cyan-500/20 bg-cyan-500/10",
  },
  {
    title: "Ocean Section",
    summary: "Slice across custom ocean coordinates to view thermocline depth, D20 contour, and mixed layer depth.",
    detail: "Draw a planned ocean transect across custom coordinates to inspect thermocline depth, D20 contours, and mixed-layer depth.",
    action: "Draw Section",
    icon: Compass,
    accent: "text-teal-400 border-teal-500/20 bg-teal-500/10",
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
              className="group relative overflow-hidden rounded-2xl border border-white/10 bg-neutral-950/70 p-6 text-left backdrop-blur-2xl transition-all duration-300 hover:-translate-y-1 hover:border-cyan-500/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0D47A1]"
              type="button"
              onClick={() => setActiveFeature(feature)}
            >
              <div className="flex h-full flex-col justify-between space-y-4">
                <div className={`w-fit rounded-xl border p-3 ${feature.accent}`}>
                  <Icon aria-hidden="true" size={24} />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white transition-colors group-hover:text-cyan-400">
                    {feature.title}
                  </h3>
                  <p className="mt-1 text-sm text-neutral-400">{feature.summary}</p>
                </div>
                <div className="flex items-center gap-1 pt-2 font-mono text-xs text-cyan-400">
                  <span>{feature.action}</span>
                  <ArrowRight aria-hidden="true" size={12} className="transition-transform group-hover:translate-x-1" />
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
        actionLabel={activeFeature?.actionHref ? "Open validation report" : undefined}
        onOpenChange={(open) => {
          if (!open) closeModal();
        }}
      />
    </>
  );
}
