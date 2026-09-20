"""Testy cech technicznych.

Najważniejszy jest `test_features_are_causal` — łapie każdą statystykę
policzoną na pełnej próbie zamiast w oknie rozszerzającym.
"""
import datetime as dt

import numpy as np
import polars as pl
import pytest
import yaml

from src.features.technical import (
    ATR_PERIOD, DONCHIAN, FEATURE_COLUMNS, MIN_H1_BARS_PER_DAY, VOL_PCT_MIN_DAYS,
    atr, compute_features, daily_bars, expanding_percentile_rank,
)

UTC = dt.timezone.utc
T0 = dt.datetime(2015, 1, 1, tzinfo=UTC)


def h1(closes, highs=None, lows=None, spread=3e-5) -> pl.DataFrame:
    n = len(closes)
    highs = highs if highs is not None else [c + 1e-3 for c in closes]
    lows = lows if lows is not None else [c - 1e-3 for c in closes]
    return pl.DataFrame({
        "ts": pl.Series([T0 + dt.timedelta(hours=i) for i in range(n)],
                        dtype=pl.Datetime("ms", "UTC")),
        "bid_open": closes, "bid_high": highs, "bid_low": lows, "bid_close": closes,
        "ask_open": [c + spread for c in closes],
        "ask_high": [c + spread for c in highs],
        "ask_low": [c + spread for c in lows],
        "ask_close": [c + spread for c in closes],
        "spread_max": [spread] * n, "spread_close": [spread] * n,
        "n_ticks": pl.Series([100] * n, dtype=pl.UInt32),
    })


def walk(n, seed=0, start=1.10, sigma=3e-4):
    rng = np.random.default_rng(seed)
    return list(start + np.cumsum(rng.normal(0, sigma, n)))


# --- KAUZALNOŚĆ — rdzeń modułu ----------------------------------------------

def test_features_are_causal():
    """Dołożenie przyszłych barów nie może zmienić ANI JEDNEJ wcześniejszej
    wartości. Łapie z-score, percentyl czy skaler liczony na pełnej próbie."""
    full = h1(walk(24 * 400, seed=1))
    cut = full.head(24 * 300)

    a = compute_features(cut)
    b = compute_features(full).head(cut.height)

    for col in FEATURE_COLUMNS:
        x, y = a[col].to_numpy(), b[col].to_numpy()
        both_nan = np.isnan(x) & np.isnan(y)
        assert np.array_equal(both_nan, np.isnan(x) | np.isnan(y)), f"{col}: nulle się rozjechały"
        np.testing.assert_allclose(x[~both_nan], y[~both_nan], rtol=1e-12,
                                   err_msg=f"{col} zmieniło się po dołożeniu przyszłości")


def test_expanding_rank_never_sees_future():
    s = pl.Series([5.0, 1.0, 3.0, 9.0, 2.0])
    r = expanding_percentile_rank(s, min_periods=1).to_list()
    assert r[0] == 1.0          # jedyna wartość => ranga 1
    assert r[1] == 0.5          # 1.0 jest najmniejsza z dwóch
    assert r[3] == 1.0          # 9.0 największa z czterech
    assert r[4] == pytest.approx(2 / 5)


def test_expanding_rank_respects_min_periods():
    s = pl.Series([float(i) for i in range(10)])
    r = expanding_percentile_rank(s, min_periods=5)
    assert r[:4].is_null().all()
    assert r[4] is not None


# --- vol_pct_252: ostatni ZAMKNIĘTY dzień -----------------------------------

def test_daily_volatility_comes_from_previous_day_not_current():
    """W barze o 10:00 dnia D nie wolno znać ATR dnia D — dzień trwa."""
    df = compute_features(h1(walk(24 * (VOL_PCT_MIN_DAYS + 40), seed=2)))
    df = df.with_columns(pl.col("ts").dt.truncate("1d").alias("day"))

    per_day = df.group_by("day").agg(pl.col("atr_d1_14").n_unique().alias("u"))
    assert (per_day["u"] <= 1).all(), "ATR dzienny zmienia się w ciągu dnia"

    days = df["day"].unique().sort().to_list()
    assert df.filter(pl.col("day") == days[0])["atr_d1_14"].is_null().all(), \
        "pierwszy dzień zna własny ATR — to look-ahead"


