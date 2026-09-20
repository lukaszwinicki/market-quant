"""Testy reguły V1a i warunków NO TRADE — dane syntetyczne, odpowiedź znana z góry."""
import datetime as dt
from pathlib import Path

import polars as pl
import pytest
import yaml

from src.strategy.v1a import (
    REASON_ORDER, Rules, V1aParams, data_gap_flags, decision_frame, grid_from,
    rules_from, run_v1a,
)

UTC = dt.timezone.utc
T0 = dt.datetime(2019, 1, 7, 0, tzinfo=UTC)          # poniedziałek, zima (EST)
FAR = dt.datetime(2030, 1, 1, tzinfo=UTC)
RULES = Rules()
P = V1aParams()
NO_EVENTS = pl.DataFrame(schema={"timestamp_utc": pl.Datetime("ms", "UTC"),
                                 "currency": pl.Utf8, "name": pl.Utf8,
                                 "rank": pl.Utf8, "source": pl.Utf8})


def feats(bar_ts, mom=0.5, donch=0.9, vol=0.5, atr=0.01) -> pl.DataFrame:
    n = len(bar_ts)
    col = lambda v: [v] * n if not isinstance(v, list) else v   # noqa: E731
    return pl.DataFrame({
        "ts": pl.Series(bar_ts, dtype=pl.Datetime("ms", "UTC")),
        "mom_480": pl.Series(col(mom), dtype=pl.Float64),
        "donch_pos_55": pl.Series(col(donch), dtype=pl.Float64),
        "atr_d1_14": pl.Series(col(atr), dtype=pl.Float64),
        "vol_pct_252": pl.Series(col(vol), dtype=pl.Float64),
    })


def hours(start, n):
    return [start + dt.timedelta(hours=i) for i in range(n)]


def frame(bar_ts, symbol="EURUSD", events=NO_EVENTS, split_end=FAR, **kw):
    return decision_frame(feats(bar_ts, **kw), symbol, P, RULES, events, split_end)


# --- reguła -------------------------------------------------------------------

@pytest.mark.parametrize("mom, donch, expected", [
    (0.5, 0.90, "long"), (-0.5, 0.10, "short"),
    (0.5, 0.80, None),                 # nierówność ostra
    (-0.5, 0.20, None),
    (0.0, 0.95, None),                 # mom_480 = 0 nie daje kierunku
    (0.5, 0.10, None), (-0.5, 0.90, None),
])
def test_signal_rule(mom, donch, expected):
    f = frame([T0 + dt.timedelta(hours=10)], mom=mom, donch=donch)
    assert f["signal"][0] == expected


def test_decision_is_at_bar_close():
    f = frame([T0 + dt.timedelta(hours=9)])
    assert f["ts"][0] == T0 + dt.timedelta(hours=10)
    assert f["bar_ts"][0] == T0 + dt.timedelta(hours=9)


def test_missing_features_are_warmup_not_signal():
    f = frame(hours(T0 + dt.timedelta(hours=8), 2), vol=[None, 0.5])
    assert f["warmup"].to_list() == [True, False]


def test_vol_pct_limit_is_strictly_above_095():
    f = frame(hours(T0 + dt.timedelta(hours=8), 3), vol=[0.95, 0.9501, None])
    assert f["2_vol_pct"].to_list() == [False, True, False]


# --- kalendarz sesji Nowego Jorku ----------------------------------------------

@pytest.mark.parametrize("bar_utc, rollover", [
    (dt.datetime(2019, 1, 9, 21, tzinfo=UTC), True),    # decyzja 22:00 UTC = 17:00 EST
    (dt.datetime(2019, 1, 9, 20, tzinfo=UTC), False),   # 16:00 EST
    (dt.datetime(2019, 7, 10, 20, tzinfo=UTC), True),   # 21:00 UTC = 17:00 EDT
    (dt.datetime(2019, 7, 10, 21, tzinfo=UTC), False),  # 18:00 EDT
])
def test_rollover_window_follows_new_york_dst(bar_utc, rollover):
    assert frame([bar_utc])["8_rollover"][0] is rollover


