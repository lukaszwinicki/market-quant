"""Kontrola losowa — benchmark nr 1 (PROJECT_SPEC §10.2 #1, ADR-013).

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

from typing import Callable

import numpy as np
import polars as pl

from ..data.resample import decision_time_for_bar

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
