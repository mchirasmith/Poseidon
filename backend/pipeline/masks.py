"""Wet mask, per-level bottom mask, per-day modality masks, and static fields."""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from pipeline.sources import DEPTHS_M, GRID_STEP_DEG, WET_MIN_VALID_FRACTION

KM_PER_DEG = 111.0


def fraction_mask(frac_valid: np.ndarray) -> np.ndarray:
    """Per-cell valid-day fraction -> uint8, 1 where at or above the wet threshold."""
    return (frac_valid >= WET_MIN_VALID_FRACTION).astype(np.uint8)


def wet_mask(glorys_surface: np.ndarray) -> np.ndarray:
    """(T, H, W) surface temperature -> (H, W) uint8, 1 where valid on most days."""
    return fraction_mask(np.isfinite(glorys_surface).mean(axis=0))


def bottom_mask(glorys_std_depth: np.ndarray) -> np.ndarray:
    """(T, D, H, W) target temperature -> (D, H, W) uint8, 1 = above seafloor at that depth."""
    return fraction_mask(np.isfinite(glorys_std_depth).mean(axis=0))


def bottom_depth_norm(bottom: np.ndarray) -> np.ndarray:
    """(D, H, W) bottom mask -> (H, W) deepest valid standard depth divided by the max standard depth."""
    has_any = bottom.any(axis=0)
    deepest_idx = bottom.shape[0] - 1 - np.argmax(bottom[::-1], axis=0)
    depth_m = np.where(has_any, DEPTHS_M[deepest_idx], 0.0)
    return (depth_m / DEPTHS_M.max()).astype(np.float32)


def modality_masks(x_mask_raw: np.ndarray, wet: np.ndarray) -> np.ndarray:
    """(T, 5, H, W) raw per-day validity & wet mask -> (T, 5, H, W) uint8."""
    return (x_mask_raw.astype(bool) & wet.astype(bool)[None, None, :, :]).astype(np.uint8)


def coast_distance(wet: np.ndarray) -> np.ndarray:
    """(H, W) wet mask -> (H, W) km to the nearest land cell, via a KD-tree over land cells."""
    ny, nx = wet.shape
    land_idx = np.column_stack(np.where(~wet.astype(bool)))
    if land_idx.size == 0:
        return np.zeros((ny, nx), dtype=np.float32)
    ii, jj = np.mgrid[0:ny, 0:nx]
    query = np.column_stack([ii.ravel(), jj.ravel()])
    dist_cells, _ = cKDTree(land_idx).query(query)
    return (dist_cells.reshape(ny, nx) * GRID_STEP_DEG * KM_PER_DEG).astype(np.float32)
