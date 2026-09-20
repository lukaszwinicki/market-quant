"""Testy runnera V1a — wyłącznie dane syntetyczne.

Na prawdziwych tickach nie znamy poprawnej odpowiedzi, więc widać tylko,
że coś zwraca. Tutaj każdy scenariusz jest zbudowany tak, żeby wynik był
znany z góry: trend, który MUSI trafić TP; bar, który MUSI być odrzucony;
pula, z której strategia MUSI wybrać dokładnie te wiersze.
"""
import datetime as dt

import numpy as np
import polars as pl
import pytest

from src.data.calendar import CALENDAR_SCHEMA, HIGH_SERIES
from src.data.rates import SCHEMA as RATE_SCHEMA
from src.execution.simulator import CostModel
from src.labels.triple_barrier import LabelSpec
from src.strategy.runner import (
    BENCHMARK_NARROWED, BENCHMARK_NOTE, Controls, Variant, Window, control_pool,
    daily_matrix, decision_summary, evaluators, feature_sets, plateau_check,
    preflight, render, run_variant, shifted_baseline, split_expectancies,
    subperiod_expectancies,
)
from src.strategy.v1a import Rules, V1aParams
from src.validation.cpcv import CPCVSpec
from src.validation.gate0 import make_evaluator

UTC = dt.timezone.utc
PIP = 1e-4
COST = CostModel(pip=PIP, min_roundturn_pips=1.5)
ATR = 20 * PIP

T0 = dt.datetime(2020, 1, 6, tzinfo=UTC)          # poniedziałek
WINDOW = Window(T0, T0 + dt.timedelta(days=2), T0 + dt.timedelta(days=30))
NO_EVENTS = pl.DataFrame(schema=CALENDAR_SCHEMA)
# Horyzont 1 dnia roboczego: testy mają być szybkie, a logika barier jest
# sprawdzana w testach symulatora.
RULES = Rules(horizon_business_days=1)
BASE = V1aParams(name="baseline")


# --- syntetyczny rynek --------------------------------------------------------

def trending_m1(start: dt.datetime, minutes: int, drift=0.05 * PIP,
                spread=0.5 * PIP) -> pl.DataFrame:
    """Bid rosnący liniowo — long MUSI trafić TP, short MUSI trafić SL."""
    o = 1.1 + drift * np.arange(minutes)
    c = o + drift
    return pl.DataFrame({
        "ts": pl.Series([start + dt.timedelta(minutes=i) for i in range(minutes)],
                        dtype=pl.Datetime("ms", "UTC")),
        "bid_open": o, "bid_high": c, "bid_low": o, "bid_close": c,
        "ask_open": o + spread, "ask_high": c + spread,
        "ask_low": o + spread, "ask_close": c + spread,
        "spread_max": np.full(minutes, spread),
        "spread_close": np.full(minutes, spread),
        "n_ticks": pl.Series(np.full(minutes, 10), dtype=pl.UInt32),
    })


def feats(bar_ts, donchian=55, mom=0.5, donch=0.9, vol=0.5, atr=ATR) -> pl.DataFrame:
    n = len(bar_ts)
    return pl.DataFrame({
        "ts": pl.Series(bar_ts, dtype=pl.Datetime("ms", "UTC")),
        "mom_24": pl.Series([mom] * n, dtype=pl.Float64),
        "mom_120": pl.Series([mom] * n, dtype=pl.Float64),
        "mom_480": pl.Series([mom] * n, dtype=pl.Float64),
        f"donch_pos_{donchian}": pl.Series([donch] * n, dtype=pl.Float64),
        "atr_d1_14": pl.Series([atr] * n, dtype=pl.Float64),
        "vol_pct_252": pl.Series([vol] * n, dtype=pl.Float64),
    })


def hourly(start: dt.datetime, n: int):
    return [start + dt.timedelta(hours=i) for i in range(n)]


@pytest.fixture
def market():
    return {"EURUSD": trending_m1(T0, 60 * 24 * 32)}


@pytest.fixture
def evaluate(market):
    return make_evaluator(market, {"EURUSD": COST},
                          LabelSpec(2.0, 4.0, horizon_business_days=1))


