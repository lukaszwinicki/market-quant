"""Źródło FRED/ALFRED na syntetycznych odpowiedziach API."""
import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from src.data.calendar_fred import events_for, first_release_dates, release_time

UTC = dt.timezone.utc
NY = ZoneInfo("America/New_York")


def test_first_release_dates_are_unique_and_sorted():
    obs = [{"date": "2016-01-01", "realtime_start": "2016-02-19", "value": "1"},
           {"date": "2015-12-01", "realtime_start": "2016-01-20", "value": "."},
           {"date": "2016-02-01", "realtime_start": "2016-02-19", "value": "2"}]
    assert first_release_dates(obs) == [dt.date(2016, 1, 20), dt.date(2016, 2, 19)]


@pytest.mark.parametrize("entry, err", [
    ({"local_time": "08:30", "timezone": "America/New_York", "quote": "x", "verified": False},
     PermissionError),
    ({"local_time": None, "timezone": "America/New_York", "quote": "x", "verified": True},
     ValueError),
    ({"local_time": "08:30", "timezone": "America/New_York", "quote": None, "verified": True},
     ValueError),
])
def test_time_needs_verification_and_a_source_quote(entry, err):
    with pytest.raises(err):
        release_time(entry, "US_CPI")


def test_local_time_converts_with_dst_of_the_release_date():
    at, tz = release_time({"local_time": "08:30", "timezone": "America/New_York",
                           "quote": "8:30 AM", "verified": True}, "US_CPI")
    ev = events_for("US_CPI", [dt.date(2016, 1, 20), dt.date(2016, 7, 15)], at, tz,
                    dt.date(2016, 1, 1), dt.date(2016, 12, 31))
    assert [e["timestamp_utc"] for e in ev] == [
        dt.datetime(2016, 1, 20, 13, 30, tzinfo=UTC),    # EST
        dt.datetime(2016, 7, 15, 12, 30, tzinfo=UTC),    # EDT
    ]
    assert {e["currency"] for e in ev} == {"USD"}


def test_events_are_limited_to_range_and_source_has_no_key():
    ev = events_for("US_NFP", [dt.date(2015, 12, 4), dt.date(2016, 1, 8)], dt.time(8, 30), NY,
                    dt.date(2016, 1, 1), dt.date(2016, 12, 31))
    assert len(ev) == 1
    assert ev[0]["source"] == "https://alfred.stlouisfed.org/series?seid=PAYEMS"
    assert "api_key" not in ev[0]["source"]
