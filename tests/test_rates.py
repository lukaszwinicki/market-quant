"""Stopy procentowe: opóźnienie o miesiąc, znak różnicy, pokrycie.

Najważniejszy test: seria miesięczna dla stycznia NIE MOŻE być użyta do
wyceny transakcji ze stycznia. To średnia z całego miesiąca, znana dopiero
po jego końcu.
"""
from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from src.data.rates import (
    SCHEMA, coverage_gaps, differential, rate_on, require_coverage,
    require_coverage_for_decisions,
)


def rates(rows) -> pl.DataFrame:
    """(waluta, rok, miesiąc, wartość) → ramka stóp overnight."""
    return pl.DataFrame(
        [{"date": dt.date(y, m, 1), "currency": c, "kind": "overnight",
          "value": v, "series": "TEST"} for c, y, m, v in rows],
        schema=SCHEMA)


MONTHLY = rates([("USD", 2020, 1, 1.50), ("USD", 2020, 2, 1.60),
                 ("USD", 2020, 3, 0.60), ("USD", 2020, 4, 0.05),
                 ("EUR", 2020, 1, -0.45), ("EUR", 2020, 2, -0.45),
                 ("EUR", 2020, 3, -0.45), ("EUR", 2020, 4, -0.46)])


# --- opóźnienie o miesiąc ---------------------------------------------------

def test_decision_in_march_uses_the_february_rate():
    assert rate_on(MONTHLY, "USD", dt.date(2020, 3, 15)) == 1.60


def test_first_and_last_day_of_a_month_use_the_same_rate():
    assert (rate_on(MONTHLY, "USD", dt.date(2020, 3, 1))
            == rate_on(MONTHLY, "USD", dt.date(2020, 3, 31)) == 1.60)


def test_the_current_month_value_is_never_used():
    """Marzec 2020 spadł z 1,60 do 0,60 — gdyby wyciekał, byłoby to widać."""
    for day in (1, 10, 31):
        assert rate_on(MONTHLY, "USD", dt.date(2020, 3, day)) != 0.60


def test_january_rolls_back_across_the_year_boundary():
    r = rates([("USD", 2019, 12, 2.40), ("USD", 2020, 1, 1.50)])
    assert rate_on(r, "USD", dt.date(2020, 1, 20)) == 2.40


def test_a_date_before_the_first_observation_is_an_error_not_zero():
    with pytest.raises(KeyError, match="brak stopy"):
        rate_on(MONTHLY, "USD", dt.date(2020, 1, 15))


def test_unknown_currency_is_an_error():
    with pytest.raises(KeyError):
        rate_on(MONTHLY, "NZD", dt.date(2020, 3, 15))


def test_unknown_kind_is_rejected():
    with pytest.raises(ValueError, match="nieznany rodzaj"):
        rate_on(MONTHLY, "USD", dt.date(2020, 3, 15), kind="yield_10y")


def test_gaps_are_filled_from_the_last_available_month():
    """Dziura w serii nie ma zwracać zera — bierzemy ostatni znany odczyt."""
    r = rates([("USD", 2020, 1, 1.50), ("USD", 2020, 4, 0.05)])
    assert rate_on(r, "USD", dt.date(2020, 4, 15)) == 1.50


# --- znak różnicy -----------------------------------------------------------

def test_differential_is_base_minus_quote():
    # EURUSD w marcu: EUR(luty) −0,45 − USD(luty) 1,60 = −2,05
    assert differential(MONTHLY, "EURUSD", dt.date(2020, 3, 15)) == pytest.approx(-2.05)


def test_differential_flips_with_the_pair_direction():
    d1 = differential(MONTHLY, "EURUSD", dt.date(2020, 3, 15))
    d2 = differential(MONTHLY, "USDEUR", dt.date(2020, 3, 15))
    assert d1 == pytest.approx(-d2)


def test_positive_differential_means_the_base_currency_pays_more():
    r = rates([("AUD", 2020, 1, 3.0), ("JPY", 2020, 1, -0.1)])
    assert differential(r, "AUDJPY", dt.date(2020, 2, 10)) == pytest.approx(3.1)


# --- pokrycie ---------------------------------------------------------------

def test_complete_coverage_reports_no_gaps():
    rows = [("USD", 2020, m, 1.0) for m in range(1, 13)]
    assert coverage_gaps(rates(rows), ("USD",), "overnight",
                         dt.date(2020, 1, 1), dt.date(2020, 12, 31)) == []


