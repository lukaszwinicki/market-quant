"""Parser rocznych kalendarzy BLS na syntetycznym HTML o układzie bls.gov."""
import datetime as dt

import pytest

from src.data.calendar_bls import release_times_utc, schedule_rows

UTC = dt.timezone.utc


def page(rows) -> str:
    body = "".join(
        f'<tr class="release-list-even-row"><td class="date-cell"><p>{d}</p></td>\n'
        f'  <td class="time-cell"><p>{t}</p></td>\n'
        f'  <td class="desc-cell"><p><strong>{title}</strong>{rest}</p></td></tr>'
        for d, t, title, rest in rows)
    nav = '<li><a href="/cpi/">Consumer Price Index</a></li>'    # menu strony
    return f"<html>{nav}<table>{body}</table></html>"


ROWS = [
    ("Wednesday, January 20, 2016", "08:30 AM", "Consumer Price Index", " for December 2015"),
    ("Friday, February 5, 2016", "08:30 AM", "Employment Situation", " for January 2016"),
    ("Wednesday, March 16, 2016", "08:30 AM", "Consumer Price Index", " for February 2016"),
    ("Wednesday, March 16, 2016", "08:30 AM", "Producer Price Index", " for February 2016"),
    ("Thursday, July 14, 2016", "10:00 AM", "Consumer Price Index", " for June 2016"),
    ("Monday, May 30, 2016", "&nbsp;", "Memorial Day", ""),
]


def test_rows_ignore_navigation_links():
    rows = schedule_rows(page(ROWS))
    assert len(rows) == len(ROWS)
    assert rows[0][:3] == ("Wednesday, January 20, 2016", "08:30 AM", "Consumer Price Index")


def test_times_per_release_with_new_york_dst():
    got = release_times_utc(page(ROWS), "US_CPI")
    assert got == [dt.datetime(2016, 1, 20, 13, 30, tzinfo=UTC),    # EST
                   dt.datetime(2016, 3, 16, 12, 30, tzinfo=UTC),    # EDT (od 13.03)
                   dt.datetime(2016, 7, 14, 14, 0, tzinfo=UTC)]     # wyjątek z tabeli
    assert release_times_utc(page(ROWS), "US_NFP") == [dt.datetime(2016, 2, 5, 13, 30, tzinfo=UTC)]


def test_unreadable_time_for_the_series_is_an_error():
    bad = [("Friday, February 5, 2016", "TBD", "Employment Situation", " for January 2016")]
    with pytest.raises(ValueError, match="nie zgaduję"):
        release_times_utc(page(bad), "US_NFP")
