"use client";

import { motion, AnimatePresence } from "framer-motion";

interface TrackShiftSpinnerProps {
  isLoading: boolean;
  title?: string;
  subtitle?: string;
  isFullPage?: boolean;
}

export function TrackShiftSpinner({
  isLoading,
  title = "Computing Optimal Reconstruction",
  subtitle = "Running Poseidon neural model, please wait (this takes a few seconds)",
  isFullPage = true,
}: TrackShiftSpinnerProps) {
  return (
    <AnimatePresence>
      {isLoading && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className={
            isFullPage
              ? "fixed inset-0 z-[200] flex flex-col items-center justify-center bg-black/75 backdrop-blur-md text-white select-none px-4"
              : "absolute inset-0 z-50 flex flex-col items-center justify-center rounded-2xl bg-black/65 backdrop-blur-md text-white select-none px-4"
          }
        >
          {/* Exact TrackShift Glowing Dual-Border Spinner */}
          <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-cyan-400 mb-6 shadow-[0_0_24px_rgba(34,211,238,0.55)]" />
          
          <h2 className="text-xl font-bold tracking-widest uppercase text-white drop-shadow-md text-center">
            {title}
          </h2>
          <p className="text-white/40 mt-3 text-sm font-sans tracking-wide text-center max-w-md">
            {subtitle}
          </p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
