"use client";

import { TrackShiftSpinner } from "@/components/ui/trackshift-spinner";

interface SectionLoaderProps {
  date?: string;
  isFullPage?: boolean;
}

export function SectionLoader({ date, isFullPage = false }: SectionLoaderProps) {
  return (
    <TrackShiftSpinner
      isLoading={true}
      title={date ? `Reconstructing Vertical Section · ${date}` : "Computing Vertical Section"}
      subtitle={
        date
          ? `Inverting 15-layer temperature stratification from surface satellite fields for ${date}...`
          : "Running Varuna neural inversion across 15 depth tiers, please wait (this takes a few seconds)..."
      }
      isFullPage={isFullPage}
    />
  );
}
