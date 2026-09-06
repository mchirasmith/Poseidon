# KineticGrid integration note

## Readiness and default paths

This repository already satisfies the component prerequisites:

- Next.js 16.3, React 19, TypeScript, and Tailwind CSS v4 are installed in [`frontend/package.json`](../frontend/package.json).
- shadcn configuration exists in [`frontend/components.json`](../frontend/components.json), with TypeScript enabled and the `@/components/ui` alias configured.
- Components belong in [`frontend/src/components/ui`](../frontend/src/components/ui); global styles live in [`frontend/src/app/globals.css`](../frontend/src/app/globals.css).
- `cn` is already available at [`frontend/src/lib/utils.ts`](../frontend/src/lib/utils.ts).

No shadcn, Tailwind, TypeScript, image, icon, or additional package installation is required for this component. It uses the browser Canvas 2D API and React only.

## Chosen integration

`frontend/src/components/ui/kinetic-grid.tsx` is implemented and wraps the app in `frontend/src/app/layout.tsx`, replacing the previous site-wide `TheInfiniteGrid`. The globally mounted canvas owns and renders the page surface and kinetic grid together; it is intended to be reusable for a future Layers page, which has not been built.

`the-infinite-grid.tsx` remains in the repository as legacy code. Only its card-level `SubtleGridBackground` mounts were removed from the landing page.

In the default theme, `KineticGrid` renders this exact global vertical surface: `#FFDDB0` → `#E3F2FD` → `#90CAF9` → `#2196F3` → `#0D47A1`. Its default grid marks use depth-aware contrast across that surface.

To keep the same palette useful as an application background, the canvas applies a stronger neutral translucent navy wash (`rgba(2, 18, 36, 0.42)`) after drawing those exact stops. This preserves the shallow-to-deep ocean sequence while making it a darker, more atmospheric surface. Current default grid lines and nodes are deliberately subdued, becoming lighter toward the deeper end of the surface; the cyan cursor warp and ripple treatment remain the high-visibility interaction cue.

## Public API

`KineticGrid` accepts:

| Prop | Type | Purpose |
| --- | --- | --- |
| `children` | `ReactNode` (optional) | Foreground page content rendered above the canvas. |
| `className` | `string` (optional) | Additional wrapper styles, merged through `cn`. |
| `globalColor` | `"default" | "monochrome"` (optional) | Chooses the five-stop ocean surface with depth-aware blue/cyan grid marks (`default`) or a black surface with white grid marks (`monochrome`). Defaults to `default`. |

It does not need a context provider, external assets, images, SVGs, or icons. Its internal refs track the canvas, current/target mouse point, ripple list, animation-frame handle, and viewport size. The component uses `useEffect` for browser event setup and cleanup, `useCallback` for drawing/animation functions, and `requestAnimationFrame` for continuous rendering; it must keep its `"use client"` directive.

## Interaction, responsiveness, and constraints

- It fills the viewport, eases the grid toward the pointer, and adds a ripple for every pointer press (mouse, touch, or stylus).
- It listens to `window` resize, caps canvas device-pixel ratio at 2, and remains responsive across desktop, tablet, and narrow viewport widths. It is a background, not a replacement for responsive page layouts.
- The canvas is `aria-hidden` and has `pointer-events-none`; page controls and foreground content remain above it.
- `prefers-reduced-motion` is implemented: the component stops animation and draws a static grid. It also stops animation while the document is hidden and resumes when visible.
- Continuous full-viewport canvas redraws still merit profiling on the demo machine, especially alongside future Explorer and Section interfaces.

## Accessibility and QA checklist

- [ ] Confirm keyboard focus, link/button clicks, and screen-reader content remain available above the canvas.
- [ ] Verify the background does not obscure text at desktop, tablet, and narrow widths.
- [ ] Verify pointer warp and pointer-press ripples work after resize and do not intercept controls.
- [ ] Verify animation-frame and window listeners clean up after navigation.
- [ ] Test `default` and `monochrome` contrast with the actual foreground content.
- [ ] Test reduced-motion static rendering and pause/resume after tab visibility changes.
- [ ] Run `npm run lint` and `npm run build` after integration.
- [ ] Review CPU/GPU use on the demo machine with the Explorer/Section interfaces open.

The supplied demo content is illustrative only. This repository currently has no image-asset requirement for `KineticGrid`, and Lucide should not be added unless another UI control actually needs an icon.
