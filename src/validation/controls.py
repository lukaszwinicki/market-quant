"""Kontrole obowiązkowe (PROJECT_SPEC §10.2). Tu: #1, #2, #3, #7.

    #1  random entry            rozkład zerowy — benchmark nr 1 (ADR-013)
    #2  shuffled labels         zrywa związek cecha → wynik
    #3  shifted features        cecha o bar starsza nie może POMAGAĆ
    #7  Monte Carlo permutacji  rozkład max DD przy tym samym zbiorze dni

Każda z nich pyta o co innego i żadna nie zastępuje pozostałych:

    #1  czy MOMENT wejścia niesie informację (nowe transakcje, nowy symulator)
    #2  czy przypisanie wyników do wejść jest lepsze niż losowe (te same wyniki)
    #3  czy wynik nie bierze się z off-by-one na osi czasu
    #7  czy zaobserwowany max DD jest zaskakujący dla TEJ serii dni

--- #1 ---------------------------------------------------------------------

Losowe momenty wejścia, IDENTYCZNE wyjście (te same bariery, horyzont,
symulator, koszty) i TA SAMA liczba transakcji co strategia — osobno dla
każdej pary (symbol, kierunek). Dopasowanie per kierunek jest celowe:
jeśli strategia jest w 80% długa na USDJPY, losowa też. Wtedy różnica
między nimi wynika z wyboru MOMENTU wejścia, a nie z dryfu kierunkowego
pary, który udawałby edge (kontrola #8).

Pod H₀ losowe wejścia dają expectancy ≈ −koszt (bramka 0). Rozkład
średnich R z wielu powtórzeń to rozkład zerowy dla bramek 1 i 2.

Wejścia losowe NIE respektują limitu jednej pozycji na parę. Dla średniej
R na transakcję nie ma to znaczenia (każda transakcja rozlicza się sama),
a próbkowanie z wykluczeniem zależałoby od wyników poprzednich wejść.
"""

from __future__ import annotations

from typing import Callable, Sequence

import numpy as np
import polars as pl

from ..data.resample import decision_time_for_bar
from ..labels.triple_barrier import MODELING_FEATURES
from .bootstrap import daily_totals

Counts = dict[tuple[str, str], int]
H1_SECONDS = 3600


def candidate_events(features: pl.DataFrame, symbol: str) -> pl.DataFrame:
    """Momenty decyzji, w których wejście jest w ogóle wykonalne.

    Wymagany znany `atr_d1_14` (bez niego nie ma barier). `ts` wyniku to
    moment decyzji — zamknięcie bara H1 — a nie etykieta bara.
    """
    ok = features.filter(pl.col("atr_d1_14").is_not_null() & (pl.col("atr_d1_14") > 0))
    return ok.select(
        pl.col("ts").map_elements(lambda t: decision_time_for_bar(t, H1_SECONDS),
                                  return_dtype=pl.Datetime("us", "UTC"))
        .cast(pl.Datetime("ms", "UTC")),
        pl.lit(symbol).alias("symbol"),
        pl.col("atr_d1_14"),
    )


def counts_from(trades: pl.DataFrame) -> Counts:
    """Liczba transakcji strategii per (symbol, kierunek)."""
    return {(s, d): n for s, d, n in
            trades.group_by("symbol", "side").len().iter_rows()}


def random_entries(candidates: pl.DataFrame, counts: Counts,
                   rng: np.random.Generator) -> pl.DataFrame:
    """Losuj wejścia bez zwracania, dokładnie `counts[(symbol, side)]` sztuk."""
    parts = []
    for (symbol, side), n in sorted(counts.items()):
        pool = candidates.filter(pl.col("symbol") == symbol)
        if n > pool.height:
            raise ValueError(f"{symbol}: {n} wejść, a tylko {pool.height} kandydatów")
        idx = rng.choice(pool.height, size=n, replace=False)
        parts.append(pool[np.sort(idx)].with_columns(pl.lit(side).alias("side")))
    if not parts:
        return candidates.clear().with_columns(pl.lit(None, pl.Utf8).alias("side"))
    return pl.concat(parts).sort("ts")


