"""app.main and eval.precompute must never import torch: it conflicts with lightgbm's OpenMP runtime."""
import subprocess
import sys


def _no_torch(import_stmt: str) -> None:
    code = f"import sys; {import_stmt}; assert 'torch' not in sys.modules, sorted(sys.modules)"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_app_main_never_imports_torch():
    _no_torch("import app.main")


def test_eval_precompute_never_imports_torch():
    _no_torch("import eval.precompute")
