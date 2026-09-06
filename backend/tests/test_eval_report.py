"""End-to-end eval.evaluate over climatology/gbm/lite, and report.json has no NaN tokens.

Run as a subprocess: eval.evaluate imports lightgbm, and this test session also imports torch
(via tests.test_model_train), which cannot share a process with lightgbm on macOS.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from tests.test_model_train import full_artifacts  # noqa: F401  (shared session fixture)

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _run_evaluate(data_dir: Path, art_dir: Path) -> None:
    result = subprocess.run(
        [
            sys.executable, "-m", "eval.evaluate",
            "--data-dir", str(data_dir),
            "--art-dir", str(art_dir),
            "--models", "climatology,gbm,lite",
        ],
        cwd=BACKEND_DIR,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_report_covers_three_models(full_artifacts, synthetic_store):
    _run_evaluate(synthetic_store, full_artifacts)
    raw = (synthetic_store / "report.json").read_text()
    assert "NaN" not in raw
    report = json.loads(raw)  # a bare NaN token would fail strict parsing

    for key in ("headline", "by_depth", "tables", "argo_scatter", "calibration", "learning_curve", "maps"):
        assert key in report
    for model in ("climatology", "gbm", "lite"):
        assert model in report["by_depth"]
        assert len(report["by_depth"][model]["rmse"]["overall"]["all"]) == 15

    assert (synthetic_store / "report.md").exists()


def test_report_argo_scatter_has_glorys_baseline(full_artifacts, synthetic_store):
    _run_evaluate(synthetic_store, full_artifacts)
    report = json.loads((synthetic_store / "report.json").read_text())
    assert "glorys" in report["argo_scatter"]
    assert report["argo_scatter"]["glorys"]["n"] > 0
