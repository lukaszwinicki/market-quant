"""Testy bramki 0 na danych syntetycznych — tam, gdzie znamy poprawną odpowiedź."""
import datetime as dt

import numpy as np
import polars as pl
import pytest

from src.execution.simulator import CostModel
from src.labels import triple_barrier
from src.labels.triple_barrier import LabelSpec, add_business_days, label_events
from src.validation.controls import candidate_events, random_control
from src.validation.gate0 import (
    assess, balanced_counts, contiguous_end, cost_accounting_violations,
    eligible_candidates, make_evaluator, run_random_control, spread_profile,
)
from tests.test_controls import _random_walk_m1

UTC = dt.timezone.utc
T0 = dt.datetime(2020, 1, 6, tzinfo=UTC)       # poniedziałek
PIP = 1e-4
COST = CostModel(pip=PIP, min_roundturn_pips=1.5)


def hourly(n: int, start=T0, atr=20 * PIP) -> pl.DataFrame:
    return pl.DataFrame({
        "ts": pl.Series([start + dt.timedelta(hours=i) for i in range(n)],
                        dtype=pl.Datetime("ms", "UTC")),
        "atr_d1_14": pl.Series([atr] * n, dtype=pl.Float64),
    })


# --- zakres danych i kandydaci ----------------------------------------------

def test_contiguous_end_stops_before_multi_day_hole():
    a = hourly(100)
    b = hourly(10, start=T0 + dt.timedelta(days=400))
    end = contiguous_end(pl.concat([a, b]), T0)
    assert end == a["ts"][-1]


def test_weekend_is_not_a_hole():
    fri = hourly(24, start=dt.datetime(2020, 1, 10, tzinfo=UTC))
    mon = hourly(24, start=dt.datetime(2020, 1, 12, 22, tzinfo=UTC))
    assert contiguous_end(pl.concat([fri, mon]), fri["ts"][0]) == mon["ts"][-1]


def test_candidates_have_whole_horizon_inside_range():
    spec = LabelSpec(horizon_business_days=10)
    feats = hourly(24 * 60)
    start, end = T0 + dt.timedelta(days=3), T0 + dt.timedelta(days=40)
    c = eligible_candidates(feats, "EURUSD", start, end, spec)
    assert c.height > 0
    assert c["ts"].min() >= start
    assert all(add_business_days(t, 10) <= end for t in c["ts"])
    # ostatni dopuszczony kandydat jest tuż przy granicy — filtr nie jest zbyt ostry
    assert add_business_days(c["ts"].max() + dt.timedelta(hours=1), 10) > end


def test_counts_are_balanced_per_symbol():
    assert balanced_counts(["EURUSD", "USDJPY"], 3) == {
        ("EURUSD", "long"): 3, ("EURUSD", "short"): 3,
        ("USDJPY", "long"): 3, ("USDJPY", "short"): 3}


# --- ewaluator z pamięcią -----------------------------------------------------

@pytest.fixture
def walk():
    rng = np.random.default_rng(5)
    minutes = 60 * 24 * 21
    return _random_walk_m1(T0, minutes, rng, sigma=0.3 * PIP)


def test_memoized_evaluator_matches_label_events_and_does_not_recompute(walk, monkeypatch):
    spec = LabelSpec(horizon_business_days=1)
    cands = candidate_events(hourly(24 * 10), "EURUSD")
    ev = cands.head(5).with_columns(pl.lit("long").alias("side"))

    evaluate = make_evaluator({"EURUSD": walk}, {"EURUSD": COST}, spec)
    first = evaluate(ev)
    direct = label_events(ev, walk, COST, spec)
    assert first.select(direct.columns).equals(direct)

    calls = []
    real = triple_barrier.simulate_trade
    monkeypatch.setattr(triple_barrier, "simulate_trade",
                        lambda *a, **k: calls.append(1) or real(*a, **k))
    assert evaluate(ev).equals(first)
    assert not calls


