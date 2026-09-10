"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowRight, BarChart3, Spline } from "lucide-react";
import { FeatureCards } from "@/components/landing/feature-cards";
import { TrackShiftSpinner } from "@/components/ui/trackshift-spinner";

export default function Home() {
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 600);
    return () => clearTimeout(timer);
  }, []);

  return (
    <>
      <TrackShiftSpinner
        isLoading={isLoading}
        title="Starting Varuna"
        subtitle="Loading the ocean temperature reconstruction..."
        isFullPage={true}
      />

      <main className="flex min-h-screen w-full flex-1 flex-col items-center justify-center px-6 py-24 font-sans">
        <div className="flex flex-col items-center text-center max-w-5xl mx-auto space-y-8 pointer-events-none">
          
          {/* Title & Tagline */}
          <div className="space-y-4">
            <h1 className="select-none text-6xl font-bold leading-[0.9] tracking-tighter text-[#0070c0] uppercase drop-shadow-md md:text-8xl lg:text-[110px]">
              VARUNA
            </h1>
            <p className="mx-auto max-w-2xl text-lg font-medium leading-relaxed text-neutral-200 drop-shadow md:text-xl">
              Varuna looks at the sea surface from satellites and works out the temperature below it, at 15 depths down to 1000 m, across the North Indian Ocean.
            </p>
          </div>

          {/* Navigation Action Buttons */}
          <div className="flex flex-wrap items-center justify-center gap-3.5 pt-4 pointer-events-auto">
            <Link
              href="/section"
              className="group relative flex items-center gap-2.5 rounded-full bg-gradient-to-r from-cyan-500 via-teal-500 to-blue-600 px-7 py-3.5 text-sm font-bold uppercase tracking-wider text-white shadow-lg shadow-cyan-500/25 transition-all duration-300 hover:scale-[1.03] hover:shadow-cyan-500/40 active:scale-[0.98]"
            >
              <Spline size={18} className="text-cyan-100" />
              <span>OCEAN SECTION</span>
              <ArrowRight size={16} className="transition-transform group-hover:translate-x-1" />
            </Link>

            <Link
              href="/report"
              className="flex items-center gap-2 rounded-full border border-white/20 bg-white/[0.06] px-6 py-3.5 text-sm font-semibold tracking-wide text-white shadow-lg backdrop-blur-xl transition-all duration-300 hover:scale-[1.03] hover:border-white/30 hover:bg-white/[0.12]"
            >
              <BarChart3 size={16} className="text-cyan-400" />
              <span>VALIDATION REPORT</span>
            </Link>
          </div>

          <FeatureCards />

        </div>
      </main>
    </>
  );
}