def random_control(candidates: pl.DataFrame, counts: Counts,
                   evaluate: Callable[[pl.DataFrame], pl.DataFrame],
                   n_reps: int, seed: int) -> np.ndarray:
    """Rozkład zerowy: średnie R z `n_reps` niezależnych losowań.

    `evaluate(events) -> labels` musi być tym samym etykietowaniem
    i symulatorem, którym oceniana jest strategia. Zdarzenia bez etykiety
    (NO_DATA) wypadają — średnia liczona z tego, co się rozstrzygnęło.
    """
    rng = np.random.default_rng(seed)
    out = np.empty(n_reps)
    for i in range(n_reps):
        lab = evaluate(random_entries(candidates, counts, rng))
        out[i] = lab["r"].mean() if lab.height else np.nan
    return out


def empirical_p_value(observed: float, null: np.ndarray) -> float:
    """P(null ≥ observed), z poprawką +1 (nigdy dokładnie zero)."""
    null = np.asarray(null, dtype=float)
    null = null[~np.isnan(null)]
    return float((1 + np.sum(null >= observed)) / (1 + len(null)))


# --- #2 shuffled labels -----------------------------------------------------
#
# Bierzemy WSZYSTKIE zdarzenia kandydujące wraz z ich rozstrzygniętymi
# wynikami i przetasowujemy przypisanie wynik → zdarzenie. Strategia wybiera
# ten sam podzbiór co zawsze, ale trafia już na losowo przypisane wyniki.
#
# CZEGO TO NIE MÓWI: rozkład zerowy NIE jest wyśrodkowany na zerze, tylko na
# średniej całej puli kandydatów. Jeżeli pula ma dryf (np. długie na parze,
# która rosła), ma go też ten rozkład — i dobrze, bo pytanie brzmi „czy WYBÓR
# jest lepszy niż losowy", a nie „czy wynik jest dodatni".
#
# Tasujemy WEWNĄTRZ grup (symbol, kierunek), nie w całej puli. Inaczej
# wymieszalibyśmy rozkłady zwrotów różnych par i różnych kierunków, a wtedy
# rozkład zerowy zawierałby dryf kierunkowy, który kontrola #8 ma wykrywać
# osobno. Ta sama zasada co w dopasowaniu liczebności w #1.


def _group_codes(labels: pl.DataFrame, by: Sequence[str]) -> np.ndarray:
    """Numer grupy dla każdego wiersza; [] = jedna grupa na wszystko."""
    cols = [c for c in by if c in labels.columns]
    if not cols:
        return np.zeros(labels.height, dtype=np.int64)
    keys = ["\x00".join(map(str, row)) for row in labels.select(cols).iter_rows()]
    codes = {k: i for i, k in enumerate(dict.fromkeys(keys))}
    return np.fromiter((codes[k] for k in keys), dtype=np.int64, count=len(keys))


def shuffled_label_null(labels: pl.DataFrame, selected: np.ndarray,
                        n_reps: int = 1000, seed: int = 0, value: str = "r",
                        by: Sequence[str] = ("symbol", "side")) -> np.ndarray:
    """Rozkład zerowy średniej `value` przy przetasowanych wynikach.

    `labels`   — wszystkie zdarzenia kandydujące, już z wynikiem
    `selected` — maska boolowska: które z nich wybrała strategia

    Zwraca `n_reps` średnich. Obserwowaną wartość porównuje się z nim
    przez `empirical_p_value`.
    """
    selected = np.asarray(selected, dtype=bool)
    if selected.shape != (labels.height,):
        raise ValueError(f"maska {selected.shape}, a etykiet {labels.height}")
    if not selected.any():
        raise ValueError("strategia nie wybrała żadnego zdarzenia")

    v = labels[value].to_numpy().astype(float)
    codes = _group_codes(labels, by)
    # Indeksy wierszy każdej grupy — permutujemy tylko w ich obrębie.
    groups = [np.flatnonzero(codes == g) for g in np.unique(codes)]

    rng = np.random.default_rng(seed)
    out = np.empty(n_reps)
    shuffled = v.copy()
    for i in range(n_reps):
        for idx in groups:
            shuffled[idx] = v[rng.permutation(idx)]
        out[i] = shuffled[selected].mean()
    return out


