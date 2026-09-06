"""Section geometry: distances, nearest-cell snapping, profile extraction."""
import numpy as np

from app.services.section import build, nearest_cell


def test_nearest_cell_snaps_to_closest_center():
    lat_axis = np.array([5.0, 5.5, 6.0])
    lon_axis = np.array([70.0, 70.5, 71.0])
    j, i = nearest_cell(5.6, 70.4, lat_axis, lon_axis)
    assert (j, i) == (1, 1)


def test_build_distances_monotonic_and_profiles_shaped():
    lat_axis = np.linspace(0, 10, 5)
    lon_axis = np.linspace(60, 70, 5)
    depths = np.array([0.0, 10.0, 20.0])
    mean = np.tile(np.array([28.0, 20.0, 15.0])[:, None, None], (1, 5, 5))
    sigma = np.full_like(mean, 0.5)
    glorys = mean + 0.1

    section = build(
        a=(1.0, 61.0), b=(9.0, 69.0), n=5,
        lat_axis=lat_axis, lon_axis=lon_axis, depths_m=depths,
        mean=mean, sigma=sigma, glorys=glorys,
        argo_index=None, date="2020-01-15", max_km=55, max_days=2,
    )
    assert len(section["distances_km"]) == 5
    assert section["distances_km"][0] == 0.0
    assert all(b >= a for a, b in zip(section["distances_km"], section["distances_km"][1:]))
    assert all(len(p) == 3 for p in section["poseidon"])
    assert section["poseidon"][0][0] == 28.0
    assert section["argo_markers"] == []


class _FakeArgoIndex:
    """Records day_window() call count; nearest_in_window() replays one canned match per point."""

    def __init__(self, matches):
        self.day_window_calls = 0
        self._matches = matches
        self._call = 0

    def day_window(self, date, max_days):
        self.day_window_calls += 1
        return object()

    def nearest_in_window(self, window, lat, lon, max_km):
        m = self._matches[self._call]
        self._call += 1
        return m


def test_build_dedupes_argo_markers_to_closest_hit_per_float():
    lat_axis = np.linspace(0, 10, 5)
    lon_axis = np.linspace(60, 70, 5)
    depths = np.array([0.0, 10.0, 20.0])
    mean = np.tile(np.array([28.0, 20.0, 15.0])[:, None, None], (1, 5, 5))

    matches = [
        {"wmo": "111", "distance_km": 30.0},
        {"wmo": "111", "distance_km": 10.0},  # closer hit for the same float
        {"wmo": "222", "distance_km": 5.0},
    ]
    argo_index = _FakeArgoIndex(matches)

    section = build(
        a=(1.0, 61.0), b=(9.0, 69.0), n=3,
        lat_axis=lat_axis, lon_axis=lon_axis, depths_m=depths,
        mean=mean, sigma=None, glorys=None,
        argo_index=argo_index, date="2020-01-15", max_km=55, max_days=2,
    )

    assert argo_index.day_window_calls == 1
    wmos = sorted(m["wmo"] for m in section["argo_markers"])
    assert wmos == ["111", "222"]
    marker_111 = next(m for m in section["argo_markers"] if m["wmo"] == "111")
    assert marker_111["distance_km"] == section["distances_km"][1]


def test_build_handles_nan_profile_gracefully():
    lat_axis = np.array([0.0, 1.0])
    lon_axis = np.array([60.0, 61.0])
    depths = np.array([0.0, 10.0])
    mean = np.full((2, 2, 2), np.nan)

    section = build(
        a=(0.0, 60.0), b=(1.0, 61.0), n=2,
        lat_axis=lat_axis, lon_axis=lon_axis, depths_m=depths,
        mean=mean, sigma=None, glorys=None,
        argo_index=None, date="2020-01-15", max_km=55, max_days=2,
    )
    assert section["poseidon"][0] == [None, None]
    assert section["d20_m"][0] is None
    assert section["mld_m"][0] is None
