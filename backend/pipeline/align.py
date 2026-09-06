"""Build the daily master calendar and align every product to it."""
from __future__ import annotations

import pandas as pd
import xarray as xr


def master_calendar(start: str, end: str) -> pd.DatetimeIndex:
    return pd.date_range(start, end, freq="D")


def to_daily_mean(da: xr.DataArray) -> xr.DataArray:
    """Sub-daily (e.g. 6-hourly CCMP) -> daily mean."""
    return da.resample(time="1D").mean(skipna=True)


def reindex_to_calendar(da: xr.DataArray, calendar: pd.DatetimeIndex) -> xr.DataArray:
    """Missing days become NaN (or 0 for uint mask arrays, handled by the caller)."""
    return da.reindex(time=calendar)