@pytest.fixture
def rates():
    """Stopy miesięczne dla EUR i USD; różnica 1 pp, więc swap jest niezerowy."""
    months = [dt.date(2019, m, 1) for m in range(1, 13)] + \
             [dt.date(2020, m, 1) for m in range(1, 13)]
    rows = []
    for ccy, v in (("EUR", 0.5), ("USD", 1.5)):
        rows += [{"date": d, "currency": ccy, "kind": "overnight",
                  "value": v, "series": f"X{ccy}"} for d in months]
    return pl.DataFrame(rows, schema=RATE_SCHEMA)


# --- okno ---------------------------------------------------------------------

def test_window_rejects_reversed_dates():
    with pytest.raises(ValueError):
        Window(T0, T0 - dt.timedelta(days=1), T0 + dt.timedelta(days=1))


def test_window_rejects_naive_datetimes():
    with pytest.raises(ValueError):
        Window(dt.datetime(2020, 1, 6), T0, T0 + dt.timedelta(days=1))


# --- przygotowanie ------------------------------------------------------------

def test_feature_sets_computes_one_frame_per_donchian_length():
    h1 = pl.DataFrame({
        "ts": pl.Series(hourly(T0, 200), dtype=pl.Datetime("ms", "UTC")),
        "bid_open": np.linspace(1.1, 1.2, 200), "bid_high": np.linspace(1.1, 1.2, 200),
        "bid_low": np.linspace(1.1, 1.2, 200), "bid_close": np.linspace(1.1, 1.2, 200),
        "ask_open": np.linspace(1.1, 1.2, 200), "ask_high": np.linspace(1.1, 1.2, 200),
        "ask_low": np.linspace(1.1, 1.2, 200), "ask_close": np.linspace(1.1, 1.2, 200),
    })
    grid = [V1aParams(40, name="D-"), V1aParams(55), V1aParams(70, name="D+"),
            V1aParams(55, 1.5, 4.0, "S-")]
    sets = feature_sets({"EURUSD": h1}, grid)
    assert sorted(sets) == [40, 55, 70]
    assert "donch_pos_70" in sets[70]["EURUSD"].columns


def test_evaluators_are_shared_between_variants_with_the_same_geometry(market):
    grid = [V1aParams(55, 2.0, 4.0, "baseline"), V1aParams(40, 2.0, 4.0, "D-"),
            V1aParams(70, 2.0, 4.0, "D+"), V1aParams(55, 1.5, 4.0, "S-"),
            V1aParams(55, 2.5, 4.0, "S+"), V1aParams(55, 2.0, 3.0, "T-"),
            V1aParams(55, 2.0, 5.0, "T+")]
    evals = evaluators(grid, market, {"EURUSD": COST}, 10)
    # siedem wariantów, ale tylko pięć różnych geometrii barier
    assert len(evals) == 5
    assert evals[(2.0, 4.0, 10)] is not evals[(1.5, 4.0, 10)]


# --- przebieg wariantu --------------------------------------------------------

def test_variant_enters_on_trend_and_carries_financing(evaluate, rates):
    f = {"EURUSD": feats(hourly(T0 + dt.timedelta(days=2), 20))}
    v = run_variant(BASE, f, RULES, NO_EVENTS, WINDOW, evaluate, rates, 0.5)
    assert v.trades.height >= 1
    assert "financing_r" in v.trades.columns
    assert "fin_unit_r" in v.trades.columns
    # Long na parze, gdzie kwotowana płaci więcej, PŁACI carry; plus marża.
    assert (v.trades["financing_r"] > 0).all()


def test_financing_is_applied_before_statistics(evaluate, rates):
    f = {"EURUSD": feats(hourly(T0 + dt.timedelta(days=2), 20))}
    free = run_variant(BASE, f, RULES, NO_EVENTS, WINDOW, evaluate, rates, 0.0)
    paid = run_variant(BASE, f, RULES, NO_EVENTS, WINDOW, evaluate, rates, 2.0)
    # Ta sama transakcja, wyższa marża → niższe R. Gdyby swap wchodził po
    # statystykach, obie wersje miałyby to samo `r`.
    assert paid.expectancy < free.expectancy


