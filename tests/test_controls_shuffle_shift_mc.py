"""Kontrole §10.2 #2 (shuffled labels), #3 (shifted features), #7 (max DD).

Wszystko na syntetyku, gdzie poprawna odpowiedź jest znana z konstrukcji:
na prawdziwych danych widać tylko, że funkcja coś zwraca.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import polars as pl
import pytest

from src.validation.controls import (
    empirical_p_value, max_drawdown, permutation_max_drawdown, shift_features,
    shuffled_label_null,
)

UTC = dt.timezone.utc
T0 = dt.datetime(2020, 1, 6, 0, tzinfo=UTC)     # poniedziałek


def labels(n=200, symbols=("EURUSD", "USDJPY"), seed=0) -> pl.DataFrame:
    """Kandydaci z wynikiem `r` i cechą `mom_24`, bez żadnego związku między nimi."""
    rng = np.random.default_rng(seed)
    parts = []
    for k, s in enumerate(symbols):
        parts.append(pl.DataFrame({
            "ts": pl.Series([T0 + dt.timedelta(hours=i) for i in range(n)],
                            dtype=pl.Datetime("ms", "UTC")),
            "symbol": s,
            "side": ["long", "short"] * (n // 2),
            "mom_24": rng.normal(size=n),
            "r": rng.normal(loc=0.1 * k, scale=1.0, size=n),
        }))
    return pl.concat(parts)


# --- #2 shuffled labels -----------------------------------------------------

def test_shuffled_null_is_centred_on_the_pool_mean_not_on_zero():
    """Rozkład zerowy dziedziczy dryf puli — to jest udokumentowana własność.

    Maska bierze tyle samo longów co shortów, więc oczekiwana średnia to
    średnia całej puli. Przy masce jednostronnej byłaby to średnia tej
    strony — patrz `test_shuffle_stays_inside_symbol_and_side_groups`.
    """
    lab = labels(n=400, symbols=("EURUSD",), seed=1)
    lab = lab.with_columns(pl.col("r") + 0.5)          # cała pula przesunięta
    mask = np.zeros(lab.height, dtype=bool)
    mask[:100] = True                                  # 50 longów i 50 shortów

    null = shuffled_label_null(lab, mask, n_reps=400, seed=0)
    assert abs(null.mean() - lab["r"].mean()) < 0.02
    assert abs(null.mean()) > 0.4                      # NIE jest wyśrodkowany na 0


def test_selection_with_no_information_sits_in_the_middle_of_the_null():
    """Wybór niezwiązany z wynikiem => p-value daleko od ogona."""
    lab = labels(n=400, symbols=("EURUSD",), seed=2)
    mask = np.zeros(lab.height, dtype=bool)
    mask[::3] = True

    observed = lab.filter(pl.Series(mask))["r"].mean()
    null = shuffled_label_null(lab, mask, n_reps=999, seed=0)
    assert 0.05 < empirical_p_value(observed, null) < 0.95


def test_selection_that_picks_the_winners_lands_in_the_tail():
    """Wybór idealnie skorelowany z wynikiem musi być nieosiągalny dla tasowania."""
    lab = labels(n=400, symbols=("EURUSD",), seed=3)
    order = np.argsort(lab["r"].to_numpy())
    mask = np.zeros(lab.height, dtype=bool)
    mask[order[-50:]] = True                           # 50 najlepszych

    observed = lab.filter(pl.Series(mask))["r"].mean()
    null = shuffled_label_null(lab, mask, n_reps=999, seed=0)
    assert empirical_p_value(observed, null) == pytest.approx(1 / 1000)


def test_shuffle_stays_inside_symbol_and_side_groups():
    """Wyniki nie przeciekają między parami — inaczej rozkład zerowy mieszałby
    rozkłady zwrotów różnych instrumentów."""
    lab = labels(n=200, symbols=("EURUSD", "USDJPY"), seed=4)
    # Rozjeżdżamy pule tak, żeby przeciek był widoczny gołym okiem.
    lab = lab.with_columns(
        pl.when(pl.col("symbol") == "EURUSD").then(pl.lit(-10.0))
        .otherwise(pl.lit(10.0)).alias("r"))
    mask = (lab["symbol"] == "EURUSD").to_numpy()

    null = shuffled_label_null(lab, mask, n_reps=50, seed=0)
    assert np.allclose(null, -10.0)


def test_shuffled_null_is_deterministic_in_the_seed():
    lab = labels(n=120, symbols=("EURUSD",), seed=5)
    mask = np.zeros(lab.height, dtype=bool)
    mask[::2] = True
    a = shuffled_label_null(lab, mask, n_reps=50, seed=7)
    b = shuffled_label_null(lab, mask, n_reps=50, seed=7)
    c = shuffled_label_null(lab, mask, n_reps=50, seed=8)
    assert np.array_equal(a, b) and not np.array_equal(a, c)


def test_mask_of_wrong_length_is_rejected():
    lab = labels(n=100, symbols=("EURUSD",))
    with pytest.raises(ValueError, match="maska"):
        shuffled_label_null(lab, np.ones(7, dtype=bool))


def test_empty_selection_is_rejected():
    lab = labels(n=100, symbols=("EURUSD",))
    with pytest.raises(ValueError, match="żadnego"):
        shuffled_label_null(lab, np.zeros(lab.height, dtype=bool))


# --- #3 shifted features ----------------------------------------------------

def feature_frame(n=50) -> pl.DataFrame:
    return pl.DataFrame({
        "ts": pl.Series([T0 + dt.timedelta(hours=i) for i in range(n)],
                        dtype=pl.Datetime("ms", "UTC")),
        "mom_24": np.arange(n, dtype=float),
        "mom_120": np.arange(n, dtype=float) * 2,
        "mom_480": np.arange(n, dtype=float) * 3,
        "donch_pos_55": np.linspace(0, 1, n),
        "vol_pct_252": np.linspace(0, 1, n),
        "atr_d1_14": np.full(n, 0.002),
    })


def test_shift_moves_feature_values_forward_in_time():
    """Bar i dostaje wartość bara i-1 — czyli cechę STARSZĄ."""
    f = feature_frame()
    out = shift_features(f, bars=1)
    assert out["mom_24"][0] is None
    assert out["mom_24"][5] == f["mom_24"][4]
    assert out["ts"].to_list() == f["ts"].to_list()


def test_shift_leaves_the_barrier_normaliser_alone():
    """atr_d1_14 wyznacza geometrię barier, nie treść sygnału."""
    f = feature_frame()
    out = shift_features(f, bars=3)
    assert out["atr_d1_14"].to_list() == f["atr_d1_14"].to_list()
    assert out["mom_480"][0] is None and out["mom_480"][2] is None
    assert out["mom_480"][3] == f["mom_480"][0]


def test_shift_by_more_than_one_bar():
    f = feature_frame()
    out = shift_features(f, bars=4)
    assert out["donch_pos_55"][10] == f["donch_pos_55"][6]
    assert out["donch_pos_55"].null_count() == 4


def test_unsorted_frame_is_rejected():
    f = feature_frame().reverse()
    with pytest.raises(ValueError, match="posortowane"):
        shift_features(f)


def test_multi_symbol_frame_is_rejected():
    """Przesunięcie przez granicę symbolu wciągnęłoby cudzą historię."""
    f = feature_frame(10).with_columns(
        pl.Series("symbol", ["EURUSD"] * 5 + ["USDJPY"] * 5))
    with pytest.raises(ValueError, match="jednego symbolu"):
        shift_features(f)


def test_missing_column_is_rejected():
    f = feature_frame().drop("vol_pct_252")
    with pytest.raises(ValueError, match="vol_pct_252"):
        shift_features(f)


def test_zero_shift_is_rejected():
    with pytest.raises(ValueError, match="bars"):
        shift_features(feature_frame(), bars=0)


# --- #7 Monte Carlo permutacji ----------------------------------------------

def test_max_drawdown_on_a_known_path():
    # skumulowane: 1, 3, 0, 1, -2  → szczyt 3, dołek -2  → DD = 5
    assert max_drawdown(np.array([1.0, 2.0, -3.0, 1.0, -3.0])) == pytest.approx(5.0)


def test_max_drawdown_of_a_rising_path_is_zero():
    assert max_drawdown(np.array([1.0, 2.0, 3.0])) == 0.0


def test_max_drawdown_counts_the_start_as_a_peak():
    """Strata od pierwszego dnia to obsunięcie, nie zero."""
    assert max_drawdown(np.array([-2.0, -1.0])) == pytest.approx(3.0)


def trades_from(daily: list[float]) -> pl.DataFrame:
    """Po jednej transakcji na kolejne dni robocze."""
    ts, r = [], []
    d = T0
    for v in daily:
        while d.weekday() >= 5:
            d += dt.timedelta(days=1)
        ts.append(d)
        r.append(v)
        d += dt.timedelta(days=1)
    return pl.DataFrame({"ts": pl.Series(ts, dtype=pl.Datetime("ms", "UTC")), "r": r})


def test_permutation_preserves_the_set_of_days_so_the_sum_is_invariant():
    rng = np.random.default_rng(0)
    daily = list(rng.normal(size=60))
    observed, null = permutation_max_drawdown(trades_from(daily), n_reps=500, seed=0)
    assert observed == pytest.approx(max_drawdown(np.array(daily)))
    assert np.all(null >= 0.0)
    assert len(null) == 500


def test_worst_ordering_has_the_largest_drawdown_in_the_distribution():
    """Wszystkie straty na początku = najgorsze możliwe ułożenie tych dni."""
    daily = [-1.0] * 20 + [1.0] * 20
    observed, null = permutation_max_drawdown(trades_from(daily), n_reps=800, seed=0)
    assert observed == pytest.approx(20.0)
    assert null.max() <= observed + 1e-9
    assert empirical_p_value(observed, null) < 0.05


def test_a_typical_ordering_is_not_surprising():
    rng = np.random.default_rng(3)
    daily = list(rng.normal(size=80))
    observed, null = permutation_max_drawdown(trades_from(daily), n_reps=800, seed=0)
    assert 0.05 < empirical_p_value(observed, null) < 0.95


def test_permutation_is_deterministic_in_the_seed():
    daily = list(np.random.default_rng(1).normal(size=40))
    _, a = permutation_max_drawdown(trades_from(daily), n_reps=200, seed=4)
    _, b = permutation_max_drawdown(trades_from(daily), n_reps=200, seed=4)
    _, c = permutation_max_drawdown(trades_from(daily), n_reps=200, seed=5)
    assert np.array_equal(a, b) and not np.array_equal(a, c)


def test_chunking_does_not_change_the_result():
    daily = list(np.random.default_rng(2).normal(size=50))
    _, a = permutation_max_drawdown(trades_from(daily), n_reps=300, seed=0, chunk=300)
    _, b = permutation_max_drawdown(trades_from(daily), n_reps=300, seed=0, chunk=7)
    assert np.array_equal(np.sort(a), np.sort(b))
