"""Argo profile QC, depth interpolation, and nearest-cell matching on an in-memory fake profile."""
import numpy as np

from pipeline.argo_matchups import build_matchup_row, interp_to_standard_depths, nearest_cell, select_good_temp
from pipeline.sources import GRID_LAT, GRID_LON


def test_qc_filtering_prefers_adjusted_and_drops_bad_flags():
    temp = np.array([20.0, 21.0, 22.0])
    temp_adj = np.array([20.5, 21.5, 22.5])
    temp_qc = ["1", "1", "1"]
    adj_qc = ["1", "4", "2"]

    out = select_good_temp(temp, temp_adj, temp_qc, adj_qc, data_mode="D")
    assert out[0] == 20.5
    assert np.isnan(out[1])  # flag 4 dropped
    assert out[2] == 22.5

    out_raw = select_good_temp(temp, temp_adj, temp_qc, adj_qc, data_mode="R")
    assert np.allclose(out_raw, temp)  # not adjusted mode -> use TEMP with its own QC


def test_interpolation_requires_bracketing_within_tolerance():
    pres = np.array([0, 10, 20, 100, 200])
    temp = np.array([28.0, 27.0, 26.0, 20.0, 15.0])
    out = interp_to_standard_depths(pres, temp)
    from pipeline.sources import DEPTHS_M

    idx_30 = list(DEPTHS_M).index(30)  # nearest samples are 20 and 100, gap too wide
    assert np.isnan(out[idx_30])
    idx_10 = list(DEPTHS_M).index(10)
    assert np.isclose(out[idx_10], 27.0)


def test_nearest_cell_and_distance():
    i, j, dist_km = nearest_cell(float(GRID_LAT[5]), float(GRID_LON[10]))
    assert i == 5 and j == 10
    assert dist_km < 1.0


def test_build_matchup_row_shape():
    pres = np.linspace(0, 300, 20)
    temp = 28 - 0.05 * pres
    row = build_matchup_row(
        date="2020-06-01",
        wmo=1,
        lat=float(GRID_LAT[3]),
        lon=float(GRID_LON[3]),
        pres=pres,
        temp=temp,
        temp_adj=temp,
        temp_qc=["1"] * len(pres),
        temp_adj_qc=["1"] * len(pres),
        data_mode="A",
    )
    from pipeline.sources import DEPTHS_M

    for d in DEPTHS_M:
        assert f"t_{int(d)}" in row
