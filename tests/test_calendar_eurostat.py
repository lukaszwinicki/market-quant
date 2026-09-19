"""Parser Eurostatu na syntetycznych stronach o układzie products-euro-indicators."""
import datetime as dt

from src.data.calendar_eurostat import candidate_days, is_flash, page_title, release_url


def page(title: str) -> str:
    return f"<html><head><title>{title}</title></head><body>…</body></html>"


def test_url_has_the_date_in_the_identifier():
    assert release_url(dt.date(2016, 2, 29)) == (
        "https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-29022016-ap")


def test_title_of_a_release_and_of_a_missing_page():
    assert page_title(page("Euro area annual inflation down to -0.2% - Products Euro "
                           "Indicators - Eurostat")) == "Euro area annual inflation down to -0.2%"
    assert page_title(page("EU Login")) is None


def test_flash_title_differs_from_the_final_release():
    assert is_flash("Euro area annual inflation up to 0.9%")
    assert not is_flash("Annual inflation up to 10.6% in the euro area")


def test_candidates_are_weekdays_at_the_turn_of_the_month():
    days = candidate_days(dt.date(2016, 2, 20), dt.date(2016, 3, 10))
    assert days[0] == dt.date(2016, 2, 24)          # okno zaczyna się 24.
    assert dt.date(2016, 2, 27) not in days         # sobota
    assert dt.date(2016, 2, 29) in days
    assert dt.date(2016, 3, 7) in days
    assert dt.date(2016, 3, 8) not in days          # po 7. dniu miesiąca