def test_vol_pct_is_null_before_min_history():
    df = compute_features(h1(walk(24 * 100, seed=3)))
    assert df["vol_pct_252"].is_null().all(), "percentyl bez 252 dni historii"


# --- Poprawność wartości ----------------------------------------------------

def test_atr_matches_hand_computation():
    closes = [1.1000, 1.1010, 1.1005]
    highs = [1.1005, 1.1020, 1.1015]
    lows = [1.0995, 1.1000, 1.0990]
    df = h1(closes, highs, lows)
    a = atr(df, period=3)
    # TR: bar0 = H-L = 10 pips; bar1 = max(20, |1.1020-1.1000|=20, |1.1000-1.1000|=0) = 20
    #     bar2 = max(25, |1.1015-1.1010|=5, |1.1010-1.0990|=20) = 25
    assert a[2] == pytest.approx((0.0010 + 0.0020 + 0.0025) / 3)


def test_momentum_is_scaled_by_sqrt_of_its_own_horizon():
    """Bez sqrt(n) trzy momenta różnią się skalą o ~sqrt(20)."""
    df = compute_features(h1(walk(24 * 120, seed=4)))
    d = df.drop_nulls(["mom_24", "mom_120", "mom_480"])
    if d.height:
        for c in ("mom_24", "mom_120", "mom_480"):
            assert abs(d[c].std()) < 10, f"{c} ma rozjechaną skalę"


def test_momentum_sign_follows_price():
    up = compute_features(h1([1.10 + i * 1e-4 for i in range(200)]))
    assert (up.drop_nulls("mom_24")["mom_24"] > 0).all()
    down = compute_features(h1([1.10 - i * 1e-4 for i in range(200)]))
    assert (down.drop_nulls("mom_24")["mom_24"] < 0).all()


def test_donchian_position_is_bounded_and_oriented():
    df = compute_features(h1(walk(24 * 60, seed=5)))
    d = df.drop_nulls("donch_pos_55")["donch_pos_55"]
    assert d.min() >= 0.0 and d.max() <= 1.0

    # cena rosnąca monotonicznie => zamknięcie przy szczycie zakresu
    up = compute_features(h1([1.10 + i * 1e-4 for i in range(200)],
                             highs=[1.10 + i * 1e-4 for i in range(200)],
                             lows=[1.10 + i * 1e-4 for i in range(200)]))
    assert up.drop_nulls("donch_pos_55")["donch_pos_55"].max() == pytest.approx(1.0)


def test_flat_range_gives_null_not_division_by_zero():
    df = compute_features(h1([1.10] * 100, highs=[1.10] * 100, lows=[1.10] * 100))
    assert df["donch_pos_55"].is_null().all()


# --- Okresy rozgrzewania ----------------------------------------------------

def test_warmup_periods_are_null_not_zero():
    """Brak danych ma być nullem. Zero udaje sygnał."""
    df = compute_features(h1(walk(24 * 30, seed=6)))
    assert df["atr_h1_14"][: ATR_PERIOD - 1].is_null().all()
    assert df["donch_pos_55"][: DONCHIAN - 1].is_null().all()
    assert df["mom_480"][:480].is_null().all()


def test_no_feature_column_contains_nan():
    """NaN != null. drop_nulls() nie usuwa NaN-ów, więc taka wartość
    przeszłaby przez filtrowanie i zatruła model po cichu."""
    df = compute_features(h1(walk(24 * 300, seed=7)))
    for col in FEATURE_COLUMNS:
        n = df.select(pl.col(col).is_nan().sum()).item() or 0
        assert n == 0, f"{col} zawiera {n} NaN-ów zamiast nulli"


# --- ADR-041: niepełne doby nie wchodzą do szeregu dziennego ------------------
#
# Powyższe testy używają ciągłych barów co godzinę, więc każda doba ma 24 bary
# i kalendarz FX w nich nie występuje. Poniższe budują prawdziwy kształt
# tygodnia: niedziela 3 bary, pon-czw po 24, piątek 21, soboty brak.

