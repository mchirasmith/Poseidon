"""Array-to-PNG rendering: orientation, land/NaN transparency, seafloor hatch, value round-trip."""
import numpy as np
from PIL import Image

from app.services import tiles

SCALES = {"mean": {"cmap": [[i, i, i] for i in range(256)], "vmin": 0.0, "vmax": 25.0}}


def _decode(png_bytes: bytes) -> np.ndarray:
    return np.array(Image.open(__import__("io").BytesIO(png_bytes)).convert("RGBA"))


def test_output_shape_and_row_orientation():
    h, w = 100, 240
    array = np.zeros((h, w))
    array[0, :] = 0.0  # southernmost row (input row 0)
    array[-1, :] = 25.0  # northernmost row (input row -1)
    wet = np.ones((h, w), dtype=np.uint8)
    png = tiles.render(array, "mean", SCALES, wet)
    img = _decode(png)
    assert img.shape == (h, w, 4)
    # output row 0 must be the northernmost input row (value 25 -> grey 255)
    assert img[0, 0, 0] == 255
    assert img[-1, 0, 0] == 0


def test_land_is_transparent():
    array = np.full((10, 10), 12.5)
    wet = np.ones((10, 10), dtype=np.uint8)
    wet[3, 4] = 0
    png = tiles.render(array, "mean", SCALES, wet)
    img = _decode(png)
    flipped_row, col = 10 - 1 - 3, 4
    assert img[flipped_row, col, 3] == 0


def test_nan_is_transparent():
    array = np.full((10, 10), 12.5)
    array[2, 2] = np.nan
    wet = np.ones((10, 10), dtype=np.uint8)
    png = tiles.render(array, "mean", SCALES, wet)
    img = _decode(png)
    flipped_row = 10 - 1 - 2
    assert img[flipped_row, 2, 3] == 0


def test_below_seafloor_hatch():
    array = np.full((4, 4), 12.5)
    wet = np.ones((4, 4), dtype=np.uint8)
    bottom = np.zeros((4, 4), dtype=np.uint8)  # everything below seafloor
    png = tiles.render(array, "mean", SCALES, wet, bottom)
    img = _decode(png)
    alphas = set(img[:, :, 3].ravel().tolist())
    assert alphas == {255}
    greys = {tuple(px) for px in img[:, :, :3].reshape(-1, 3).tolist()}
    assert greys == {(128, 128, 128), (96, 96, 96)}


def test_value_roundtrip_within_one_bin():
    n = 256
    vmin, vmax = SCALES["mean"]["vmin"], SCALES["mean"]["vmax"]
    ramp = np.linspace(vmin, vmax, n).reshape(1, n)
    wet = np.ones_like(ramp, dtype=np.uint8)
    png = tiles.render(ramp, "mean", SCALES, wet)
    img = _decode(png)
    bin_width = (vmax - vmin) / (n - 1)
    for col in range(n):
        recovered_idx = img[0, col, 0]  # grayscale cmap: channel value == bin index
        expected_idx = round((ramp[0, col] - vmin) / bin_width)
        assert abs(int(recovered_idx) - expected_idx) <= 1
