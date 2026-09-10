import { Suspense } from "react";
import { SectionDashboard } from "@/components/section/section-dashboard";

export const metadata = {
  title: "Ocean Vertical Section | Varuna",
  description:
    "Interactive vertical cross-section of North Indian Ocean temperature stratification, thermocline D20, and mixed layer depth.",
};

export default function SectionPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center font-mono text-xs text-cyan-200">
          Loading ocean section...
        </div>
      }
    >
      <SectionDashboard />
    </Suspense>
  );
}
