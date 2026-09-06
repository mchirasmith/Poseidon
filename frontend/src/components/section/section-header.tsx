"use client";

import Link from "next/link";
import { ArrowLeft, ChevronLeft, ChevronRight } from "lucide-react";
import type { TransectPreset } from "@/lib/section";

interface SectionHeaderProps {
  date: string;
  preset?: TransectPreset;
  totalDistanceKm: number;
  isLoading?: boolean;
  onDateChange: (date: string) => void;
}

export function SectionHeader({
  date,
  preset,
  totalDistanceKm,
  onDateChange,
}: SectionHeaderProps) {
  const stepDate = (days: number) => {
    const d = new Date(date);
    d.setDate(d.getDate() + days);
    const minDate = new Date("2019-01-01");
    const maxDate = new Date("2020-12-31");
    const clamped = d < minDate ? minDate : d > maxDate ? maxDate : d;
    onDateChange(clamped.toISOString().split("T")[0]);
  };

  return (
    <header className="flex flex-col gap-5 border-b border-white/15 pb-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-4">
        <Link
          aria-label="Back to Poseidon home"
          className="grid size-10 place-items-center rounded-full border border-white/20 bg-white/[0.05] text-white/80 shadow-[inset_0_1px_1px_rgba(255,255,255,0.35)] backdrop-blur-xl transition-all duration-200 hover:scale-105 hover:border-white/40 hover:bg-white/[0.10] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200"
          href="/"
        >
          <ArrowLeft aria-hidden="true" size={18} />
        </Link>
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.22em] text-cyan-200/80">
            Poseidon / section · {preset?.name || "Custom Transect"} ({totalDistanceKm} km)
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl text-white">
            Ocean vertical section
          </h1>
        </div>
      </div>

      <div className="flex items-center">
        {/* Date Selector Strip (Clean, without blue icon) */}
        <div className="flex items-center rounded-xl border border-white/20 bg-white/[0.04] p-1 shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)] backdrop-blur-xl">
          <button
            type="button"
            onClick={() => stepDate(-1)}
            aria-label="Previous day"
            className="p-1.5 text-white/70 hover:text-white rounded-lg hover:bg-white/10 transition-colors"
          >
            <ChevronLeft size={16} />
          </button>

          <div className="flex items-center px-2.5">
            <input
              type="date"
              min="2019-01-01"
              max="2020-12-31"
              value={date}
              onChange={(e) => onDateChange(e.target.value)}
              className="bg-transparent font-mono text-xs font-semibold text-white focus:outline-none cursor-pointer"
            />
          </div>

          <button
            type="button"
            onClick={() => stepDate(1)}
            aria-label="Next day"
            className="p-1.5 text-white/70 hover:text-white rounded-lg hover:bg-white/10 transition-colors"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </header>
  );
}
