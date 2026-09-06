"""Zarr store wrapper, window builder, tiler and training sampler for poseidon.zarr."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import zarr

from pipeline.sources import DEPTHS_M, SPLIT_PURGED, X_MASK_VARS, X_VARS


class Store:
    """Read-only view over a consolidated poseidon.zarr, with a window builder for model input."""

    def __init__(self, root: zarr.Group):
        self.root = root
        self.time = np.asarray(root["time"][:]).astype("datetime64[D]")
        self.lat = np.asarray(root["lat"][:], dtype=np.float32)
        self.lon = np.asarray(root["lon"][:], dtype=np.float32)
        self.depths = np.asarray(root["depth"][:], dtype=np.float32)
        self.split = np.asarray(root["split"][:], dtype=np.uint8)
        self.static = np.asarray(root["static"][:], dtype=np.float32)
        self.wet = np.asarray(root["wet"][:], dtype=np.uint8)
        self.bottom = np.asarray(root["bottom"][:], dtype=np.uint8)
        self.clim_x = np.asarray(root["clim_x"][:], dtype=np.float32)
        self.clim_y = np.asarray(root["clim_y"][:], dtype=np.float32)
        self.norm = _load_norm(root)
        self.T = len(self.time)
        self.H, self.W = self.wet.shape
        self.doy = (self.time.astype("datetime64[D]") - self.time.astype("datetime64[Y]")).astype(int) + 1
        self.n_x = len(X_VARS)
        self.n_mask = len(X_MASK_VARS)
        self.n_depth = len(DEPTHS_M)
        self._ram_t0: int | None = None
        self._ram_x = None
        self._ram_mask = None
        self._ram_y = None

    @classmethod
    def open(cls, path: str | Path) -> "Store":
        root = zarr.open_consolidated(str(path), mode="r")
        return cls(root)

    def load_in_ram(self, t0: int, t1: int) -> None:
        """Load x, x_mask, y for days [t0, t1) into float16 numpy, replacing per-day zarr reads."""
        t0, t1 = max(t0, 0), min(t1, self.T)
        self._ram_t0, self._ram_t1 = t0, t1
        self._ram_x = np.asarray(self.root["x"][t0:t1])
        self._ram_mask = np.asarray(self.root["x_mask"][t0:t1])
        self._ram_y = np.asarray(self.root["y"][t0:t1])

    def _in_ram(self, dt: int) -> bool:
        return self._ram_x is not None and self._ram_t0 <= dt < self._ram_t1

    def _valid_day(self, dt: int) -> bool:
        return 0 <= dt < self.T and self.split[dt] != SPLIT_PURGED

    def field_day(self, dt: int) -> tuple[np.ndarray, np.ndarray]:
        """(7,H,W) x anomalies with NaN preserved and (5,H,W) modality mask for one valid day."""
        if not self._valid_day(dt):
            return (
                np.full((self.n_x, self.H, self.W), np.nan, dtype=np.float32),
                np.zeros((self.n_mask, self.H, self.W), dtype=np.uint8),
            )
        if self._in_ram(dt):
            x = self._ram_x[dt - self._ram_t0]
            m = self._ram_mask[dt - self._ram_t0]
        else:
            x = self.root["x"][dt]
            m = self.root["x_mask"][dt]
        return np.asarray(x, dtype=np.float32), np.asarray(m, dtype=np.uint8)

    def window(self, t: int, k: int) -> np.ndarray:
        """(k, 12, H, W) float32 for days t-k+1..t: 7 field channels then 5 mask channels per day."""
        frames = []
        for dt in range(t - k + 1, t + 1):
            x, m = self.field_day(dt)
            x = np.nan_to_num(x, nan=0.0)
            frames.append(np.concatenate([x, m.astype(np.float32)], axis=0))
        return np.stack(frames, axis=0).astype(np.float32)

    def day_target(self, dt: int) -> tuple[np.ndarray, np.ndarray]:
        """(15,H,W) normalised anomaly y and loss mask (wet & bottom & not purged) for one day."""
        if not self._valid_day(dt):
            return (
                np.zeros((self.n_depth, self.H, self.W), dtype=np.float32),
                np.zeros((self.n_depth, self.H, self.W), dtype=bool),
            )
        if self._in_ram(dt):
            y = self._ram_y[dt - self._ram_t0]
        else:
            y = self.root["y"][dt]
        y = np.asarray(y, dtype=np.float32)
        mask = np.isfinite(y) & self.bottom.astype(bool) & self.wet.astype(bool)[None]
        return np.nan_to_num(y, nan=0.0), mask

    def y_raw_day(self, dt: int) -> np.ndarray:
        """(15,H,W) absolute GLORYS temperature for one day, NaN on land / below bottom."""
        return np.asarray(self.root["y_raw"][dt], dtype=np.float32)

    def train_days(self) -> np.ndarray:
        return np.where(self.split == 0)[0]


def _load_norm(root: zarr.Group) -> dict:
    import json

    raw = root.attrs.get("norm", "{}")
    return json.loads(raw) if isinstance(raw, str) else raw


def full_domain_batch(store: Store, t: int, window: int, mult: int = 8):
    """Zero-padded batch-of-1 (x, static) for whole-domain inference, plus the true (H, W) to crop back to."""
    x = store.window(t, window)
    x_p, h, w = pad_to_multiple(x, mult)
    s_p, _, _ = pad_to_multiple(store.static, mult)
    return x_p[None], s_p[None], h, w


def pad_to_multiple(arr: np.ndarray, mult: int = 8) -> tuple[np.ndarray, int, int]:
    """Zero-pad the trailing two (H, W) dims up to the next multiple of `mult`."""
    *lead, h, w = arr.shape
    ph = (-h) % mult
    pw = (-w) % mult
    if ph == 0 and pw == 0:
        return arr, h, w
    pad = [(0, 0)] * len(lead) + [(0, ph), (0, pw)]
    return np.pad(arr, pad), h, w


def _axis_plan(size: int, tile: int, core: int) -> list[tuple[int, int, int]]:
    """Tile origins centred on their core segment, plus each tile's [start, end) core responsibility in global coords."""
    if size <= tile:
        return [(0, 0, size)]
    margin = (tile - core) // 2
    starts = list(range(0, size, core))
    ends = starts[1:] + [size]
    plan: list[tuple[int, int, int]] = []
    for s0, s1 in zip(starts, ends):
        o = max(0, min(s0 - margin, size - tile))
        if plan and plan[-1][0] == o:
            po, ps0, _ = plan[-1]
            plan[-1] = (po, ps0, s1)
        else:
            plan.append((o, s0, s1))
    return plan


