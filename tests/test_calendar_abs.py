"""Parser ABS na syntetycznym HTML o układzie abs.gov.au i starego ausstats."""
import datetime as dt

import pytest

from src.data.calendar_abs import (
    new_release_time_utc, new_release_urls, old_release_time_utc, old_release_urls,
)

UTC = dt.timezone.utc
P = "/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia"


def test_new_list_takes_release_pages_only():
    html = (f'<a href="{P}/sep-quarter-2023">x</a><a href="{P}/oct-2025">y</a>'
            f'<a href="{P}/jul-2026/640101.xlsx">z</a><a href="{P}">all</a>')
    assert new_release_urls(html) == [f"https://www.abs.gov.au{P}/oct-2025",
                                      f"https://www.abs.gov.au{P}/sep-quarter-2023"]


def test_old_list_gives_url_and_reference_period():
    html = ("<li><a href='allprimarymainfeatures/6BDA735E785FECB3CA257FFC00133646?opendocument'>"
            "Consumer Price Index, Australia Mar 2016</a></li>"
            "<li><a href='allprimarymainfeatures/C73611BB292C8447CA257FA100231451?opendocument'>"
            "Consumer Price Index, Australia Dec 2015</a></li>")
    assert old_release_urls(html) == [
        ("https://www.abs.gov.au/AUSSTATS/abs@.nsf/allprimarymainfeatures/"
         "6BDA735E785FECB3CA257FFC00133646?opendocument", "Mar 2016"),
        ("https://www.abs.gov.au/AUSSTATS/abs@.nsf/allprimarymainfeatures/"
         "C73611BB292C8447CA257FA100231451?opendocument", "Dec 2015"),
    ]


@pytest.mark.parametrize("text, expected", [
    ("Release date and time 25/10/2023 11:30am AEDT", dt.datetime(2023, 10, 25, 0, 30)),
    ("Release date and time 26/08/2026 11:30am AEST", dt.datetime(2026, 8, 26, 1, 30)),
])
def test_new_page_time(text, expected):
    assert new_release_time_utc(f"<p>{text}</p>", "x") == expected.replace(tzinfo=UTC)


def test_new_page_zone_must_match_the_date():
    with pytest.raises(ValueError, match="AEDT"):
        new_release_time_utc("Release date and time 26/08/2026 11:30am AEDT", "x")


def test_old_page_time_canberra():
    html = "<p>Released at 11:30 AM (CANBERRA TIME) 27/04/2016</p>"
    assert old_release_time_utc(html, "x") == dt.datetime(2016, 4, 27, 1, 30, tzinfo=UTC)


def test_page_without_time_is_an_error():
    with pytest.raises(ValueError, match="nie zgaduję"):
        old_release_time_utc("<p>ARCHIVED ISSUE</p>", "x")