def test_decisions_never_start_before_trade_start(evaluate, rates):
    bars = hourly(T0, 60)                       # także przed `trade_start`
    v = run_variant(BASE, {"EURUSD": feats(bars)}, RULES, NO_EVENTS, WINDOW,
                    evaluate, rates, 0.5)
    assert v.decisions["ts"].min() >= WINDOW.trade_start


def test_every_bar_after_trade_start_gets_a_decision_row(evaluate, rates):
    bars = hourly(WINDOW.trade_start, 30)
    v = run_variant(BASE, {"EURUSD": feats(bars)}, RULES, NO_EVENTS, WINDOW,
                    evaluate, rates, 0.5)
    assert v.decisions.height == len(bars)
    assert v.decisions["action"].is_in(["enter", "no_trade"]).all()


def test_decision_summary_accounts_for_every_bar(evaluate, rates):
    bars = hourly(WINDOW.trade_start, 30)
    v = run_variant(BASE, {"EURUSD": feats(bars)}, RULES, NO_EVENTS, WINDOW,
                    evaluate, rates, 0.5)
    assert decision_summary(v.decisions)["n"].sum() == v.decisions.height


def test_decision_summary_shows_conditions_that_are_never_the_first_reason():
    """Warunek o niskim priorytecie może działać na każdym objętym barze
    i mieć zero w kolumnie „pierwszy”. Bez `n_any` znikałby z raportu —
    tak było z `10_sunday_open` (ADR-042), który stoi po `no_signal`."""
    dec = pl.DataFrame({
        "reason": ["no_signal", "no_signal", "9_friday", None],
        "reasons": ["no_signal,10_sunday_open", "no_signal",
                    "9_friday,10_sunday_open", ""],
    })
    s = decision_summary(dec)
    row = s.filter(pl.col("reason") == "10_sunday_open").row(0, named=True)
    assert row["n"] == 0, "warunek nie był pierwszym powodem ani razu"
    assert row["n_any"] == 2
    assert s.filter(pl.col("reason") == "no_signal")["n_any"][0] == 2
    assert s["n"].sum() == dec.height


def test_split_boundary_blocks_entries_whose_horizon_leaves_the_split(evaluate, rates):
    late = Window(T0, T0 + dt.timedelta(days=2), T0 + dt.timedelta(days=4))
    bars = hourly(T0 + dt.timedelta(days=3), 10)
    v = run_variant(BASE, {"EURUSD": feats(bars)}, RULES, NO_EVENTS, late,
                    evaluate, rates, 0.5)
    assert (v.decisions["reason"] == "split_boundary").any()


def test_shifted_baseline_keeps_atr_and_shifts_only_the_signal(evaluate, rates):
    bars = hourly(WINDOW.trade_start, 30)
    f = {"EURUSD": feats(bars)}
    v = shifted_baseline(BASE, f, RULES, NO_EVENTS, WINDOW, evaluate, rates, 0.5)
    # ATR jest normalizatorem barier — przesunięcie go zmieniłoby geometrię
    # transakcji, a nie treść sygnału (§10.2 #3).
    assert v.decisions.height == len(bars)
    assert v.decisions["reason"].head(1).to_list() == ["warmup"]


# --- metryki ------------------------------------------------------------------

def _trades(days, r, symbol="EURUSD", side="long") -> pl.DataFrame:
    return pl.DataFrame({
        "ts": pl.Series([T0 + dt.timedelta(days=int(d)) for d in days],
                        dtype=pl.Datetime("ms", "UTC")),
        "t1": pl.Series([T0 + dt.timedelta(days=int(d) + 1) for d in days],
                        dtype=pl.Datetime("ms", "UTC")),
        "symbol": [symbol] * len(days), "side": [side] * len(days),
        "r": pl.Series(r, dtype=pl.Float64),
    })


def test_daily_matrix_puts_variants_on_one_axis():
    a = Variant(V1aParams(name="a"), pl.DataFrame(), _trades([0, 1], [1.0, 2.0]))
    b = Variant(V1aParams(name="b"), pl.DataFrame(), _trades([1, 2], [3.0, 4.0]))
    days, m = daily_matrix([a, b])
    assert len(days) == 3 and m.shape == (3, 2)
    # dzień bez transakcji wariantu to zero, nie brak
    assert m[0, 1] == 0.0 and m[2, 0] == 0.0
    assert m[:, 0].sum() == pytest.approx(3.0)


