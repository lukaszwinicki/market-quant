"""Parser Bank of England na syntetycznym HTML o układzie bankofengland.co.uk."""
import datetime as dt

import pytest

from src.data.calendar_boe import BASE, listing_pages, published_on

P = "/monetary-policy-summary-and-minutes"


def test_only_regular_meeting_slugs_are_scheduled():
    html = "".join(f'<a href="{P}/{path}">x</a>' for path in [
        "2016/mpc-january-2016", "2025/february-2025",
        "2020/13march-2020",
        "2020/monetary-policy-summary-for-the-special-monetary-policy-committee-meeting-on-19-march-2020",
        "2017/march-2016",                           # rok w slugu ≠ rok katalogu
    ]) + '<a href="/news/2023/december/mpc-dates-for-2025">y</a>'
    scheduled, other = listing_pages(html)
    assert scheduled == [f"{BASE}{P}/2016/mpc-january-2016", f"{BASE}{P}/2025/february-2025"]
    assert len(other) == 3


def page(text):
    return f"<main><h1>Bank Rate held</h1><div class='published-date'>{text}</div></main>"


def test_published_date_is_read_from_page():
    assert published_on(page("Published on 14 January 2016"), "x") == dt.date(2016, 1, 14)


def test_non_thursday_publication_is_an_error():
    with pytest.raises(ValueError, match="czwartek"):
        published_on(page("Published on 13 March 2020"), "x")      # piątek


def test_missing_date_is_an_error():
    with pytest.raises(ValueError, match="nie zgaduję"):
        published_on(page("Bank Rate held at 0.5%"), "x")
