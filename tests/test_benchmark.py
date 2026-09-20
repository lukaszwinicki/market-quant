"""Testy koszyka carry + trend (§12, ADR-038/039/040) — dane syntetyczne.

Każdy scenariusz jest zbudowany tak, że znamy odpowiedź: waluta, która MUSI
wylądować na długiej nodze; tydzień, który MUSI zostać pominięty; pozycja,
która MUSI przetrwać rebalans bez kosztu.
"""
import datetime as dt

import numpy as np
import polars as pl
import pytest

from src.data.rates import SCHEMA as RATE_SCHEMA
from src.execution.simulator import CostModel
from src.features.technical import daily_bars
from src.validation.benchmark import (
    BenchmarkSpec, compare, daily_series, legs, mean_open_risk, momentum,
    pair_side, ranking, rebalance_days, run_anchor, run_benchmark, spec_from,
    usd_pairs,
)

UTC = dt.timezone.utc
PIP = 1e-4
ATR = 20 * PIP
SPEC = BenchmarkSpec(currencies=("EUR", "GBP", "JPY", "AUD", "CAD"),
                     lookback_business_days=5)
PAIRS = {"EUR": ("EURUSD", True), "GBP": ("GBPUSD", True), "JPY": ("USDJPY", False),
         "AUD": ("AUDUSD", True), "CAD": ("USDCAD", False)}
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
COSTS = {s: CostModel(pip=0.01 if "JPY" in s else PIP, min_roundturn_pips=1.5)
         for s in SYMBOLS}
T0 = dt.datetime(2020, 1, 6, tzinfo=UTC)         # poniedziałek


# --- syntetyczny rynek --------------------------------------------------------

def h1_bars(start: dt.datetime, hours: int, base: float, drift: float,
            spread: float, atr: float) -> pl.DataFrame:
    """Bary godzinowe z liniowym dryfem i gotową kolumną `atr_d1_14`."""
    bid = base + drift * np.arange(hours)
    return pl.DataFrame({
        "ts": pl.Series([start + dt.timedelta(hours=i) for i in range(hours)],
                        dtype=pl.Datetime("ms", "UTC")),
        "bid_open": bid, "bid_high": bid, "bid_low": bid, "bid_close": bid,
        "ask_open": bid + spread, "ask_high": bid + spread,
        "ask_low": bid + spread, "ask_close": bid + spread,
        "spread_max": np.full(hours, spread), "spread_close": np.full(hours, spread),
        "n_ticks": pl.Series(np.full(hours, 10), dtype=pl.UInt32),
        "atr_d1_14": np.full(hours, atr),
    })


def market(drifts: dict[str, float], hours=24 * 80) -> dict[str, pl.DataFrame]:
    out = {}
    for sym, d in drifts.items():
        jpy = "JPY" in sym
        out[sym] = h1_bars(T0, hours, 110.0 if jpy else 1.1, d,
                           0.01 if jpy else 0.5 * PIP, 2.0 if jpy else ATR)
    return out


@pytest.fixture
def rates():
    """Stopy 3M: EUR najwyższa, JPY najniższa, USD w środku."""
    months = [dt.date(2019, m, 1) for m in range(1, 13)] + \
             [dt.date(2020, m, 1) for m in range(1, 13)]
    vals = {"USD": 1.0, "EUR": 3.0, "GBP": 1.2, "JPY": -0.5, "AUD": 1.1, "CAD": 0.9}
    return pl.DataFrame(
        [{"date": d, "currency": c, "kind": "interbank_3m", "value": v,
          "series": f"X{c}"} for c, v in vals.items() for d in months],
        schema=RATE_SCHEMA)


# --- konfiguracja i mapowanie par ---------------------------------------------

def test_spec_comes_from_config():
    import yaml
    cfg = yaml.safe_load(open("config/v1_baseline.yaml"))
    s = spec_from(cfg)
    assert s.currencies == ("EUR", "GBP", "JPY", "AUD", "CAD")
    assert s.anchors == (0, 1, 2, 3, 4)          # pięć kotwic, ADR-039
    assert s.r_multiple == cfg["labels"]["sl_multiple"]   # ta sama jednostka R
    assert s.carry_kind == "interbank_3m"        # ADR-038


def test_usd_pairs_knows_which_currency_is_the_base():
    assert usd_pairs(SYMBOLS, ("EUR", "JPY")) == {
        "EUR": ("EURUSD", True), "JPY": ("USDJPY", False)}