def test_evaluator_column_order_does_not_depend_on_who_called_first(walk):
    """REGRESJA: memo jest dzielone między strategią a kontrolą, a te podają
    te same kolumny zdarzenia w RÓŻNEJ kolejności (`run_v1a`: ts, symbol,
    side, atr_d1_14; kontrola: ts, atr_d1_14, symbol, side). Kolejność kolumn
    wyniku nie może od tego zależeć — `pl.concat` powtórzeń kontroli porównuje
    kolejność, nie nazwy, więc rozjazd wywracał cały przebieg."""
    spec = LabelSpec(horizon_business_days=1)
    cands = candidate_events(hourly(24 * 10), "EURUSD")
    base = cands.head(6).with_columns(pl.lit("long").alias("side"))

    as_strategy = base.select("ts", "symbol", "side", "atr_d1_14")
    as_control = base.select("ts", "atr_d1_14", "symbol", "side")

    evaluate = make_evaluator({"EURUSD": walk}, {"EURUSD": COST}, spec)
    evaluate(as_strategy.head(3))                  # memo zapełnia strategia

    # Dwa „powtórzenia” kontroli: pierwsze liczy od zera (kolejność kontroli),
    # drugie trafia w memo zapełnione przez strategię (kolejność strategii).
    rep1 = evaluate(as_control.tail(3))
    rep2 = evaluate(as_control.head(3))
    assert rep1.columns == rep2.columns
    assert pl.concat([rep1, rep2], how="vertical_relaxed").height == 6


def test_evaluator_rejects_labels_with_a_different_column_set(walk):
    """Inny ZBIÓR kolumn to inne zdarzenia. Cicha projekcja gubiłaby dane,
    więc ma być błąd."""
    spec = LabelSpec(horizon_business_days=1)
    cands = candidate_events(hourly(24 * 10), "EURUSD")
    base = cands.head(4).with_columns(pl.lit("long").alias("side"))

    evaluate = make_evaluator({"EURUSD": walk}, {"EURUSD": COST}, spec)
    evaluate(base.head(2))
    with pytest.raises(ValueError, match="różnymi kolumnami"):
        evaluate(base.with_columns(pl.lit(1.0).alias("extra")))


def test_rep_means_equal_random_control(walk):
    spec = LabelSpec(horizon_business_days=1)
    cands = eligible_candidates(hourly(24 * 20), "EURUSD", T0,
                                walk["ts"][-1], spec)
    counts = balanced_counts(["EURUSD"], 5)
    evaluate = make_evaluator({"EURUSD": walk}, {"EURUSD": COST}, spec)

    labels = run_random_control(cands, counts, evaluate, 4, seed=3)
    means = labels.group_by("rep").agg(pl.col("r").mean()).sort("rep")["r"].to_numpy()
    assert means == pytest.approx(random_control(cands, counts, evaluate, 4, seed=3))
    assert labels.height == 4 * 10


# --- kryteria (ADR-025) --------------------------------------------------------

RISK = 50 * PIP


