"""6-hourly to daily mean, and missing days becoming NaN on the master calendar."""
import numpy as np
import pandas as pd
import xarray as xr

from pipeline.align import master_calendar, reindex_to_calendar, to_daily_mean


def test_six_hourly_to_daily_mean():
    times = pd.date_range("2020-01-01", periods=8, freq="6h")
    values = np.arange(8, dtype=float)
    da = xr.DataArray(values, dims=["time"], coords={"time": times})

    daily = to_daily_mean(da)
    assert len(daily) == 2
    assert np.isclose(daily.values[0], np.mean(values[:4]))
    assert np.isclose(daily.values[1], np.mean(values[4:]))


def test_missing_day_becomes_nan_on_master_calendar():
    calendar = master_calendar("2020-01-01", "2020-01-05")
    present = pd.date_range("2020-01-01", "2020-01-05").delete(2)  # drop 2020-01-03
    da = xr.DataArray(np.arange(len(present), dtype=float), dims=["time"], coords={"time": present})

    aligned = reindex_to_calendar(da, calendar)
    assert len(aligned) == 5
    assert np.isnan(aligned.sel(time="2020-01-03").values)