# --- #3 shifted features ----------------------------------------------------
#
# Cechę przesuwamy O BAR W PRZYSZŁOŚĆ: decyzja o 10:00 dostaje wartość
# policzoną dla bara wcześniejszego. To czyni ją STARSZĄ, nie świeższą.
#
# Kryterium (§10.2 #3): wynik NIE MOŻE ROSNĄĆ. Jeżeli strategia na starszych
# cechach radzi sobie lepiej, to „sygnał" nie jest tym, za co go uważamy —
# najczęściej dlatego, że gdzieś siedzi off-by-one i wersja bazowa czyta bar,
# który w momencie decyzji nie był jeszcze zamknięty.
#
# Przesuwamy wyłącznie cechy modelujące. `atr_d1_14` i `atr_h1_14` są
# normalizatorami barier (patrz nagłówek `labels/triple_barrier.py`) —
# przesunięcie ich zmieniłoby geometrię transakcji, a nie treść sygnału,
# i test mierzyłby co innego niż deklaruje.


def shift_features(features: pl.DataFrame, bars: int = 1,
                   columns: Sequence[str] | None = None) -> pl.DataFrame:
    """Przesuń cechy modelujące o `bars` barów w przyszłość (= robi je starsze).

    Wymaga ramki JEDNEGO symbolu, posortowanej po `ts`. Pierwsze `bars`
    wierszy dostaje null — tak jak przy rozgrzewce, więc dalszy kod
    odfiltruje je tą samą drogą co zwykle.
    """
    if bars < 1:
        raise ValueError("bars musi być >= 1")
    if not features["ts"].is_sorted():
        raise ValueError("cechy muszą być posortowane po ts")
    if "symbol" in features.columns and features["symbol"].n_unique() > 1:
        raise ValueError("przesunięcie działa na ramce jednego symbolu")

    cols = list(columns) if columns is not None else MODELING_FEATURES
    missing = [c for c in cols if c not in features.columns]
    if missing:
        raise ValueError(f"brak kolumn do przesunięcia: {missing}")
    return features.with_columns([pl.col(c).shift(bars) for c in cols])


# --- #7 Monte Carlo permutacji: rozkład max DD ------------------------------
#
# Permutujemy KOLEJNOŚĆ DNI, nie transakcji. Ten sam zbiór dziennych wyników
# ułożony inaczej daje inną krzywą kapitału — rozkład max DD z takich ułożeń
# mówi, czy zaobserwowane obsunięcie jest zaskakujące, czy jest zwykłą
# konsekwencją tego, jak wyglądają pojedyncze dni.
#
# Dzień jako jednostka jest wymuszony tą samą korelacją co w bootstrapie
# (§10.2 #6): transakcje z jednego dnia na sześciu parach nie są niezależne.
#
# Uwaga na kierunek testu: max DD jest tym gorszy, im WIĘKSZY. P-value liczymy
# więc dla „null >= observed" i interesuje nas duże p (obserwacja typowa),
# a nie małe.


def max_drawdown(daily: np.ndarray) -> float:
    """Największe obsunięcie skumulowanego R. Zawsze >= 0 (start liczy się)."""
    equity = np.cumsum(np.asarray(daily, dtype=float))
    peak = np.maximum.accumulate(np.concatenate(([0.0], equity)))[1:]
    return float(np.max(np.maximum(peak, 0.0) - equity, initial=0.0))


def permutation_max_drawdown(trades: pl.DataFrame, n_reps: int = 10_000,
                             seed: int = 0, value: str = "r",
                             chunk: int = 1000) -> tuple[float, np.ndarray]:
    """(max DD zaobserwowany, rozkład max DD z permutacji kolejności dni)."""
    sums, _ = daily_totals(trades, value)
    d = len(sums)
    if d < 2:
        raise ValueError("za mało dni na permutację")

    rng = np.random.default_rng(seed)
    null = np.empty(n_reps)
    for lo in range(0, n_reps, chunk):
        k = min(chunk, n_reps - lo)
        # argsort losowej macierzy = k niezależnych permutacji naraz
        perm = np.argsort(rng.random((k, d)), axis=1)
        equity = np.cumsum(sums[perm], axis=1)
        peak = np.maximum.accumulate(
            np.concatenate((np.zeros((k, 1)), equity), axis=1), axis=1)[:, 1:]
        null[lo:lo + k] = np.max(np.maximum(peak, 0.0) - equity, axis=1)
    return max_drawdown(sums), null
