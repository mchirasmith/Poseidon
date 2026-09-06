"""Copernicus Marine, PO.DAAC and Argo downloads with a resumable manifest.

Never runs in tests: every function here needs network and/or credentials.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import requests
import xarray as xr

from pipeline.interim import _std_dims
from pipeline.sources import (
    ARGO_DAC_BASE_URL,
    ARGO_INDEX_URL,
    BOX_LAT_MAX,
    BOX_LAT_MIN,
    BOX_LON_MAX,
    BOX_LON_MIN,
    GLORYS_MAX_DEPTH_M,
    PRODUCTS,
    CopernicusProduct,
    PodaacProduct,
)

MANIFEST_NAME = "manifest.json"
COPERNICUS_CRED_FILE = Path.home() / ".copernicusmarine" / ".copernicusmarine-credentials"
NETRC_FILE = Path.home() / ".netrc"
URS_HOST = "urs.earthdata.nasa.gov"
ARGO_REQUEST_TIMEOUT_S = 60


def credentials_status() -> dict[str, bool]:
    """Which of the two services can be used without prompting, for the CLI to check up front."""
    import os

    copernicus = COPERNICUS_CRED_FILE.exists() or bool(
        os.environ.get("COPERNICUSMARINE_SERVICE_USERNAME") and os.environ.get("COPERNICUSMARINE_SERVICE_PASSWORD")
    )
    podaac = bool(os.environ.get("EARTHDATA_USERNAME") and os.environ.get("EARTHDATA_PASSWORD"))
    if not podaac and NETRC_FILE.exists():
        podaac = URS_HOST in NETRC_FILE.read_text()
    return {"copernicus": copernicus, "podaac": podaac}


def credentials_instructions(needed: set[str] | None = None) -> str:
    lines = ["Missing credentials. Fix with:"]
    if needed is None or "copernicus" in needed:
        lines.append("  Copernicus Marine: `uv run copernicusmarine login`")
    if needed is None or "podaac" in needed:
        lines.append(f"  NASA Earthdata: add to {NETRC_FILE}:")
        lines.append(f"    machine {URS_HOST} login <user> password <pass>")
        lines.append("    then `chmod 600 ~/.netrc`")
    return "\n".join(lines)


def _manifest_path(base_dir: Path, product: str) -> Path:
    return base_dir / product / MANIFEST_NAME


def _load_manifest(base_dir: Path, product: str) -> dict:
    path = _manifest_path(base_dir, product)
    if path.exists():
        return json.loads(path.read_text())
    return {"completed": []}


def _save_manifest(base_dir: Path, product: str, manifest: dict) -> None:
    # One manifest per product, written via rename, so parallel product downloads never clobber each other.
    path = _manifest_path(base_dir, product)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, indent=2))
    tmp.replace(path)


def is_done(base_dir: Path, product: str, month: str) -> bool:
    return month in _load_manifest(base_dir, product)["completed"]


def mark_done(base_dir: Path, product: str, month: str) -> None:
    manifest = _load_manifest(base_dir, product)
    if month not in manifest["completed"]:
        manifest["completed"].append(month)
    _save_manifest(base_dir, product, manifest)


def _month_range(year: int, month: int) -> tuple[str, str]:
    start = pd.Timestamp(year, month, 1)
    end = start + pd.offsets.MonthEnd(0)
    return start.strftime("%Y-%m-%dT00:00:00"), end.strftime("%Y-%m-%dT23:59:59")


def download_copernicus_month(product: CopernicusProduct, year: int, month: int, raw_dir: Path) -> Path:
    """Server-side subset to raw/<product>/<yyyy-mm>.nc, skipping if already downloaded."""
    import copernicusmarine

    out_dir = raw_dir / product.name
    out_dir.mkdir(parents=True, exist_ok=True)
    month_key = f"{year:04d}-{month:02d}"
    out_file = f"{month_key}.nc"
    start, end = _month_range(year, month)

    if is_done(raw_dir, product.name, month_key):
        return out_dir / out_file

    kwargs = dict(
        dataset_id=product.dataset_id,
        variables=product.variables,
        minimum_longitude=BOX_LON_MIN,
        maximum_longitude=BOX_LON_MAX,
        minimum_latitude=BOX_LAT_MIN,
        maximum_latitude=BOX_LAT_MAX,
        start_datetime=start,
        end_datetime=end,
        output_filename=out_file,
        output_directory=str(out_dir),
        coordinates_selection_method="inside",
        skip_existing=True,
    )
    if product.name == "glorys":
        kwargs["maximum_depth"] = GLORYS_MAX_DEPTH_M
    copernicusmarine.subset(**kwargs)
    mark_done(raw_dir, product.name, month_key)
    return out_dir / out_file


def _podaac_login():
    """Try netrc then environment, skipping a strategy with no usable credentials; never interactive."""
    import earthaccess
    from earthaccess.exceptions import LoginStrategyUnavailable

    for strategy in ("netrc", "environment"):
        try:
            auth = earthaccess.login(strategy=strategy)
        except LoginStrategyUnavailable:
            continue
        if auth.authenticated:
            return auth
    raise RuntimeError("PO.DAAC login failed: no usable Earthdata credentials in netrc or environment")


def _crop_to_box(ds: xr.Dataset, product: PodaacProduct) -> xr.Dataset:
    """Standardise dims, sort ascending, subset to the product's variables, and crop to the box."""
    ds = _std_dims(ds)
    if "lon" in ds.coords:
        ds = ds.assign_coords(lon=((ds["lon"] + 180) % 360) - 180)
    ds = ds.sortby([d for d in ("lat", "lon") if d in ds.coords])
    keep = [v for v in product.variables if v in ds.data_vars]
    box = ds[keep].sel(lat=slice(BOX_LAT_MIN, BOX_LAT_MAX), lon=slice(BOX_LON_MIN, BOX_LON_MAX))
    if box.sizes.get("lat", 0) == 0 or box.sizes.get("lon", 0) == 0:
        raise ValueError(f"empty crop for {product.name}: source grid does not cover the target box")
    return box.load()


