"""Train/dev/cal/test split codes with a purge window at each year boundary."""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.sources import PURGE_DAYS, SPLIT_BOUNDARIES, SPLIT_PURGED, split_for_year


def split_codes(time: pd.DatetimeIndex) -> np.ndarray:
    """Split code per day: 0 train, 1 dev, 2 cal, 3 test, 255 purged."""
    codes = np.array([split_for_year(t.year) for t in time], dtype=np.uint8)
    days = time.normalize()
    for boundary in SPLIT_BOUNDARIES:
        b = pd.Timestamp(boundary)
        delta = (days - b).days
        purge = (delta >= -(PURGE_DAYS - 1)) & (delta <= PURGE_DAYS)
        codes[purge] = SPLIT_PURGED
    return codes