def test_daily_matrix_handles_a_variant_without_trades():
    a = Variant(V1aParams(name="a"), pl.DataFrame(), _trades([0, 1], [1.0, 2.0]))
    empty = Variant(V1aParams(name="b"), pl.DataFrame(), pl.DataFrame())
    days, m = daily_matrix([a, empty])
    assert m.shape == (len(days), 2)
    assert m[:, 1].sum() == 0.0


def test_split_expectancies_returns_one_value_per_cpcv_split():
    spec = CPCVSpec(6, 2, 0, 0)
    trades = _trades(range(60), np.linspace(-1, 1, 60))
    assert len(split_expectancies(trades, spec)) == spec.n_splits == 15


def test_subperiods_cover_the_whole_window_without_overlap():
    trades = _trades(range(30), np.ones(30))
    window = Window(T0, T0, T0 + dt.timedelta(days=30))
    subs = subperiod_expectancies(trades, window, n=3)
    assert len(subs) == 3
    assert sum(n for _, n, _ in subs) == trades.height


def _variant(name, mean):
    return Variant(V1aParams(name=name), pl.DataFrame(),
                   _trades([0, 1], [mean, mean]))


def test_plateau_passes_when_every_neighbour_stays_above_half_of_baseline():
    vs = [_variant("baseline", 0.20)] + [_variant(f"n{i}", 0.12) for i in range(6)]
    assert plateau_check(vs).passed


def test_plateau_fails_on_a_single_spike():
    vs = [_variant("baseline", 0.20)] + [_variant(f"n{i}", 0.12) for i in range(5)]
    vs.append(_variant("n5", 0.05))
    chk = plateau_check(vs)
    assert not chk.passed and "n5" in chk.detail


def test_plateau_fails_when_baseline_is_not_positive():
    vs = [_variant("baseline", -0.01)] + [_variant(f"n{i}", -0.005) for i in range(6)]
    assert not plateau_check(vs).passed


# --- kontrole -----------------------------------------------------------------

def test_control_pool_always_contains_the_strategy_trades(evaluate, rates):
    bars = hourly(WINDOW.trade_start, 40)
    f = {"EURUSD": feats(bars)}
    v = run_variant(BASE, f, RULES, NO_EVENTS, WINDOW, evaluate, rates, 0.5)
    assert v.trades.height >= 1

    candidates = (feats(bars).select("ts", "atr_d1_14")
                  .with_columns(pl.lit("EURUSD").alias("symbol")))
    # Pula przycięta do jednego wiersza na (para, kierunek) — wiersze
    # strategii i tak muszą się w niej znaleźć, inaczej maska nie ma sensu.
    pool, selected = control_pool(candidates, v.trades, evaluate, rates, 0.5,
                                  per_group=1, seed=0)
    taken = set(v.trades.select("symbol", "ts", "side").iter_rows())
    in_pool = set(pool.filter(pl.Series(selected))
                  .select("symbol", "ts", "side").iter_rows())
    assert taken <= in_pool
    assert int(selected.sum()) == v.trades.height


# --- preflight ----------------------------------------------------------------

def _calendar(year: int, currencies=("EUR", "USD")) -> pl.DataFrame:
    rows = []
    for ccy in currencies:
        for i, name in enumerate(HIGH_SERIES[ccy]):
            rows.append({
                "timestamp_utc": dt.datetime(year, 3, 1 + i, 12, tzinfo=UTC),
                "currency": ccy, "name": name, "rank": "HIGH",
                "source": "https://example.invalid/test",
            })
    return pl.DataFrame(rows, schema=CALENDAR_SCHEMA)


def test_preflight_passes_on_complete_calendar_and_rates(rates):
    window = Window(dt.datetime(2020, 1, 1, tzinfo=UTC),
                    dt.datetime(2020, 1, 1, tzinfo=UTC),
                    dt.datetime(2020, 12, 31, tzinfo=UTC))
    preflight(_calendar(2020), rates, ["EURUSD"], window)