def test_missing_pair_is_an_error_not_a_smaller_basket():
    with pytest.raises(ValueError, match="brak pary z USD"):
        usd_pairs(["EURUSD"], ("EUR", "NZD"))


@pytest.mark.parametrize("ccy_side, is_base, expected", [
    ("long", True, "long"), ("short", True, "short"),
    ("long", False, "short"), ("short", False, "long"),
])
def test_long_currency_on_usd_base_pair_is_short_the_pair(ccy_side, is_base, expected):
    assert pair_side(ccy_side, is_base) == expected


# --- ranking ------------------------------------------------------------------

def test_rebalance_days_are_weekly_on_the_anchor_weekday():
    days = rebalance_days(2, T0, T0 + dt.timedelta(days=21))   # środy
    assert all(d.weekday() == 2 for d in days)
    assert all((b - a).days == 7 for a, b in zip(days, days[1:]))


def test_momentum_flips_sign_for_usd_base_pairs():
    up = market({"USDJPY": 0.01})["USDJPY"]
    d1 = daily_bars(up)
    day = d1["ts"][-1].date()
    as_pair = momentum(d1, day, 5, is_base=True)
    as_currency = momentum(d1, day, 5, is_base=False)
    assert as_pair > 0                      # para rosła
    assert as_currency == pytest.approx(-as_pair)   # więc JPY tracił do USD


def test_ranking_is_none_when_a_currency_lacks_history(rates):
    m = market({s: 0.0 for s in SYMBOLS}, hours=24 * 3)
    d1 = {s: daily_bars(b) for s, b in m.items()}
    assert ranking(T0.date() + dt.timedelta(days=2), d1, rates, PAIRS, SPEC) is None


def test_ranking_is_none_when_a_rate_is_missing(rates):
    m = market({s: 0.0 for s in SYMBOLS})
    d1 = {s: daily_bars(b) for s, b in m.items()}
    thin = rates.filter(pl.col("currency") != "AUD")
    assert ranking(T0.date() + dt.timedelta(days=40), d1, thin, PAIRS, SPEC) is None


def test_ranking_sums_carry_and_momentum_literally(rates):
    """Bez dryfu zostaje sam carry — dokładnie różnica stóp vs USD."""
    m = market({s: 0.0 for s in SYMBOLS})
    d1 = {s: daily_bars(b) for s, b in m.items()}
    scores = ranking(T0.date() + dt.timedelta(days=40), d1, rates, PAIRS, SPEC)
    assert scores["EUR"] == pytest.approx(3.0 - 1.0)
    assert scores["JPY"] == pytest.approx(-0.5 - 1.0)


def test_legs_take_the_extremes_of_the_ranking():
    scores = {"EUR": 2.0, "GBP": 0.2, "JPY": -1.5, "AUD": 0.1, "CAD": -0.3}
    assert legs(scores, SPEC) == {"EUR": "long", "JPY": "short"}


def test_momentum_dominates_a_small_carry_edge(rates):
    """EUR ma najwyższy carry (+2 pp), ale spada — zwrot 3M go wyprzedza."""
    m = market({"EURUSD": -0.0005, "GBPUSD": 0.0005, "USDJPY": 0.0,
                "AUDUSD": 0.0, "USDCAD": 0.0})
    d1 = {s: daily_bars(b) for s, b in m.items()}
    scores = ranking(T0.date() + dt.timedelta(days=40), d1, rates, PAIRS, SPEC)
    assert legs(scores, SPEC)["GBP"] == "long"
    assert scores["EUR"] < scores["GBP"]


# --- egzekucja ----------------------------------------------------------------

@pytest.fixture
def flat_run(rates):
    """Rynek bez dryfu: ranking jest stały, więc pozycje nie powinny się zmieniać."""
    m = market({s: 0.0 for s in SYMBOLS})
    return run_anchor(0, m, {s: daily_bars(b) for s, b in m.items()},
                      rates, COSTS, PAIRS, SPEC,
                      T0 + dt.timedelta(days=30), T0 + dt.timedelta(days=70))


def test_stable_ranking_opens_each_leg_once(flat_run):
    """ADR-039: waluta, która zostaje w koszyku, NIE jest przehandlowana."""
    trades, stats = flat_run
    assert stats["n_rebalances"] >= 5
    # dwie nogi (long EUR, short JPY), każda otwarta raz i zamknięta na końcu
    assert trades.height == 2
    assert set(trades["symbol"]) == {"EURUSD", "USDJPY"}


