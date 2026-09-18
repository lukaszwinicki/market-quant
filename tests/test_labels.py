"""Testy etykietowania triple barrier.

Najważniejsze są testy wokół `t1` — bez poprawnego momentu rozstrzygnięcia
purging jest niewykonalny, a przy nakładających się etykietach każdy wynik
walidacji będzie zawyżony.
"""
import datetime as dt

import polars as pl
import pytest

from src.execution.simulator import CostModel, ExitReason, Side
from src.labels.triple_barrier import (
    LabelSpec, MODELING_FEATURES, add_business_days, barriers,
    effective_sample_size, label_events, overlap_fraction,
)

UTC = dt.timezone.utc
T0 = dt.datetime(2020, 1, 2, 10, 0, tzinfo=UTC)   # czwartek
PIP = 1e-4
ATR_D1 = 100 * PIP
COST = CostModel(pip=PIP, min_roundturn_pips=0.0,
                 entry_slippage_x_spread=0.0, stop_slippage_x_spread=0.0)


def m1(rows, spread=2 * PIP) -> pl.DataFrame:
    out = []
    for r in rows:
        out.append({
            "ts": T0 + dt.timedelta(minutes=r["min"]),
            "bid_open": r["o"], "bid_high": r["h"], "bid_low": r["l"], "bid_close": r["c"],
            "ask_open": r["o"] + spread, "ask_high": r["h"] + spread,
            "ask_low": r["l"] + spread, "ask_close": r["c"] + spread,
            "spread_max": spread, "spread_close": spread, "n_ticks": 100,
        })
    return pl.DataFrame(out).with_columns(
        pl.col("ts").cast(pl.Datetime("ms", "UTC")),
        pl.col("n_ticks").cast(pl.UInt32))


def flat(n, price=1.1000):
    return [{"min": i, "o": price, "h": price, "l": price, "c": price} for i in range(n)]


def events(times, side=Side.LONG, atr=ATR_D1) -> pl.DataFrame:
    return pl.DataFrame({
        "ts": pl.Series(times, dtype=pl.Datetime("ms", "UTC")),
        "side": [side.value] * len(times),
        "atr_d1_14": [atr] * len(times),
    })


# --- SPLĄTANIE ETYKIETY Z CECHĄ ---------------------------------------------

def test_atr_is_not_a_modeling_feature():
    """Bariery są w ATR. Gdyby ATR był też cechą, model uczyłby się
    geometrii barier zamiast sygnału."""
    assert "atr_d1_14" not in MODELING_FEATURES
    assert "atr_h1_14" not in MODELING_FEATURES


# --- t1: moment rozstrzygnięcia ---------------------------------------------

def test_t1_records_when_label_was_resolved():
    bars = m1(flat(3) + [{"min": 3, "o": 1.1000, "h": 1.1000, "l": 1.0700, "c": 1.0700}]
              + flat(20)[4:])
    lab = label_events(events([T0]), bars, COST)
    assert lab.height == 1
    assert lab["t1"][0] == T0 + dt.timedelta(minutes=3)   # bar, w którym padł SL
    assert lab["y"][0] == 0


def test_t1_is_after_or_equal_entry_always():
    bars = m1(flat(1600))   # 1 dzień roboczy = 1440 minut
    ts = [T0 + dt.timedelta(minutes=i) for i in (0, 10, 20)]
    lab = label_events(events(ts), bars, COST, LabelSpec(horizon_business_days=1))
    assert (lab["t1"] >= lab["ts"]).all()


# --- Nakładanie się etykiet — powód, dla którego purge jest obowiązkowy ------

def test_overlap_is_detected_and_quantified():
    """Etykiety co minutę z długim horyzontem nakładają się prawie w całości."""
    bars = m1(flat(1600))   # 1 dzień roboczy = 1440 minut
    ts = [T0 + dt.timedelta(minutes=i) for i in range(50)]
    lab = label_events(events(ts), bars, COST, LabelSpec(horizon_business_days=1))
    assert overlap_fraction(lab) > 0.9, "nakładanie się nie zostało wykryte"


