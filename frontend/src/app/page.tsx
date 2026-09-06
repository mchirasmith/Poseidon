import Link from "next/link";
import { ArrowRight, Compass, BarChart3, Layers, Info } from "lucide-react";
import { SubtleGridBackground } from "@/components/ui/the-infinite-grid";

export default function Home() {
  return (
    <main className="flex-1 w-full bg-transparent text-white font-sans flex flex-col items-center justify-center px-6 py-24 min-h-screen">
      <div className="flex flex-col items-center text-center max-w-5xl mx-auto space-y-8 pointer-events-none">
        
        {/* Badge */}
        <div className="flex items-center gap-3 justify-center">
          <div className="h-[2px] w-8 bg-cyan-500" aria-hidden="true" />
          <span className="font-mono text-xs tracking-[0.35em] text-cyan-400 uppercase font-semibold">
            SIH 2026 • PS SIH26066 • INCOIS
          </span>
          <div className="h-[2px] w-8 bg-cyan-500" aria-hidden="true" />
        </div>

        {/* Title & Tagline */}
        <div className="space-y-4">
          <h1 className="text-6xl md:text-8xl lg:text-[110px] font-bold tracking-tighter uppercase leading-[0.9] select-none text-white drop-shadow-md">
            POSEI<span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-cyan-400 to-teal-300">DON</span>
          </h1>
          <p className="text-lg md:text-xl text-neutral-400 font-medium leading-relaxed max-w-2xl mx-auto">
            Deep Ocean Temperature Intelligence. AI-driven 3D subsurface temperature reconstruction across 15 depth layers using only surface satellite observations.
          </p>
        </div>

        {/* Navigation Action Buttons */}
        <div className="flex flex-wrap items-center justify-center gap-4 pt-4 pointer-events-auto">
          <Link
            href="/explore"
            className="group relative flex items-center gap-3 px-8 py-4 bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-full font-bold tracking-wider uppercase text-sm shadow-lg shadow-cyan-500/25 transition-all duration-300 hover:scale-[1.03] active:scale-[0.98] hover:shadow-cyan-500/40"
          >
            <span>LAUNCH 3D EXPLORER</span>
            <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
          </Link>

          <Link
            href="/report"
            className="flex items-center gap-2 px-8 py-4 bg-white/5 hover:bg-white/10 text-neutral-200 border border-white/10 rounded-full font-semibold tracking-wide text-sm transition-all duration-300 hover:scale-[1.03]"
          >
            <BarChart3 size={16} className="text-cyan-400" />
            <span>VALIDATION REPORT</span>
          </Link>
        </div>

        {/* Feature Cards with Subtle Grid Background */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 w-full mt-16 pointer-events-auto text-left">
          
          <Link 
            href="/report" 
            className="relative group p-6 rounded-2xl border border-white/10 bg-neutral-950/60 backdrop-blur-md overflow-hidden hover:border-cyan-500/50 transition-all duration-300 hover:-translate-y-1"
          >
            <SubtleGridBackground id="report-card-grid" theme="ocean" />
            <div className="relative z-10 flex flex-col h-full justify-between space-y-4">
              <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-xl w-fit text-blue-400">
                <BarChart3 size={24} />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white group-hover:text-cyan-400 transition-colors">Validation Report</h3>
                <p className="text-sm text-neutral-400 mt-1">
                  Rigorous locked test set benchmarks (2019-2020) with Argo float comparisons and baseline models.
                </p>
              </div>
              <div className="text-xs font-mono text-cyan-400 flex items-center gap-1 pt-2">
                <span>View Metrics</span>
                <ArrowRight size={12} className="group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          </Link>

          <Link 
            href="/explore" 
            className="relative group p-6 rounded-2xl border border-white/10 bg-neutral-950/60 backdrop-blur-md overflow-hidden hover:border-cyan-500/50 transition-all duration-300 hover:-translate-y-1"
          >
            <SubtleGridBackground id="explore-card-grid" theme="ocean" />
            <div className="relative z-10 flex flex-col h-full justify-between space-y-4">
              <div className="p-3 bg-cyan-500/10 border border-cyan-500/20 rounded-xl w-fit text-cyan-400">
                <Layers size={24} />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white group-hover:text-cyan-400 transition-colors">3D Depth Stack</h3>
                <p className="text-sm text-neutral-400 mt-1">
                  Interactive peeling of 15 depth layers (0m to 1000m) with live point temperature profile extraction.
                </p>
              </div>
              <div className="text-xs font-mono text-cyan-400 flex items-center gap-1 pt-2">
                <span>Open Explorer</span>
                <ArrowRight size={12} className="group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          </Link>

          <Link 
            href="/section" 
            className="relative group p-6 rounded-2xl border border-white/10 bg-neutral-950/60 backdrop-blur-md overflow-hidden hover:border-cyan-500/50 transition-all duration-300 hover:-translate-y-1"
          >
            <SubtleGridBackground id="section-card-grid" theme="ocean" />
            <div className="relative z-10 flex flex-col h-full justify-between space-y-4">
              <div className="p-3 bg-teal-500/10 border border-teal-500/20 rounded-xl w-fit text-teal-400">
                <Compass size={24} />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white group-hover:text-cyan-400 transition-colors">Vertical Section</h3>
                <p className="text-sm text-neutral-400 mt-1">
                  Slice across custom ocean coordinates to view thermocline depth, D20 contour, and mixed layer depth.
                </p>
              </div>
              <div className="text-xs font-mono text-cyan-400 flex items-center gap-1 pt-2">
                <span>Draw Section</span>
                <ArrowRight size={12} className="group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          </Link>

        </div>

      </div>
    </main>
  );
}
