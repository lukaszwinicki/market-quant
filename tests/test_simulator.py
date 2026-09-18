"""Testy symulatora egzekucji.

Wszystkie przypadki są syntetyczne i mają odpowiedź znaną Z GÓRY. Na
prawdziwych tickach nie wiadomo, co *powinno* wyjść, więc nie da się nimi
sprawdzić poprawności — widać tylko, że coś zwraca.

Najważniejsze testy to te o kolejności barier: to tam siedzi cichy bias
optymistyczny, który zawyża każdy naiwny backtest.
"""
import datetime as dt

import polars as pl
import pytest

from src.execution.simulator import (
    CostModel, ExitReason, Side, simulate_trade,
)

UTC = dt.timezone.utc
T0 = dt.datetime(2020, 1, 2, 10, 0, tzinfo=UTC)
PIP = 1e-4

# Podłoga wyłączona tam, gdzie testujemy mechanikę barier, żeby koszt
# nie zaciemniał sprawdzanej wielkości.
NO_FLOOR = CostModel(pip=PIP, min_roundturn_pips=0.0,
                     entry_slippage_x_spread=0.0, stop_slippage_x_spread=0.0)


def m1(rows: list[dict]) -> pl.DataFrame:
    """rows: [{min, bid_o, bid_h, bid_l, bid_c, spread}]"""
    out = []
    for r in rows:
        s = r.get("spread", 2 * PIP)
        out.append({
            "ts": T0 + dt.timedelta(minutes=r["min"]),
            "bid_open": r["bid_o"], "bid_high": r["bid_h"],
            "bid_low": r["bid_l"], "bid_close": r["bid_c"],
            "ask_open": r["bid_o"] + s, "ask_high": r["bid_h"] + s,
            "ask_low": r["bid_l"] + s, "ask_close": r["bid_c"] + s,
            "spread_max": s, "spread_close": s,
            "n_ticks": 100,
        })
    return pl.DataFrame(out).with_columns(
        pl.col("ts").cast(pl.Datetime("ms", "UTC")),
        pl.col("n_ticks").cast(pl.UInt32),
    )


def ticks(prices_bid: list[float], spread: float = 2 * PIP) -> pl.DataFrame:
    return pl.DataFrame({
        "ts": [T0 + dt.timedelta(seconds=i) for i in range(len(prices_bid))],
        "bid": prices_bid,
        "ask": [p + spread for p in prices_bid],
    })


FLAT = dict(bid_o=1.1000, bid_h=1.1000, bid_l=1.1000, bid_c=1.1000)


# --- KOLEJNOŚĆ BARIER — rdzeń modułu ----------------------------------------

def test_both_barriers_in_one_bar_resolves_to_stop_without_ticks():
    """Bez ticków kolejność jest NIEZNANA — wariant pesymistyczny, nigdy TP."""
    bars = m1([{"min": 0, **FLAT},
               {"min": 1, "bid_o": 1.1000, "bid_h": 1.1050, "bid_l": 1.0950,
                "bid_c": 1.1000}])
    res = simulate_trade(Side.LONG, T0, sl=1.0960, tp=1.1040,
                         time_barrier=T0 + dt.timedelta(minutes=5),
                         m1=bars, cost=NO_FLOOR, load_ticks=None)
    assert res.reason is ExitReason.STOP_LOSS
    assert res.ticks_scanned == 0


def test_both_barriers_resolved_on_ticks_can_give_take_profit():
    """Z tickami kolejność jest ustalana faktycznie — TP przed SL daje TP."""
    bars = m1([{"min": 0, **FLAT},
               {"min": 1, "bid_o": 1.1000, "bid_h": 1.1050, "bid_l": 1.0950,
                "bid_c": 1.1000}])
    # cena najpierw rośnie do TP, dopiero potem spada poniżej SL
    tk = ticks([1.1000, 1.1020, 1.1045, 1.1000, 1.0950])

    res = simulate_trade(Side.LONG, T0, sl=1.0960, tp=1.1040,
                         time_barrier=T0 + dt.timedelta(minutes=5),
                         m1=bars, cost=NO_FLOOR,
                         load_ticks=lambda a, b: tk)
    assert res.reason is ExitReason.TAKE_PROFIT
    assert res.ticks_scanned > 0