SUNDAY_RANGE_FRACTION = 0.2       # zmierzone 20-25% zakresu doby pełnej
FULL_RANGE = 0.0100
SUNDAY_RANGE = FULL_RANGE * SUNDAY_RANGE_FRACTION


def fx_week_h1(n_weeks: int, base: float = 1.10, spread: float = 3e-5,
               vary: bool = False) -> pl.DataFrame:
    """Bary H1 o kształcie tygodnia FX, ze sterowanym zakresem dobowym.

    Cena zamknięcia jest stała, więc TR doby = jej zakres (high - low)
    i ATR14 da się policzyć w pamięci. Niedziela ma zakres
    SUNDAY_RANGE, każda inna doba FULL_RANGE.

    `vary=True` nadaje każdej pełnej dobie inny zakres, dzięki czemu wartość
    ATR jednoznacznie wskazuje dobę źródłową.
    """
    first_sunday = dt.datetime(2015, 1, 4, tzinfo=UTC)   # niedziela
    rows = []
    full_day_i = 0
    for w in range(n_weeks):
        week = first_sunday + dt.timedelta(weeks=w)
        days = [(week, range(21, 24))]                         # ndz: 3 bary
        days += [(week + dt.timedelta(days=d), range(24))      # pon-czw: 24
                 for d in (1, 2, 3, 4)]
        days.append((week + dt.timedelta(days=5), range(21)))  # pt: 21 barów
        for day, hours in days:
            if day.weekday() == 6:
                rng_ = SUNDAY_RANGE
            else:
                rng_ = FULL_RANGE * (1 + full_day_i / 100) if vary else FULL_RANGE
                full_day_i += 1
            half = rng_ / 2
            for h in hours:
                rows.append((day + dt.timedelta(hours=h), base + half, base - half))

    ts, hi, lo = zip(*rows)
    n = len(rows)
    return pl.DataFrame({
        "ts": pl.Series(list(ts), dtype=pl.Datetime("ms", "UTC")),
        "bid_open": [base] * n, "bid_high": list(hi), "bid_low": list(lo),
        "bid_close": [base] * n,
        "ask_open": [base + spread] * n,
        "ask_high": [h + spread for h in hi],
        "ask_low": [lo_ + spread for lo_ in lo],
        "ask_close": [base + spread] * n,
        "spread_max": [spread] * n, "spread_close": [spread] * n,
        "n_ticks": pl.Series([100] * n, dtype=pl.UInt32),
    })


def test_min_h1_bars_matches_config():
    """Próg jest wielkością ZAMROŻONĄ — wartość w kodzie musi się zgadzać
    z `data.d1_boundary.min_h1_bars`, inaczej pieczęć konfiguracji przestaje
    opisywać to, co faktycznie policzono."""
    cfg = yaml.safe_load(open("config/v1_baseline.yaml", encoding="utf-8"))
    assert cfg["data"]["d1_boundary"]["min_h1_bars"] == MIN_H1_BARS_PER_DAY


def test_sunday_stub_is_dropped_from_daily_series():
    d1 = daily_bars(fx_week_h1(6))
    dows = d1["ts"].dt.weekday().unique().sort().to_list()
    assert 7 not in dows, "niedzielny kikut (3 bary H1) wszedł do szeregu D1"
    assert dows == [1, 2, 3, 4, 5], "wypadła doba, która nie jest kikutem"


def test_full_friday_is_kept_despite_having_21_bars():
    """Piątek ma 21 barów zamiast 24, ale zakres pełnej doby (99-116%
    zakresu pon-czw). Próg nie może go wyciąć."""
    d1 = daily_bars(fx_week_h1(6))
    fridays = d1.filter(pl.col("ts").dt.weekday() == 5)
    assert fridays.height == 6
    assert (fridays["bid_high"] - fridays["bid_low"]).to_list() == \
        pytest.approx([FULL_RANGE] * 6)


