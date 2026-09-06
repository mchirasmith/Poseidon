import type { ReactNode } from "react";
import { DatabaseZap, ShieldAlert } from "lucide-react";
import type { ReportAvailability, ReportMetricDefinition } from "@/lib/report";

export function ReportPanel({
  title,
  description,
  children,
  className = "",
}: {
  title: string;
  description: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`group relative overflow-hidden rounded-2xl border border-white/20 bg-white/[0.03] p-6 shadow-[inset_0_1px_1px_rgba(255,255,255,0.35),0_8px_32px_rgba(0,0,0,0.25)] backdrop-blur-2xl transition-all duration-300 sm:p-7 ${className}`}
    >
      {/* Liquid glass light sheen & top edge reflection */}
      <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-white/[0.10] via-transparent to-transparent opacity-70 transition-opacity" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/40 to-transparent" />

      <div className="relative z-10">
        <div className="mb-5">
          <h2 className="text-lg font-bold tracking-tight text-white">{title}</h2>
          <p className="mt-1 text-sm leading-relaxed text-neutral-200/80">{description}</p>
        </div>
        {children}
      </div>
    </section>
  );
}

export function AvailabilityNotice({ availability }: { availability: ReportAvailability }) {
  const content = {
    unconfigured: {
      title: "No report payload is connected.",
      body: "Metric values, figures, and comparison tables will remain unavailable until the approved API response and schema are available.",
    },
    loading: {
      title: "Report payload loading.",
      body: "Metric and chart regions reserve their layout while the approved report is requested.",
    },
    error: {
      title: "Report payload could not be loaded.",
      body: "A retry action and any approved cached copy belong here once the API boundary is implemented.",
    },
  }[availability];

  return (
    <div
      className="group relative overflow-hidden rounded-2xl border border-amber-300/25 bg-amber-400/[0.04] p-5 shadow-[inset_0_1px_1px_rgba(255,255,255,0.25),0_8px_32px_rgba(0,0,0,0.25)] backdrop-blur-2xl"
      role="status"
      aria-live="polite"
    >
      {/* Liquid glass light sheen & top edge reflection */}
      <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-white/[0.08] via-transparent to-transparent opacity-70" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-amber-300/40 to-transparent" />

      <div className="relative z-10 flex items-start gap-3">
        <div className="rounded-xl border border-amber-300/30 bg-amber-400/10 p-2.5 shadow-[inset_0_1px_1px_rgba(255,255,255,0.25)] backdrop-blur-md">
          <ShieldAlert aria-hidden="true" className="shrink-0 text-amber-200" size={20} />
        </div>
        <div>
          <p className="text-sm font-semibold text-amber-100">{content.title}</p>
          <p className="mt-1 text-sm leading-relaxed text-amber-100/75">{content.body}</p>
        </div>
      </div>
    </div>
  );
}

export function UnavailableRegion({
  label,
  detail = "Waiting for the validated report payload. No scientific values are displayed until it is connected.",
  className = "",
}: {
  label: string;
  detail?: string;
  className?: string;
}) {
  return (
    <div
      className={`relative overflow-hidden flex min-h-44 flex-col items-center justify-center rounded-2xl border border-dashed border-white/20 bg-white/[0.02] p-6 text-center shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)] backdrop-blur-xl ${className}`}
      role="status"
    >
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-white/[0.04] to-transparent opacity-60" />
      <div className="relative z-10 flex flex-col items-center">
        <div className="mb-3 rounded-xl border border-cyan-500/20 bg-cyan-500/10 p-2.5 text-cyan-300 shadow-[inset_0_1px_1px_rgba(255,255,255,0.2)] backdrop-blur-md">
          <DatabaseZap aria-hidden="true" size={22} />
        </div>
        <p className="text-sm font-semibold text-white/90">{label}</p>
        <p className="mt-1 max-w-sm text-xs leading-relaxed text-neutral-300/70">{detail}</p>
      </div>
    </div>
  );
}

export function MetricShell({ metric }: { metric: ReportMetricDefinition }) {
  return (
    <article className="group relative overflow-hidden rounded-2xl border border-white/20 bg-white/[0.03] p-5 shadow-[inset_0_1px_1px_rgba(255,255,255,0.35),0_8px_32px_rgba(0,0,0,0.25)] backdrop-blur-2xl transition-all duration-300 hover:-translate-y-1 hover:border-white/40 hover:bg-white/[0.06] hover:shadow-[inset_0_1px_1px_rgba(255,255,255,0.55),0_16px_48px_rgba(0,0,0,0.35)]">
      {/* Liquid glass light sheen & top edge reflection */}
      <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-white/[0.12] via-transparent to-transparent opacity-70 transition-opacity group-hover:opacity-100" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/40 to-transparent" />

      <div className="relative z-10 flex h-full flex-col justify-between space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-neutral-200">
            {metric.label}
            {metric.unit ? ` (${metric.unit})` : ""}
          </p>
          <span className="rounded-lg border border-cyan-500/20 bg-cyan-500/10 px-2 py-0.5 font-mono text-[10px] text-cyan-300 shadow-[inset_0_1px_1px_rgba(255,255,255,0.2)] backdrop-blur-md">
            HELD-OUT
          </span>
        </div>
        <div>
          <p className="font-mono text-2xl font-bold tracking-tight text-white/90">Unavailable</p>
          <p className="mt-1 text-xs leading-relaxed text-neutral-300/70">{metric.sublabel}</p>
        </div>
      </div>
    </article>
  );
}

export function DisabledControl({ children }: { children: ReactNode }) {
  return (
    <button
      className="rounded-full border border-white/20 bg-white/[0.04] px-3.5 py-1.5 font-mono text-xs text-neutral-300/70 shadow-[inset_0_1px_0_rgba(255,255,255,0.15)] backdrop-blur-md cursor-not-allowed"
      disabled
      type="button"
    >
      {children}
    </button>
  );
}
