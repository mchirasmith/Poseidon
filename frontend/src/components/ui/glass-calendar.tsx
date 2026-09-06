"use client";

import * as React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  format,
  addDays,
  addMonths,
  addWeeks,
  subMonths,
  subWeeks,
  startOfWeek,
  endOfWeek,
  startOfMonth,
  endOfMonth,
  getDate,
  getDay,
  getDaysInMonth,
  getYear,
  setYear,
  isSameDay,
  isToday,
} from "date-fns";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

// --- TYPE DEFINITIONS ---
type ViewMode = "weekly" | "monthly";

interface Day {
  date: Date;
  isToday: boolean;
  isSelected: boolean;
  isDisabled: boolean;
}

interface GlassCalendarProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "onSelect"> {
  selectedDate?: Date;
  onDateSelect?: (date: Date) => void;
  /** Earliest selectable day, inclusive. */
  minDate?: Date;
  /** Latest selectable day, inclusive. */
  maxDate?: Date;
  /** Extra per-day rule, e.g. only days with precomputed data. */
  isDateDisabled?: (date: Date) => boolean;
  className?: string;
}

/** Start of the range on screen for a given anchor and mode. */
function rangeStartOf(anchor: Date, mode: ViewMode): Date {
  return mode === "weekly" ? startOfWeek(anchor) : startOfMonth(anchor);
}

/** End of the range on screen for a given anchor and mode. */
function rangeEndOf(anchor: Date, mode: ViewMode): Date {
  return mode === "weekly" ? endOfWeek(anchor) : endOfMonth(anchor);
}