def download_podaac_month(product: PodaacProduct, year: int, month: int, raw_dir: Path) -> Path:
    """PO.DAAC files are global; search+download per month, crop to the box, concat, delete globals."""
    import earthaccess

    out_dir = raw_dir / product.name
    out_dir.mkdir(parents=True, exist_ok=True)
    month_key = f"{year:04d}-{month:02d}"
    out_file = out_dir / f"{month_key}.nc"

    if is_done(raw_dir, product.name, month_key):
        return out_file

    _podaac_login()
    start, end = _month_range(year, month)
    results = earthaccess.search_data(
        short_name=product.short_name,
        temporal=(start, end),
        bounding_box=(BOX_LON_MIN, BOX_LAT_MIN, BOX_LON_MAX, BOX_LAT_MAX),
        count=-1,
    )
    tmp_dir = out_dir / f"_tmp_{month_key}"
    tmp_dir.mkdir(exist_ok=True)
    files = earthaccess.download(results, str(tmp_dir))

    cropped = []
    for f in files:
        with xr.open_dataset(f) as ds:
            cropped.append(_crop_to_box(ds, product))
    combined = xr.concat(cropped, dim="time").sortby("time")
    combined.to_netcdf(out_file)
    shutil.rmtree(tmp_dir)
    mark_done(raw_dir, product.name, month_key)
    return out_file


def download_argo_index() -> pd.DataFrame:
    resp = requests.get(ARGO_INDEX_URL, timeout=ARGO_REQUEST_TIMEOUT_S)
    resp.raise_for_status()
    lines = [l for l in resp.text.splitlines() if l and not l.startswith("#")]
    header = lines[0].split(",")
    rows = [l.split(",") for l in lines[1:]]
    df = pd.DataFrame(rows, columns=header)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d%H%M%S", errors="coerce")
    return df


def filter_argo_index(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    in_box = (
        df["latitude"].between(BOX_LAT_MIN, BOX_LAT_MAX)
        & df["longitude"].between(BOX_LON_MIN, BOX_LON_MAX)
        & df["date"].between(pd.Timestamp(start), pd.Timestamp(end))
    )
    return df[in_box].reset_index(drop=True)


def download_argo_profiles(index: pd.DataFrame, raw_dir: Path) -> list[Path]:
    """Fetch profile files into raw/argo/, resuming by skipping files already on disk."""
    out_dir = raw_dir / "argo"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for file_rel in index["file"]:
        dest = out_dir / Path(file_rel).name
        if not dest.exists():
            resp = requests.get(ARGO_DAC_BASE_URL + file_rel, timeout=ARGO_REQUEST_TIMEOUT_S)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
        paths.append(dest)
    return paths


def main() -> None:
    """`--check`: exit 1 with setup instructions if either service's credentials are missing."""
    import argparse
    import sys

    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    if not args.check:
        return
    status = credentials_status()
    missing = {s for s, ok in status.items() if not ok}
    if missing:
        print(credentials_instructions(missing))
        sys.exit(1)
    print("credentials ok")


if __name__ == "__main__":
    main()