def test_preflight_rejects_a_calendar_missing_one_series(rates):
    window = Window(dt.datetime(2020, 1, 1, tzinfo=UTC),
                    dt.datetime(2020, 1, 1, tzinfo=UTC),
                    dt.datetime(2020, 12, 31, tzinfo=UTC))
    thin = _calendar(2020).filter(pl.col("name") != "US_CPI")
    with pytest.raises(ValueError, match="kalendarz nie pokrywa"):
        preflight(thin, rates, ["EURUSD"], window)


def test_preflight_rejects_missing_rates(rates):
    window = Window(dt.datetime(2020, 1, 1, tzinfo=UTC),
                    dt.datetime(2020, 1, 1, tzinfo=UTC),
                    dt.datetime(2020, 12, 31, tzinfo=UTC))
    with pytest.raises(ValueError, match="niepełne stopy"):
        preflight(_calendar(2020), rates.filter(pl.col("currency") != "USD"),
                  ["EURUSD"], window)


def test_preflight_asks_only_for_currencies_of_the_run(rates):
    """Przebieg na EURUSD nie potrzebuje stóp dla AUD ani CAD."""
    window = Window(dt.datetime(2020, 1, 1, tzinfo=UTC),
                    dt.datetime(2020, 1, 1, tzinfo=UTC),
                    dt.datetime(2020, 12, 31, tzinfo=UTC))
    preflight(_calendar(2020), rates, ["EURUSD"], window)   # brak AUD/CAD w `rates`


# --- raport -------------------------------------------------------------------

def test_report_states_that_the_section_12_benchmark_was_not_computed():
    """ADR-036 pkt 1 i ADR-038 pkt 6: milczenie jest gorsze niż brak liczby."""
    assert "NIE ZOSTAŁ" in BENCHMARK_NOTE and "§12" in BENCHMARK_NOTE
    assert "ADR-038" in BENCHMARK_NOTE


# --- cały przebieg na syntetyku ----------------------------------------------
#
# Test integracyjny: siatka 7 wariantów, finansowanie, wszystkie metryki
# i kontrole, aż do raportu. Nie sprawdza, czy strategia zarabia — tego na
# syntetyku sprawdzić się nie da. Sprawdza, że przebieg przechodzi całą
# drogę i że raport ma wszystkie sekcje, których wymagają ADR-y.

E2E_SYMBOLS = ("EURUSD", "USDJPY")
E2E_DAYS = 60


def walk_m1(start, minutes, rng, sigma, base=1.1, spread=0.5 * PIP):
    steps = rng.standard_normal((minutes, 4)) * sigma / 2
    path = base + np.cumsum(steps.ravel()).reshape(minutes, 4)
    o, c = path[:, 0], path[:, 3]
    return pl.DataFrame({
        "ts": pl.Series([start + dt.timedelta(minutes=i) for i in range(minutes)],
                        dtype=pl.Datetime("ms", "UTC")),
        "bid_open": o, "bid_high": path.max(1), "bid_low": path.min(1), "bid_close": c,
        "ask_open": o + spread, "ask_high": path.max(1) + spread,
        "ask_low": path.min(1) + spread, "ask_close": c + spread,
        "spread_max": np.full(minutes, spread),
        "spread_close": np.full(minutes, spread),
        "n_ticks": pl.Series(np.full(minutes, 10), dtype=pl.UInt32),
    })


