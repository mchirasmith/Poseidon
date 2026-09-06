"""Tiny end-to-end training runs: nn checkpoints/curve/card, gbm boosters/feature spec.

lightgbm and torch cannot coexist in one process on macOS (conflicting OpenMP runtimes), so
every gbm codepath here runs in a subprocess; only torch-based calls run in-process.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from model import calibrate, train_nn
from model.export import export_lite

TINY_CFG = "configs/tiny.yaml"
GBM_CFG = "configs/gbm.yaml"
BACKEND_DIR = Path(__file__).resolve().parent.parent


def _run_module(args: list[str]) -> None:
    result = subprocess.run(
        [sys.executable, "-m", *args],
        cwd=BACKEND_DIR,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_train_nn_tiny_writes_checkpoints_curve_card(synthetic_store, tmp_path):
    out_dir = train_nn.train(TINY_CFG, str(synthetic_store), str(tmp_path))
    assert out_dir == tmp_path / "lite"
    ckpts = list((out_dir / "checkpoints").glob("step_*.pt"))
    assert len(ckpts) > 0
    assert (out_dir / "best.pt").exists()
    assert (out_dir / "learning_curve.json").exists()
    curve = json.loads((out_dir / "learning_curve.json").read_text())
    assert len(curve) > 0 and "dev_nll" in curve[0]
    card = json.loads((out_dir / "model_card.json").read_text())
    assert card["name"] == "poseidon-lite"
    assert card["steps"] == 30


def test_train_gbm_tiny_writes_15_boosters_and_feature_spec(synthetic_store, tmp_path):
    _run_module([
        "model.train_gbm",
        "--cfg", GBM_CFG,
        "--rows", "tiny",
        "--data-dir", str(synthetic_store),
        "--art-dir", str(tmp_path),
    ])
    out_dir = tmp_path / "gbm"
    boosters = list(out_dir.glob("depth_*.txt"))
    assert len(boosters) == 15
    spec = json.loads((out_dir / "feature_spec.json").read_text())
    assert len(spec["columns"]) == 24
    assert len(spec["depths_m"]) == 15
    card = json.loads((out_dir / "model_card.json").read_text())
    assert card["name"] == "poseidon-gbm"


@pytest.fixture(scope="session")
def full_artifacts(synthetic_store, tmp_path_factory):
    """One tiny lite + gbm training/calibration/export run, reused by export and eval report tests."""
    art_dir = tmp_path_factory.mktemp("full_artifacts")
    train_nn.train(TINY_CFG, str(synthetic_store), str(art_dir))
    _run_module([
        "model.train_gbm",
        "--cfg", GBM_CFG,
        "--rows", "tiny",
        "--data-dir", str(synthetic_store),
        "--art-dir", str(art_dir),
    ])
    calibrate.calibrate(TINY_CFG, str(synthetic_store), str(art_dir))
    export_lite(TINY_CFG, str(synthetic_store), str(art_dir))
    _run_module([
        "model.export",
        "--model", "gbm",
        "--data-dir", str(synthetic_store),
        "--art-dir", str(art_dir),
    ])
    return art_dir


def test_train_gbm_module_never_imports_torch():
    """model.train_gbm and eval.evaluate must stay torch-free so they never clash with lightgbm's OpenMP runtime."""
    code = "import app, eval.evaluate, model.train_gbm, sys; assert 'torch' not in sys.modules"
    result = subprocess.run([sys.executable, "-c", code], cwd=BACKEND_DIR, env=os.environ.copy(), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_train_nn_module_never_imports_lightgbm():
    """model.train_nn must stay lightgbm-free so it never clashes with torch's OpenMP runtime."""
    code = "import model.train_nn, sys; assert 'lightgbm' not in sys.modules"
    result = subprocess.run([sys.executable, "-c", code], cwd=BACKEND_DIR, env=os.environ.copy(), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