def test_ticks_confirm_stop_when_stop_comes_first():
    bars = m1([{"min": 0, **FLAT},
               {"min": 1, "bid_o": 1.1000, "bid_h": 1.1050, "bid_l": 1.0950,
                "bid_c": 1.1000}])
    tk = ticks([1.1000, 1.0955, 1.1045])   # SL pierwszy

    res = simulate_trade(Side.LONG, T0, sl=1.0960, tp=1.1040,
                         time_barrier=T0 + dt.timedelta(minutes=5),
                         m1=bars, cost=NO_FLOOR, load_ticks=lambda a, b: tk)
    assert res.reason is ExitReason.STOP_LOSS


# --- STRONY RYNKU: long na bidzie, short na asku ----------------------------

def test_long_stop_triggers_on_bid_not_ask():
    """Long wychodzi po bidzie — szeroki spread nie chroni przed stopem."""
    bars = m1([{"min": 0, **FLAT},
               {"min": 1, "bid_o": 1.1000, "bid_h": 1.1000, "bid_l": 1.0950,
                "bid_c": 1.0960, "spread": 10 * PIP}])
    res = simulate_trade(Side.LONG, T0, sl=1.0970, tp=1.2000,
                         time_barrier=T0 + dt.timedelta(minutes=5),
                         m1=bars, cost=NO_FLOOR)
    assert res.reason is ExitReason.STOP_LOSS


def test_spread_spike_stops_short_intrabar_but_leaves_long_untouched():
    """Rdzeń asymetrii: ta sama świeca, dwa przeciwne wyniki.

    Bid stoi w miejscu, ask rośnie przez rozszerzenie spreadu. Short ma
    stop na asku i wylatuje; long ma stop na bidzie i nie jest ruszony.
    Backtest na cenach mid nie widzi tego w ogóle.
    """
    bar = {"min": 1, "bid_o": 1.1000, "bid_h": 1.1015, "bid_l": 1.1000,
           "bid_c": 1.1000, "spread": 10 * PIP}      # ask: 1.1010 -> 1.1025
    bars = m1([{"min": 0, **FLAT}, bar])
    kw = dict(time_barrier=T0 + dt.timedelta(minutes=5), m1=bars, cost=NO_FLOOR)

    short = simulate_trade(Side.SHORT, T0, sl=1.1020, tp=1.0900, **kw)
    long_ = simulate_trade(Side.LONG, T0, sl=1.0980, tp=1.1200, **kw)

    assert short.reason is ExitReason.STOP_LOSS, "skok spreadu nie ruszył shorta"
    assert long_.reason is not ExitReason.STOP_LOSS, "long nie powinien być ruszony"


def test_spread_gap_beyond_stop_fills_at_market_not_at_stop_level():
    """Gdy spread rozjedzie się ponad stop JUŻ NA OTWARCIU bara, nie ma
    fillu po poziomie stopu — jest po cenie rynkowej, czyli gorzej."""
    bars = m1([{"min": 0, **FLAT},
               {"min": 1, "bid_o": 1.1000, "bid_h": 1.1000, "bid_l": 1.1000,
                "bid_c": 1.1000, "spread": 30 * PIP}])     # ask_open = 1.1030
    res = simulate_trade(Side.SHORT, T0, sl=1.1020, tp=1.0900,
                         time_barrier=T0 + dt.timedelta(minutes=5),
                         m1=bars, cost=NO_FLOOR)
    assert res.reason is ExitReason.GAP_STOP
    assert res.exit.price == pytest.approx(1.1030)    # ask_open, nie poziom stopu
    assert res.r < -1.0, "luka spreadowa nie może dawać straty <= 1 R"


# --- LUKI -------------------------------------------------------------------

def test_gap_through_stop_fills_at_open_not_at_stop_level():
    """Stop nie chroni przez lukę — strata przekracza 1 R."""
    bars = m1([{"min": 0, **FLAT},
               {"min": 1, "bid_o": 1.0800, "bid_h": 1.0810, "bid_l": 1.0790,
                "bid_c": 1.0800}])
    res = simulate_trade(Side.LONG, T0, sl=1.0950, tp=1.1100,
                         time_barrier=T0 + dt.timedelta(minutes=5),
                         m1=bars, cost=NO_FLOOR)
    assert res.reason is ExitReason.GAP_STOP
    assert res.exit.price == pytest.approx(1.0800)     # cena otwarcia
    assert res.r < -1.0, f"luka dała tylko {res.r:.2f} R — stop jakby chronił"


