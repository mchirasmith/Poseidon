"""Split codes by year, purge windows at each boundary, no leakage across a purge gap."""
import numpy as np
import pandas as pd

from pipeline.sources import PURGE_DAYS, SPLIT_CAL, SPLIT_DEV, SPLIT_PURGED, SPLIT_TEST, SPLIT_TRAIN
from pipeline.split import split_codes


def test_codes_by_year():
    time = pd.date_range("2016-03-01", "2016-03-05")
    codes = split_codes(time)
    assert (codes == SPLIT_TRAIN).all()

    time = pd.date_range("2017-06-01", "2017-06-05")
    assert (split_codes(time) == SPLIT_DEV).all()

    time = pd.date_range("2019-06-01", "2019-06-05")
    assert (split_codes(time) == SPLIT_TEST).all()


def test_purge_window_at_each_boundary():
    time = pd.date_range("2016-12-01", "2017-01-31")
    codes = split_codes(time)
    boundary = pd.Timestamp("2016-12-31")
    for t, c in zip(time, codes):
        gap = (t - boundary).days
        if -(PURGE_DAYS - 1) <= gap <= PURGE_DAYS:
            assert c == SPLIT_PURGED
        elif gap < -(PURGE_DAYS - 1):
            assert c == SPLIT_TRAIN
        else:
            assert c == SPLIT_DEV


def test_no_train_day_within_purge_days_of_dev_or_test():
    time = pd.date_range("2014-01-01", "2020-12-31")
    codes = split_codes(time)
    train_days = np.array(time)[codes == SPLIT_TRAIN]
    other_days = np.array(time)[np.isin(codes, [SPLIT_DEV, SPLIT_CAL, SPLIT_TEST])]
    for boundary_day in other_days[:: max(1, len(other_days) // 50)]:
        min_gap = np.min(np.abs((train_days - boundary_day) / np.timedelta64(1, "D")))
        assert min_gap >= PURGE_DAYS
