import Link from "next/link";
import { ArrowLeft, Waves } from "lucide-react";
import { REPORT_AVAILABILITY, REPORT_METRICS } from "@/lib/report";
import { AvailabilityNotice, MetricShell, ReportPanel, UnavailableRegion } from "@/components/report/report-primitives";
import { OceanDepthStack } from "@/components/report/ocean-depth-stack";

function ReportHeader() {
  return (
    <header className="flex flex-col gap-5 border-b border-white/15 pb-5 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex items-center gap-4">
        <Link
          aria-label="Back to Poseidon home"
          className="grid size-10 place-items-center rounded-full border border-white/20 bg-white/[0.05] text-white/80 shadow-[inset_0_1px_1px_rgba(255,255,255,0.3)] backdrop-blur-xl transition-all duration-200 hover:scale-105 hover:border-white/40 hover:bg-white/[0.10] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200"
          href="/"
        >
          <ArrowLeft aria-hidden="true" size={18} />
        </Link>
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.22em] text-cyan-200/80">Poseidon / report</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Validation report</h1>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs" aria-label="Report navigation and status">
        <span aria-current="page" className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3.5 py-1.5 font-mono text-cyan-200 shadow-[inset_0_1px_0_rgba(255,255,255,0.2)] backdrop-blur-md">Report</span>
        <span aria-disabled="true" className="rounded-full border border-white/15 bg-white/[0.03] px-3.5 py-1.5 font-mono text-white/40 backdrop-blur-md">Explorer · planned</span>
        <span aria-disabled="true" className="rounded-full border border-white/15 bg-white/[0.03] px-3.5 py-1.5 font-mono text-white/40 backdrop-blur-md">Section · planned</span>
        <span className="rounded-full border border-amber-300/30 bg-amber-400/10 px-3.5 py-1.5 font-mono text-amber-200 shadow-[inset_0_1px_0_rgba(255,255,255,0.2)] backdrop-blur-md">data unavailable</span>
      </div>
    </header>
  );
}

function SkillByDepthShell() {
  return (
    <ReportPanel
      title="Skill by depth · 3D Ocean Stratification"
      description="Interactive 15-layer subsurface temperature reconstruction from satellite surface observations for the North Indian Ocean (0 m to 1000 m)."
    >
      <OceanDepthStack />
    </ReportPanel>
  );
}

function TableShell({ title, description, columns }: { title: string; description: string; columns: string[] }) {
  return (
    <ReportPanel title={title} description={description}>
      <div className="relative overflow-hidden rounded-2xl border border-white/20 bg-white/[0.02] shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)] backdrop-blur-xl" role="status">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/30 to-transparent" />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[34rem] text-left text-sm">
            <caption className="sr-only">{title} — unavailable pending an approved report payload.</caption>
            <thead className="border-b border-white/15 bg-white/[0.04] text-xs font-mono uppercase tracking-wider text-white/60">
              <tr>{columns.map((column) => <th key={column} className="px-4 py-3.5 font-medium">{column}</th>)}</tr>
            </thead>
            <tbody>
              <tr>
                <td className="px-4 py-8 text-center text-sm text-neutral-300/70" colSpan={columns.length}>
                  <span className="inline-flex items-center gap-2 font-mono text-xs text-cyan-200/80">
                    <span className="size-1.5 rounded-full bg-cyan-400 animate-pulse" />
                    Awaiting validated report payload
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </ReportPanel>
  );
}

export function ReportDashboard() {
  return (
    <main className="min-h-screen px-4 pb-5 pt-24 text-white sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <ReportHeader />
        <section className="mt-8 space-y-6" aria-labelledby="report-overview">
          <div className="group relative overflow-hidden rounded-2xl border border-white/20 bg-white/[0.03] p-6 sm:p-8 shadow-[inset_0_1px_1px_rgba(255,255,255,0.35),0_8px_32px_rgba(0,0,0,0.25)] backdrop-blur-2xl transition-all duration-300">
            {/* Liquid glass light sheen & top edge reflection */}
            <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-white/[0.10] via-transparent to-transparent opacity-70 transition-opacity" />
            <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/40 to-transparent" />

            <div className="relative z-10 max-w-3xl">
              <p className="font-mono text-xs uppercase tracking-[0.22em] text-cyan-200/80">Locked evaluation workspace</p>
              <h2 id="report-overview" className="mt-2 text-2xl font-bold tracking-tight text-white sm:text-3xl lg:text-4xl">
                Evidence, ready for the approved test-set report.
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-neutral-200/80 sm:text-base">
                This dashboard will display the held-out validation report returned by{" "}
                <code className="rounded border border-cyan-400/30 bg-cyan-500/10 px-1.5 py-0.5 font-mono text-cyan-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.15)] backdrop-blur-sm">
                  /api/report
                </code>
                . The backend payload and NetCDF outputs remain the scientific authority.
              </p>
            </div>
          </div>
          <AvailabilityNotice availability={REPORT_AVAILABILITY} />
        </section>
        <section className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Headline metrics" aria-busy="true">{REPORT_METRICS.map((metric) => <MetricShell key={metric.label} metric={metric} />)}</section>
        <section className="mt-6"><SkillByDepthShell /></section>
        <section className="mt-6 grid gap-6 lg:grid-cols-2" aria-busy="true"><ReportPanel title="Spatial RMSE" description="Map at the selected report depth."><UnavailableRegion label="RMSE map unavailable" /></ReportPanel><ReportPanel title="Spatial bias" description="Bias map at the same selected report depth."><UnavailableRegion label="Bias map unavailable" /></ReportPanel></section>
        <section className="mt-6 grid gap-6 lg:grid-cols-2" aria-busy="true"><ReportPanel title="Argo consistency" description="Observed versus predicted matchups."><UnavailableRegion label="Poseidon–Argo comparison unavailable" /></ReportPanel><ReportPanel title="Reference consistency" description="GLORYS versus Argo at identical matchups."><UnavailableRegion label="GLORYS–Argo comparison unavailable" /></ReportPanel></section>
        <section className="mt-6" aria-busy="true"><ReportPanel title="Uncertainty calibration" description="Nominal and empirical coverage, plus interval width."><UnavailableRegion label="Calibration curve unavailable" /></ReportPanel></section>
        <section className="mt-6 grid gap-6 lg:grid-cols-2" aria-busy="true"><TableShell title="Per-basin and per-season summary" description="RMSE, bias, correlation, and CRPS by evaluation slice." columns={["Slice", "RMSE", "Bias", "Correlation", "CRPS"]} /><TableShell title="Baselines and ablations" description="Method comparisons from the approved report." columns={["Method", "RMSE", "Bias", "Correlation", "CRPS"]} /></section>
        <footer className="flex flex-col gap-3 py-10 text-xs text-white/45 sm:flex-row sm:items-center sm:justify-between"><span>Read-only validation workspace · values appear only from the approved report payload.</span><span className="flex items-center gap-2"><Waves aria-hidden="true" size={14} /> Poseidon ocean temperature intelligence</span></footer>
      </div>
    </main>
  );
}