def test_legs_use_the_strategy_r_unit(flat_run):
    """1 R = sl_multiple × atr_d1_14, nie 1 × ATR (ADR-039)."""
    trades, _ = flat_run
    eur = trades.filter(pl.col("symbol") == "EURUSD").row(0, named=True)
    assert abs(eur["entry_price"] - eur["sl"]) == pytest.approx(SPEC.r_multiple * ATR)


def test_cost_accounting_matches_the_simulator_identity(flat_run):
    """cost_r = max(spread_r, podłoga/ryzyko) oraz r = gross_r − dopłata."""
    trades, _ = flat_run
    for t in trades.iter_rows(named=True):
        risk = abs(t["entry_price"] - t["sl"])
        floor_r = COSTS[t["symbol"]].floor / risk
        assert t["cost_r"] == pytest.approx(max(t["spread_r"], floor_r))
        assert t["r"] == pytest.approx(t["gross_r"] - t["cost_r"] + t["spread_r"])


def test_a_flat_market_loses_exactly_the_cost_plus_slippage(flat_run):
    """Bez ruchu ceny wynik to dokładnie −(koszt + poślizg).

    Poślizg siedzi w CENACH fillów, a nie w `cost_r` — tak samo jak
    w symulatorze. Gdyby spread był liczony dwa razy, ta równość by pękła.
    """
    trades, _ = flat_run
    for t in trades.iter_rows(named=True):
        assert t["r"] == pytest.approx(-(t["cost_r"] + t["slip_r"]), abs=1e-9)


def test_short_yen_gains_when_the_pair_rises(rates):
    """JPY ma najniższy carry → short JPY → long USDJPY; para rośnie, zysk rośnie."""
    m = market({"EURUSD": 0.0, "GBPUSD": 0.0, "USDJPY": 0.002,
                "AUDUSD": 0.0, "USDCAD": 0.0})
    trades, _ = run_anchor(0, m, {s: daily_bars(b) for s, b in m.items()}, rates,
                           COSTS, PAIRS, SPEC, T0 + dt.timedelta(days=30),
                           T0 + dt.timedelta(days=70))
    jpy = trades.filter(pl.col("symbol") == "USDJPY").row(0, named=True)
    assert jpy["side"] == "long"            # short JPY = long USDJPY
    assert jpy["r"] > 0


def test_incomplete_week_is_skipped_whole(rates):
    """Brak stopy jednej waluty → cały tydzień pomijany, nie ranking z czterech."""
    m = market({s: 0.0 for s in SYMBOLS})
    thin = rates.filter(pl.col("currency") != "CAD")
    trades, stats = run_anchor(0, m, {s: daily_bars(b) for s, b in m.items()},
                               thin, COSTS, PAIRS, SPEC,
                               T0 + dt.timedelta(days=30), T0 + dt.timedelta(days=70))
    assert stats["n_skipped"] == stats["n_rebalances"]
    assert trades.height == 0


def test_run_benchmark_produces_one_portfolio_per_anchor(rates):
    m = market({s: 0.0 for s in SYMBOLS})
    per_anchor, stats = run_benchmark(m, rates, COSTS, SYMBOLS, SPEC,
                                      T0 + dt.timedelta(days=30),
                                      T0 + dt.timedelta(days=70))
    assert sorted(per_anchor) == [0, 1, 2, 3, 4]
    assert {s["anchor"] for s in stats} == {0, 1, 2, 3, 4}
    assert all(f.height == 2 for f in per_anchor.values())


# --- porównanie (kontrola #5) -------------------------------------------------

def _series(days, r, symbol="EURUSD", hold_days=1) -> pl.DataFrame:
    return pl.DataFrame({
        "ts": pl.Series([T0 + dt.timedelta(days=int(d)) for d in days],
                        dtype=pl.Datetime("ms", "UTC")),
        "t1": pl.Series([T0 + dt.timedelta(days=int(d) + hold_days) for d in days],
                        dtype=pl.Datetime("ms", "UTC")),
        "symbol": [symbol] * len(days), "side": ["long"] * len(days),
        "r": pl.Series(r, dtype=pl.Float64),
    })


