"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef } from "react";

interface FeatureModalProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  actionHref?: string;
  actionLabel?: string;
}

export function FeatureModal({
  isOpen,
  onOpenChange,
  title,
  description,
  actionHref,
  actionLabel,
}: FeatureModalProps) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const prefersReducedMotion = useReducedMotion();

  useEffect(() => {
    if (!isOpen) return;

    returnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusTimer = window.setTimeout(() => closeButtonRef.current?.focus(), 0);

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onOpenChange(false);
      if (event.key !== "Tab") return;

      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable?.length) {
        event.preventDefault();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      returnFocusRef.current?.focus();
      returnFocusRef.current = null;
    };
  }, [isOpen, onOpenChange]);

  return (
    <AnimatePresence>
      {isOpen ? (
        <motion.div
          className="pointer-events-auto fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-md"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: prefersReducedMotion ? 0 : 0.2 }}
          onClick={() => onOpenChange(false)}
          onPointerDown={(event) => event.stopPropagation()}
        >
          <motion.section
            ref={dialogRef}
            aria-labelledby="feature-modal-title"
            aria-modal="true"
            className="relative max-h-[calc(100dvh-2rem)] w-full max-w-lg overflow-y-auto rounded-[28px] border border-white/15 bg-neutral-950/40 p-5 text-white shadow-[0_16px_40px_rgba(0,0,0,0.6)] backdrop-blur-2xl sm:p-8"
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98, y: 10 }}
            transition={prefersReducedMotion ? { duration: 0 } : { type: "spring", stiffness: 320, damping: 24 }}
            role="dialog"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              ref={closeButtonRef}
              aria-label="Close dialog"
              className="absolute right-5 top-5 grid size-10 place-items-center rounded-full border border-white/15 bg-white/5 text-white transition hover:bg-white/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
              type="button"
              onClick={() => onOpenChange(false)}
            >
              <X aria-hidden="true" size={18} />
            </button>

            <div className="pr-12">
              <h2 id="feature-modal-title" className="text-2xl font-semibold tracking-tight">
                {title}
              </h2>
              <p className="mt-3 leading-relaxed text-white/70">{description}</p>
            </div>

            <div className="mt-8 flex flex-wrap justify-end gap-3 border-t border-white/15 pt-5">
              {actionHref && actionLabel ? (
                <Link
                  className="rounded-full border border-cyan-200/30 bg-cyan-300/10 px-5 py-2.5 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-300/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
                  href={actionHref}
                >
                  {actionLabel}
                </Link>
              ) : null}
              <button
                className="rounded-full bg-cyan-300 px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
                type="button"
                onClick={() => onOpenChange(false)}
              >
                Got it
              </button>
            </div>
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
