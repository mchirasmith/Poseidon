"""Render a 2D field to an RGBA PNG tile using a frozen colour scale.

Row 0 of the OUTPUT image is the northernmost latitude, because that is what the frontend's image tag expects to line up with a north-up map.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

SEAFLOOR_GREY = (128, 128, 128, 255)
SEAFLOOR_GREY_DARK = (96, 96, 96, 255)


def _colour_lookup(values: np.ndarray, cmap: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
    n = cmap.shape[0]
    safe = np.nan_to_num(values, nan=vmin)
    clipped = np.clip(safe, vmin, vmax)
    idx = ((clipped - vmin) / (vmax - vmin) * (n - 1)).astype(np.int64)
    return cmap[idx]


def render(
    array2d: np.ndarray,
    mode: str,
    scales: dict,
    wet: np.ndarray,
    bottom: np.ndarray | None = None,
) -> bytes:
    """Render one (H, W) field to RGBA PNG bytes per the shared colour scale."""
    array2d = np.asarray(array2d, dtype=np.float64)
    wet = np.asarray(wet).astype(bool)
    if bottom is None:
        bottom = np.ones_like(wet, dtype=bool)
    else:
        bottom = np.asarray(bottom).astype(bool)

    h, w = array2d.shape
    scale = scales[mode]
    cmap = np.asarray(scale["cmap"], dtype=np.uint8)
    vmin, vmax = scale["vmin"], scale["vmax"]

    rgb = _colour_lookup(array2d, cmap, vmin, vmax)
    alpha = np.full((h, w), 255, dtype=np.uint8)
    rgba = np.dstack([rgb, alpha]).astype(np.uint8)

    land = ~wet
    below_seafloor = wet & ~bottom
    missing = wet & bottom & np.isnan(array2d)

    rgba[land] = (0, 0, 0, 0)
    rgba[missing] = (0, 0, 0, 0)

    if below_seafloor.any():
        rows, cols = np.nonzero(below_seafloor)
        hatch = (rows + cols) % 2 == 0
        rgba[rows[hatch], cols[hatch]] = SEAFLOOR_GREY
        rgba[rows[~hatch], cols[~hatch]] = SEAFLOOR_GREY_DARK

    rgba = np.flipud(rgba)

    buf = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(buf, format="PNG")
    return buf.getvalue()
