"use client";

import React, { useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { 
  motion, 
  useMotionValue, 
  useMotionTemplate, 
  useAnimationFrame 
} from "framer-motion";

interface InfiniteGridProps {
  children?: React.ReactNode;
  className?: string;
  theme?: "trackshift" | "ocean";
}

export const TheInfiniteGrid = ({ 
  children, 
  className,
  theme = "ocean" 
}: InfiniteGridProps) => {
  const containerRef = useRef<HTMLDivElement>(null);

  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const { left, top } = e.currentTarget.getBoundingClientRect();
    mouseX.set(e.clientX - left);
    mouseY.set(e.clientY - top);
  };

  const gridOffsetX = useMotionValue(0);
  const gridOffsetY = useMotionValue(0);

  const speedX = 0.5; 
  const speedY = 0.5;

  useAnimationFrame(() => {
    const currentX = gridOffsetX.get();
    const currentY = gridOffsetY.get();
    gridOffsetX.set((currentX + speedX) % 40);
    gridOffsetY.set((currentY + speedY) % 40);
  });

  const maskImage = useMotionTemplate`radial-gradient(600px circle at ${mouseX}px ${mouseY}px, black, transparent)`;

  const gradientClasses = theme === "ocean" 
    ? "from-blue-500/30 via-cyan-500/20 to-teal-500/30" 
    : "from-blue-500/30 to-red-500/30";

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      className={cn(
        "relative w-full min-h-screen flex flex-col overflow-x-hidden bg-black",
        className
      )}
    >
      <div className="absolute inset-0 z-0 opacity-[0.05]">
        <GridPattern offsetX={gridOffsetX} offsetY={gridOffsetY} theme={theme} />
      </div>
      <motion.div 
        className="absolute inset-0 z-0 opacity-80"
        style={{ maskImage, WebkitMaskImage: maskImage }}
      >
        <div className={cn("absolute inset-0 bg-gradient-to-r", gradientClasses)} />
        <GridPattern offsetX={gridOffsetX} offsetY={gridOffsetY} theme={theme} />
      </motion.div>

      <div className="relative z-10 flex flex-col w-full h-full pointer-events-auto">
        {children}
      </div>
    </div>
  );
};

const GridPattern = ({ 
  offsetX, 
  offsetY, 
  id = "grid",
  theme = "ocean" 
}: { 
  offsetX: import('framer-motion').MotionValue<number>; 
  offsetY: import('framer-motion').MotionValue<number>; 
  id?: string;
  theme?: "trackshift" | "ocean";
}) => {
  const stopColor1 = "#3b82f6";
  const stopColor2 = theme === "ocean" ? "#06b6d4" : "#ef4444";

  return (
    <svg className="w-full h-full">
      <defs>
        <linearGradient id={`${id}-grad`} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor={stopColor1} />
          <stop offset="100%" stopColor={stopColor2} />
        </linearGradient>
        <motion.pattern
          id={`${id}-pattern`}
          width="40"
          height="40"
          patternUnits="userSpaceOnUse"
          x={offsetX}
          y={offsetY}
        >
          <path
            d="M 40 0 L 0 0 0 40"
            fill="none"
            stroke={`url(#${id}-grad)`}
            strokeWidth="1"
            className="opacity-40"
          />
        </motion.pattern>
      </defs>
      <rect width="100%" height="100%" fill={`url(#${id}-pattern)`} />
    </svg>
  );
};

/**
 * The drifting grid plus cursor spotlight, toned down for cards or modal backdrops.
 */
export const SubtleGridBackground = ({ 
  id = "card-grid",
  theme = "ocean" 
}: { 
  id?: string;
  theme?: "trackshift" | "ocean";
}) => {
  const ref = useRef<HTMLDivElement>(null);
  const offsetX = useMotionValue(0);
  const offsetY = useMotionValue(0);
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  useAnimationFrame(() => {
    offsetX.set((offsetX.get() + 0.5) % 40);
    offsetY.set((offsetY.get() + 0.5) % 40);
  });

  useEffect(() => {
    const rect = ref.current?.getBoundingClientRect();
    if (rect) {
      mouseX.set(rect.width / 2);
      mouseY.set(rect.height / 2);
    }

    const handleMouseMove = (e: MouseEvent) => {
      const bounds = ref.current?.getBoundingClientRect();
      if (!bounds) return;
      mouseX.set(e.clientX - bounds.left);
      mouseY.set(e.clientY - bounds.top);
    };

    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, [mouseX, mouseY]);

  const maskImage = useMotionTemplate`radial-gradient(600px circle at ${mouseX}px ${mouseY}px, black, transparent)`;
  const gradientClasses = theme === "ocean" 
    ? "from-blue-500/30 via-cyan-500/20 to-teal-500/30" 
    : "from-blue-500/30 to-red-500/30";

  return (
    <div ref={ref} className="absolute inset-0 z-0 pointer-events-none">
      <div className="absolute inset-0 opacity-[0.13]">
        <GridPattern offsetX={offsetX} offsetY={offsetY} id={id} theme={theme} />
      </div>
      <motion.div
        className="absolute inset-0 opacity-70"
        style={{ maskImage, WebkitMaskImage: maskImage }}
      >
        <div className={cn("absolute inset-0 bg-gradient-to-r", gradientClasses)} />
        <GridPattern offsetX={offsetX} offsetY={offsetY} id={`${id}-lit`} theme={theme} />
      </motion.div>
    </div>
  );
};