@pytest.mark.parametrize("bar_utc, blocked", [
    (dt.datetime(2019, 1, 11, 19, tzinfo=UTC), True),   # pt 20:00 UTC = 15:00 EST
    (dt.datetime(2019, 1, 11, 18, tzinfo=UTC), False),  # pt 14:00 EST
    (dt.datetime(2019, 7, 12, 18, tzinfo=UTC), True),   # pt 19:00 UTC = 15:00 EDT
    (dt.datetime(2019, 1, 10, 21, tzinfo=UTC), False),  # czwartek wieczorem
])
def test_friday_cutoff_is_15_new_york_inclusive(bar_utc, blocked):
    assert frame([bar_utc])["9_friday"][0] is blocked


# --- ADR-042: sesja otwarcia tygodnia -----------------------------------------

@pytest.mark.parametrize("bar_utc, blocked", [
    (dt.datetime(2019, 1, 13, 21, tzinfo=UTC), True),   # ndz 21:00 -> decyzja ndz 22:00
    (dt.datetime(2019, 1, 13, 22, tzinfo=UTC), True),   # ndz 22:00 -> decyzja ndz 23:00
    (dt.datetime(2019, 1, 13, 23, tzinfo=UTC), False),  # ndz 23:00 -> decyzja pon 00:00
    (dt.datetime(2019, 1, 11, 20, tzinfo=UTC), False),  # pt 20:00 -> decyzja pt 21:00
    (dt.datetime(2019, 1, 14, 3, tzinfo=UTC), False),   # pon 04:00 UTC, Tokio
])
def test_sunday_open_blocks_the_decision_not_the_bar(bar_utc, blocked):
    """Reguła zaczepia się o moment DECYZJI, jak warunki 8 i 9. Bar 23:00
    daje decyzję o 00:00 UTC w poniedziałek i przechodzi."""
    assert frame([bar_utc])["10_sunday_open"][0] is blocked


@pytest.mark.parametrize("bar_utc", [
    dt.datetime(2019, 1, 13, 23, tzinfo=UTC),   # decyzja pon 00:00 UTC = ndz 19:00 EST
    dt.datetime(2019, 7, 14, 23, tzinfo=UTC),   # decyzja pon 00:00 UTC = ndz 20:00 EDT
    dt.datetime(2019, 1, 14, 3, tzinfo=UTC),    # decyzja pon 04:00 UTC = ndz 23:00 EST
])
def test_sunday_open_uses_utc_so_tokyo_morning_stays_open(bar_utc):
    """W czasie NY te chwile są jeszcze niedzielą (tydzień FX otwiera się
    17:00 NY), więc kryterium „niedziela NY” obcięłoby poranną sesję
    tokijską. Kryterium jest w UTC — patrz ADR-042."""
    assert frame([bar_utc])["10_sunday_open"][0] is False


# --- luki w danych ------------------------------------------------------------

def test_weekend_is_not_a_data_gap():
    fri = hours(dt.datetime(2019, 1, 11, 12, tzinfo=UTC), 10)          # do 21:00
    sun = hours(dt.datetime(2019, 1, 13, 22, tzinfo=UTC), 5)
    assert not data_gap_flags(pl.Series(fri + sun), 2, 480).any()


def test_midweek_gap_blocks_for_lookback_bars_then_clears():
    a = hours(T0 + dt.timedelta(days=1), 10)
    b = hours(a[-1] + dt.timedelta(hours=4), 20)          # 3 brakujące bary
    flags = data_gap_flags(pl.Series(a + b), max_missing=2, lookback=5).to_list()
    assert flags[:10] == [False] * 10
    assert flags[10:15] == [True] * 5                      # luka w ostatnich 5 barach
    assert flags[15:] == [False] * 15