// --- MAIN COMPONENT ---
export const GlassCalendar = React.forwardRef<HTMLDivElement, GlassCalendarProps>(
  ({ className, selectedDate: propSelectedDate, onDateSelect, minDate, maxDate, isDateDisabled, ...props }, ref) => {
    const selectedDate = React.useMemo(() => propSelectedDate ?? new Date(), [propSelectedDate]);
    const [viewMode, setViewMode] = React.useState<ViewMode>("weekly");

    // Anchor day the visible week or month is derived from. `syncedTo` lets the
    // view follow a selected date that changes outside the calendar (e.g. the
    // header's day stepper) without discarding manual navigation.
    const [view, setView] = React.useState({ anchor: selectedDate, syncedTo: selectedDate });
    if (!isSameDay(view.syncedTo, selectedDate)) {
      const inRange =
        selectedDate >= rangeStartOf(view.anchor, viewMode) &&
        selectedDate <= rangeEndOf(view.anchor, viewMode);
      setView({ anchor: inRange ? view.anchor : selectedDate, syncedTo: selectedDate });
    }
    const anchor = view.anchor;

    // Days of the visible week or month
    const days = React.useMemo(() => {
      const isWeekly = viewMode === "weekly";
      const start = rangeStartOf(anchor, viewMode);
      const total = isWeekly ? 7 : getDaysInMonth(anchor);
      const result: Day[] = [];
      for (let i = 0; i < total; i++) {
        const date = isWeekly
          ? addDays(start, i)
          : new Date(start.getFullYear(), start.getMonth(), i + 1);
        result.push({
          date,
          isToday: isToday(date),
          isSelected: isSameDay(date, selectedDate),
          isDisabled: Boolean((minDate && date < minDate) || (maxDate && date > maxDate) || isDateDisabled?.(date)),
        });
      }
      return result;
    }, [anchor, viewMode, selectedDate, minDate, maxDate, isDateDisabled]);

    // Narrow weekday initials in locale order (S M T W T F S)
    const weekdayInitials = React.useMemo(() => {
      const start = startOfWeek(new Date());
      return Array.from({ length: 7 }, (_, i) => format(addDays(start, i), "EEEEE"));
    }, []);

    // Selectable years, bounded by minDate/maxDate when the caller supplies them
    const years = React.useMemo(() => {
      const viewedYear = getYear(anchor);
      const first = minDate ? getYear(minDate) : viewedYear - 10;
      const last = maxDate ? getYear(maxDate) : viewedYear + 10;
      return Array.from({ length: last - first + 1 }, (_, i) => first + i);
    }, [anchor, minDate, maxDate]);

    const stepBack = viewMode === "weekly" ? subWeeks : subMonths;
    const stepForward = viewMode === "weekly" ? addWeeks : addMonths;
    const canGoPrev = !minDate || rangeEndOf(stepBack(anchor, 1), viewMode) >= minDate;
    const canGoNext = !maxDate || rangeStartOf(stepForward(anchor, 1), viewMode) <= maxDate;

    const handleDateClick = (date: Date) => {
      onDateSelect?.(date);
    };

    const handlePrev = () => {
      setView((v) => ({ ...v, anchor: stepBack(v.anchor, 1) }));
    };

    const handleNext = () => {
      setView((v) => ({ ...v, anchor: stepForward(v.anchor, 1) }));
    };

    const handleYearChange = (year: number) => {
      setView((v) => {
        let next = setYear(v.anchor, year);
        if (minDate && next < minDate) next = minDate;
        if (maxDate && next > maxDate) next = maxDate;
        return { ...v, anchor: next };
      });
    };

    const renderDay = (day: Day) => (
      <button
        key={format(day.date, "yyyy-MM-dd")}
        onClick={() => handleDateClick(day.date)}
        disabled={day.isDisabled}
        aria-label={format(day.date, "d MMMM yyyy")}
        aria-current={day.isSelected ? "date" : undefined}
        className={cn(
          "flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold transition-all duration-200 relative",
          {
            "bg-gradient-to-br from-[#1E577C] to-[#124370] text-white ring-1 ring-white/40 shadow-[0_6px_18px_rgba(30,87,124,0.65)]":
              day.isSelected,
            "hover:bg-white/20": !day.isSelected && !day.isDisabled,
            "text-white": !day.isSelected,
            "cursor-not-allowed text-white/25": day.isDisabled,
          }
        )}
      >
        {day.isToday && !day.isSelected && (
          <span className="absolute bottom-1 h-1 w-1 rounded-full bg-cyan-300"></span>
        )}
        {getDate(day.date)}
      </button>
    );

    return (
      <div
        ref={ref}
        className={cn(
          "w-full max-w-[360px] rounded-3xl p-5 overflow-hidden",
          "bg-white/12 backdrop-blur-2xl border border-white/25",
          "shadow-[0_24px_60px_rgba(0,0,0,0.45),inset_0_1px_0_rgba(255,255,255,0.25)]",
          "text-white font-sans",
          className
        )}
        {...props}
      >
        {/* Header: Range Tabs */}
        <div
          role="tablist"
          aria-label="Calendar range"
          className="flex w-fit items-center space-x-1 rounded-lg bg-white/10 p-1"
        >
          {(["weekly", "monthly"] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              role="tab"
              aria-selected={viewMode === tab}
              onClick={() => setViewMode(tab)}
              className={cn(
                "rounded-md px-4 py-1 text-xs capitalize transition-colors",
                viewMode === tab
                  ? "bg-white font-bold text-slate-900 shadow-md"
                  : "font-semibold text-white/65 hover:text-white"
              )}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Date Display and Navigation */}
        <div className="my-6 flex items-center justify-between">
          <div className="flex items-baseline gap-2">
            <motion.p
              key={format(anchor, "MMMM yyyy")}
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className="text-4xl font-bold tracking-tight"
            >
              {format(anchor, "MMMM")}
            </motion.p>
            <select
              aria-label="Year"
              value={getYear(anchor)}
              onChange={(e) => handleYearChange(Number(e.target.value))}
              className="cursor-pointer rounded-md bg-white/10 px-1.5 py-0.5 text-base font-semibold text-white/80 transition-colors hover:bg-white/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
            >
              {years.map((year) => (
                <option key={year} value={year} className="bg-slate-900 text-white">
                  {year}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={handlePrev}
              disabled={!canGoPrev}
              aria-label={viewMode === "weekly" ? "Previous week" : "Previous month"}
              className="p-1 rounded-full text-white/70 transition-colors hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-25 disabled:hover:bg-transparent"
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
            <button
              onClick={handleNext}
              disabled={!canGoNext}
              aria-label={viewMode === "weekly" ? "Next week" : "Next month"}
              className="p-1 rounded-full text-white/70 transition-colors hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-25 disabled:hover:bg-transparent"
            >
              <ChevronRight className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Day Grid */}
        {viewMode === "weekly" ? (
          <div className="flex items-start justify-between">
            {days.map((day) => (
              <div
                key={format(day.date, "yyyy-MM-dd")}
                className="flex flex-col items-center space-y-2"
              >
                <span className="text-xs font-bold text-white/65">
                  {format(day.date, "EEEEE")}
                </span>
                {renderDay(day)}
              </div>
            ))}
          </div>
        ) : (
          <div>
            <div className="grid grid-cols-7 place-items-center">
              {weekdayInitials.map((initial, i) => (
                <span key={i} className="text-xs font-bold text-white/65">
                  {initial}
                </span>
              ))}
            </div>
            <div className="mt-2 grid grid-cols-7 place-items-center gap-y-1.5">
              {Array.from({ length: getDay(startOfMonth(anchor)) }, (_, i) => (
                <span key={`blank-${i}`} aria-hidden="true" />
              ))}
              {days.map(renderDay)}
            </div>
          </div>
        )}
      </div>
    );
  }
);

GlassCalendar.displayName = "GlassCalendar";
