"""Sześć cech technicznych z PROJECT_SPEC §6. Nic więcej.

DWIE ROZŁĄCZNE SKALE ZMIENNOŚCI (ADR-023) — mylenie ich degeneruje etykiety:

    atr_h1_14   WYŁĄCZNIE normalizacja cech
    atr_d1_14   WYŁĄCZNIE skalowanie barier i sizingu

KAUZALNOŚĆ

Cecha w barze T korzysta wyłącznie z barów <= T. Wszystkie statystyki
normalizujące liczone w oknie ROZSZERZAJĄCYM, nigdy na pełnej próbie.
Pilnuje tego `test_features_are_causal`: policzenie cech na dłuższej serii
nie może zmienić ani jednej wcześniejszej wartości.

Najgroźniejsze miejsce to `vol_pct_252`. Liczy się z ATR dziennego, więc
w barze o 10:00 dnia D **nie wolno** użyć ATR dnia D — ten dzień jeszcze
się nie skończył. Używamy ostatniego ZAMKNIĘTEGO dnia.

LICZENIE W BARACH, NIE W GODZINACH ZEGAROWYCH

`close[-24]` to 24 bary wstecz, nie 24 godziny kalendarzowe. Przez weekend
te dwie rzeczy się rozjeżdżają. Wersja barowa jest właściwa: oznacza stałą
porcję aktywności rynku, a nie stały odstęp zegarowy, w którym rynek mógł
stać. Przy ~120 godzinach handlu tygodniowo `mom_480` obejmuje ~4 tygodnie,
czyli ~20 dni handlowych, zgodnie ze specyfikacją.

CENA REFERENCYJNA

Wszystkie cechy liczone na BID. Konsekwentnie jedna strona rynku — cena
mid nie występuje nigdzie w systemie. Dla kierunku rynku wybór strony jest
bez znaczenia, bo spread wchodzi do wyniku dopiero przez symulator fillów.
"""

from __future__ import annotations

import numpy as np
import polars as pl

ATR_PERIOD = 14
MOM_LOOKBACKS = (24, 120, 480)
DONCHIAN = 55
VOL_PCT_MIN_DAYS = 252

FEATURE_COLUMNS = [
    "atr_h1_14", "mom_24", "mom_120", "mom_480", "donch_pos_55",
    "atr_d1_14", "vol_pct_252",
]


def true_range(high: pl.Expr, low: pl.Expr, close: pl.Expr) -> pl.Expr:
    """TR = max(H-L, |H-C_prev|, |L-C_prev|). Pierwszy bar: H-L."""
    prev = close.shift(1)
    return pl.max_horizontal(
        high - low,
        (high - prev).abs(),
        (low - prev).abs(),
    ).fill_null(high - low)


def atr(df: pl.DataFrame, period: int, prefix: str = "bid") -> pl.Series:
    """ATR jako prosta średnia krocząca z TR.

    Świadomie NIE wygładzanie Wildera: jedna konwencja mniej do uzgadniania,
    a różnica jest kosmetyczna wobec niepewności całej reszty.
    """
    tr = df.select(
        true_range(pl.col(f"{prefix}_high"), pl.col(f"{prefix}_low"),
                   pl.col(f"{prefix}_close")).alias("tr")
    )["tr"]
    return tr.rolling_mean(window_size=period, min_samples=period)


def daily_bars(h1: pl.DataFrame) -> pl.DataFrame:
    """Bary D1 z H1. Granica dnia: 00:00 UTC (config: data.d1_boundary)."""
    return (
        h1.sort("ts")
        .group_by_dynamic("ts", every="1d", closed="left", label="left")
        .agg(
            pl.col("bid_high").max(),
            pl.col("bid_low").min(),
            pl.col("bid_close").last(),
        )
        .sort("ts")
    )


