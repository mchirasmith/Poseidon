"""Product catalogue, grid, calendar and tolerance constants for the data pipeline.

One place to change a product, the box, or a split boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from app.config import STANDARD_DEPTHS_M

# download box has a 1 deg margin around the target grid to avoid edge artefacts on regrid
BOX_MARGIN_DEG = 1.0
GRID_LAT_MIN, GRID_LAT_MAX = 5.0, 30.0
GRID_LON_MIN, GRID_LON_MAX = 45.0, 105.0
GRID_STEP_DEG = 0.25
BOX_LAT_MIN = GRID_LAT_MIN - BOX_MARGIN_DEG
BOX_LAT_MAX = GRID_LAT_MAX + BOX_MARGIN_DEG
BOX_LON_MIN = GRID_LON_MIN - BOX_MARGIN_DEG
BOX_LON_MAX = GRID_LON_MAX + BOX_MARGIN_DEG

GRID_LAT = np.round(np.arange(GRID_LAT_MIN, GRID_LAT_MAX, GRID_STEP_DEG) + GRID_STEP_DEG / 2, 3)
GRID_LON = np.round(np.arange(GRID_LON_MIN, GRID_LON_MAX, GRID_STEP_DEG) + GRID_STEP_DEG / 2, 3)


@dataclass(frozen=True)
class Grid:
    """Target lat/lon centres for one assembly run; lets tests use a small grid."""

    lat: np.ndarray
    lon: np.ndarray


DEFAULT_GRID = Grid(GRID_LAT, GRID_LON)

DEPTHS_M = np.array(STANDARD_DEPTHS_M, dtype=np.float32)
GLORYS_MAX_DEPTH_M = 1100.0
DOWNLOAD_RETRIES = 4
DOWNLOAD_RETRY_WAIT_S = 60
TARGET_SHALLOW_CLAMP_TOL_M = 1.0  # a standard depth this close above the shallowest source sample takes that sample

# calendar / splits
TRAIN_END_YEAR = 2016
DEV_YEAR = 2017
CAL_YEAR = 2018
TEST_START_YEAR = 2019
PURGE_DAYS = 8
SPLIT_TRAIN, SPLIT_DEV, SPLIT_CAL, SPLIT_TEST, SPLIT_PURGED = 0, 1, 2, 3, 255

HARMONIC_ORDERS = 2  # annual + semi-annual -> 5 coefficients (a0, a1, b1, a2, b2)
HARMONIC_PERIOD_DAYS = 365.25

# input channel / mask ordering, fixed across the store
X_VARS = ["sst", "sss", "sla", "cur_u", "cur_v", "wnd_u", "wnd_v"]
X_MASK_VARS = ["sst", "sss", "sla", "cur", "wnd"]

# QC plausible ranges, per variable
QC_RANGES = {
    "sst": (-2.0, 40.0),
    "sss": (0.0, 45.0),
    "sla": (-3.0, 3.0),
    "cur_u": (-5.0, 5.0),
    "cur_v": (-5.0, 5.0),
    "wnd_u": (-60.0, 60.0),
    "wnd_v": (-60.0, 60.0),
    "thetao": (-2.0, 40.0),
}

REGRID_MIN_VALID_FRACTION = 0.5  # source pixels needed in a target cell, else NaN
WET_MIN_VALID_FRACTION = 0.99  # fraction of days GLORYS surface must be valid to call a cell wet

SST_MAX_ANALYSIS_ERROR_C = 1.0  # OSTIA analysis_error stated uncertainty, degC
SLA_MAX_ERR_M = 0.05  # DUACS err_sla stated uncertainty, metres

ARGO_INDEX_URL = "https://data-argo.ifremer.fr/ar_index_global_prof.txt"
ARGO_DAC_BASE_URL = "https://data-argo.ifremer.fr/dac/"
ARGO_GOOD_QC_FLAGS = {"1", "2"}
ARGO_ADJUSTED_MODES = {"A", "D"}
ARGO_DEPTH_TOL_M = 10.0  # require a sample within this many metres above and below a std depth

ZARR_TIME_CHUNK = 32


@dataclass(frozen=True)
class CopernicusProduct:
    name: str
    dataset_id: str
    variables: list[str]
    source_step_deg: float
    kind: str = "copernicus"


@dataclass(frozen=True)
class PodaacProduct:
    name: str
    short_name: str
    variables: list[str]
    source_step_deg: float
    hourly_steps_per_day: int = 1
    kind: str = "podaac"


PRODUCTS: dict[str, object] = {
    "sst": CopernicusProduct(
        name="sst",
        dataset_id="METOFFICE-GLO-SST-L4-REP-OBS-SST",
        variables=["analysed_sst", "analysis_error", "mask"],
        source_step_deg=0.05,
    ),
    "sss": CopernicusProduct(
        name="sss",
        dataset_id="cmems_obs-mob_glo_phy-sss_my_multi_P1D",
        variables=["sos"],
        source_step_deg=0.125,
    ),
    "sla": CopernicusProduct(
        name="sla",
        # DUACS L4 is 0.125 deg
        dataset_id="cmems_obs-sl_glo_phy-ssh_my_allsat-l4-duacs-0.125deg_P1D",
        variables=["sla", "err_sla"],
        source_step_deg=0.125,
    ),
    "glorys": CopernicusProduct(
        name="glorys",
        dataset_id="cmems_mod_glo_phy-all_my_0.25deg_P1D-m",
        variables=["thetao_glor"],
        source_step_deg=0.25,
    ),
    "cur": PodaacProduct(
        name="cur",
        short_name="OSCAR_L4_OC_FINAL_V2.0",
        variables=["u", "v"],
        source_step_deg=0.25,
    ),
    "wnd": PodaacProduct(
        name="wnd",
        short_name="CCMP_WINDS_10M6HR_L4_V3.1",
        variables=["uwnd", "vwnd"],
        source_step_deg=0.25,
        hourly_steps_per_day=4,
    ),
}


def required_services(product_names: list[str]) -> set[str]:
    """Which credentialed services a set of products needs: copernicus and/or podaac."""
    return {PRODUCTS[name].kind for name in product_names}


def split_for_year(year: int) -> int:
    if year <= TRAIN_END_YEAR:
        return SPLIT_TRAIN
    if year == DEV_YEAR:
        return SPLIT_DEV
    if year == CAL_YEAR:
        return SPLIT_CAL
    if year >= TEST_START_YEAR:
        return SPLIT_TEST
    return SPLIT_PURGED


SPLIT_BOUNDARIES = [
    date(TRAIN_END_YEAR, 12, 31),
    date(DEV_YEAR, 12, 31),
    date(CAL_YEAR, 12, 31),
]