def test_two_missing_bars_are_tolerated():
    a = hours(T0 + dt.timedelta(days=1), 10)
    b = hours(a[-1] + dt.timedelta(hours=3), 5)           # 2 brakujące bary
    assert not data_gap_flags(pl.Series(a + b), 2, 480).any()


# --- blackout i granica splitu -----------------------------------------------

def test_blackout_uses_calendar_of_pair_currencies():
    e = dt.datetime(2019, 1, 9, 13, 30, tzinfo=UTC)
    events = pl.DataFrame([{"timestamp_utc": e, "currency": "USD", "name": "US_CPI",
                            "rank": "HIGH", "source": "https://x"}], schema=NO_EVENTS.schema)
    bars = [e - dt.timedelta(hours=2), e - dt.timedelta(hours=1), e + dt.timedelta(minutes=30)]
    bars = [b.replace(minute=0) for b in bars]             # decyzje 12:00, 13:00, 15:00
    assert frame(bars, events=events)["1_blackout"].to_list() == [False, True, True]
    assert not frame(bars, symbol="EURJPY", events=events)["1_blackout"].any()


def test_split_boundary_requires_whole_horizon_inside():
    end = dt.datetime(2019, 1, 25, 23, 59, tzinfo=UTC)
    bars = [dt.datetime(2019, 1, 10, 9, tzinfo=UTC), dt.datetime(2019, 1, 14, 9, tzinfo=UTC)]
    assert frame(bars, split_end=end)["split_boundary"].to_list() == [False, True]


# --- przebieg sekwencyjny -------------------------------------------------------

def fake_evaluate(hold=dt.timedelta(days=3), empty=()):
    """Symulator zastępczy: każda transakcja trwa `hold`, r = 1."""
    def evaluate(ev):
        rows = [{**r, "t1": r["ts"] + hold, "r": 1.0}
                for r in ev.iter_rows(named=True) if r["symbol"] not in empty]
        return pl.DataFrame(rows) if rows else pl.DataFrame()
    return evaluate


def run(frames, **kw):
    return run_v1a(frames, RULES, fake_evaluate(**kw))


def test_open_position_blocks_the_pair_until_after_exit():
    """Wejście o T0+10:00, t1 = T0+3 dni 10:00. Decyzja równa t1 — jeszcze
    otwarta; pierwsza PÓŹNIEJSZA — wolne."""
    log, trades = run([frame(hours(T0 + dt.timedelta(hours=9), 80))],
                      hold=dt.timedelta(days=3))
    act = log["action"].to_list()
    assert act[0] == "enter"
    assert set(log["reason"][1:73]) == {"6_open_position"}
    assert log["ts"][72] == T0 + dt.timedelta(days=3, hours=10)
    assert act[73] == "enter"
    assert trades.height == 2


def test_usd_block_limit_is_net_two_r():
    """long EURUSD + long GBPUSD = −2 R USD; short USDJPY dołożyłby −3 R."""
    t = [T0 + dt.timedelta(hours=9)]
    frames = [frame(t, "EURUSD"), frame(t, "GBPUSD"),
              frame(t, "USDJPY", mom=-0.5, donch=0.1)]
    log, _ = run(frames)
    got = dict(zip(log["symbol"], log["reason"]))
    assert got == {"EURUSD": None, "GBPUSD": None, "USDJPY": "4_ccy_limit"}


def test_exposure_that_reduces_the_block_is_allowed():
    t = [T0 + dt.timedelta(hours=9)]
    frames = [frame(t, "EURUSD"), frame(t, "GBPUSD"), frame(t, "USDJPY")]   # long USDJPY: +1 USD
    log, _ = run(frames)
    assert log["action"].to_list() == ["enter"] * 3


