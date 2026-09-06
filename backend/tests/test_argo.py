"""ArgoIndex.nearest tolerance behaviour on a hand-built matchup table."""
import pandas as pd

from app.services.argo import ArgoIndex
from pipeline.sources import DEPTHS_M


def _write_parquet(tmp_path):
    row = {"date": pd.Timestamp("2020-01-15"), "wmo": "1234", "lat": 10.0, "lon": 70.0}
    for d in DEPTHS_M:
        row[f"t_{int(d)}"] = 20.0
    path = tmp_path / "argo.parquet"
    pd.DataFrame([row]).to_parquet(path)
    return path


def test_nearest_within_tolerance(tmp_path):
    index = ArgoIndex(_write_parquet(tmp_path))
    m = index.nearest("2020-01-15", 10.01, 70.01, max_km=55, max_days=2)
    assert m is not None
    assert m["wmo"] == "1234"
    assert m["day_offset"] == 0
    assert len(m["temp"]) == len(DEPTHS_M)


def test_nearest_outside_distance_tolerance(tmp_path):
    index = ArgoIndex(_write_parquet(tmp_path))
    assert index.nearest("2020-01-15", 15.0, 70.0, max_km=55, max_days=2) is None


def test_nearest_outside_day_tolerance(tmp_path):
    index = ArgoIndex(_write_parquet(tmp_path))
    assert index.nearest("2020-01-20", 10.0, 70.0, max_km=55, max_days=2) is None


def test_missing_parquet_returns_none(tmp_path):
    index = ArgoIndex(tmp_path / "does-not-exist.parquet")
    assert index.nearest("2020-01-15", 10.0, 70.0, max_km=55, max_days=2) is None
