"""Samples cmocean colormaps to 256 RGB stops and writes backend/scales.json.

Frozen output: the frontend shares this file, so re-run only on a deliberate
palette change.
"""
from __future__ import annotations

import json
from pathlib import Path

import cmocean
import numpy as np

MODES = {
    "mean": ("thermal", 2, 32),
    "sigma": ("amp", 0, 2),
    "anom": ("balance", -4, 4),
    "error": ("balance", -3, 3),
    "rmse": ("amp", 0, 3),
    "bias": ("balance", -2, 2),
    "sst": ("thermal", 15, 35),
    "sss": ("haline", 30, 40),
    "sla": ("balance", -0.5, 0.5),
    "cur": ("speed", 0, 1.5),
    "wind": ("speed", 0, 15),
}

N_STOPS = 256


def sample_cmap(name: str) -> list[list[int]]:
    cmap = getattr(cmocean.cm, name)
    stops = cmap(np.linspace(0, 1, N_STOPS))[:, :3]
    return (stops * 255).round().astype(int).tolist()


def main() -> None:
    out = {}
    for mode, (cmap_name, vmin, vmax) in MODES.items():
        out[mode] = {"cmap": sample_cmap(cmap_name), "vmin": vmin, "vmax": vmax}

    out_path = Path(__file__).resolve().parent.parent / "scales.json"
    out_path.write_text(json.dumps(out))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
