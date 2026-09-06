import Link from "next/link";
import { ArrowRight, BarChart3 } from "lucide-react";
import { FeatureCards } from "@/components/landing/feature-cards";

export default function Home() {
  return (
    <main className="flex min-h-screen w-full flex-1 flex-col items-center justify-center px-6 py-24 font-sans">
      <div className="flex flex-col items-center text-center max-w-5xl mx-auto space-y-8 pointer-events-none">
        
        {/* Title & Tagline */}
        <div className="space-y-4">
          <h1 className="select-none text-6xl font-bold leading-[0.9] tracking-tighter text-[#0070c0] uppercase drop-shadow-md md:text-8xl lg:text-[110px]">
            POSEIDON
          </h1>
          <p className="mx-auto max-w-2xl text-lg font-medium leading-relaxed text-neutral-200 drop-shadow md:text-xl">
            Deep Ocean Temperature Intelligence. AI-driven 3D subsurface temperature reconstruction across 15 depth layers using only surface satellite observations.
          </p>
        </div>

        {/* Navigation Action Buttons */}
        <div className="flex flex-wrap items-center justify-center gap-4 pt-4 pointer-events-auto">
          <Link
            href="#feature-previews"
            className="group relative flex items-center gap-3 px-8 py-4 bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-full font-bold tracking-wider uppercase text-sm shadow-lg shadow-cyan-500/25 transition-all duration-300 hover:scale-[1.03] active:scale-[0.98] hover:shadow-cyan-500/40"
          >
            <span>EXPLORE PLANNED VIEWS</span>
            <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
          </Link>

          <Link
            href="/report"
            className="flex items-center gap-2 rounded-full border border-white/20 bg-white/[0.06] px-8 py-4 text-sm font-semibold tracking-wide text-white shadow-lg backdrop-blur-xl transition-all duration-300 hover:scale-[1.03] hover:bg-white/[0.12] hover:border-white/30"
          >
            <BarChart3 size={16} className="text-cyan-400" />
            <span>VALIDATION REPORT</span>
          </Link>
        </div>

        <FeatureCards />

      </div>
    </main>
  );
}