class Tiler:
    """Overlapping tiles of size `tile` with a central `core`; core regions tile the domain exactly once."""

    def __init__(self, H: int, W: int, tile: int, core: int):
        self.H, self.W, self.tile, self.core = H, W, tile, core
        self.plan_h = _axis_plan(H, tile, core)
        self.plan_w = _axis_plan(W, tile, core)
        self.tiles = [(oh, ow) for oh, _, _ in self.plan_h for ow, _, _ in self.plan_w]

    def n_tiles(self) -> int:
        return len(self.tiles)

    def core_mask(self, oh: int, ow: int) -> np.ndarray:
        """(tile, tile) bool: True where this tile is responsible for the output (its core segment)."""
        ph = next(p for p in self.plan_h if p[0] == oh)
        pw = next(p for p in self.plan_w if p[0] == ow)
        mask = np.zeros((self.tile, self.tile), dtype=bool)
        h0, h1 = ph[1] - oh, ph[2] - oh
        w0, w1 = pw[1] - ow, pw[2] - ow
        mask[h0:h1, w0:w1] = True
        return mask

    def extract(self, arr: np.ndarray, oh: int, ow: int) -> tuple[np.ndarray, np.ndarray]:
        """Zero-padded (..., tile, tile) crop at origin (oh, ow) plus a (tile, tile) validity mask."""
        h1, w1 = min(oh + self.tile, self.H), min(ow + self.tile, self.W)
        lead = arr.shape[:-2]
        out = np.zeros((*lead, self.tile, self.tile), dtype=arr.dtype)
        valid = np.zeros((self.tile, self.tile), dtype=bool)
        out[..., : h1 - oh, : w1 - ow] = arr[..., oh:h1, ow:w1]
        valid[: h1 - oh, : w1 - ow] = True
        return out, valid


class Sampler:
    """Uniform over the given training days, tiles weighted by wet fraction; skips tiles below min_wet_frac."""

    def __init__(self, store: Store, tiler: Tiler, train_days: np.ndarray, min_wet_frac: float, rng: np.random.Generator):
        self.store = store
        self.tiler = tiler
        self.rng = rng
        self.train_days = train_days
        weights = []
        eligible = []
        for oh, ow in tiler.tiles:
            wet_crop, valid = tiler.extract(store.wet.astype(np.float32), oh, ow)
            n_valid = valid.sum()
            wet_frac = wet_crop.sum() / n_valid if n_valid else 0.0
            if wet_frac >= min_wet_frac:
                eligible.append((oh, ow))
                weights.append(wet_frac)
        if not eligible:
            raise ValueError("no tile clears min_wet_frac")
        self.eligible = eligible
        self.weights = np.asarray(weights, dtype=np.float64)
        self.weights /= self.weights.sum()

    def sample(self, n: int) -> list[tuple[int, int, int]]:
        """n samples of (day_index, tile_origin_h, tile_origin_w)."""
        days = self.rng.choice(self.train_days, size=n)
        idx = self.rng.choice(len(self.eligible), size=n, p=self.weights)
        return [(int(d), *self.eligible[i]) for d, i in zip(days, idx)]
