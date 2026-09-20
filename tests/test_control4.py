"""Testy kontroli #4 (ADR-044) — dane syntetyczne, odpowiedź znana z góry.

Dwa ramiona mają różny status i testy pilnują właśnie tego:
4a jest ablacją koszyka §12 i ma werdykt, 4b nie ma i mieć nie może.
"""
import datetime as dt

import numpy as np
import polars as pl
import pytest

from src.data.rates import SCHEMA as RATE_SCHEMA
from src.execution.simulator import CostModel
from src.validation.benchmark import BenchmarkSpec, ranking, run_benchmark, usd_pairs
from src.validation.control4 import (
    BuyAndHold, CarryOnly, Control4, buy_and_hold_legs, compare_carry_only,
    render_section, run_carry_only, summarize_buy_and_hold,
)
from src.features.technical import daily_bars

UTC = dt.timezone.utc
PIP = 1e-4
ATR = 20 * PIP
SPEC = BenchmarkSpec(currencies=("EUR", "GBP", "JPY", "AUD", "CAD"),
                     lookback_business_days=5)
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
COSTS = {s: CostModel(pip=0.01 if "JPY" in s else PIP, min_roundturn_pips=1.5)
         for s in SYMBOLS}
T0 = dt.datetime(2020, 1, 6, tzinfo=UTC)         # poniedziałek


def h1_bars(start, hours, base, drift, spread, atr) -> pl.DataFrame:
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


@pytest.fixture
def flat():
    return market({s: 0.0 for s in SYMBOLS})


@pytest.fixture
def rotating_rates():
    """Stopy, w których szczyt i dno rankingu zamieniają się co miesiąc.

    Przy stopach stałych ranking carry-only nigdy się nie zmienia, więc
    koszyk zawiera dwie transakcje na kotwicę i seria dzienna jest za rzadka,
    żeby bootstrap blokowy miał co próbkować. To fixture do testów
    okablowania, nie do wniosków o carry.
    """
    months = [dt.date(y, m, 1) for y in (2019, 2020, 2021) for m in range(1, 13)]
    rows = []
    for i, d in enumerate(months):
        hi, lo = ("EUR", "JPY") if i % 2 == 0 else ("JPY", "EUR")
        vals = {"USD": 1.0, "GBP": 1.2, "AUD": 1.1, "CAD": 0.9, hi: 3.0, lo: -0.5}
        rows += [{"date": d, "currency": c, "kind": "interbank_3m", "value": v,
                  "series": f"X{c}"} for c, v in vals.items()]
    return pl.DataFrame(rows, schema=RATE_SCHEMA)


# --- 4a: ablacja, nie inny benchmark ------------------------------------------

def test_carry_only_drops_momentum_from_the_score(rates):
    """Ranking 4a to sam carry: EUR +2,0 pp, JPY −1,5 pp — DOKŁADNIE tyle,
    ile wynoszą różnice stóp, mimo że ceny się ruszają.

    Rynek musi mieć dryf, inaczej momentum jest zerem i test przeszedłby
    także wtedy, gdyby ablacja w ogóle nie działała."""
    m = market({"EURUSD": 1e-5, "GBPUSD": -1e-5, "USDJPY": 2e-3,
                "AUDUSD": 3e-6, "USDCAD": -2e-6})
    pairs = usd_pairs(SYMBOLS, SPEC.currencies)
    d1 = {s: daily_bars(m[s]) for s in SYMBOLS}
    day = (T0 + dt.timedelta(days=40)).date()

    scores = ranking(day, d1, rates, pairs, SPEC.carry_only())
    assert scores is not None
    assert scores["EUR"] == pytest.approx(2.0)
    assert scores["JPY"] == pytest.approx(-1.5)
    assert max(scores, key=scores.get) == "EUR"
    assert min(scores, key=scores.get) == "JPY"


def test_carry_only_differs_from_the_full_ranking_when_momentum_matters(rates):
    """Gdy momentum jest silne, oba rankingi dają co innego — inaczej ablacja
    nie mierzyłaby niczego. JPY ma najniższy carry, ale mocno rośnie."""
    m = market({"EURUSD": 0.0, "GBPUSD": 0.0, "AUDUSD": 0.0, "USDCAD": 0.0,
                "USDJPY": -0.06})          # USDJPY spada => JPY rośnie
    pairs = usd_pairs(SYMBOLS, SPEC.currencies)
    d1 = {s: daily_bars(m[s]) for s in SYMBOLS}
    day = (T0 + dt.timedelta(days=12)).date()

    full = ranking(day, d1, rates, pairs, SPEC)
    carry = ranking(day, d1, rates, pairs, SPEC.carry_only())
    assert min(carry, key=carry.get) == "JPY"        # sam carry: JPY na dole
    assert max(full, key=full.get) == "JPY"          # z momentum: JPY na górze
    assert full != carry


