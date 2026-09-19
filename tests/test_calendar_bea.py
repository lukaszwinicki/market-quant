"""Parser BEA na syntetycznym HTML — warianty nagłówków spotkane w archiwum."""
import datetime as dt

import pytest

from src.data.calendar_bea import archive_rows, embargo_time_utc, wanted

UTC = dt.timezone.utc
URL = "https://www.bea.gov/news/2016/x"


@pytest.mark.parametrize("header, expected", [
    ("EMBARGOED UNTIL RELEASE AT 10:00 A.M. EST, Friday, February 26, 2016",
     dt.datetime(2016, 2, 26, 15, 0)),
    ("EMBARGOED FOR RELEASE: 8:30 A.M. EDT, Friday, March 26, 2021",
     dt.datetime(2021, 3, 26, 12, 30)),
    ("EMBARGOED UNTIL RELEASE AT 8:30 A.M. EDT, Friday July 29, 2022",       # bez przecinka
     dt.datetime(2022, 7, 29, 12, 30)),
    ("EMBARGOED UNTIL RELEASE AT 8:30 A.M. EDT, Friday, Sept. 30, 2016",
     dt.datetime(2016, 9, 30, 12, 30)),
    ("EMBARGOED UNTIL RELEASE AT 9:30 A.M. EDT, Thursday, October 31, 2019",
     dt.datetime(2019, 10, 31, 13, 30)),
])
def test_embargo_header_variants(header, expected):
    html = f"<div><p>{header}</p><p>BEA 16-07 Personal Income</p></div>"
    assert embargo_time_utc(html, URL) == expected.replace(tzinfo=UTC)


def test_missing_header_is_an_error_not_a_guess():
    with pytest.raises(ValueError, match="nie zgaduję"):
        embargo_time_utc("<p>Next release: April 30, 2021 at 8:30 A.M. EDT</p>", URL)


@pytest.mark.parametrize("name, title, ok", [
    ("US_PCE", "Personal Income and Outlays, January 2016", True),
    ("US_PCE", "Personal Income and Outlays: May 2020", True),
    ("US_PCE", "Personal Income, February 2019; Personal Outlays, January 2019", True),
    ("US_PCE", "Personal Income and Outlays, Data Update, September 2025", False),
    ("US_PCE", "Personal Income by State, 2nd Quarter 2016", False),
    ("US_GDP_ADVANCE", "GDP (Advance Estimate), 1st Quarter 2026", True),
    ("US_GDP_ADVANCE", "Gross Domestic Product: Fourth Quarter and Annual 2015 (Advance Estimate)", True),
    # prawdziwe tytuły z archiwum BEA
    ("US_GDP_ADVANCE", "Gross Domestic Product, Fourth Quarter and Annual 2018 (Initial Estimate)", True),
    ("US_GDP_ADVANCE", "Gross Domestic Product, Second Quarter 2019 (Advance Estimate) and Annual Update", True),
    ("US_GDP_ADVANCE", "GDP (Second Estimate) and Corporate Profits, 1st Quarter 2026", False),
    ("US_GDP_ADVANCE", "GDP (Third Estimate), Industries, Corporate Profits, 1st Quarter 2026", False),
])
def test_title_filter(name, title, ok):
    assert wanted(name, title) is ok


def test_archive_rows():
    html = ('<tr><td><a href="/news/2016/personal-income-and-outlays-january-2016" hreflang="en">'
            'Personal Income and Outlays, January 2016</a></td>'
            '<td><time datetime="2016-02-26T08:30:00-05:00">February 26, 2016</time></td></tr>')
    assert archive_rows(html) == [("https://www.bea.gov/news/2016/personal-income-and-outlays-january-2016",
                                   2016, "Personal Income and Outlays, January 2016")]