@pytest.fixture
def e2e(rates):
    from src.strategy.v1a import grid_from

    rng = np.random.default_rng(11)
    minutes = 60 * 24 * (E2E_DAYS + 5)
    market = {
        "EURUSD": walk_m1(T0, minutes, rng, sigma=0.4 * PIP, base=1.1),
        "USDJPY": walk_m1(T0, minutes, rng, sigma=0.4, base=110.0),
    }
    costs = {"EURUSD": CostModel(pip=PIP, min_roundturn_pips=1.5),
             "USDJPY": CostModel(pip=0.01, min_roundturn_pips=1.5)}
    grid = grid_from({"signal_v1a": {"sensitivity_grid": [
        {"name": "baseline", "donchian_lookback": 55, "sl_multiple": 2.0, "tp_multiple": 4.0},
        {"name": "D-", "donchian_lookback": 40, "sl_multiple": 2.0, "tp_multiple": 4.0},
        {"name": "D+", "donchian_lookback": 70, "sl_multiple": 2.0, "tp_multiple": 4.0},
        {"name": "S-", "donchian_lookback": 55, "sl_multiple": 1.5, "tp_multiple": 4.0},
        {"name": "S+", "donchian_lookback": 55, "sl_multiple": 2.5, "tp_multiple": 4.0},
        {"name": "T-", "donchian_lookback": 55, "sl_multiple": 2.0, "tp_multiple": 3.0},
        {"name": "T+", "donchian_lookback": 55, "sl_multiple": 2.0, "tp_multiple": 5.0},
    ]}})

    window = Window(T0, T0 + dt.timedelta(days=1),
                    T0 + dt.timedelta(days=E2E_DAYS))
    bars = hourly(T0, 24 * (E2E_DAYS + 1))
    # Sygnał daje kierunek na każdym barze; o tym, ile transakcji powstanie,
    # decydują limity portfela i zajętość pary do `t1`.
    features = {n: {s: feats(bars, donchian=n,
                             atr=ATR if s == "EURUSD" else 0.2)
                    for s in E2E_SYMBOLS} for n in (40, 55, 70)}
    rates_all = pl.concat([rates, pl.DataFrame(
        [{"date": d, "currency": "JPY", "kind": "overnight", "value": -0.1,
          "series": "XJPY"} for d in rates["date"].unique().to_list()],
        schema=RATE_SCHEMA)])
    return grid, market, costs, features, window, rates_all


def test_full_grid_runs_end_to_end_and_renders_a_report(e2e):
    from src.strategy.runner import assess, run_controls

    grid, market, costs, features, window, rates_all = e2e
    evals = evaluators(grid, market, costs, RULES.horizon_business_days)

    variants = [
        run_variant(p, features[p.donchian_lookback], RULES, NO_EVENTS, window,
                    evals[(p.sl_multiple, p.tp_multiple, RULES.horizon_business_days)],
                    rates_all, 0.5)
        for p in grid
    ]
    assert all(v.trades.height > 5 for v in variants)

    base = variants[0]
    base_eval = evals[(2.0, 4.0, RULES.horizon_business_days)]
    candidates = pl.concat([
        feats(hourly(T0, 24 * (E2E_DAYS + 1)), atr=ATR if s == "EURUSD" else 0.2)
        .select("ts", "atr_d1_14").with_columns(pl.lit(s).alias("symbol"))
        .filter(pl.col("ts") >= window.trade_start)
        for s in E2E_SYMBOLS])

    controls = run_controls(base, candidates, base_eval, rates_all, 0.5,
                            pool_per_group=40, n_reps=20, seed=1)
    shifted = shifted_baseline(base.params, features[55], RULES, NO_EVENTS,
                               window, base_eval, rates_all, 0.5)
    controls.shifted_expectancy = shifted.expectancy
    controls.shifted_trades = shifted.trades.height

    cfg = {
        "validation": {"acceptance_thresholds": {
            "expectancy_net_R_min": 0.10, "t_stat_min": 2.0,
            "deflated_sharpe_min": 0.95, "pbo_max": 0.30,
            "positive_at_cost_multiple": 2.0, "min_instruments_positive": 2,
            "min_subperiods_positive": 2}},
        "costs": {"sensitivity_multipliers": [1.0, 2.0, 3.0],
                  "financing": {"cohort_a_markup_annual_pct": 0.5,
                                "cohort_a_markup_sensitivity": [0.5, 1.0, 2.0]}},
    }
    result = assess(variants, cfg, window, n_trials=7, controls=controls,
                    block_days=5, boot_reps=200, seed=1, cpcv=CPCVSpec(6, 2, 0, 0))

    assert len(result.checks) == 11
    # Bez policzonego koszyka kontrola #5 MUSI wypaść na czerwono — brak
    # liczby nie może być domyślnym „przeszło" (ADR-036 pkt 1).
    # Tak samo kontrola #4 (ADR-044).
    for tag in ("#5", "#4"):
        found = [c for c in result.checks if tag in c.name]
        assert len(found) == 1 and not found[0].passed, tag
    assert not result.benchmark.computed
    assert not result.control4.computed
    assert len(result.costs) == 3 and len(result.markups) == 3
    assert result.effective_n <= base.trades.height
    assert 0.0 <= result.dsr.dsr <= 1.0
    assert result.pbo is not None and 0.0 <= result.pbo.pbo <= 1.0
    assert len(result.split_r) == 15
    assert len(result.subperiods) == 3
    assert controls.random_null.size == 20
    assert controls.shuffled_null.size == 20
    assert 0.0 < controls.random_p <= 1.0

    params = {"symbols": list(E2E_SYMBOLS), "data_start": window.data_start,
              "trade_start": window.trade_start, "split_end": window.split_end}
    report = render("test-run", params, result)
    for section in ("Kryteria bramki 2", "Log decyzji", "Koszt 1×, 2×, 3×",
                    "Oś marży swapu", "Warianty siatki", "CPCV", "Podokresy",
                    "Kontrole §10.2", "Kontrola #5"):
        assert section in report
    assert BENCHMARK_NOTE in report
    # Ścieżki CPCV są zdegenerowane przy regule nieuczonej — raport ma to mówić.
    assert "zdegenerowane" in report