def test_carry_only_runs_on_exactly_the_same_weeks_as_the_benchmark(rates, flat):
    """ADR-044: oba ramiona mają różnić się RANKINGIEM, nie próbą. Momentum
    jest nadal liczone, bo decyduje o pełności tygodnia."""
    a, stats_a = run_benchmark(flat, rates, COSTS, SYMBOLS, SPEC,
                               T0, T0 + dt.timedelta(days=79))
    b, stats_b = run_carry_only(flat, rates, COSTS, SYMBOLS, SPEC,
                                T0, T0 + dt.timedelta(days=79))
    assert [s["n_rebalances"] for s in stats_a] == [s["n_rebalances"] for s in stats_b]
    assert [s["n_skipped"] for s in stats_a] == [s["n_skipped"] for s in stats_b]


def test_carry_only_inherits_the_whole_benchmark_spec(rates, flat):
    """Ablacja nakładana jest w `run_carry_only`, więc wołający nie może
    policzyć #4a na innych parametrach niż #5."""
    spec = SPEC.carry_only()
    assert spec.include_momentum is False
    for f in ("currencies", "anchors", "r_multiple", "rebalance_time_local",
              "rebalance_timezone", "long_top_n", "short_bottom_n"):
        assert getattr(spec, f) == getattr(SPEC, f)


def test_carry_only_verdict_needs_the_whole_ci_above_zero():
    from src.validation.benchmark import Comparison
    mk = lambda lo, hi: CarryOnly(comparison=Comparison(  # noqa: E731
        strategy_sharpe=0.0, benchmark_sharpe=0.0, difference=0.0,
        ci_low=lo, ci_high=hi, strategy_mean_daily_r=0.0,
        benchmark_mean_daily_r=0.0, strategy_open_risk_r=0.0,
        benchmark_open_risk_r=0.0, n_days=10, n_reps=10))
    assert mk(0.1, 0.5).beaten
    assert not mk(-0.1, 0.5).beaten          # przedział obejmuje zero
    assert not mk(0.0, 0.5).beaten           # dokładnie zero to nie „powyżej"
    assert not CarryOnly().beaten            # nie policzone to nie pobite


# --- 4b: diagnostyka, nie próg ------------------------------------------------

def test_buy_and_hold_is_one_long_leg_per_pair(flat):
    trades = buy_and_hold_legs(flat, COSTS, SYMBOLS, SPEC,
                               T0, T0 + dt.timedelta(days=79))
    assert trades.height == len(SYMBOLS)
    assert set(trades["side"]) == {"long"}
    assert sorted(trades["symbol"]) == sorted(SYMBOLS)
    # jedna noga na parę, więc każda trzyma się przez całe okno
    assert (trades["t1"] - trades["ts"]).min() > dt.timedelta(days=60)


def test_buy_and_hold_gains_on_a_rising_pair_and_loses_on_a_falling_one():
    m = market({"EURUSD": +2e-5, "GBPUSD": -2e-5, "USDJPY": 0.0,
                "AUDUSD": 0.0, "USDCAD": 0.0})
    trades = buy_and_hold_legs(m, COSTS, SYMBOLS, SPEC, T0, T0 + dt.timedelta(days=79))
    r = {row["symbol"]: row["r"] for row in trades.select("symbol", "r").iter_rows(named=True)}
    assert r["EURUSD"] > 0
    assert r["GBPUSD"] < 0
    assert r["EURUSD"] == pytest.approx(-r["GBPUSD"], rel=0.05)


def test_buy_and_hold_skips_a_pair_without_bars(flat):
    """Cicha noga o zerowym R udawałaby parę, która nic nie zarobiła."""
    partial = {s: b for s, b in flat.items() if s != "USDCAD"}
    trades = buy_and_hold_legs(partial, COSTS, SYMBOLS, SPEC,
                               T0, T0 + dt.timedelta(days=79))
    assert "USDCAD" not in set(trades["symbol"])
    assert trades.height == len(SYMBOLS) - 1


