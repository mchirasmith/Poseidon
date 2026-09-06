"""Cache directory layout: cache/<date>/<model>/... and helpers to read/write it."""
from __future__ import annotations

import json
from pathlib import Path

TILE_MODES = ("mean", "sigma", "anom", "error")


def day_dir(cache_root: Path, date: str) -> Path:
    return cache_root / date


def model_dir(cache_root: Path, date: str, model: str) -> Path:
    return day_dir(cache_root, date) / model


def tile_path(cache_root: Path, date: str, model: str, mode: str, depth_index: int) -> Path:
    return model_dir(cache_root, date, model) / mode / f"z{depth_index:02d}.png"


def input_tile_path(cache_root: Path, date: str, var: str, t: int) -> Path:
    return day_dir(cache_root, date) / "in" / f"{var}_t{t}.png"


def meta_path(cache_root: Path, date: str, model: str) -> Path:
    return model_dir(cache_root, date, model) / "meta.json"


def fields_path(cache_root: Path, date: str, model: str) -> Path:
    return model_dir(cache_root, date, model) / "fields.npz"


def netcdf_path(cache_root: Path, date: str, model: str) -> Path:
    return model_dir(cache_root, date, model) / f"poseidon_{model}_{date}.nc"


def exists(cache_root: Path, date: str, model: str) -> bool:
    return meta_path(cache_root, date, model).exists()


def read_meta(cache_root: Path, date: str, model: str) -> dict:
    return json.loads(meta_path(cache_root, date, model).read_text())


def write_meta(cache_root: Path, date: str, model: str, meta: dict) -> None:
    path = meta_path(cache_root, date, model)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta))


def list_cached_days(cache_root: Path, model: str) -> list[str]:
    if not cache_root.exists():
        return []
    days = []
    for entry in sorted(cache_root.iterdir()):
        if entry.is_dir() and exists(cache_root, entry.name, model):
            days.append(entry.name)
    return days
