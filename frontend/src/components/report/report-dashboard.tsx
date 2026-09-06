import Link from "next/link";
import { ArrowLeft, Waves } from "lucide-react";
import { REPORT_AVAILABILITY, REPORT_DEPTHS_M, REPORT_METRICS, REPORT_SERIES } from "@/lib/report";
import { AvailabilityNotice, DisabledControl, MetricShell, ReportPanel, UnavailableRegion } from "@/components/report/report-primitives";

function ReportHeader() {
  return (
    <header className="flex flex-col gap-5 border-b border-white/15 pb-5 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex items-center gap-4">
        <Link aria-label="Back to Poseidon home" className="grid size-10 place-items-center rounded-full border border-white/15 bg-white/5 text-white/80 transition hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200" href="/"><ArrowLeft aria-hidden="true" size={18} /></Link>
        <div><p className="font-mono text-xs uppercase tracking-[0.22em] text-cyan-200/80">Poseidon / report</p><h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Validation report</h1></div>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs" aria-label="Report navigation and status">
        <span aria-current="page" className="rounded-full border border-cyan-200/35 bg-cyan-200/10 px-3 py-1.5 text-cyan-100">Report</span>
        <span aria-disabled="true" className="rounded-full border border-white/10 px-3 py-1.5 text-white/40">Explorer · planned</span>
        <span aria-disabled="true" className="rounded-full border border-white/10 px-3 py-1.5 text-white/40">Section · planned</span>
        <span className="rounded-full border border-amber-200/25 bg-amber-200/10 px-3 py-1.5 text-amber-100">data unavailable</span>
      </div>
    </header>
  );
}

function SkillByDepthShell() {
  return (
    <ReportPanel title="Skill by depth" description="The approved report will populate the depth axis, comparison series, and filters.">
      <div className="mb-4 flex flex-wrap gap-2" aria-label="Unconfigured report filters">
        {["RMSE", "Bias", "Correlation", "Anomaly correlation", "All basins", "All seasons"].map((control) => <DisabledControl key={control}>{control}</DisabledControl>)}
      </div>
      <div className="grid min-h-[380px] grid-cols-[4rem_1fr] overflow-hidden rounded-2xl border border-dashed border-white/15 bg-black/15" aria-busy="true">
        <div className="flex flex-col justify-between border-r border-white/10 px-2 py-4 text-right text-[10px] text-white/45" aria-label="Planned depth labels in metres">
          {REPORT_DEPTHS_M.map((depth) => <span key={depth}>{depth} m</span>)}
        </div>
        <UnavailableRegion label="Skill-by-depth chart unavailable" detail="The chart will render only after metric series, depth coordinates, basin, and season fields are approved." />
      </div>
      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-xs text-white/55" aria-label="Planned comparison series">{REPORT_SERIES.map((method) => <span key={method}>○ {method}</span>)}</div>
    </ReportPanel>
  );
}

function TableShell({ title, description, columns }: { title: string; description: string; columns: string[] }) {
  return (
    <ReportPanel title={title} description={description}>
      <div className="overflow-x-auto rounded-2xl border border-white/10" role="status">
        <table className="w-full min-w-[34rem] text-left text-sm"><caption className="sr-only">{title} — unavailable pending an approved report payload.</caption><thead className="bg-white/5 text-xs uppercase tracking-wide text-white/50"><tr>{columns.map((column) => <th key={column} className="px-4 py-3 font-medium">{column}</th>)}</tr></thead><tbody><tr className="border-t border-white/10"><td className="px-4 py-5 text-white/60" colSpan={columns.length}>Awaiting validated report payload</td></tr></tbody></table>
      </div>
    </ReportPanel>
  );
}

export function ReportDashboard() {
  return (
    <main className="min-h-screen px-4 py-5 text-white sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <ReportHeader />
        <section className="mt-8" aria-labelledby="report-overview">
          <div className="max-w-3xl"><p className="font-mono text-xs uppercase tracking-[0.22em] text-cyan-200/80">Locked evaluation workspace</p><h2 id="report-overview" className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Evidence, ready for the approved test-set report.</h2><p className="mt-3 text-sm leading-relaxed text-white/65 sm:text-base">This dashboard will display the held-out validation report returned by <code className="rounded bg-white/10 px-1.5 py-0.5 text-cyan-100">/api/report</code>. The backend payload and NetCDF outputs remain the scientific authority.</p></div>
          <div className="mt-6"><AvailabilityNotice availability={REPORT_AVAILABILITY} /></div>
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