def expanding_percentile_rank(values: pl.Series, min_periods: int) -> pl.Series:
    """Ranga percentylowa w oknie rozszerzającym, wyłącznie z przeszłości.

    Dla pozycji i: udział wartości z [0..i] nie większych od values[i].
    Pierwsze `min_periods` pozycji to null — nie ma z czego rangować.

    Implementacja jest O(n^2), ale n to liczba DNI (rzędu 2600 dla 10 lat),
    więc to ułamek sekundy. Wersja szybsza (drzewo indeksowane) byłaby
    trudniejsza do zweryfikowania, a to jest miejsce, w którym cicha pomyłka
    oznacza look-ahead.
    """
    v = values.to_numpy()
    out = np.full(len(v), np.nan)
    for i in range(len(v)):
        if i + 1 < min_periods or np.isnan(v[i]):
            continue
        past = v[: i + 1]
        past = past[~np.isnan(past)]
        if len(past) < min_periods:
            continue
        out[i] = float((past <= v[i]).sum()) / len(past)
    # NaN -> null. W polars to RÓŻNE rzeczy: drop_nulls() nie usuwa NaN-ów,
    # więc NaN przeszedłby przez filtrowanie i zatruł model po cichu.
    return pl.Series("vol_pct_252", out).fill_nan(None)


def compute_features(h1: pl.DataFrame, donchian: int = DONCHIAN) -> pl.DataFrame:
    """Dolicz sześć cech do barów H1. Wejście musi być posortowane po ts.

    `donchian` — okres kanału (parametr swobodny V1a, siatka ADR-028).
    Kolumna nazywa się `donch_pos_{donchian}`, żeby wariant był widoczny
    w nazwie i nie dało się pomylić cech z różnych przebiegów.
    """
    if h1.is_empty():
        names = [f"donch_pos_{donchian}" if c == "donch_pos_55" else c
                 for c in FEATURE_COLUMNS]
        return h1.with_columns([pl.lit(None, pl.Float64).alias(c) for c in names])

    df = h1.sort("ts")
    a_h1 = atr(df, ATR_PERIOD)
    df = df.with_columns(a_h1.alias("atr_h1_14"))

    # Momentum znormalizowane zmiennością WŁASNEGO horyzontu.
    # Bez czynnika sqrt(n) trzy cechy różnią się skalą o ~sqrt(20),
    # mają nieporównywalne rozkłady i psują regularyzację L2.
    df = df.with_columns([
        (
            (pl.col("bid_close") - pl.col("bid_close").shift(n))
            / (pl.col("atr_h1_14") * np.sqrt(n))
        ).alias(f"mom_{n}")
        for n in MOM_LOOKBACKS
    ])

    lo = pl.col("bid_low").rolling_min(donchian, min_samples=donchian)
    hi = pl.col("bid_high").rolling_max(donchian, min_samples=donchian)
    df = df.with_columns(
        pl.when(hi > lo)
        .then((pl.col("bid_close") - lo) / (hi - lo))
        .otherwise(None)                      # zakres zerowy: cecha nieokreślona
        .alias(f"donch_pos_{donchian}")
    )

    return _attach_daily_volatility(df)


def _attach_daily_volatility(h1: pl.DataFrame) -> pl.DataFrame:
    """Dolicz atr_d1_14 i vol_pct_252 z OSTATNIEGO ZAMKNIĘTEGO dnia.

    W barze o 10:00 dnia D wartości dnia D jeszcze nie znamy — dzień się
    nie skończył. Stąd shift(1) na serii dziennej przed złączeniem.
    """
    d1 = daily_bars(h1)
    if d1.height < 2:
        return h1.with_columns(
            pl.lit(None, pl.Float64).alias("atr_d1_14"),
            pl.lit(None, pl.Float64).alias("vol_pct_252"),
        )

    a_d1 = atr(d1, ATR_PERIOD)
    d1 = d1.with_columns(a_d1.alias("atr_d1_14"))
    d1 = d1.with_columns(
        expanding_percentile_rank(d1["atr_d1_14"], VOL_PCT_MIN_DAYS)
    )

    # shift(1): wartości stają się dostępne dopiero NAZAJUTRZ
    available = d1.select(
        (pl.col("ts") + pl.duration(days=1)).alias("day"),
        pl.col("atr_d1_14"),
        pl.col("vol_pct_252"),
    )

    return (
        h1.with_columns(pl.col("ts").dt.truncate("1d").alias("day"))
        .join(available, on="day", how="left")
        .drop("day")
        .sort("ts")
    )
