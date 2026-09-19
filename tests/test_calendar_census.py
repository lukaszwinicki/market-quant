"""Parser Census na syntetycznym HTML i tekście nagłówków PDF (oba układy)."""
import datetime as dt

import pytest

from src.data.calendar_census import (
    historic_pdf_urls, listview_times_utc, pdf_release_time_utc,
)

UTC = dt.timezone.utc
U = "https://www2.census.gov/retail/releases/historical/marts/adv{}.pdf"


def listview(rows) -> str:
    return "<table>" + "".join(
        f'<tr height="20"><td height="20"><a href="/x">{name}</a></td>'
        f'<td sorttable_customkey="1">{d}</td><td>{t}</td><td>Dec</td></tr>'
        for name, d, t in rows) + "</table>"


def test_listview_takes_only_retail_rows_with_their_own_time():
    html = listview([
        ("Business Formation Statistics", "January 12, 2022", "10:00 AM"),
        ("Advance Monthly Sales for Retail and Food Services", "January 14, 2022", "8:30 AM"),
        ("Advance Monthly Sales for Retail and Food Services", "July 15, 2022", "10:00 AM"),
    ])
    assert listview_times_utc(html) == [dt.datetime(2022, 1, 14, 13, 30, tzinfo=UTC),
                                        dt.datetime(2022, 7, 15, 14, 0, tzinfo=UTC)]


@pytest.mark.parametrize("text, expected", [
    ("FOR IMMEDIATE RELEASE FRIDAY, FEBRUARY 12, 2016, AT 8:30 A.M. EST Rebecca",
     dt.datetime(2016, 2, 12, 13, 30)),
    ("FOR IMMEDIATE RELEASE WEDNESDAY APRIL 13, 2016, AT 8:30 A.M. EDT Rebecca",   # bez przecinka
     dt.datetime(2016, 4, 13, 12, 30)),
    ("Data adjusted for seasonal variation. FOR RELEASE AT 8:30 AM EST, FRIDAY, JANUARY 13, 2017",
     dt.datetime(2017, 1, 13, 13, 30)),
])
def test_pdf_header_layouts(text, expected):
    assert pdf_release_time_utc(text, "x") == expected.replace(tzinfo=UTC)


def test_next_release_sentence_is_not_taken_for_this_release():
    text = ("The August 2018 Advance Monthly Retail report is scheduled for release on "
            "September 14, 2018 at 8:30 a.m. EDT.")
    with pytest.raises(ValueError, match="nie zgaduję"):
        pdf_release_time_utc(text, "x")


def test_historic_links_are_filtered_by_data_month():
    html = "".join(f'<a href="{U.format(m)}">PDF</a>' for m in ("1511", "1512", "1601", "1912", "2001"))
    assert historic_pdf_urls(html, "1512", "1912") == [U.format("1512"), U.format("1601"),
                                                       U.format("1912")]
