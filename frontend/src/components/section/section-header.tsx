"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { format } from "date-fns";
import { ArrowLeft, CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { GlassCalendar } from "@/components/ui/glass-calendar";
import type { TransectPreset } from "@/lib/section";

interface SectionHeaderProps {
  date: string;
  /** Days with precomputed fields in the static bundle, ascending ISO dates. */
  availableDates: string[];
  dayLabel?: string;
  preset?: TransectPreset;
  totalDistanceKm: number;
  isLoading?: boolean;
  onDateChange: (date: string) => void;
}

/** Parses `YYYY-MM-DD` in local time so day comparisons never shift across timezones. */
function parseISODate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function SectionHeader({
  date,
  availableDates,
  dayLabel,
  preset,
  totalDistanceKm,
  onDateChange,
}: SectionHeaderProps) {
  const [isCalendarOpen, setIsCalendarOpen] = useState(false);
  const pickerRef = useRef<HTMLDivElement | null>(null);
  const selectedDate = useMemo(() => parseISODate(date), [date]);
  const availableSet = useMemo(() => new Set(availableDates), [availableDates]);
  const minDate = useMemo(() => parseISODate(availableDates[0] ?? "2019-01-01"), [availableDates]);
  const maxDate = useMemo(() => parseISODate(availableDates[availableDates.length - 1] ?? "2020-12-31"), [availableDates]);
  const isDateDisabled = useCallback((d: Date) => !availableSet.has(format(d, "yyyy-MM-dd")), [availableSet]);

  /** Previous or next bundled day; the arrows never land on a day without data. */
  const stepDate = (direction: number) => {
    const idx = availableDates.indexOf(date);
    const next = availableDates[(idx < 0 ? 0 : idx) + direction];
    if (next) onDateChange(next);
  };

  const handleDateSelect = useCallback(
    (next: Date) => {
      onDateChange(format(next, "yyyy-MM-dd"));
      setIsCalendarOpen(false);
    },
    [onDateChange]
  );

  // Dismiss the calendar on outside click or Escape
  useEffect(() => {
    if (!isCalendarOpen) return;

    const handlePointerDown = (event: PointerEvent) => {
      if (!pickerRef.current?.contains(event.target as Node)) setIsCalendarOpen(false);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsCalendarOpen(false);
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isCalendarOpen]);

  return (
    <header className="flex flex-col gap-5 border-b border-white/15 pb-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-4">
        <Link
          aria-label="Back to Varuna home"
          className="grid size-10 place-items-center rounded-full border border-white/20 bg-white/[0.05] text-white/80 shadow-[inset_0_1px_1px_rgba(255,255,255,0.35)] backdrop-blur-xl transition-all duration-200 hover:scale-105 hover:border-white/40 hover:bg-white/[0.10] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200"
          href="/"
        >
          <ArrowLeft aria-hidden="true" size={18} />
        </Link>
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.22em] text-cyan-200/80">
            Varuna / section · {preset?.name || "Custom Transect"} ({totalDistanceKm} km)
            {dayLabel ? ` · ${dayLabel}` : ""}
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl text-white">
            Ocean vertical section
          </h1>
        </div>
      </div>

      <div ref={pickerRef} className="relative flex items-center">
        {/* Date Selector Strip */}
        <div className="flex items-center rounded-xl border border-white/20 bg-white/[0.04] p-1 shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)] backdrop-blur-xl">
          <button
            type="button"
            onClick={() => stepDate(-1)}
            aria-label="Previous curated day"
            className="p-1.5 text-white/70 hover:text-white rounded-lg hover:bg-white/10 transition-colors"
          >
            <ChevronLeft size={16} />
          </button>

          <button
            type="button"
            onClick={() => setIsCalendarOpen((open) => !open)}
            aria-expanded={isCalendarOpen}
            aria-haspopup="dialog"
            aria-label={`Change section date, currently ${format(selectedDate, "d MMMM yyyy")}`}
            className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 font-mono text-xs font-semibold text-white transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200 ${
              isCalendarOpen ? "bg-white/10" : ""
            }`}
          >
            <CalendarDays aria-hidden="true" size={14} className="text-cyan-300" />
            <span>{format(selectedDate, "dd MMM yyyy")}</span>
          </button>

          <button
            type="button"
            onClick={() => stepDate(1)}
            aria-label="Next curated day"
            className="p-1.5 text-white/70 hover:text-white rounded-lg hover:bg-white/10 transition-colors"
          >
            <ChevronRight size={16} />
          </button>
        </div>

        {isCalendarOpen && (
          <GlassCalendar
            role="dialog"
            aria-label="Section date picker"
            selectedDate={selectedDate}
            onDateSelect={handleDateSelect}
            minDate={minDate}
            maxDate={maxDate}
            isDateDisabled={isDateDisabled}
            className="absolute right-0 top-full z-50 mt-2 w-[340px]"
          />
        )}
      </div>
    </header>
  );
}