def test_report_swaps_the_note_when_the_benchmark_is_computed(e2e):
    """Policzony koszyk zdejmuje notkę „nie policzony", ale NIE notkę o zawężeniu.

    ADR-038 pkt 6: każdy raport powołujący się na §12 musi mówić, że koszyk
    jest węższy niż ten, który uzasadniał ADR-019.
    """
    from src.strategy.runner import Benchmark, assess, benchmark_check
    from src.validation.benchmark import Comparison

    c = Comparison(strategy_sharpe=0.20, benchmark_sharpe=0.05, difference=0.15,
                   ci_low=0.02, ci_high=0.28, strategy_mean_daily_r=0.03,
                   benchmark_mean_daily_r=0.01, strategy_open_risk_r=4.38,
                   benchmark_open_risk_r=2.0, n_days=200, n_reps=400)
    bench = Benchmark(comparison=c, per_anchor={a: 0.01 * a for a in range(5)},
                      anchor_stats=[{"anchor": a, "n_rebalances": 40,
                                     "n_skipped": 1, "n_trades": 12}
                                    for a in range(5)])
    assert benchmark_check(bench).passed          # CI95 w całości > 0

    grid, market_, costs, features, window, rates_all = e2e
    evals = evaluators(grid, market_, costs, RULES.horizon_business_days)
    variants = [
        run_variant(p, features[p.donchian_lookback], RULES, NO_EVENTS, window,
                    evals[(p.sl_multiple, p.tp_multiple, RULES.horizon_business_days)],
                    rates_all, 0.5)
        for p in grid
    ]
    cfg = {
        "validation": {"acceptance_thresholds": {
            "expectancy_net_R_min": 0.10, "t_stat_min": 2.0,
            "deflated_sharpe_min": 0.95, "pbo_max": 0.30,
            "positive_at_cost_multiple": 2.0, "min_instruments_positive": 2,
            "min_subperiods_positive": 2}},
        "costs": {"sensitivity_multipliers": [1.0, 2.0, 3.0],
                  "financing": {"cohort_a_markup_annual_pct": 0.5,
                                "cohort_a_markup_sensitivity": [0.5, 1.0, 2.0]}},
    }
    result = assess(variants, cfg, window, n_trials=7, controls=Controls(),
                    block_days=5, boot_reps=200, seed=1, cpcv=CPCVSpec(6, 2, 0, 0),
                    benchmark=bench)
    params = {"symbols": list(E2E_SYMBOLS), "data_start": window.data_start,
              "trade_start": window.trade_start, "split_end": window.split_end}
    report = render("test-run", params, result)

    assert BENCHMARK_NOTE not in report
    assert BENCHMARK_NARROWED in report
    assert "otwartego ryzyka" in report or "otwarte ryzyko" in report
    assert "4.38 R" in report and "2.00 R" in report     # ADR-040 pkt 4
    assert "poniedziałek" in report and "piątek" in report   # ADR-040 pkt 5
