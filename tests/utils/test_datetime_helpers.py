# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone

import pytest

from utils.datetime_helpers import (
    BEIJING_TZ,
    datetime_to_beijing_iso,
    to_beijing_time,
)


def test_to_beijing_time_from_naive_utc():
    utc_dt = datetime(2025, 10, 20, 16, 0, 0)

    beijing_dt = to_beijing_time(utc_dt)

    assert beijing_dt.tzinfo == BEIJING_TZ
    assert beijing_dt.hour == 0
    assert beijing_dt.day == 21


def test_to_beijing_time_from_aware_non_utc():
    paris_tz = timezone(timedelta(hours=2))
    aware_dt = datetime(2025, 10, 20, 18, 0, 0, tzinfo=paris_tz)

    beijing_dt = to_beijing_time(aware_dt)

    assert beijing_dt.tzinfo == BEIJING_TZ
    assert beijing_dt.hour == 0
    assert beijing_dt.day == 21


@pytest.mark.parametrize(
    "dt, expected",
    [
        (datetime(2025, 10, 20, 16, 0, 0), "2025-10-21T00:00:00+08:00"),
        (
            datetime(2025, 10, 20, 16, 0, 0, tzinfo=timezone.utc),
            "2025-10-21T00:00:00+08:00",
        ),
        (None, None),
    ],
)
def test_datetime_to_beijing_iso(dt, expected):
    assert datetime_to_beijing_iso(dt) == expected

