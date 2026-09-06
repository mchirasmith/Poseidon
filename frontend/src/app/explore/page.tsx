import { Layers } from "lucide-react";
import { OceanLayerExplorer } from "@/components/explore/ocean-layer-explorer";

export default function ExplorePage() {
  return (
    <main className="min-h-screen px-4 pb-5 pt-24 font-mono text-white sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <header className="flex flex-col gap-5 border-b border-white/15 pb-5 sm:flex-row sm:items-center sm:justify-between">
          <div><p className="text-xs uppercase tracking-[0.22em] text-cyan-200/80">Poseidon / explorer</p><h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Ocean 3D layer explorer</h1></div>
          <div className="flex flex-wrap items-center gap-2 text-xs"><span className="rounded-full border border-cyan-200/35 bg-cyan-200/10 px-3 py-1.5 text-cyan-100" aria-current="page">Explorer</span><span className="rounded-full border border-amber-200/25 bg-amber-200/10 px-3 py-1.5 text-amber-100">no data connected</span></div>
        </header>

        <section className="mt-8 max-w-3xl" aria-labelledby="explorer-introduction">
          <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-cyan-200/80"><Layers aria-hidden="true" size={15} />Depth navigation prototype</div>
          <h2 id="explorer-introduction" className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Inspect the depth structure before connecting the model.</h2>
          <p className="mt-3 text-sm leading-relaxed text-white/70 sm:text-base">Use the depth scrollbar to change layer. This route deliberately contains no day selection, temperature field, profile, or derived values until an approved backend payload is available.</p>
        </section>

        <OceanLayerExplorer />
      </div>
    </main>
  );
}
