import type { ReactNode } from "react";
import { DatabaseZap, ShieldAlert } from "lucide-react";
import type { ReportAvailability, ReportMetricDefinition } from "@/lib/report";

export function ReportPanel({ title, description, children, className = "" }: { title: string; description: string; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-3xl border border-white/15 bg-neutral-950/55 p-5 backdrop-blur-xl sm:p-6 ${className}`}>
      <div className="mb-5">
        <h2 className="text-lg font-medium text-white">{title}</h2>
        <p className="mt-1 text-sm text-white/55">{description}</p>
      </div>
      {children}
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
    <div className="flex items-start gap-3 rounded-2xl border border-amber-200/20 bg-amber-200/10 p-4" role="status" aria-live="polite">
      <ShieldAlert aria-hidden="true" className="mt-0.5 shrink-0 text-amber-100" size={20} />
      <div><p className="text-sm font-medium text-amber-50">{content.title}</p><p className="mt-1 text-sm text-amber-50/75">{content.body}</p></div>
    </div>
  );
}

export function UnavailableRegion({ label, detail = "Waiting for the validated report payload. No scientific values are displayed until it is connected." }: { label: string; detail?: string }) {
  return (
    <div className="flex min-h-44 flex-col items-center justify-center rounded-2xl border border-dashed border-white/15 bg-black/15 p-6 text-center" role="status">
      <DatabaseZap aria-hidden="true" className="mb-3 text-cyan-200/70" size={24} />
      <p className="text-sm font-medium text-white/85">{label}</p>
      <p className="mt-1 max-w-sm text-xs leading-relaxed text-white/50">{detail}</p>
    </div>
  );
}

export function MetricShell({ metric }: { metric: ReportMetricDefinition }) {
  return (
    <article className="rounded-2xl border border-white/15 bg-neutral-950/55 p-5 backdrop-blur-xl">
      <p className="text-sm text-white/60">{metric.label}{metric.unit ? ` (${metric.unit})` : ""}</p>
      <p className="mt-4 text-2xl font-medium tracking-tight text-white/85">Unavailable</p>
      <p className="mt-2 text-xs leading-relaxed text-white/45">{metric.sublabel}</p>
    </article>
  );
}

export function DisabledControl({ children }: { children: ReactNode }) {
  return <button className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/45" disabled type="button">{children}</button>;
}
