"""Parser ONS na syntetycznym HTML o układzie kalendarza ons.gov.uk."""
import datetime as dt

import pytest

from src.data.calendar_ons import (
    bulletin_release_date, calendar_items, release_times_utc, result_count,
)

UTC = dt.timezone.utc


def item(title, url, day, at):
    # Tytuł jak na stronie: słowa zapytania w <em>, całość zakodowana podwójnie.
    enc = (title.replace("price", '<em class="ons-highlight">price</em>')
           .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&#34;"))
    return (f'<li><a href="{url}" data-gtm-release-title = "{enc}"\n'
            f'  data-gtm-release-url="{url}"\n  data-gtm-release-date="{day}"\n'
            f'  data-gtm-release-time="{at}"\n  data-gtm-release-calendar-page="1">{title}</a></li>')


PAGE = ("<span>Published (6)</span><ol>" + "".join([
    item("UK consumer price inflation: Jan 2016", "/releases/a", "20160216", "09:30"),
    item("Consumer price inflation, UK: August 2020", "/releases/b", "20200819", "07:00"),
    item("Consumer price inflation, UK: August 2020 time series", "/releases/c", "20200819", "07:00"),
    item("Labour market statistics: February 2016", "/releases/d", "20160217", "09:30"),
    item("UK Labour Market April 2024", "/releases/e", "20240416", "07:00"),
    item("Labour market in the regions of the UK: April 2024", "/releases/f", "20240416", "07:00"),
]) + "</ol>")


def test_items_and_count():
    items = calendar_items(PAGE)
    assert result_count(PAGE) == len(items) == 6
    assert items[1] == ("Consumer price inflation, UK: August 2020",
                        "https://www.ons.gov.uk/releases/b", dt.date(2020, 8, 19), "07:00")


def test_only_main_releases_with_london_time():
    items = calendar_items(PAGE)
    assert release_times_utc(items, "UK_CPI") == [
        (dt.datetime(2016, 2, 16, 9, 30, tzinfo=UTC), "https://www.ons.gov.uk/releases/a"),  # GMT
        (dt.datetime(2020, 8, 19, 6, 0, tzinfo=UTC), "https://www.ons.gov.uk/releases/b"),   # BST
    ]
    assert [u for _, u in release_times_utc(items, "UK_LABOUR")] == [
        "https://www.ons.gov.uk/releases/d", "https://www.ons.gov.uk/releases/e"]


def test_release_without_time_is_an_error():
    items = calendar_items(item("UK labour market: May 2024", "/releases/g", "20240514", ""))
    with pytest.raises(ValueError, match="nie zgaduję"):
        release_times_utc(items, "UK_LABOUR")


def test_bulletin_release_date():
    html = "<p>Contact: Email James Tucker</p><p>Release date: <br>19 January 2016</p>"
    assert bulletin_release_date(html, "x") == dt.date(2016, 1, 19)
