"""Credential resolution (env/.env, store, netrc) and the parallel download path."""
from __future__ import annotations

import shutil

import numpy as np
import pytest
import zarr

from pipeline import download, run
from tests.test_real_assembly import GRID, YEAR, data_dir  # noqa: F401  (shared fixture + builders)

_ENV_VARS = (
    "COPERNICUSMARINE_SERVICE_USERNAME",
    "COPERNICUSMARINE_SERVICE_PASSWORD",
    "EARTHDATA_USERNAME",
    "EARTHDATA_PASSWORD",
)


@pytest.fixture(autouse=True)
def _isolated_creds(tmp_path, monkeypatch):
    """No real .env, credential store, or netrc leaks into these tests."""
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("POSEIDON_ENV_FILE", str(tmp_path / "does-not-exist.env"))
    monkeypatch.setattr(download, "COPERNICUS_CRED_FILE", tmp_path / "no-store")
    monkeypatch.setattr(download, "NETRC_FILE", tmp_path / "no-netrc")


def test_credentials_status_env_present(monkeypatch):
    monkeypatch.setenv("COPERNICUSMARINE_SERVICE_USERNAME", "u")
    monkeypatch.setenv("COPERNICUSMARINE_SERVICE_PASSWORD", "p")
    monkeypatch.setenv("EARTHDATA_USERNAME", "u")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "p")
    assert download.credentials_status() == {"copernicus": "env", "podaac": "env"}


def test_credentials_status_absent():
    assert download.credentials_status() == {"copernicus": None, "podaac": None}


def test_credentials_status_netrc_fallback(monkeypatch, tmp_path):
    netrc = tmp_path / "netrc-fallback"
    netrc.write_text(f"machine {download.URS_HOST}\nlogin someone\npassword secret\n")
    monkeypatch.setattr(download, "NETRC_FILE", netrc)
    status = download.credentials_status()
    assert status["podaac"] == "netrc"
    assert status["copernicus"] is None


def test_credentials_status_copernicus_store(monkeypatch, tmp_path):
    store = tmp_path / "store-file"
    store.write_text("not read, only existence checked")
    monkeypatch.setattr(download, "COPERNICUS_CRED_FILE", store)
    assert download.credentials_status()["copernicus"] == "store"


def test_subset_receives_username_password_from_env(monkeypatch, tmp_path):
    import copernicusmarine

    monkeypatch.setenv("COPERNICUSMARINE_SERVICE_USERNAME", "someone")
    monkeypatch.setenv("COPERNICUSMARINE_SERVICE_PASSWORD", "secret")

    calls = []
    monkeypatch.setattr(copernicusmarine, "subset", lambda **kwargs: calls.append(kwargs))

    product = download.CopernicusProduct(
        name="sst", dataset_id="dummy-dataset", variables=["analysed_sst"], source_step_deg=0.05
    )
    download.download_copernicus_month(product, 2014, 1, tmp_path / "raw")

    assert len(calls) == 1
    assert calls[0]["username"] == "someone"
    assert calls[0]["password"] == "secret"


def test_subset_omits_creds_when_env_absent(monkeypatch, tmp_path):
    import copernicusmarine

    calls = []
    monkeypatch.setattr(copernicusmarine, "subset", lambda **kwargs: calls.append(kwargs))

    product = download.CopernicusProduct(
        name="sst", dataset_id="dummy-dataset", variables=["analysed_sst"], source_step_deg=0.05
    )
    download.download_copernicus_month(product, 2014, 1, tmp_path / "raw")

    assert "username" not in calls[0] and "password" not in calls[0]


def test_download_workers_2_matches_sequential(data_dir):
    """Parallel and sequential downloads must assemble byte-identical stores.

    The interim manifest already marks every month done after the first (sequential, in-process
    mocked) build, so the ProcessPoolExecutor workers spawned for the second build read that real
    on-disk manifest and skip immediately -- no mocks need to cross the process boundary.
    """
    products = ["sst", "sss"]

    zarr_path = run.assemble_real(data_dir, products, YEAR, YEAR, GRID, download_workers=1)
    x_seq = zarr.open_consolidated(str(zarr_path))["x"][:]

    shutil.rmtree(zarr_path)
    (data_dir / "argo_matchups.parquet").unlink()

    zarr_path2 = run.assemble_real(data_dir, products, YEAR, YEAR, GRID, download_workers=2)
    x_par = zarr.open_consolidated(str(zarr_path2))["x"][:]

    np.testing.assert_array_equal(np.asarray(x_seq), np.asarray(x_par))
