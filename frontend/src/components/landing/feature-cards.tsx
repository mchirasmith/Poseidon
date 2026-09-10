"use client";

import { ArrowRight, BarChart3, Spline, type LucideIcon } from "lucide-react";
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
    title: "Ocean Section",
    summary: "Pick a day, draw a line across the sea, and see the temperature at every depth along it.",
    detail: "Choose one of five showcase days, drag the two ends of the line anywhere in the basin, and read the reconstructed temperature from the surface to 1000 m, with the thermocline, the mixed layer and any Argo floats nearby.",
    action: "Draw Section",
    icon: Spline,
    accent: "text-emerald-400 border-emerald-500/20 bg-emerald-500/10",
    actionHref: "/section",
    modalActionLabel: "Open ocean section",
  },
  {
    title: "Validation Report",
    summary: "How accurate the model is, measured on two years it never saw, depth by depth.",
    detail: "Every number here is averaged over the 731 test days of 2019 and 2020. Compare Varuna with a gradient-boosted baseline and a seasonal climatology, and check that its uncertainty estimates are honest.",
    action: "View Metrics",
    icon: BarChart3,
    accent: "text-blue-400 border-blue-500/20 bg-blue-500/10",
    actionHref: "/report",
    modalActionLabel: "Open validation report",
  },
];

export function FeatureCards() {
  const [activeFeature, setActiveFeature] = useState<Feature | null>(null);
  const closeModal = useCallback(() => setActiveFeature(null), []);

  return (
    <>
      <div id="feature-previews" className="pointer-events-auto mt-16 grid w-full grid-cols-1 gap-5 text-left md:grid-cols-2">
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