def test_daily_series_puts_both_sides_on_one_axis():
    strat = _series([0, 1], [1.0, 2.0])
    per_anchor = {0: _series([1, 2], [1.0, 1.0]), 1: _series([1, 2], [3.0, 3.0])}
    days, s, b = daily_series(strat, per_anchor)
    assert len(days) == len(s) == len(b) == 3
    # koszyk to ŚREDNIA z podportfeli, nie suma
    assert b[1] == pytest.approx(2.0)
    assert b[0] == pytest.approx(0.0)


def test_open_risk_counts_simultaneous_positions():
    """Dwie pozycje trzymane przez cały okres to 2 R średniego ryzyka."""
    a = _series([0], [0.0], hold_days=10)
    b = _series([0], [0.0], symbol="GBPUSD", hold_days=10)
    both = pl.concat([a, b])
    assert mean_open_risk(both) == pytest.approx(2.0)


def test_comparison_detects_a_clearly_better_strategy():
    rng = np.random.default_rng(3)
    n = 200
    bench = rng.standard_normal(n) * 0.1
    strat = bench + 0.30                      # ten sam szum, stała przewaga
    c = compare(strat, bench, _series(range(n), strat),
                [_series(range(n), bench)], block_days=10, n_reps=400, seed=1)
    assert c.strategy_sharpe > c.benchmark_sharpe
    assert c.beaten and c.ci_low > 0


def test_comparison_does_not_declare_a_win_on_noise():
    rng = np.random.default_rng(4)
    n = 200
    bench = rng.standard_normal(n) * 0.1
    strat = rng.standard_normal(n) * 0.1
    c = compare(strat, bench, _series(range(n), strat),
                [_series(range(n), bench)], block_days=10, n_reps=400, seed=1)
    assert not c.beaten
    assert c.ci_low < 0 < c.ci_high


def test_comparison_is_not_fooled_by_a_bigger_risk_budget():
    """Ta sama seria przeskalowana 2x to ta sama jakość — Sharpe się nie zmienia.

    Gdyby kryterium zostało przy różnicy ŚREDNICH (ADR-039), strategia
    trzymająca dwa razy większe ryzyko „biłaby" koszyk bez przewagi.
    Dokładnie to koryguje ADR-040.
    """
    rng = np.random.default_rng(5)
    n = 200
    bench = rng.standard_normal(n) * 0.1 + 0.02
    strat = bench * 2.0                       # ten sam sygnał, podwójna ekspozycja
    c = compare(strat, bench, _series(range(n), strat),
                [_series(range(n), bench)], block_days=10, n_reps=400, seed=1)
    assert c.strategy_mean_daily_r == pytest.approx(2 * c.benchmark_mean_daily_r)
    assert c.difference == pytest.approx(0.0, abs=1e-9)
    assert not c.beaten


def test_comparison_uses_the_same_blocks_for_both_series():
    """Wspólne bloki zachowują korelację dzienną, więc CI różnicy jest węższe.

    Obie serie są tu prawie identyczne (ten sam szum, stałe przesunięcie),
    więc przy sparowanym losowaniu różnica Sharpe'ów jest niemal stała.
    Gdyby każda seria dostała własne bloki, przedział rozdąłby się o cały
    szum obu serii — a to jest dokładnie ten błąd, przed którym stoi
    ADR-040 pkt 3.
    """
    from src.validation.bootstrap import block_indices
    from src.validation.dsr import sharpe

    rng = np.random.default_rng(6)
    n, reps, block = 200, 400, 10
    bench = rng.standard_normal(n) * 0.5
    strat = bench + 0.05

    paired = compare(strat, bench, _series(range(n), strat),
                     [_series(range(n), bench)], block_days=block,
                     n_reps=reps, seed=1)
    paired_width = paired.ci_high - paired.ci_low

    # Ta sama maszyneria, ale DWA niezależne losowania bloków.
    idx_s = block_indices(n, block, reps, np.random.default_rng(1))
    idx_b = block_indices(n, block, reps, np.random.default_rng(2))
    unpaired = np.array([sharpe(strat[a]) - sharpe(bench[b])
                         for a, b in zip(idx_s, idx_b)])
    unpaired_width = float(np.diff(np.percentile(unpaired, [2.5, 97.5]))[0])

    assert paired_width < unpaired_width


def test_comparison_rejects_series_of_different_length():
    with pytest.raises(ValueError, match="tej samej długości"):
        compare(np.zeros(10), np.zeros(9), _series([0], [0.0]), [_series([0], [0.0])])
