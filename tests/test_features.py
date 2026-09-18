"""Testy cech technicznych.

Najważniejszy jest `test_features_are_causal` — łapie każdą statystykę
policzoną na pełnej próbie zamiast w oknie rozszerzającym.
"""
import datetime as dt

import numpy as np
import polars as pl
import pytest

from src.features.technical import (
    ATR_PERIOD, DONCHIAN, FEATURE_COLUMNS, VOL_PCT_MIN_DAYS,
    atr, compute_features, expanding_percentile_rank,
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