def test_commodity_block_sums_aud_and_cad():
    """ρ = 1 w bloku: long AUDUSD (+1 AUD) i short USDCAD (+1 CAD) = +2 R w bloku."""
    rules = Rules(max_net_block_r=1.0)
    t = [T0 + dt.timedelta(hours=9)]
    frames = [decision_frame(feats(t), "AUDUSD", P, rules, NO_EVENTS, FAR),
              decision_frame(feats(t, mom=-0.5, donch=0.1), "USDCAD", P, rules, NO_EVENTS, FAR)]
    log, _ = run_v1a(frames, rules, fake_evaluate())
    assert log["reason"].to_list() == [None, "4_ccy_limit"]


def test_portfolio_limit():
    rules = Rules(max_portfolio_r=2.0, max_net_block_r=10.0)
    t = [T0 + dt.timedelta(hours=9)]
    frames = [decision_frame(feats(t), s, P, rules, NO_EVENTS, FAR)
              for s in ("AUDUSD", "EURUSD", "GBPUSD")]
    log, _ = run_v1a(frames, rules, fake_evaluate())
    assert log["reason"].to_list() == [None, None, "5_portfolio"]


def test_all_reasons_are_logged_and_first_follows_the_order():
    bar = dt.datetime(2019, 1, 11, 21, tzinfo=UTC)         # pt 22:00 UTC: rollover i piątek
    log, trades = run([frame([bar], vol=0.99)])
    assert log["reason"][0] == "2_vol_pct"
    assert log["reasons"][0] == "2_vol_pct,8_rollover,9_friday"
    assert trades.is_empty()


def test_no_signal_and_warmup_rows_are_logged_too():
    bars = hours(T0 + dt.timedelta(hours=8), 2)
    log, _ = run([frame(bars, mom=[None, 0.0])])
    assert log["reason"].to_list() == ["warmup", "no_signal"]
    assert set(log["reason"].drop_nulls()) <= set(REASON_ORDER)


def test_simulator_without_data_is_a_logged_no_fill():
    log, trades = run([frame([T0 + dt.timedelta(hours=9)])], empty=("EURUSD",))
    assert (log["action"][0], log["reason"][0]) == ("no_trade", "no_fill")
    assert trades.is_empty()


# --- konfiguracja ---------------------------------------------------------------

def test_rules_and_grid_come_from_config():
    cfg = yaml.safe_load((Path(__file__).parents[1] / "config" / "v1_baseline.yaml").read_text())
    r = rules_from(cfg)
    assert (r.donch_pos_min, r.vol_pct_max, r.max_net_block_r) == (0.80, 0.95, 2.0)
    assert (r.blackout_before_min, r.blackout_after_min) == (30, 120)
    assert r.blocks["commodity"] == ("AUD", "NZD", "CAD")
    grid = grid_from(cfg)
    assert len(grid) == 7 and grid[0] == V1aParams(55, 2.0, 4.0, "baseline")


def test_runs_on_the_real_simulator_and_respects_exit_times():
    """Integracja z `gate0.make_evaluator`: prawdziwe bariery, prawdziwe `t1`."""
    import numpy as np

    from src.execution.simulator import CostModel
    from src.validation.gate0 import make_evaluator
    from tests.test_controls import _random_walk_m1

    m1 = _random_walk_m1(T0, 60 * 24 * 26, np.random.default_rng(3), sigma=0.5e-4)
    spec = P.label_spec(horizon_business_days=2)
    evaluate = make_evaluator({"EURUSD": m1}, {"EURUSD": CostModel(pip=1e-4)}, spec)
    bars = [b for b in hours(T0, 24 * 10) if b.weekday() < 5]
    log, trades = run_v1a([frame(bars, atr=20e-4)], RULES, evaluate)

    assert trades.height >= 2
    assert (log["action"] == "enter").sum() == trades.height
    entries = trades.sort("ts")
    assert (entries["ts"][1:] > entries["t1"][:-1]).all()      # nigdy dwie naraz
