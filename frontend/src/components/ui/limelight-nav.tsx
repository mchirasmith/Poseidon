"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, useReducedMotion } from "framer-motion";
import { Home, ScrollText, Spline } from "lucide-react";
import { cn } from "@/lib/utils";

const navigationItems = [
  { href: "/", label: "Home", icon: Home },
  { href: "/report", label: "Validation report", icon: ScrollText },
  { href: "/section", label: "Ocean section", icon: Spline },
] as const;

/** Shared route navigation with a moving limelight that follows the active page. */
export function LimelightNav({ className }: { className?: string }) {
  const pathname = usePathname();
  const prefersReducedMotion = useReducedMotion();

  return (
    <nav aria-label="Primary navigation" className={cn("relative inline-flex h-14 items-center rounded-2xl border border-white/15 bg-slate-950/55 px-1.5 text-white shadow-[0_12px_32px_rgba(0,0,0,0.3),inset_0_1px_0_rgba(255,255,255,0.16)] backdrop-blur-2xl", className)}>
      {navigationItems.map((item) => {
        const Icon = item.icon;
        const active = pathname === item.href;

        return (
          <Link aria-current={active ? "page" : undefined} aria-label={item.label} className="relative z-10 grid size-11 place-items-center rounded-xl text-white/55 outline-none transition-colors hover:text-white focus-visible:ring-2 focus-visible:ring-cyan-100 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950" href={item.href} key={item.href} title={item.label}>
            {active ? (
              <motion.span aria-hidden="true" className="pointer-events-none absolute inset-x-2 top-0 h-1 rounded-full bg-cyan-200 shadow-[0_14px_18px_rgba(103,232,249,0.78)]" layoutId="poseidon-nav-limelight" transition={prefersReducedMotion ? { duration: 0 } : { type: "spring", stiffness: 380, damping: 30 }}>
                <span className="absolute left-[-35%] top-1 h-10 w-[170%] bg-gradient-to-b from-cyan-200/20 to-transparent [clip-path:polygon(10%_100%,28%_0,72%_0,90%_100%)]" />
              </motion.span>
            ) : null}
            <Icon aria-hidden="true" className={active ? "text-cyan-50" : undefined} size={20} strokeWidth={active ? 2.25 : 1.8} />
            <span className="sr-only">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
