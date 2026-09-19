"""Parser Statistics Canada na syntetycznym JSON i tekście PDF o układzie The Daily."""
import datetime as dt
import json

import pytest

from src.data.calendar_statcan import releases, release_time_utc

UTC = dt.timezone.utc
KEY = json.dumps([
    {"date": "2016-02-19 00:00:01", "type": "meeting", "title": "Consumer Price Index",
     "description": "January 2016", "url": "/daily-quotidien/160219/dq160219a-eng.htm"},
    {"date": "2016-02-19 00:00:02", "type": "meeting", "title": "Retail trade",
     "description": "December 2015", "url": "/daily-quotidien/160219/dq160219b-eng.htm"},
    {"date": "2020-08-19 00:00:01", "type": "meeting", "title": "Consumer Price Index",
     "description": "July 2020", "url": "/daily-quotidien/200819/dq200819b-eng.htm"},
    {"date": "2026-10-19 00:00:01", "type": "meeting", "title": "Consumer Price Index",
     "description": "September 2026", "url": ""},                         # zapowiedź
])


def test_releases_pick_series_and_point_to_pdf():
    assert releases(KEY, "CA_CPI") == [
        (dt.date(2016, 2, 19),
         "https://www150.statcan.gc.ca/n1/daily-quotidien/160219/dq160219a-eng.pdf"),
        (dt.date(2020, 8, 19),
         "https://www150.statcan.gc.ca/n1/daily-quotidien/200819/dq200819b-eng.pdf"),
        (dt.date(2026, 10, 19), None),
    ]


@pytest.mark.parametrize("header, day, expected", [
    ("Released at 8:30 a.m. Eastern time in The Daily, Friday, February 19, 2016",
     dt.date(2016, 2, 19), dt.datetime(2016, 2, 19, 13, 30)),               # EST
    # pypdf bez spacji; czas letni
    ("Releasedat8:30a.m.EasterntimeinTheDaily,Tuesday,April15,2025",
     dt.date(2025, 4, 15), dt.datetime(2025, 4, 15, 12, 30)),               # EDT
])
def test_time_from_pdf_header(header, day, expected):
    text = f"ConsumerPriceIndex,January 2016\n{header}\nThe Consumer Price Index rose"
    assert release_time_utc(text, day, "x") == expected.replace(tzinfo=UTC)


def test_header_date_must_match_calendar():
    with pytest.raises(ValueError, match="kalendarz"):
        release_time_utc("Released at 8:30 a.m. Eastern time in The Daily, Friday, "
                         "February 19, 2016", dt.date(2016, 2, 18), "x")


def test_missing_header_is_an_error():
    with pytest.raises(ValueError, match="nie zgaduję"):
        release_time_utc("The Consumer Price Index rose 2.0%", dt.date(2016, 2, 19), "x")