def fake_labels(n_days=200, per_day=6, bias=0.0, sd=0.5, seed=0) -> pl.DataFrame:
    """Transakcje o znanym rozkładzie i spójnym rachunku kosztu.

    Wynik przed kosztem ~ N(bias, sd); spread 0,3 pipsa = 0,006 R,
    podłoga 1,5 pipsa = 0,03 R wiąże, więc koszt = 0,03 R.
    """
    rng = np.random.default_rng(seed)
    days = [T0 + dt.timedelta(days=d) for d in range(n_days * 7 // 5 + 7)]
    days = [d for d in days if d.weekday() < 5][:n_days]
    ts = [d + dt.timedelta(hours=h) for d in days for h in range(per_day)]
    n = len(ts)
    spread_r = np.full(n, 0.3 * PIP / RISK)
    cost_r = np.maximum(spread_r, COST.floor / RISK)
    pre = rng.standard_normal(n) * sd + bias
    gross_r = pre - spread_r                       # fille już po spreadzie
    return pl.DataFrame({
        "ts": pl.Series(ts, dtype=pl.Datetime("ms", "UTC")),
        "symbol": ["EURUSD"] * n, "side": ["long", "short"] * (n // 2),
        "r": gross_r - (cost_r - spread_r), "cost_r": cost_r,
        "gross_r": gross_r, "spread_r": spread_r, "y": (pre > 1).astype(int),
        "reason": ["sl"] * n, "entry_price": np.full(n, 1.1), "sl": np.full(n, 1.1 - RISK),
    })


def spreads_ok():
    return {"EURUSD": {"distinct": 500, "negative": 0, "crossed_bars": 0}}


def check(res, prefix):
    return next(c for c in res.checks if c.name.startswith(prefix))


def test_unbiased_random_entries_pass():
    res = assess(fake_labels(), {"EURUSD": COST}, spreads_ok(), 20, 2000, 0)
    assert res.passed, [c for c in res.checks if not c.passed]
    assert res.mean_cost_r == pytest.approx(0.03)
    assert res.net.expectancy == pytest.approx(res.pre_cost.expectancy - 0.03)


def test_positive_pre_cost_result_on_random_entries_fails():
    """Symulator zerkający w przyszłość daje zysk z losowych wejść."""
    res = assess(fake_labels(bias=0.3), {"EURUSD": COST}, spreads_ok(), 20, 2000, 0)
    c = check(res, "c.")
    assert not c.passed and "bias" in c.detail
    assert not res.passed


def test_wide_ci_is_inconclusive_not_a_pass():
    """Mało danych → szeroki CI zawiera 0 zawsze. To nie jest przejście."""
    res = assess(fake_labels(n_days=60, per_day=2, sd=1.0), {"EURUSD": COST},
                 spreads_ok(), 20, 2000, 0)
    c = check(res, "c.")
    assert res.pre_cost.ci_low <= 0 <= res.pre_cost.ci_high
    assert res.half_ci > 0.05
    assert not c.passed and "NIEROZSTRZYGNIĘTE" in c.detail


def test_cost_below_floor_is_caught_per_trade():
    lab = fake_labels().with_columns(
        pl.when(pl.int_range(pl.len()) == 7).then(pl.col("cost_r") * 0.5)
        .otherwise(pl.col("cost_r")).alias("cost_r"))
    assert cost_accounting_violations(lab, {"EURUSD": COST}).height == 1
    res = assess(lab, {"EURUSD": COST}, spreads_ok(), 20, 2000, 0)
    assert not check(res, "a.").passed


def test_spread_charged_twice_is_caught_per_trade():
    """Błąd naprawiony wcześniej w symulatorze: spread w fillach i drugi raz w r."""
    lab = fake_labels()
    twice = lab.with_columns((pl.col("r") - pl.col("spread_r")).alias("r"))
    assert cost_accounting_violations(twice, {"EURUSD": COST}).height == lab.height
    assert cost_accounting_violations(lab, {"EURUSD": COST}).is_empty()


def test_jpy_floor_uses_jpy_pip_and_unknown_symbol_is_a_violation():
    lab = fake_labels(n_days=5).with_columns(pl.lit("EURJPY").alias("symbol"))
    jpy = CostModel(pip=0.01, min_roundturn_pips=2.5)
    assert cost_accounting_violations(lab, {"EURJPY": jpy}).height == lab.height
    assert cost_accounting_violations(lab, {"EURUSD": COST}).height == lab.height


def test_resolution_is_half_ci_over_cost():
    res = assess(fake_labels(), {"EURUSD": COST}, spreads_ok(), 20, 2000, 0)
    assert res.half_ci == pytest.approx((res.pre_cost.ci_high - res.pre_cost.ci_low) / 2)
    assert res.resolution == pytest.approx(res.half_ci / 0.03)


def test_constant_or_negative_spread_fails(walk):
    const = spread_profile(walk, PIP)                  # syntetyk ma spread stały
    assert const["distinct"] == 1
    res = assess(fake_labels(), {"EURUSD": COST}, {"EURUSD": const}, 20, 2000, 0)
    assert not check(res, "spread").passed

    noisy = walk.with_columns(
        (pl.col("spread_close") * (1 + pl.int_range(pl.len()) % 50 / 10)).alias("spread_close"))
    assert spread_profile(noisy, PIP)["distinct"] >= 20
    neg = noisy.with_columns(pl.when(pl.int_range(pl.len()) == 3).then(-PIP)
                             .otherwise(pl.col("spread_close")).alias("spread_close"))
    res = assess(fake_labels(), {"EURUSD": COST}, {"EURUSD": spread_profile(neg, PIP)},
                 20, 2000, 0)
    assert not check(res, "spread").passed


def test_real_simulator_labels_satisfy_cost_accounting(walk):
    """Tożsamość kosztu na etykietach z prawdziwego symulatora, nie z fake'a."""
    spec = LabelSpec(horizon_business_days=1)
    cands = eligible_candidates(hourly(24 * 20), "EURUSD", T0, walk["ts"][-1], spec)
    cost = CostModel(pip=PIP, min_roundturn_pips=1.5)
    evaluate = make_evaluator({"EURUSD": walk}, {"EURUSD": cost}, spec)
    lab = run_random_control(cands, balanced_counts(["EURUSD"], 10), evaluate, 2, seed=1)
    assert lab.height == 40
    assert cost_accounting_violations(lab, {"EURUSD": cost}).is_empty()
