"""Testy kalendarza i blackoutu — dane syntetyczne, odpowiedź znana z góry."""
import datetime as dt

import polars as pl
import pytest

from src.data.calendar import (
    HIGH_SERIES, blackout, coverage_gaps, validate_calendar,
)

UTC = dt.timezone.utc
E = dt.datetime(2016, 3, 16, 18, 0, tzinfo=UTC)       # zdarzenie syntetyczne
SRC = "https://example.org/source"


def cal(rows) -> pl.DataFrame:
    return pl.DataFrame(
        [{"timestamp_utc": t, "currency": c, "name": n, "rank": "HIGH", "source": SRC}
         for t, c, n in rows],
        schema={"timestamp_utc": pl.Datetime("ms", "UTC"), "currency": pl.Utf8,
                "name": pl.Utf8, "rank": pl.Utf8, "source": pl.Utf8})


def ts(*minutes_from_event) -> pl.Series:
    return pl.Series([E + dt.timedelta(minutes=m) for m in minutes_from_event],
                     dtype=pl.Datetime("ms", "UTC"))


# --- okno (ADR-032) -----------------------------------------------------------

def test_window_is_30_min_before_and_120_after_the_event():
    ev = cal([(E, "USD", "FOMC")])
    got = blackout(ts(-31, -30, 0, 120, 121), "EURUSD", ev, 30, 120).to_list()
    assert got == [False, True, True, True, False]


def test_either_currency_of_the_pair_triggers_and_others_do_not():
    ev = cal([(E, "JPY", "BOJ_RATE")])
    assert blackout(ts(0), "USDJPY", ev, 30, 120).to_list() == [True]
    assert blackout(ts(0), "EURJPY", ev, 30, 120).to_list() == [True]
    assert blackout(ts(0), "EURUSD", ev, 30, 120).to_list() == [False]


def test_nearest_event_is_found_among_many():
    evs = cal([(E + dt.timedelta(days=d), "USD", "US_CPI") for d in range(0, 300, 7)])
    t = ts(7 * 24 * 60 * 10 + 60, 7 * 24 * 60 * 10 + 200, 3 * 24 * 60)
    assert blackout(t, "GBPUSD", evs, 30, 120).to_list() == [True, False, False]


def test_empty_calendar_gives_no_blackout_which_is_why_coverage_is_checked():
    ev = cal([])
    assert not blackout(ts(0), "EURUSD", ev, 30, 120).any()


# --- walidacja ----------------------------------------------------------------

def test_values_are_rejected():
    bad = cal([(E, "USD", "US_CPI")]).with_columns(pl.lit(0.3).alias("consensus"))
    with pytest.raises(ValueError, match="consensus"):
        validate_calendar(bad)


@pytest.mark.parametrize("mutate, msg", [
    (lambda d: d.with_columns(pl.lit("MEDIUM").alias("rank")), "ranga"),
    (lambda d: d.with_columns(pl.lit("USD").alias("currency"),
                              pl.lit("BOJ_RATE").alias("name")), "listy zamkniętej"),
    (lambda d: d.with_columns(pl.lit("from memory").alias("source")), "URL"),
    (lambda d: d.with_columns(pl.col("timestamp_utc").dt.replace_time_zone(None)), "timestamp"),
    (lambda d: pl.concat([d, d]), "zduplikowanych"),
])
def test_calendar_invariants(mutate, msg):
    with pytest.raises(ValueError, match=msg):
        validate_calendar(mutate(cal([(E, "USD", "FOMC")])))


def test_valid_calendar_is_sorted():
    out = validate_calendar(cal([(E, "USD", "FOMC"), (E - dt.timedelta(days=1), "EUR", "ECB_RATE")]))
    assert out["timestamp_utc"].is_sorted()


# --- pokrycie -------------------------------------------------------------------

def full_year(y: int, currencies) -> list:
    return [(dt.datetime(y, 6, 1, 12, tzinfo=UTC) + dt.timedelta(minutes=i), c, n)
            for i, (c, n) in enumerate((c, n) for c in currencies for n in HIGH_SERIES[c])]


def test_coverage_requires_every_series_every_year():
    start, end = dt.datetime(2016, 1, 1, tzinfo=UTC), dt.datetime(2017, 12, 31, tzinfo=UTC)
    ev = cal(full_year(2016, ["EUR", "USD"]) + full_year(2017, ["EUR", "USD"]))
    assert coverage_gaps(ev, ["EUR", "USD"], start, end) == []

    missing = ev.filter(~((pl.col("name") == "US_PCE")
                          & (pl.col("timestamp_utc").dt.year() == 2017)))
    assert coverage_gaps(missing, ["EUR", "USD"], start, end) == [("USD", "US_PCE", 2017)]
    assert ("JPY", "BOJ_RATE", 2016) in coverage_gaps(ev, ["JPY"], start, end)


def test_short_edge_fragment_of_a_year_is_not_required():
    start = dt.datetime(2016, 1, 1, tzinfo=UTC)
    end = dt.datetime(2017, 1, 20, tzinfo=UTC)          # 19 dni 2017
    ev = cal(full_year(2016, ["USD"]))
    assert coverage_gaps(ev, ["USD"], start, end) == []