def test_gap_through_target_fills_at_open_too():
    bars = m1([{"min": 0, **FLAT},
               {"min": 1, "bid_o": 1.1200, "bid_h": 1.1210, "bid_l": 1.1190,
                "bid_c": 1.1200}])
    res = simulate_trade(Side.LONG, T0, sl=1.0950, tp=1.1100,
                         time_barrier=T0 + dt.timedelta(minutes=5),
                         m1=bars, cost=NO_FLOOR)
    assert res.reason is ExitReason.GAP_TARGET
    assert res.exit.price == pytest.approx(1.1200)


# --- BARIERA CZASOWA --------------------------------------------------------

def test_time_barrier_exits_at_last_close():
    bars = m1([{"min": i, **FLAT} for i in range(6)])
    tb = T0 + dt.timedelta(minutes=5)
    res = simulate_trade(Side.LONG, T0, sl=1.0900, tp=1.1100,
                         time_barrier=tb, m1=bars, cost=NO_FLOOR)
    assert res.reason is ExitReason.TIME_BARRIER
    assert res.exit.price == pytest.approx(1.1000)


def test_missing_data_is_flagged_not_silently_treated_as_time_exit():
    """Urwane dane to inny wynik niż dotrwanie do bariery czasowej."""
    bars = m1([{"min": i, **FLAT} for i in range(2)])
    res = simulate_trade(Side.LONG, T0, sl=1.0900, tp=1.1100,
                         time_barrier=T0 + dt.timedelta(hours=5),
                         m1=bars, cost=NO_FLOOR)
    assert res.reason is ExitReason.NO_DATA


def test_no_data_at_decision_time_returns_none():
    bars = m1([{"min": 30, **FLAT}])
    assert simulate_trade(Side.LONG, T0, sl=1.09, tp=1.11,
                          time_barrier=T0 + dt.timedelta(hours=1),
                          m1=bars, cost=NO_FLOOR) is None


# --- KOSZTY -----------------------------------------------------------------

def test_cost_floor_applies_when_real_spread_is_tighter():
    """Surowy spread Dukascopy jest węższy niż detaliczny — ADR-024."""
    cost = CostModel(pip=PIP, min_roundturn_pips=1.5,
                     entry_slippage_x_spread=0.0, stop_slippage_x_spread=0.0)
    bars = m1([{"min": i, **FLAT, "spread": 0.3 * PIP} for i in range(6)])
    res = simulate_trade(Side.LONG, T0, sl=1.0900, tp=1.1100,
                         time_barrier=T0 + dt.timedelta(minutes=5),
                         m1=bars, cost=cost)
    assert res.cost == pytest.approx(1.5 * PIP)        # podłoga, nie 0.3


def test_stop_slippage_is_adverse_and_in_the_price():
    cost = CostModel(pip=PIP, min_roundturn_pips=0.0,
                     entry_slippage_x_spread=0.0, stop_slippage_x_spread=1.0)
    bars = m1([{"min": 0, **FLAT},
               {"min": 1, "bid_o": 1.1000, "bid_h": 1.1000, "bid_l": 1.0940,
                "bid_c": 1.0950, "spread": 2 * PIP}])
    res = simulate_trade(Side.LONG, T0, sl=1.0950, tp=1.1100,
                         time_barrier=T0 + dt.timedelta(minutes=5),
                         m1=bars, cost=cost)
    # fill poniżej poziomu stopu o pełny spread
    assert res.exit.price == pytest.approx(1.0950 - 2 * PIP)


def test_entry_is_at_ask_for_long_and_bid_for_short():
    bars = m1([{"min": i, **FLAT, "spread": 4 * PIP} for i in range(6)])
    kw = dict(time_barrier=T0 + dt.timedelta(minutes=5), m1=bars, cost=NO_FLOOR)
    lo = simulate_trade(Side.LONG, T0, sl=1.0900, tp=1.1100, **kw)
    sh = simulate_trade(Side.SHORT, T0, sl=1.1100, tp=1.0900, **kw)
    assert lo.entry.price == pytest.approx(1.1000 + 4 * PIP)   # ask
    assert sh.entry.price == pytest.approx(1.1000)             # bid
