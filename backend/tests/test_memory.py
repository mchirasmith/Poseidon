"""Subprocess memory guard: synthetic.generate and eval.evaluate must stream, not stack, full periods.

Runs each target as a subprocess so `resource.getrusage(RUSAGE_SELF).ru_maxrss` measures its own
peak, not this pytest process's.
"""
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.test_model_train import full_artifacts  # noqa: F401  (shared session fixture)

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="uses resource.getrusage, unix only")

BACKEND_DIR = Path(__file__).resolve().parent.parent
MAX_RSS_MB = 2048
GEN_TIMEOUT_S = 180

_GEN_SCRIPT = """
import resource, sys
from pipeline import synthetic
synthetic.generate(sys.argv[1], "2016-01-01", "2016-12-31", 100, 240, seed=3)
print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
"""

_EVAL_SCRIPT = """
import resource, sys
from eval.evaluate import evaluate, write_report
report = evaluate(sys.argv[1], sys.argv[2], ["climatology", "gbm", "lite"])
write_report(report, sys.argv[1])
print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
"""

_EVAL_CLIM_SCRIPT = """
import resource, sys
from eval.evaluate import evaluate
evaluate(sys.argv[1], sys.argv[1], ["climatology"])
print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
"""


def _peak_rss_mb(stdout: str) -> float:
    kb_or_bytes = int(stdout.strip().splitlines()[-1])
    # ru_maxrss is bytes on macOS/BSD, kilobytes on Linux
    return kb_or_bytes / (1024 * 1024) if sys.platform == "darwin" else kb_or_bytes / 1024


def test_synthetic_generate_100x240_one_year_peak_rss(tmp_path):
    t0 = time.time()
    result = subprocess.run(
        [sys.executable, "-c", _GEN_SCRIPT, str(tmp_path / "data")],
        cwd=BACKEND_DIR, capture_output=True, text=True, timeout=120,
    )
    elapsed = time.time() - t0
    assert result.returncode == 0, result.stderr
    peak_mb = _peak_rss_mb(result.stdout)
    print(f"synthetic.generate 100x240 x 1yr: peak {peak_mb:.0f} MB in {elapsed:.1f}s")
    assert peak_mb < MAX_RSS_MB, f"peak RSS {peak_mb:.0f} MB exceeds {MAX_RSS_MB} MB"
    assert elapsed < GEN_TIMEOUT_S, f"generate took {elapsed:.1f}s, expected under {GEN_TIMEOUT_S}s"


def test_eval_evaluate_peak_rss(full_artifacts, synthetic_store):
    result = subprocess.run(
        [sys.executable, "-c", _EVAL_SCRIPT, str(synthetic_store), str(full_artifacts)],
        cwd=BACKEND_DIR, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    peak_mb = _peak_rss_mb(result.stdout)
    print(f"eval.evaluate on tiny fixture: peak {peak_mb:.0f} MB")
    assert peak_mb < MAX_RSS_MB, f"peak RSS {peak_mb:.0f} MB exceeds {MAX_RSS_MB} MB"


def test_eval_evaluate_100x240_peak_rss(tmp_path):
    """A grid and test-day count large enough that a per-day cache would actually show up in RSS.

    Single run only: a second store to compare test-day counts would double an already ~2.5
    minute test (100x240 generation dominates the time, not the eval loop under test).
    """
    from pipeline import synthetic

    data_dir = tmp_path / "data"
    t0 = time.time()
    synthetic.generate(data_dir, "2016-01-01", "2019-03-01", 100, 240, seed=11)
    result = subprocess.run(
        [sys.executable, "-c", _EVAL_CLIM_SCRIPT, str(data_dir)],
        cwd=BACKEND_DIR, capture_output=True, text=True, timeout=180,
    )
    elapsed = time.time() - t0
    assert result.returncode == 0, result.stderr
    peak_mb = _peak_rss_mb(result.stdout)
    print(f"eval.evaluate 100x240, ~52 test days: peak {peak_mb:.0f} MB in {elapsed:.1f}s total")
    assert peak_mb < MAX_RSS_MB, f"peak RSS {peak_mb:.0f} MB exceeds {MAX_RSS_MB} MB"
