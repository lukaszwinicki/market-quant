"""Testy raportu jakości danych.

Kluczowy test to `test_detects_feed_outage_across_all_symbols` — broni
przed scenariuszem, w którym awaria feedu zapisuje się jako "brak rynku"
i luka staje się niewidoczna dla backtestu.
"""
import datetime as dt

import polars as pl
import pytest

from src.data.quality import (
    build_report, missing_trading_hours, render_markdown, trading_cells,
)

UTC = dt.timezone.utc


def bars(hours: list[dt.datetime], spread: float = 3e-5) -> pl.DataFrame:
    n = len(hours)
    return pl.DataFrame({
        "ts": pl.Series(hours, dtype=pl.Datetime("ms", "UTC")),
        "bid_open": [1.1] * n, "bid_high": [1.11] * n,
        "bid_low": [1.09] * n, "bid_close": [1.1] * n,
        "ask_open": [1.1 + spread] * n, "ask_high": [1.11 + spread] * n,
        "ask_low": [1.09 + spread] * n, "ask_close": [1.1 + spread] * n,
        "spread_max": [spread * 2] * n, "spread_close": [spread] * n,
        "n_ticks": pl.Series([1000] * n, dtype=pl.UInt32),
    })


def weekday_hours(start: dt.date, weeks: int) -> list[dt.datetime]:
    """Pon-pt, całą dobę — prosty, regularny kalendarz handlowy."""
    out = []
    for w in range(weeks):
        for d in range(5):                      # pon..pt
            day = start + dt.timedelta(days=7 * w + d)
            out += [dt.datetime(day.year, day.month, day.day, h, tzinfo=UTC)
                    for h in range(24)]
    return out


MONDAY = dt.date(2019, 3, 4)


# --- Kalendarz wyprowadzany z danych ----------------------------------------

def test_trading_calendar_is_derived_not_assumed():
    """Weekendy mają wyjść jako niehandlowe, bo ich w danych nie ma."""
    cells = trading_cells(bars(weekday_hours(MONDAY, 12)))
    trading = cells.filter("is_trading")
    assert set(trading["weekday"].to_list()) == {1, 2, 3, 4, 5}   # pon..pt
    assert cells.filter(pl.col("weekday").is_in([6, 7]))["is_trading"].any() == False


def test_missing_hour_inside_trading_calendar_is_flagged():
    hrs = weekday_hours(MONDAY, 12)
    hole = dt.datetime(2019, 3, 19, 10, tzinfo=UTC)      # wtorek, środek sesji
    kept = [h for h in hrs if h != hole]
    b = bars(kept)
    assert missing_trading_hours(b, trading_cells(b))["ts"].to_list() == [hole]


def test_weekend_absence_is_not_a_gap():
    b = bars(weekday_hours(MONDAY, 12))
    assert missing_trading_hours(b, trading_cells(b)).is_empty()


# --- Wykrywanie awarii feedu — rdzeń modułu ---------------------------------

def test_detects_feed_outage_across_all_symbols():
    """Godzina pusta u WSZYSTKICH par = awaria, nie zamknięcie rynku."""
    hrs = weekday_hours(MONDAY, 12)
    outage = dt.datetime(2019, 3, 19, 10, tzinfo=UTC)
    kept = [h for h in hrs if h != outage]

    rep = build_report({s: bars(kept) for s in ("EURUSD", "GBPUSD", "USDJPY")})

    assert rep.suspected_outages["ts"].to_list() == [outage]
    ok, reasons = rep.passes_gate_0()
    assert not ok and "awarię feedu" in " ".join(reasons)


def test_single_symbol_gap_is_not_an_outage():
    """Luka u jednej pary to problem instrumentu, nie feedu."""
    hrs = weekday_hours(MONDAY, 12)
    hole = dt.datetime(2019, 3, 19, 10, tzinfo=UTC)

    rep = build_report({
        "EURUSD": bars([h for h in hrs if h != hole]),
        "GBPUSD": bars(hrs),
        "USDJPY": bars(hrs),
    })

    assert rep.suspected_outages.is_empty()
    assert rep.per_symbol_gaps.filter(pl.col("symbol") == "EURUSD").height == 1


# --- Kryterium Bramki 0 -----------------------------------------------------

def test_gate_0_fails_when_two_symbols_exceed_gap_budget():
    hrs = weekday_hours(MONDAY, 10)
    few = hrs[:len(hrs) // 2]        # połowa brakuje => ~50% luk
    rep = build_report({"EURUSD": bars(few), "GBPUSD": bars(few), "USDJPY": bars(hrs)})
    ok, reasons = rep.passes_gate_0(max_gap_pct=5.0)
    assert not ok
    assert any("luki >" in r for r in reasons)


def test_gate_0_passes_on_clean_data():
    hrs = weekday_hours(MONDAY, 6)
    rep = build_report({s: bars(hrs) for s in ("EURUSD", "GBPUSD", "USDJPY")})
    ok, reasons = rep.passes_gate_0()
    assert ok, reasons


def test_invariant_violation_fails_gate_0():
    hrs = weekday_hours(MONDAY, 12)
    broken = bars(hrs).with_columns(pl.lit(1.0).alias("ask_close"))   # ask < bid
    rep = build_report({"EURUSD": broken, "GBPUSD": bars(hrs), "USDJPY": bars(hrs)})
    ok, reasons = rep.passes_gate_0()
    assert not ok and any("niezmienn" in r for r in reasons)


# --- Renderowanie -----------------------------------------------------------

def test_markdown_states_verdict_and_spread():
    hrs = weekday_hours(MONDAY, 6)
    md = render_markdown(build_report({s: bars(hrs) for s in ("EURUSD", "GBPUSD")}))
    assert "Bramka 0: **PRZECHODZI**" in md
    assert "| EURUSD |" in md
    assert "0.30" in md          # spread 3e-5 => 0.30 pipsa


def test_truncated_series_is_reported_as_gaps_not_as_clean():
    """Symbol, którego dane urywają się wcześniej, nie może wyglądać idealnie."""
    hrs = weekday_hours(MONDAY, 12)
    rep = build_report({
        "EURUSD": bars(hrs[:len(hrs)//2]),    # urwane w połowie zakresu
        "GBPUSD": bars(hrs),
        "USDJPY": bars(hrs),
    })
    eur = rep.symbol_coverage.filter(pl.col("symbol") == "EURUSD").row(0, named=True)
    assert eur["gap_pct"] > 40, f"obcięcie niewykryte: {eur['gap_pct']:.1f}%"
    gbp = rep.symbol_coverage.filter(pl.col("symbol") == "GBPUSD").row(0, named=True)
    assert gbp["gap_pct"] == pytest.approx(0.0)
