"""Wet mask, per-level bottom mask, and modality masks on small hand-built arrays."""
import numpy as np

from pipeline.masks import bottom_mask, modality_masks, wet_mask


def test_wet_mask_thresholds_on_valid_fraction():
    T, H, W = 1000, 2, 2
    surface = np.zeros((T, H, W))
    surface[:, 0, 0] = np.nan  # never valid -> not wet
    surface[:5, 0, 1] = np.nan  # valid fraction 0.995 -> above threshold, wet
    wet = wet_mask(surface)
    assert wet[0, 0] == 0
    assert wet[0, 1] == 1
    assert wet[1, 0] == 1 and wet[1, 1] == 1


def test_bottom_mask_per_level():
    T, D, H, W = 50, 3, 1, 1
    target = np.zeros((T, D, H, W))
    target[:, 2, 0, 0] = np.nan  # deepest level never valid -> below seafloor
    bottom = bottom_mask(target)
    assert bottom[0, 0, 0] == 1
    assert bottom[1, 0, 0] == 1
    assert bottom[2, 0, 0] == 0


def test_modality_masks_combine_validity_and_wet():
    T, M, H, W = 3, 1, 2, 2
    raw = np.ones((T, M, H, W), dtype=np.uint8)
    raw[0, 0, 0, 0] = 0
    wet = np.ones((H, W), dtype=np.uint8)
    wet[1, 1] = 0
    out = modality_masks(raw, wet)
    assert out[0, 0, 0, 0] == 0  # missing that day
    assert out[1, 0, 0, 0] == 1
    assert (out[:, 0, 1, 1] == 0).all()  # land cell always masked