def test_sunday_stub_deflates_atr_when_threshold_is_disabled():
    """Test samego zjawiska: przy progu 1 (stan sprzed ADR-041) niedziele
    wchodzą do ATR14 i zaniżają go o kilkanaście procent."""
    h = fx_week_h1(12)
    fixed = atr(daily_bars(h), ATR_PERIOD).drop_nulls()
    broken = atr(daily_bars(h, min_bars=1), ATR_PERIOD).drop_nulls()

    assert fixed.median() == pytest.approx(FULL_RANGE)
    # okno 14 dób przy 6 dobach na tydzień to ~2,33 kikuta
    expected = (FULL_RANGE * (14 - 14 / 6) + SUNDAY_RANGE * 14 / 6) / 14
    assert broken.median() == pytest.approx(expected, rel=0.05)
    assert broken.median() < fixed.median() * 0.9


def test_monday_keeps_atr_after_sunday_is_dropped():
    """REGRESJA: samo odfiltrowanie niedziel zostawiłoby poniedziałki bez
    ATR, bo join po dacie szukałby nieistniejącego bara niedzielnego.
    Asof musi im dać wartość z piątku."""
    df = compute_features(fx_week_h1(6))
    mondays = df.filter((pl.col("ts").dt.weekday() == 1)
                        & (pl.col("ts") > df["ts"].min() + dt.timedelta(days=21)))
    assert mondays.height > 0
    assert mondays["atr_d1_14"].is_not_null().all(), \
        "poniedziałki straciły atr_d1_14 po wycięciu niedziel"


def test_sunday_bars_get_atr_from_the_last_full_day():
    """Bary sesji niedzielnej dostają ATR z piątku (ADR-041 pkt 4).
    Do ADR-041 miały null, przez co były blokowane przypadkiem, a nie regułą
    — jawną regułę dokłada ADR-042."""
    df = compute_features(fx_week_h1(6))
    late = df.filter(pl.col("ts") > df["ts"].min() + dt.timedelta(days=21))
    sundays = late.filter(pl.col("ts").dt.weekday() == 7)
    fridays = late.filter(pl.col("ts").dt.weekday() == 5)

    assert sundays.height > 0
    assert sundays["atr_d1_14"].is_not_null().all()
    # ta sama wartość co ostatni bar piątku tego samego tygodnia
    assert sundays["atr_d1_14"][-1] == pytest.approx(fridays["atr_d1_14"][-1])


def test_daily_values_are_causal_across_weekend_gaps():
    """Kauzalność na kalendarzu z lukami — `test_features_are_causal` używa
    barów ciągłych, więc asof po dobach nie jest tam w ogóle sprawdzany."""
    full = fx_week_h1(40)
    cut = full.filter(pl.col("ts") < full["ts"].min() + dt.timedelta(weeks=30))

    a = compute_features(cut)
    b = compute_features(full).head(cut.height)
    for col in ("atr_d1_14", "vol_pct_252"):
        x, y = a[col].to_numpy(), b[col].to_numpy()
        both_nan = np.isnan(x) & np.isnan(y)
        assert np.array_equal(both_nan, np.isnan(x) | np.isnan(y))
        np.testing.assert_allclose(x[~both_nan], y[~both_nan], rtol=1e-12,
                                   err_msg=f"{col} zmieniło się po dołożeniu przyszłości")


def test_atr_comes_from_the_last_full_day_strictly_before_the_bars_day():
    """Wprost semantyka ADR-041 pkt 2, na serii o RÓŻNYCH zakresach dobowych,
    więc wartość ATR jednoznacznie wskazuje dobę źródłową."""
    h = fx_week_h1(20, vary=True)
    d1 = daily_bars(h)
    d1 = d1.with_columns(atr(d1, ATR_PERIOD).alias("a")).drop_nulls("a")
    expected_for = dict(zip(d1["ts"].to_list(), d1["a"].to_list()))
    full_days = d1["ts"].to_list()

    df = compute_features(h).with_columns(pl.col("ts").dt.truncate("1d").alias("day"))
    checked = 0
    for bar_day, got in zip(df["day"].to_list(), df["atr_d1_14"].to_list()):
        earlier = [d for d in full_days if d < bar_day]
        if not earlier:
            assert got is None, "bar dostał ATR, choć nie ma wcześniejszej pełnej doby"
            continue
        assert got == pytest.approx(expected_for[earlier[-1]]), \
            f"bar z doby {bar_day} nie wziął ATR z {earlier[-1]}"
        checked += 1
    assert checked > 1000