def test_missing_months_are_counted_per_currency():
    rows = ([("USD", 2020, m, 1.0) for m in range(1, 13)]
            + [("EUR", 2020, m, 1.0) for m in range(1, 10)])
    gaps = coverage_gaps(rates(rows), ("USD", "EUR"), "overnight",
                         dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert gaps == [("EUR", 3)]


def test_a_currency_absent_entirely_is_reported_as_fully_missing():
    rows = [("USD", 2020, m, 1.0) for m in range(1, 13)]
    gaps = coverage_gaps(rates(rows), ("USD", "JPY"), "overnight",
                         dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert gaps == [("JPY", 12)]


def test_require_coverage_raises_on_a_gap():
    rows = [("USD", 2020, m, 1.0) for m in range(1, 11)]
    with pytest.raises(ValueError, match="USD brakuje 2"):
        require_coverage(rates(rows), ("USD",), "overnight",
                         dt.date(2020, 1, 1), dt.date(2020, 12, 31))


def test_require_coverage_passes_when_complete():
    rows = [("USD", 2020, m, 1.0) for m in range(1, 13)]
    require_coverage(rates(rows), ("USD",), "overnight",
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))


def test_coverage_spans_a_year_boundary():
    rows = ([("USD", 2020, m, 1.0) for m in range(11, 13)]
            + [("USD", 2021, m, 1.0) for m in range(1, 3)])
    assert coverage_gaps(rates(rows), ("USD",), "overnight",
                         dt.date(2020, 11, 1), dt.date(2021, 2, 28)) == []


# --- pokrycie liczone dniami decyzji ----------------------------------------
#
# Bramka 1 przeszła kontrolę wstępną, policzyła 200 powtórzeń i dopiero
# `apply_financing` rzucił „brak stopy overnight dla USD na 2015-01-22".
# Seria zaczynała się dokładnie tam, gdzie split — a `rate_on()` czyta
# miesiąc wcześniejszy. Kontrola sprawdzała nie te miesiące, co kod.

def test_series_starting_with_the_split_does_not_cover_the_first_month():
    rows = [("USD", 2020, m, 1.0) for m in range(1, 13)]
    with pytest.raises(ValueError, match="USD brakuje 1"):
        require_coverage_for_decisions(
            rates(rows), ("USD",), "overnight",
            dt.date(2020, 1, 1), dt.date(2020, 11, 30))


def test_one_extra_month_before_the_split_is_enough():
    rows = ([("USD", 2019, 12, 1.0)]
            + [("USD", 2020, m, 1.0) for m in range(1, 12)])
    require_coverage_for_decisions(
        rates(rows), ("USD",), "overnight",
        dt.date(2020, 1, 1), dt.date(2020, 12, 31))


def test_the_month_of_the_last_decision_day_is_not_required():
    """Grudniowa decyzja czyta listopad, więc grudnia w serii być nie musi."""
    rows = ([("USD", 2019, 12, 1.0)]
            + [("USD", 2020, m, 1.0) for m in range(1, 12)])
    require_coverage_for_decisions(
        rates(rows), ("USD",), "overnight",
        dt.date(2020, 12, 1), dt.date(2020, 12, 31))


def test_the_real_research_split_is_covered_end_to_end():
    """Gdyby stopy znowu zaczynały się 2015-01, ten test upada."""
    from pathlib import Path

    from src.data.rates import COHORT_A_CURRENCIES
    path = Path(__file__).resolve().parents[1] / "data" / "rates" / "fred.parquet"
    if not path.exists():
        pytest.skip("brak data/rates/fred.parquet — uruchom scripts/fetch_rates.py")
    require_coverage_for_decisions(
        pl.read_parquet(path), COHORT_A_CURRENCIES, "overnight",
        dt.date(2015, 1, 1), dt.date(2021, 12, 31))


# --- pobrany plik, jeśli istnieje -------------------------------------------

def test_fetched_file_covers_cohort_a_overnight_completely():
    """Sprawdzenie na tym, co faktycznie leży na dysku. Bez pliku — pominięte."""
    from pathlib import Path

    from src.data.rates import COHORT_A_CURRENCIES
    path = Path(__file__).resolve().parents[1] / "data" / "rates" / "fred.parquet"
    if not path.exists():
        pytest.skip("brak data/rates/fred.parquet — uruchom scripts/fetch_rates.py")
    r = pl.read_parquet(path)
    require_coverage(r, COHORT_A_CURRENCIES, "overnight",
                     dt.date(2015, 1, 1), dt.date(2025, 12, 31))
