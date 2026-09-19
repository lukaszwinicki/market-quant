"""Parser FOMC na syntetycznym HTML o układzie stron federalreserve.gov."""
import datetime as dt

import pytest

from src.data.calendar_fomc import release_time_utc, scheduled_statements

UTC = dt.timezone.utc
PR = "/newsevents/pressreleases/monetary{}a.htm"


def historical(panels) -> str:
    return "".join(
        f'<h5 class="panel-heading panel-heading--shaded">{label}</h5>'
        f'<div><strong>Statement:</strong> <a href="{PR.format(d)}">HTML</a>'
        f'<a href="/newsevents/pressreleases/monetary{d}a1.htm">Note</a></div>'
        for label, d in panels)


def current(rows) -> str:
    return '<h5>Unrelated heading</h5>' + "".join(
        f'<div class="row fomc-meeting"><div class="fomc-meeting__month"><strong>X</strong></div>'
        f'<div class="fomc-meeting__date col-xs-4 col-lg-1">{label}</div>'
        f'<div><a href="{PR.format(d)}">HTML</a></div></div>'
        for label, d in rows)


def test_historical_page_skips_unscheduled_cancelled_and_notation_votes():
    html = historical([
        ("January 28-29 Meeting - 2020", "20200129"),
        ("March 2 (unscheduled) Meeting - 2020", "20200303"),
        ("March 15 (unscheduled) Meeting - 2020", "20200315"),
        ("March 17-18 (cancelled) Meeting - 2020", "20200319"),
        ("March 19 (notation vote) - 2020", "20200319"),
        ("April 28-29 Meeting - 2020", "20200429"),
    ])
    got = scheduled_statements(html, 2020)
    assert [u.rsplit("monetary", 1)[1] for _, u in got] == ["20200129a.htm", "20200429a.htm"]
    assert all(u.startswith("https://www.federalreserve.gov/") for _, u in got)


def test_current_page_uses_date_cells_and_filters_by_year():
    html = current([("13-14*", "20221214"), ("26-27", "20210127"),
                    ("22 (notation vote)", "20210822"), ("16-17*", "20210317")])
    got = scheduled_statements(html, 2021)
    assert [label for label, _ in got] == ["26-27", "16-17*"]


@pytest.mark.parametrize("text, date, expected", [
    ("For release at 2:00 p.m. EST", "20160127", dt.datetime(2016, 1, 27, 19, 0)),
    ("For release at 2:00 p.m. EDT", "20160615", dt.datetime(2016, 6, 15, 18, 0)),
    ("For release at 11:00 a.m. EDT", "20191011", dt.datetime(2019, 10, 11, 15, 0)),
    ("For release at 12:30 p.m. EST", "20170201", dt.datetime(2017, 2, 1, 17, 30)),
])
def test_release_time_comes_from_the_page(text, date, expected):
    html = f'<p class="article__time">X</p><p>{text}   \r\n </p>'
    assert release_time_utc(html, PR.format(date)) == expected.replace(tzinfo=UTC)


def test_missing_release_time_is_an_error_not_a_guess():
    with pytest.raises(ValueError, match="nie zgaduję"):
        release_time_utc('<p class="article__time">January 28, 2015</p>', PR.format("20150128"))
