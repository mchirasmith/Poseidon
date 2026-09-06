"""Window builder, tiler and sampler behaviour on the synthetic store."""
import shutil

import numpy as np
import pytest
import zarr

from model.dataset import Sampler, Store, Tiler, full_domain_batch, pad_to_multiple


@pytest.fixture(scope="module")
def store(synthetic_store):
    return Store.open(synthetic_store / "poseidon.zarr")


def test_window_shape(store):
    w = store.window(20, 3)
    assert w.shape == (3, 12, store.H, store.W)
    assert w.dtype == np.float32


def test_window_before_store_start_is_zero_with_mask_zero(store):
    """Days before t=0 fall outside the store; the window fills them with zeros and mask 0."""
    w = store.window(1, 5)  # needs days -3..1
    assert np.all(w[0] == 0.0)
    assert np.all(w[1] == 0.0)
    assert not np.all(w[-1] == 0.0)  # day 1 itself is real data


def test_purged_day_is_zero_with_mask_zero(store):
    """field_day flags a purged day as fully invalid (mask 0); window() then zero-fills it."""
    purged = np.where(store.split == 255)[0]
    assert len(purged) > 0
    t = int(purged[0])
    x, m = store.field_day(t)
    assert np.all(m == 0)
    w = store.window(t, 1)
    assert np.all(w == 0.0)


def test_day_target_mask_matches_wet_and_bottom(store):
    y, mask = store.day_target(100)
    assert y.shape == (store.n_depth, store.H, store.W)
    assert mask.dtype == bool
    # a masked-out cell must not be wet-and-bottom-and-valid everywhere at once
    assert mask.sum() <= (store.wet.astype(bool)[None] & store.bottom.astype(bool)).sum()


def test_tiler_core_covers_domain_exactly_once(store):
    tiler = Tiler(store.H, store.W, tile=16, core=12)
    coverage = np.zeros((store.H, store.W), dtype=int)
    for oh, ow in tiler.tiles:
        core = tiler.core_mask(oh, ow)
        h1, w1 = min(oh + tiler.tile, store.H), min(ow + tiler.tile, store.W)
        core_valid = core[: h1 - oh, : w1 - ow]
        coverage[oh:h1, ow:w1] += core_valid.astype(int)
    assert np.all(coverage == 1)


def test_tiler_core_is_centred_except_at_domain_edges():
    H, W, tile, core = 100, 100, 16, 12
    tiler = Tiler(H, W, tile, core)
    margin = (tile - core) // 2
    for oh, s0, s1 in tiler.plan_h:
        if oh in (0, H - tile):
            continue
        assert s0 - oh == margin and s1 - s0 == core
    for ow, s0, s1 in tiler.plan_w:
        if ow in (0, W - tile):
            continue
        assert s0 - ow == margin and s1 - s0 == core


def test_tiler_pads_when_domain_smaller_than_tile():
    tiler = Tiler(H=4, W=6, tile=16, core=12)
    assert tiler.plan_h == [(0, 0, 4)]
    arr = np.ones((4, 6), dtype=np.float32)
    crop, valid = tiler.extract(arr, 0, 0)
    assert crop.shape == (16, 16)
    assert valid[:4, :6].all()
    assert not valid[4:, :].any()


def test_sampler_skips_low_wet_tiles(store):
    tiler = Tiler(store.H, store.W, tile=16, core=12)
    rng = np.random.default_rng(0)
    threshold = 0.3
    sampler = Sampler(store, tiler, store.train_days(), min_wet_frac=threshold, rng=rng)
    all_origins = {(oh, ow) for oh, _, _ in tiler.plan_h for ow, _, _ in tiler.plan_w}
    for oh, ow in sampler.eligible:
        wet_crop, valid = tiler.extract(store.wet.astype(np.float32), oh, ow)
        assert wet_crop.sum() / valid.sum() >= threshold
    skipped = all_origins - set(sampler.eligible)
    for oh, ow in skipped:
        wet_crop, valid = tiler.extract(store.wet.astype(np.float32), oh, ow)
        assert wet_crop.sum() / valid.sum() < threshold


def test_full_domain_batch_pads_to_multiple_of_8(store):
    x, s, h, w = full_domain_batch(store, 50, window=3, mult=8)
    assert x.shape[-2] % 8 == 0 and x.shape[-1] % 8 == 0
    assert s.shape[-2] % 8 == 0 and s.shape[-1] % 8 == 0
    assert (h, w) == (store.H, store.W)


def test_pad_to_multiple_noop_when_already_aligned():
    arr = np.zeros((3, 16, 24))
    out, h, w = pad_to_multiple(arr, 8)
    assert out.shape == arr.shape
    assert (h, w) == (16, 24)


def test_sampler_only_yields_days_in_years_train_and_split_zero(store):
    tiler = Tiler(store.H, store.W, tile=16, core=12)
    rng = np.random.default_rng(0)
    years = store.time.astype("datetime64[Y]").astype(int) + 1970
    y0, y1 = 2015, 2015
    train_days = np.where((store.split == 0) & (years >= y0) & (years <= y1))[0]
    sampler = Sampler(store, tiler, train_days, min_wet_frac=0.0, rng=rng)
    for t, _, _ in sampler.sample(200):
        assert store.split[t] == 0
        assert y0 <= years[t] <= y1


def test_window_never_reads_beyond_t(synthetic_store, tmp_path):
    """Perturbing day t+1 in the store must not change window(t, k)."""
    copy_path = tmp_path / "poseidon.zarr"
    shutil.copytree(synthetic_store / "poseidon.zarr", copy_path)
    store = Store.open(copy_path)
    t, k = 50, 3
    before = store.window(t, k).copy()

    root = zarr.open(str(copy_path), mode="r+")
    root["x"][t + 1] = root["x"][t + 1] + 1000.0

    after = Store.open(copy_path).window(t, k)
    assert np.array_equal(before, after)
