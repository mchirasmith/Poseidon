"use client";

import { useCallback, useEffect, useRef, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

interface Point {
  x: number;
  y: number;
}

interface Ripple {
  x: number;
  y: number;
  radius: number;
  opacity: number;
  born: number;
}

interface Color {
  r: number;
  g: number;
  b: number;
  a: number;
}

const CELL_SIZE = 55;
const INFLUENCE_RADIUS = 260;
const MAX_WARP = 24;
const DOT_SPACING = 28;
const LERP_SPEED = 0.08;
const MAX_DEVICE_PIXEL_RATIO = 2;

const NODE_BASE_RADIUS = 1.8;
const NODE_ACTIVE_RADIUS = 3.2;

function lerpN(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function lerpColor(base: Color, active: Color, t: number) {
  const r = Math.round(lerpN(base.r, active.r, t));
  const g = Math.round(lerpN(base.g, active.g, t));
  const b = Math.round(lerpN(base.b, active.b, t));
  const a = lerpN(base.a, active.a, t);
  return `rgba(${r},${g},${b},${a.toFixed(3)})`;
}

export default function KineticGrid({
  children,
  className,
  globalColor = "default",
  staticGrid,
}: {
  children?: ReactNode;
  className?: string;
  globalColor?: "default" | "monochrome";
  staticGrid?: boolean;
}) {
  const pathname = usePathname();
  const normalizedPath = pathname ? pathname.replace(/\/+$/, "") || "/" : "/";
  const isStatic = staticGrid !== undefined ? staticGrid : false;

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouseRef = useRef<Point>({ x: -9999, y: -9999 });
  const targetMouseRef = useRef<Point>({ x: -9999, y: -9999 });
  const ripplesRef = useRef<Ripple[]>([]);
  const rafRef = useRef<number | null>(null);
  const sizeRef = useRef({ w: 0, h: 0, dpr: 1 });
  const reducedMotionRef = useRef(false);
  const visibleRef = useRef(true);

  const getWarpedPoint = useCallback(
    (
      gx: number,
      gy: number,
      col: number,
      row: number,
      mouse: Point,
      ripples: Ripple[],
      cols: number,
      rows: number,
    ): { pt: Point; proximity: number } => {
      const edgeMargin = 1.5;
      const colPin = Math.min(col / edgeMargin, (cols - 1 - col) / edgeMargin, 1);
      const rowPin = Math.min(row / edgeMargin, (rows - 1 - row) / edgeMargin, 1);
      const pinFactor = colPin * colPin * rowPin * rowPin;

      const dx = gx - mouse.x;
      const dy = gy - mouse.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const proximity = Math.max(0, 1 - dist / INFLUENCE_RADIUS) * pinFactor;

      let rx = 0;
      let ry = 0;
      for (const ripple of ripples) {
        const rdx = gx - ripple.x;
        const rdy = gy - ripple.y;
        const rippleDistance = Math.sqrt(rdx * rdx + rdy * rdy);
        const waveWidth = 55;
        const difference = rippleDistance - ripple.radius;

        if (Math.abs(difference) < waveWidth) {
          const strength =
            (1 - Math.abs(difference) / waveWidth) * ripple.opacity * 18 * pinFactor;
          const angle = Math.atan2(rdy, rdx);
          const sign = difference < 0 ? -1 : 1;
          rx += Math.cos(angle) * strength * sign * -1;
          ry += Math.sin(angle) * strength * sign * -1;
        }
      }

      if (dist < INFLUENCE_RADIUS && dist > 0 && pinFactor > 0) {
        const t = dist / INFLUENCE_RADIUS;
        const eased = t < 0.01 ? 0 : (1 - t) * (1 - t) * Math.min(1, dist / 60);
        const warpAmount = eased * MAX_WARP * pinFactor;
        const angle = Math.atan2(dy, dx);
        return {
          pt: {
            x: gx - Math.cos(angle) * warpAmount + rx,
            y: gy - Math.sin(angle) * warpAmount + ry,
          },
          proximity,
        };
      }

      return { pt: { x: gx + rx, y: gy + ry }, proximity };
    },
    [],
  );

  const draw = useCallback(
    (now: number, isStatic = false) => {
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext("2d");
      if (!canvas || !ctx) return;

      const { w: W, h: H, dpr } = sizeRef.current;
      if (!W || !H) return;

      const theme = {
        default: {
          lineBase: { r: 50, g: 130, b: 200, a: 0.18 },
          nodeBase: { r: 60, g: 145, b: 215, a: 0.22 },
          lineActive: { r: 34, g: 211, b: 238, a: 0.9 },
          nodeActive: { r: 103, g: 232, b: 249, a: 1 },
          glow: "34,211,238",
          ripple: "103,232,249",
        },
        monochrome: {
          lineBase: { r: 255, g: 255, b: 255, a: 0.13 },
          nodeBase: { r: 255, g: 255, b: 255, a: 0.2 },
          lineActive: { r: 255, g: 255, b: 255, a: 0.9 },
          nodeActive: { r: 255, g: 255, b: 255, a: 1 },
          glow: "255,255,255",
          ripple: "255,255,255",
        },
      }[globalColor];

      const depthColor = (base: Color, y: number): Color => {
        const depth = Math.min(1, Math.max(0, y / H));
        return {
          r: Math.round(lerpN(base.r, 220, depth * 0.6)),
          g: Math.round(lerpN(base.g, 235, depth * 0.6)),
          b: Math.round(lerpN(base.b, 255, depth * 0.6)),
          a: lerpN(base.a, globalColor === "default" ? 0.22 : 0.2, depth),
        };
      };

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      const surface = ctx.createLinearGradient(0, 0, 0, H);
      if (globalColor === "default") {
        surface.addColorStop(0, "#9C6F42");
        surface.addColorStop(0.20, "#9C6F42");
        surface.addColorStop(0.48, "#1E577C");
        surface.addColorStop(0.70, "#124370");
        surface.addColorStop(0.88, "#0A2E59");
        surface.addColorStop(1, "#04132B");
      } else {
        surface.addColorStop(0, "#000000");
        surface.addColorStop(1, "#000000");
      }
      ctx.fillStyle = surface;
      ctx.fillRect(0, 0, W, H);
      if (globalColor === "default") {
        ctx.fillStyle = "rgba(1, 12, 28, 0.58)";
        ctx.fillRect(0, 0, W, H);
      }

      for (let x = DOT_SPACING / 2; x < W; x += DOT_SPACING) {
        for (let y = DOT_SPACING / 2; y < H; y += DOT_SPACING) {
          ctx.beginPath();
          ctx.arc(x, y, 0.7, 0, Math.PI * 2);
          ctx.fillStyle = lerpColor(depthColor(theme.lineBase, y), depthColor(theme.lineBase, y), 1);
          ctx.fill();
        }
      }

      const ripples = ripplesRef.current;
      if (!isStatic) {
        for (let index = ripples.length - 1; index >= 0; index -= 1) {
          const ripple = ripples[index];
          const age = (now - ripple.born) / 1000;
          ripple.radius = Math.max(0, age * 400);
          ripple.opacity = Math.max(0, 1 - age * 1.2);
          if (ripple.opacity <= 0) ripples.splice(index, 1);
        }
      }

      const cols = Math.max(2, Math.ceil(W / CELL_SIZE)) + 1;
      const rows = Math.max(2, Math.ceil(H / CELL_SIZE)) + 1;
      const cellW = W / (cols - 1);
      const cellH = H / (rows - 1);
      const mouse = isStatic ? { x: -9999, y: -9999 } : mouseRef.current;
      const activeRipples = isStatic ? [] : ripples;
      const points: Point[][] = [];
      const proximity: number[][] = [];

      for (let row = 0; row < rows; row += 1) {
        points[row] = [];
        proximity[row] = [];
        for (let col = 0; col < cols; col += 1) {
          const warped = getWarpedPoint(
            col * cellW,
            row * cellH,
            col,
            row,
            mouse,
            activeRipples,
            cols,
            rows,
          );
          points[row][col] = warped.pt;
          proximity[row][col] = warped.proximity;
        }
      }

      const drawSegment = (p1: Point, p2: Point, pr1: number, pr2: number) => {
        const average = (pr1 + pr2) / 2;
        const t = average * average * (3 - 2 * average);
        const base = depthColor(theme.lineBase, (p1.y + p2.y) / 2);
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.strokeStyle = lerpColor(base, theme.lineActive, t);
        ctx.lineWidth = lerpN(0.8, 1.5, t);
        ctx.stroke();
      };

      ctx.lineCap = "butt";
      for (let row = 0; row < rows; row += 1) {
        for (let col = 0; col < cols - 1; col += 1) {
          drawSegment(points[row][col], points[row][col + 1], proximity[row][col], proximity[row][col + 1]);
        }
      }
      for (let col = 0; col < cols; col += 1) {
        for (let row = 0; row < rows - 1; row += 1) {
          drawSegment(points[row][col], points[row + 1][col], proximity[row][col], proximity[row + 1][col]);
        }
      }

      for (let row = 0; row < rows; row += 1) {
        for (let col = 0; col < cols; col += 1) {
          const point = points[row][col];
          const pr = proximity[row][col];
          const t = pr * pr * (3 - 2 * pr);
          const radius = lerpN(NODE_BASE_RADIUS, NODE_ACTIVE_RADIUS, t);

          if (t > 0.3) {
            const glowRadius = radius + lerpN(0, 6, (t - 0.3) / 0.7);
            const gradient = ctx.createRadialGradient(point.x, point.y, radius * 0.5, point.x, point.y, glowRadius);
            gradient.addColorStop(0, `rgba(${theme.glow},${(t * 0.3).toFixed(3)})`);
            gradient.addColorStop(1, `rgba(${theme.glow},0)`);
            ctx.beginPath();
            ctx.arc(point.x, point.y, glowRadius, 0, Math.PI * 2);
            ctx.fillStyle = gradient;
            ctx.fill();
          }

          ctx.beginPath();
          ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
          ctx.fillStyle = lerpColor(depthColor(theme.nodeBase, point.y), theme.nodeActive, t);
          ctx.fill();
        }
      }

      if (!isStatic) {
        for (const ripple of ripples) {
          ctx.beginPath();
          ctx.arc(ripple.x, ripple.y, Math.max(0, ripple.radius), 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(${theme.ripple},${(ripple.opacity * 0.28).toFixed(3)})`;
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }
      }
    },
    [getWarpedPoint, globalColor],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    function animate(now: number) {
      rafRef.current = null;
      if (isStatic || reducedMotionRef.current || !visibleRef.current) return;

      mouseRef.current.x = lerpN(mouseRef.current.x, targetMouseRef.current.x, LERP_SPEED);
      mouseRef.current.y = lerpN(mouseRef.current.y, targetMouseRef.current.y, LERP_SPEED);
      draw(now, false);
      rafRef.current = requestAnimationFrame(animate);
    }

    const stopAnimation = () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };

    const startAnimation = () => {
      if (!isStatic && !reducedMotionRef.current && visibleRef.current && rafRef.current === null) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };

    const setSize = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      const dpr = Math.min(window.devicePixelRatio || 1, MAX_DEVICE_PIXEL_RATIO);
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      sizeRef.current = { w, h, dpr };
      draw(performance.now(), isStatic || reducedMotionRef.current);
    };

    const onPointerMove = (event: PointerEvent) => {
      if (isStatic || reducedMotionRef.current) return;
      targetMouseRef.current = { x: event.clientX, y: event.clientY };
    };

    const onPointerDown = (event: PointerEvent) => {
      if (isStatic || reducedMotionRef.current) return;
      ripplesRef.current.push({
        x: event.clientX,
        y: event.clientY,
        radius: 0,
        opacity: 1,
        born: performance.now(),
      });
      startAnimation();
    };

    const onVisibilityChange = () => {
      visibleRef.current = document.visibilityState === "visible";
      if (visibleRef.current) {
        if (isStatic || reducedMotionRef.current) draw(performance.now(), true);
        else startAnimation();
      } else {
        stopAnimation();
      }
    };

    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onMotionPreferenceChange = () => {
      reducedMotionRef.current = motionQuery.matches;
      if (isStatic || reducedMotionRef.current) {
        stopAnimation();
        ripplesRef.current = [];
        draw(performance.now(), true);
      } else {
        startAnimation();
      }
    };

    reducedMotionRef.current = motionQuery.matches;
    visibleRef.current = document.visibilityState === "visible";

    if (isStatic) {
      stopAnimation();
      ripplesRef.current = [];
      mouseRef.current = { x: -9999, y: -9999 };
      targetMouseRef.current = { x: -9999, y: -9999 };
      setSize();
    } else {
      setSize();
      startAnimation();
    }

    window.addEventListener("resize", setSize);
    if (!isStatic) {
      window.addEventListener("pointermove", onPointerMove, { passive: true });
      window.addEventListener("pointerdown", onPointerDown, { passive: true });
    }
    document.addEventListener("visibilitychange", onVisibilityChange);
    motionQuery.addEventListener("change", onMotionPreferenceChange);

    return () => {
      stopAnimation();
      window.removeEventListener("resize", setSize);
      if (!isStatic) {
        window.removeEventListener("pointermove", onPointerMove);
        window.removeEventListener("pointerdown", onPointerDown);
      }
      document.removeEventListener("visibilitychange", onVisibilityChange);
      motionQuery.removeEventListener("change", onMotionPreferenceChange);
    };
  }, [draw, isStatic]);

  return (
    <div
      className={cn(
        "relative min-h-screen w-full overflow-hidden",
        className,
      )}
    >
      <canvas
        ref={canvasRef}
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 z-0 h-full w-full"
      />
      <div className="relative z-10 h-full w-full">{children}</div>
    </div>
  );
}
