"""One-shot pipeline runner: data -> gbm -> nn -> calibrate -> export -> eval -> precompute.

Each stage runs as its own subprocess so torch and lightgbm never share a process
(their OpenMP runtimes conflict on macOS). Stages skip when their output marker exists.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

TAIL_LINES = 30
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
MIN_FREE_DISK_GB = 20


def _marker_data(data_dir: Path) -> bool:
    return (data_dir / "poseidon.zarr" / ".zmetadata").exists()


def _marker_gbm(art_dir: Path) -> bool:
    return (art_dir / "gbm" / "feature_spec.json").exists()


def _marker_nn(art_dir: Path) -> bool:
    return (art_dir / "lite" / "best.pt").exists()


def _marker_calibrate(art_dir: Path) -> bool:
    card = art_dir / "lite" / "model_card.json"
    return card.exists() and "calibration_alphas" in json.loads(card.read_text())


def _marker_export_lite(art_dir: Path) -> bool:
    return (art_dir / "lite" / "poseidon-lite.onnx").exists()


def _marker_export_gbm(art_dir: Path) -> bool:
    card = art_dir / "gbm" / "model_card.json"
    return card.exists() and json.loads(card.read_text()).get("validated")


def _marker_eval(data_dir: Path) -> bool:
    return (data_dir / "report.json").exists()


def _marker_precompute(fixtures_dir: Path, fallback_dir: Path) -> bool:
    """True once precompute's terminal artefacts (the fallback bundle and the synthetic fixtures) exist."""
    fallback_meta = fallback_dir / "meta.json"
    fixtures_meta = fixtures_dir / "meta.json"
    if not fallback_meta.exists() or not fixtures_meta.exists():
        return False
    return json.loads(fixtures_meta.read_text()).get("fixture_kind") == "synthetic"


def _run(cmd: list[str]) -> tuple[bool, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    return proc.returncode == 0, out


def _stage(name: str, marker_ok: bool, cmd: list[str], force: bool) -> None:
    if marker_ok and not force:
        print(f"[skip] {name} (output already present)")
        return
    t0 = time.time()
    ok, out = _run(cmd)
    elapsed = time.time() - t0
    if not ok:
        tail = "\n".join(out.splitlines()[-TAIL_LINES:])
        print(f"[fail] {name} after {elapsed:.1f}s\n{tail}")
        sys.exit(1)
    print(f"[ok]   {name} in {elapsed:.1f}s")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--years", default="2016-2020")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--ny", type=int, default=100)
    p.add_argument("--nx", type=int, default=240)
    p.add_argument("--start", default="2016-01-01")
    p.add_argument("--end", default="2020-12-31")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--workers", type=int, default=None, help="parallel download workers passed to pipeline.run")
    p.add_argument("--cfg", default="configs/lite.yaml")
    p.add_argument("--gbm-cfg", default="configs/gbm.yaml")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--art-dir", default="artifacts")
    p.add_argument("--force", action="store_true")
    p.add_argument("--only", default=None, help="comma-separated stage names to run")
    p.add_argument("--fixtures-dir", default=None, help="test-only override for the precompute stage")
    p.add_argument("--fallback-dir", default=None, help="test-only override for the precompute stage")
    args = p.parse_args()

    data_dir, art_dir = Path(args.data_dir), Path(args.art_dir)
    py = sys.executable
    only = {s.strip() for s in args.only.split(",")} if args.only else None

    def wanted(name: str) -> bool:
        return only is None or name in only

    if wanted("check"):
        check_path = data_dir if data_dir.exists() else Path(".")
        free_gb = shutil.disk_usage(check_path).free / 1e9
        if free_gb < MIN_FREE_DISK_GB:
            print(f"[fail] check: {free_gb:.1f} GB free, need at least {MIN_FREE_DISK_GB} GB")
            sys.exit(1)
        if args.synthetic:
            print("[skip] check (synthetic)")
        else:
            ok, out = _run([py, "-m", "pipeline.download", "--check"])
            if not ok:
                print(out)
                sys.exit(1)
        print("[ok]   check")

    if wanted("data"):
        if args.synthetic:
            cmd = [
                py, "-m", "pipeline.run", "--synthetic",
                "--data-dir", str(data_dir), "--start", args.start, "--end", args.end,
                "--ny", str(args.ny), "--nx", str(args.nx), "--seed", str(args.seed),
            ]
        else:
            cmd = [py, "-m", "pipeline.run", "--data-dir", str(data_dir), "--years", args.years]
            if args.workers is not None:
                cmd += ["--workers", str(args.workers)]
        _stage("data", _marker_data(data_dir), cmd, args.force)

    if wanted("gbm"):
        rows_key = "tiny" if "tiny" in args.cfg else "lite"
        cmd = [py, "-m", "model.train_gbm", "--cfg", args.gbm_cfg, "--rows", rows_key, "--data-dir", str(data_dir), "--art-dir", str(art_dir)]
        _stage("gbm", _marker_gbm(art_dir), cmd, args.force)

    if wanted("nn"):
        cmd = [py, "-m", "model.train_nn", "--cfg", args.cfg, "--data-dir", str(data_dir), "--art-dir", str(art_dir)]
        _stage("nn", _marker_nn(art_dir), cmd, args.force)

    if wanted("calibrate"):
        cmd = [py, "-m", "model.calibrate", "--cfg", args.cfg, "--data-dir", str(data_dir), "--art-dir", str(art_dir)]
        _stage("calibrate", _marker_calibrate(art_dir), cmd, args.force)

    if wanted("export_lite"):
        cmd = [py, "-m", "model.export", "--model", "lite", "--cfg", args.cfg, "--data-dir", str(data_dir), "--art-dir", str(art_dir)]
        _stage("export_lite", _marker_export_lite(art_dir), cmd, args.force)

    if wanted("export_gbm"):
        cmd = [py, "-m", "model.export", "--model", "gbm", "--cfg", args.gbm_cfg, "--data-dir", str(data_dir), "--art-dir", str(art_dir)]
        _stage("export_gbm", _marker_export_gbm(art_dir), cmd, args.force)

    if wanted("eval"):
        cmd = [py, "-m", "eval.evaluate", "--data-dir", str(data_dir), "--art-dir", str(art_dir), "--models", "climatology,gbm,lite"]
        _stage("eval", _marker_eval(data_dir), cmd, args.force)

    if wanted("precompute"):
        fixtures_dir = Path(args.fixtures_dir) if args.fixtures_dir else BACKEND_DIR / "fixtures"
        fallback_dir = Path(args.fallback_dir) if args.fallback_dir else REPO_ROOT / "frontend" / "public" / "fallback"
        cmd = [py, "-m", "eval.precompute", "--data-dir", str(data_dir), "--art-dir", str(art_dir), "--models", "lite,gbm", "--fixtures"]
        if args.fixtures_dir:
            cmd += ["--fixtures-dir", args.fixtures_dir]
        if args.fallback_dir:
            cmd += ["--fallback-dir", args.fallback_dir]
        _stage("precompute", _marker_precompute(fixtures_dir, fallback_dir), cmd, args.force)

    print("done.")


if __name__ == "__main__":
    main()
