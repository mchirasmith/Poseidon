"""Plausible-range checks and mask/error-field application, producing NaN outside valid ocean."""
from __future__ import annotations

import xarray as xr

from pipeline.sources import QC_RANGES


def range_check(da: xr.DataArray, var: str) -> xr.DataArray:
    """Values outside the plausible range for `var` become NaN."""
    lo, hi = QC_RANGES[var]
    return da.where((da >= lo) & (da <= hi))


def apply_flag_mask(da: xr.DataArray, flag: xr.DataArray, valid_value: float = 1.0) -> xr.DataArray:
    """A product mask/quality field (e.g. OSTIA `mask`) gates the data: keep only valid_value cells."""
    return da.where(flag == valid_value)


def apply_error_threshold(da: xr.DataArray, error: xr.DataArray, max_error: float) -> xr.DataArray:
    """Drop cells whose stated analysis/observation error exceeds max_error."""
    return da.where(error <= max_error)


def kelvin_to_celsius(da: xr.DataArray) -> xr.DataArray:
    return da - 273.15
