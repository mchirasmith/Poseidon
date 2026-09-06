import Link from "next/link";
import { ArrowLeft, DatabaseZap, ShieldAlert, Waves } from "lucide-react";

const metricLabels = ["RMSE (°C)", "Bias (°C)", "Correlation", "CRPS (°C)"];
const methodLabels = ["Poseidon", "Climatology", "Ridge/EOF", "U-Net (same day)", "ConvLSTM U-Net"];

function DataUnavailable({ label }: { label: string }) {
  return (
    <div className="flex min-h-44 flex-col items-center justify-center rounded-2xl border border-dashed border-white/15 bg-black/15 p-6 text-center" role="status">
      <DatabaseZap aria-hidden="true" className="mb-3 text-cyan-200/70" size={24} />
      <p className="text-sm font-medium text-white/85">{label}</p>
      <p className="mt-1 max-w-sm text-xs leading-relaxed text-white/50">Waiting for the validated report payload. No scientific values are displayed until it is connected.</p>
    </div>
  );
}

function Panel({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <section className="rounded-3xl border border-white/15 bg-neutral-950/55 p-5 backdrop-blur-xl sm:p-6">
      <div className="mb-5">
        <h2 className="text-lg font-medium text-white">{title}</h2>
        <p className="mt-1 text-sm text-white/55">{description}</p>
      </div>
      {children}
    </section>
  );
}

export default function ReportPage() {
  return (
    <main className="min-h-screen px-4 py-5 text-white sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-col gap-5 border-b border-white/15 pb-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <Link aria-label="Back to Poseidon home" className="grid size-10 place-items-center rounded-full border border-white/15 bg-white/5 text-white/80 transition hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200" href="/">
              <ArrowLeft aria-hidden="true" size={18} />
            </Link>
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.22em] text-cyan-200/80">Poseidon / report</p>
              <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Validation report</h1>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-white/65">model version pending</span>
            <span className="rounded-full border border-amber-200/25 bg-amber-200/10 px-3 py-1.5 text-amber-100">report data unavailable</span>
          </div>
        </header>

        <section className="mt-8" aria-labelledby="report-overview">
          <div className="max-w-3xl">
            <p className="font-mono text-xs uppercase tracking-[0.22em] text-cyan-200/80">Locked evaluation workspace</p>
            <h2 id="report-overview" className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Evidence, ready for the approved test-set report.</h2>
            <p className="mt-3 text-sm leading-relaxed text-white/65 sm:text-base">This dashboard will display the held-out validation report returned by <code className="rounded bg-white/10 px-1.5 py-0.5 text-cyan-100">/api/report</code>. The backend payload and NetCDF outputs remain the scientific authority.</p>
          </div>
          <div className="mt-6 flex items-start gap-3 rounded-2xl border border-amber-200/20 bg-amber-200/10 p-4" role="status" aria-live="polite">
            <ShieldAlert aria-hidden="true" className="mt-0.5 shrink-0 text-amber-100" size={20} />
            <div><p className="text-sm font-medium text-amber-50">No report payload is connected.</p><p className="mt-1 text-sm text-amber-50/75">Metric values, figures, and comparison tables will remain unavailable until the validated API response is available.</p></div>
          </div>
        </section>

        <section className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Headline metrics" aria-busy="true">
          {metricLabels.map((label) => <article key={label} className="rounded-2xl border border-white/15 bg-neutral-950/55 p-5 backdrop-blur-xl"><p className="text-sm text-white/60">{label}</p><p className="mt-4 text-2xl font-medium tracking-tight text-white/85">Unavailable</p><p className="mt-2 text-xs leading-relaxed text-white/45">all depths, all test days, ocean cells only</p></article>)}
        </section>

        <section className="mt-6" aria-busy="true">
          <Panel title="Skill by depth" description="Metric and basin controls are ready for the report payload.">
            <div className="mb-4 flex flex-wrap gap-2" aria-label="Unavailable report controls">
              {["RMSE", "Bias", "Correlation", "Anomaly correlation", "All basins", "All seasons"].map((control) => <button key={control} className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/45" disabled type="button">{control}</button>)}
            </div>
            <DataUnavailable label="Skill-by-depth chart will load here" />
            <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-xs text-white/55" aria-label="Planned comparison series">{methodLabels.map((method) => <span key={method}>○ {method}</span>)}</div>
          </Panel>
        </section>

        <section className="mt-6 grid gap-6 lg:grid-cols-2" aria-busy="true">
          <Panel title="Spatial error" description="RMSE map at the selected depth."><DataUnavailable label="RMSE map unavailable" /></Panel>
          <Panel title="Spatial bias" description="Bias map at the same selected depth."><DataUnavailable label="Bias map unavailable" /></Panel>
        </section>
        <section className="mt-6 grid gap-6 lg:grid-cols-2" aria-busy="true">
          <Panel title="Argo consistency" description="Observed versus predicted matchups."><DataUnavailable label="Poseidon–Argo scatter unavailable" /></Panel>
          <Panel title="Reference consistency" description="GLORYS versus Argo at identical matchups."><DataUnavailable label="GLORYS–Argo scatter unavailable" /></Panel>
        </section>
        <section className="mt-6" aria-busy="true"><Panel title="Uncertainty calibration" description="Nominal and empirical coverage, plus interval width."><DataUnavailable label="Calibration curve unavailable" /></Panel></section>
        <section className="mt-6 grid gap-6 lg:grid-cols-2" aria-busy="true">
          <Panel title="Per-basin and per-season summary" description="RMSE, bias, correlation, and CRPS by evaluation slice."><DataUnavailable label="Summary table unavailable" /></Panel>
          <Panel title="Baselines and ablations" description="Method comparisons will appear once the report is available."><DataUnavailable label="Baseline table unavailable" /></Panel>
        </section>
        <footer className="flex flex-col gap-3 py-10 text-xs text-white/45 sm:flex-row sm:items-center sm:justify-between"><span>Read-only validation workspace · values appear only from the approved report payload.</span><span className="flex items-center gap-2"><Waves aria-hidden="true" size={14} /> Poseidon ocean temperature intelligence</span></footer>
      </div>
    </main>
  );
}
