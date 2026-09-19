"""Testy kontroli losowej.

Test integracyjny odtwarza logikę bramki 0 tam, gdzie odpowiedź jest
znana: na błądzeniu losowym (martyngał) losowe wejścia MUSZĄ dać
expectancy ≈ −koszt. Jeśli nie — model kosztów albo symulator są zepsute.
"""
import datetime as dt

import numpy as np
import polars as pl
import pytest

from src.execution.simulator import CostModel
from src.labels.triple_barrier import LabelSpec, add_business_days, label_events
from src.validation.controls import (
    candidate_events, counts_from, empirical_p_value, random_control,
    random_entries,
)

UTC = dt.timezone.utc
T0 = dt.datetime(2020, 1, 6, 0, tzinfo=UTC)     # poniedziałek
PIP = 1e-4


def features(n_bars=200, symbol_atr=20 * PIP) -> pl.DataFrame:
    atr = [None] * 10 + [symbol_atr] * (n_bars - 10)
    return pl.DataFrame({
        "ts": pl.Series([T0 + dt.timedelta(hours=i) for i in range(n_bars)],
                        dtype=pl.Datetime("ms", "UTC")),
        "atr_d1_14": pl.Series(atr, dtype=pl.Float64),
    })


def candidates() -> pl.DataFrame:
    return pl.concat([candidate_events(features(), s) for s in ("EURUSD", "USDJPY")])


# --- Kandydaci --------------------------------------------------------------

def test_candidate_time_is_bar_close_not_bar_label():
    """Bar 09:00 zamyka się o 10:00 — dopiero wtedy można na nim decydować."""
    c = candidate_events(features(), "EURUSD")
    assert c["ts"][0] == T0 + dt.timedelta(hours=11)    # bar 10:00 -> decyzja 11:00


def test_bars_without_daily_atr_are_not_candidates():
    c = candidate_events(features(), "EURUSD")
    assert c.height == 190
    assert c["atr_d1_14"].null_count() == 0


# --- Losowanie --------------------------------------------------------------

def test_counts_match_strategy_per_symbol_and_side():
    trades = pl.DataFrame({"symbol": ["EURUSD"] * 5 + ["USDJPY"] * 3,
                           "side": ["long"] * 4 + ["short"] + ["short"] * 3})
    counts = counts_from(trades)
    ev = random_entries(candidates(), counts, np.random.default_rng(0))
    assert counts_from(ev) == counts == {("EURUSD", "long"): 4, ("EURUSD", "short"): 1,
                                         ("USDJPY", "short"): 3}


def test_random_entries_come_only_from_candidates():
    c = candidates()
    ev = random_entries(c, {("EURUSD", "long"): 50}, np.random.default_rng(1))
    allowed = set(c.filter(pl.col("symbol") == "EURUSD")["ts"].to_list())
    assert set(ev["ts"].to_list()) <= allowed
    assert ev["ts"].n_unique() == 50                     # bez zwracania


def test_same_seed_same_draw_different_seed_different_draw():
    c, k = candidates(), {("EURUSD", "long"): 20}
    a = random_entries(c, k, np.random.default_rng(7))
    b = random_entries(c, k, np.random.default_rng(7))
    d = random_entries(c, k, np.random.default_rng(8))
    assert a.equals(b)
    assert not a.equals(d)


def test_more_entries_than_candidates_is_rejected():
    with pytest.raises(ValueError):
        random_entries(candidates(), {("EURUSD", "long"): 1000}, np.random.default_rng(0))


# --- Rozkład zerowy i p-value ----------------------------------------------

def test_random_control_returns_one_mean_per_replication():
    def evaluate(ev):
        return ev.with_columns(pl.lit(-0.1).alias("r"))
    null = random_control(candidates(), {("EURUSD", "long"): 10}, evaluate, 25, seed=0)
    assert null.shape == (25,)
    assert null == pytest.approx(-0.1)


def test_p_value_never_zero_and_ordered():
    null = np.linspace(-1, 1, 99)
    assert empirical_p_value(5.0, null) == pytest.approx(1 / 100)
    assert empirical_p_value(-5.0, null) == pytest.approx(1.0)
    assert empirical_p_value(0.5, null) < empirical_p_value(0.0, null)


# --- Integracja: logika bramki 0 na martyngale ------------------------------

def _random_walk_m1(start: dt.datetime, minutes: int, rng, sigma=0.5 * PIP,
                    spread=0.5 * PIP) -> pl.DataFrame:
    """Bid jako błądzenie losowe; OHLC z czterech kroków na minutę."""
    steps = rng.standard_normal((minutes, 4)) * sigma / 2
    path = 1.1 + np.cumsum(steps.ravel()).reshape(minutes, 4)
    o, c = path[:, 0], path[:, 3]
    h, lo = path.max(1), path.min(1)
    return pl.DataFrame({
        "ts": pl.Series([start + dt.timedelta(minutes=i) for i in range(minutes)],
                        dtype=pl.Datetime("ms", "UTC")),
        "bid_open": o, "bid_high": h, "bid_low": lo, "bid_close": c,
        "ask_open": o + spread, "ask_high": h + spread,
        "ask_low": lo + spread, "ask_close": c + spread,
        "spread_max": np.full(minutes, spread), "spread_close": np.full(minutes, spread),
        "n_ticks": pl.Series(np.full(minutes, 10), dtype=pl.UInt32),
    })


def test_random_entries_on_random_walk_lose_exactly_the_cost():
    """Bramka 0 w miniaturze: na martyngale E[R] = −koszt, E[R + koszt] = 0.

    Każda transakcja dostaje własną, niezależną ścieżkę — wtedy transakcje
    są niezależne i błąd standardowy jest znany (~1/√n). Podłoga kosztu
    ustawiona wysoko (0.5 R), żeby 'koszt policzony' i 'koszt pominięty'
    były rozróżnialne statystycznie.
    """
    rng = np.random.default_rng(123)
    spec = LabelSpec(horizon_business_days=1)
    cost = CostModel(pip=PIP, min_roundturn_pips=20.0,
                     entry_slippage_x_spread=0.0, stop_slippage_x_spread=0.0)

    def evaluate(ev: pl.DataFrame) -> pl.DataFrame:
        out = []
        for row in ev.iter_rows(named=True):
            horizon = add_business_days(row["ts"], 1) - row["ts"]
            m1 = _random_walk_m1(row["ts"], int(horizon.total_seconds() // 60) + 5, rng)
            out.append(label_events(pl.DataFrame([row]).with_columns(
                pl.col("ts").cast(pl.Datetime("ms", "UTC"))), m1, cost, spec))
        return pl.concat(out, how="vertical_relaxed")

    c = candidate_events(features(n_bars=500), "EURUSD")
    ev = random_entries(c, {("EURUSD", "long"): 150, ("EURUSD", "short"): 150},
                        np.random.default_rng(0))
    lab = evaluate(ev)

    assert lab.height == 300
    assert lab["cost_r"].mean() == pytest.approx(0.5, rel=0.01)
    gross_r = lab["r"] + lab["cost_r"]
    se = gross_r.std() / np.sqrt(lab.height)
    assert abs(gross_r.mean()) < 3 * se, f"brutto {gross_r.mean():+.3f} R, se {se:.3f}"
    assert lab["r"].mean() == pytest.approx(-0.5, abs=3 * se)