def test_effective_sample_is_far_below_nominal_count():
    """Nominalne n zawyża moc statystyczną o rząd wielkości."""
    bars = m1(flat(1600))   # 1 dzień roboczy = 1440 minut
    ts = [T0 + dt.timedelta(minutes=i) for i in range(50)]
    lab = label_events(events(ts), bars, COST, LabelSpec(horizon_business_days=1))
    eff = effective_sample_size(lab)
    assert eff < lab.height / 10, f"efektywne {eff} vs nominalne {lab.height}"


def test_non_overlapping_labels_give_full_effective_size():
    bars = m1(flat(1600))   # 1 dzień roboczy = 1440 minut
    # wejścia rzadsze niż horyzont => brak nakładania
    lab = label_events(events([T0]), bars, COST, LabelSpec(horizon_business_days=1))
    assert effective_sample_size(lab) == lab.height


# --- Bariery ----------------------------------------------------------------

def test_barrier_levels_are_symmetric_for_both_sides():
    sl_l, tp_l = barriers(1.1000, ATR_D1, Side.LONG, LabelSpec())
    sl_s, tp_s = barriers(1.1000, ATR_D1, Side.SHORT, LabelSpec())
    assert sl_l == pytest.approx(1.1000 - 2 * ATR_D1)
    assert tp_l == pytest.approx(1.1000 + 4 * ATR_D1)
    assert sl_s == pytest.approx(1.1000 + 2 * ATR_D1)
    assert tp_s == pytest.approx(1.1000 - 4 * ATR_D1)


def test_zero_atr_is_rejected_loudly():
    with pytest.raises(ValueError):
        barriers(1.1, 0.0, Side.LONG, LabelSpec())


# --- Konwencje etykiety -----------------------------------------------------

def test_time_barrier_is_labelled_zero_conservatively():
    bars = m1(flat(1600))   # 1 dzień roboczy = 1440 minut
    lab = label_events(events([T0]), bars, COST, LabelSpec(horizon_business_days=1))
    assert lab["reason"][0] == ExitReason.TIME_BARRIER.value
    assert lab["y"][0] == 0


def test_take_profit_is_labelled_one():
    bars = m1(flat(3) + [{"min": 3, "o": 1.1000, "h": 1.1500, "l": 1.1000, "c": 1.1500}]
              + flat(20)[4:])
    lab = label_events(events([T0]), bars, COST)
    assert lab["y"][0] == 1


def test_gap_beyond_target_counts_as_win():
    bars = m1(flat(3) + [{"min": 3, "o": 1.1600, "h": 1.1600, "l": 1.1600, "c": 1.1600}]
              + flat(20)[4:])
    lab = label_events(events([T0]), bars, COST)
    assert lab["reason"][0] == ExitReason.GAP_TARGET.value
    assert lab["y"][0] == 1


def test_undefined_outcome_is_dropped_not_labelled_zero():
    """Urwane dane to brak etykiety. Zero udawałoby przegraną."""
    bars = m1(flat(5))          # dane kończą się długo przed horyzontem
    lab = label_events(events([T0]), bars, COST, LabelSpec(horizon_business_days=10))
    assert lab.height == 0


def test_event_without_atr_is_skipped():
    bars = m1(flat(1600))   # 1 dzień roboczy = 1440 minut
    ev = events([T0]).with_columns(pl.lit(None, pl.Float64).alias("atr_d1_14"))
    assert label_events(ev, bars, COST).height == 0


# --- Dni robocze ------------------------------------------------------------

def test_business_days_skip_weekends():
    friday = dt.datetime(2020, 1, 3, 10, tzinfo=UTC)
    assert add_business_days(friday, 1) == dt.datetime(2020, 1, 6, 10, tzinfo=UTC)
    assert add_business_days(friday, 5) == dt.datetime(2020, 1, 10, 10, tzinfo=UTC)


def test_ten_business_days_spans_two_calendar_weeks():
    thursday = dt.datetime(2020, 1, 2, 10, tzinfo=UTC)
    end = add_business_days(thursday, 10)
    assert (end - thursday).days == 14
    assert end.weekday() < 5