def test_buy_and_hold_has_no_verdict_and_no_sharpe(flat):
    """ADR-044: 4b jest diagnostyką. Gdyby kiedyś dorobiono jej werdykt,
    ten test ma upaść — poprzeczka zależałaby od kierunku dolara w próbie."""
    trades = buy_and_hold_legs(flat, COSTS, SYMBOLS, SPEC,
                               T0, T0 + dt.timedelta(days=79))
    bh = summarize_buy_and_hold(trades, pl.DataFrame({"r": [0.5, -0.2]}))
    assert not hasattr(bh, "beaten")
    assert not hasattr(bh, "sharpe")
    assert not hasattr(bh, "comparison")
    assert bh.strategy_total_r == pytest.approx(0.3)
    assert bh.total_r == pytest.approx(sum(bh.per_symbol.values()))


def test_buy_and_hold_summary_is_empty_without_trades():
    bh = summarize_buy_and_hold(pl.DataFrame(), pl.DataFrame({"r": [1.0]}))
    assert not bh.computed
    assert bh.total_r == 0.0


# --- raport -------------------------------------------------------------------

def test_report_says_plainly_when_control_4_was_not_computed():
    text = "\n".join(render_section(Control4()))
    assert "nie zostało policzone" in text
    assert "niepełny" in text


def test_short_axis_is_a_recorded_gap_not_an_exception(rotating_rates):
    """Ranking po samym carry jest stabilny, więc na krótkim oknie to ramię
    handluje rzadko. Brak liczby ma być ZAPISANY, nie wyrzucony wyjątkiem —
    inaczej dry run przewraca się na właściwości benchmarku."""
    m = market({s: 0.0 for s in SYMBOLS}, hours=24 * 40)
    end = T0 + dt.timedelta(days=39)
    per_anchor, _ = run_carry_only(m, rotating_rates, COSTS, SYMBOLS, SPEC, T0, end)
    strategy = pl.concat([f for f in per_anchor.values() if f.height])

    cmp_, note = compare_carry_only(strategy, per_anchor, block_days=20,
                                    n_reps=50, seed=1)
    assert cmp_ is None
    assert "oś dzienna" in note and "carry" in note

    text = "\n".join(render_section(Control4(carry_only=CarryOnly(note=note))))
    assert note in text and "niepełny" in text


def test_report_marks_4b_as_not_a_threshold(flat):
    """Status 4b musi być widoczny w raporcie, a nie tylko w ADR-ze."""
    from src.validation.benchmark import Comparison
    trades = buy_and_hold_legs(flat, COSTS, SYMBOLS, SPEC,
                               T0, T0 + dt.timedelta(days=79))
    c4 = Control4(
        carry_only=CarryOnly(comparison=Comparison(
            strategy_sharpe=0.1, benchmark_sharpe=0.0, difference=0.1,
            ci_low=-0.2, ci_high=0.4, strategy_mean_daily_r=0.0,
            benchmark_mean_daily_r=0.0, strategy_open_risk_r=1.0,
            benchmark_open_risk_r=2.0, n_days=50, n_reps=100)),
        buy_and_hold=summarize_buy_and_hold(trades, pl.DataFrame({"r": [0.1]})))
    text = "\n".join(render_section(c4))
    assert "NIE próg" in text
    assert "Bez werdyktu i bez Sharpe" in text
    assert "NIE POBITY" in text          # CI obejmuje zero


def test_full_control_4_runs_end_to_end(rotating_rates):
    """Okablowanie: 4a liczy się do porównania, 4b do tabeli."""
    from src.validation.benchmark import Comparison

    m = market({"EURUSD": 1e-5, "GBPUSD": -1e-5, "USDJPY": 2e-3,
                "AUDUSD": 3e-6, "USDCAD": -2e-6}, hours=24 * 400)
    end = T0 + dt.timedelta(days=399)
    per_anchor, stats = run_carry_only(m, rotating_rates, COSTS, SYMBOLS,
                                       SPEC, T0, end)
    assert sum(f.height for f in per_anchor.values()) > 10, "koszyk nie handluje"
    strategy = pl.concat([f for f in per_anchor.values() if f.height])
    cmp_, note = compare_carry_only(strategy, per_anchor, block_days=5,
                                    n_reps=50, seed=1)
    assert isinstance(cmp_, Comparison) and note == ""
    assert cmp_.n_days > 0

    c4 = Control4(
        carry_only=CarryOnly(comparison=cmp_,
                             per_anchor={a: 0.0 for a in per_anchor},
                             anchor_stats=stats),
        buy_and_hold=summarize_buy_and_hold(
            buy_and_hold_legs(m, COSTS, SYMBOLS, SPEC, T0, end), strategy))
    text = "\n".join(render_section(c4))
    assert "4a — carry-only" in text
    assert "4b — buy & hold" in text
    assert "ADR-044" in text
