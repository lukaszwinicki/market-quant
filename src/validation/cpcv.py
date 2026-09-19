"""Combinatorial Purged Cross-Validation (PROJECT_SPEC §10.1, ADR-008).

GRUPY

Oś czasu dzielona jest na `n_groups` ciągłych bloków CAŁYCH DNI (UTC),
wspólnych dla wszystkich par. Dzień nigdy nie trafia do dwóch grup, a
transakcje z różnych par z tego samego dnia zawsze lądują razem — inaczej
EURUSD w treningu i EURJPY w teście z tego samego dnia przeciekałyby przez
wspólny czynnik EUR.

Każda kombinacja `n_test_groups` z `n_groups` grup to jeden podział
trening/test. Dla 6/2 daje to C(6,2) = 15 podziałów, które składają się
w C(5,1) = 5 pełnych ścieżek backtestu (każda grupa testowana dokładnie
raz na ścieżkę).

PURGE

Etykieta ze znacznikiem `ts` rozstrzyga się w `t1`. Obserwacja treningowa,
której przedział [ts, t1] zachodzi na okres testowy, zna fragment wyniku
testu — jest usuwana. To kryterium dokładne. Dodatkowo, jako podłoga,
usuwamy każdą obserwację treningową z `ts` w ciągu `purge_business_days`
przed początkiem grupy testowej (= maksymalny horyzont etykiety): chroni to
przed etykietą z błędnym `t1`, a kosztuje kilka procent próby.

Okres testowy grupy kończy się nie na jej ostatnim dniu, lecz na
najpóźniejszym `t1` jej obserwacji — do tego momentu wyniki testu są
jeszcze nieznane.

EMBARGO

Po końcu okresu testowego przez `embargo_business_days` obserwacje
treningowe są usuwane. Powód: cechy liczone na oknach wstecznych (mom_480
to 20 dni) tuż po teście są funkcją cen z okresu testowego, więc model
uczony na nich widzi test pośrednio.
"""

from __future__ import annotations

import datetime as dt
import itertools
from dataclasses import dataclass
from math import comb

import numpy as np
import polars as pl

from ..labels.triple_barrier import add_business_days


@dataclass(frozen=True)
class CPCVSpec:
    n_groups: int = 6
    n_test_groups: int = 2
    purge_business_days: int = 10
    embargo_business_days: int = 5

    def __post_init__(self):
        if not 0 < self.n_test_groups < self.n_groups:
            raise ValueError("wymagane 0 < n_test_groups < n_groups")
        if self.purge_business_days < 0 or self.embargo_business_days < 0:
            raise ValueError("purge i embargo nie mogą być ujemne")

    @property
    def n_splits(self) -> int:
        return comb(self.n_groups, self.n_test_groups)

    @property
    def n_paths(self) -> int:
        return comb(self.n_groups - 1, self.n_test_groups - 1)


@dataclass(frozen=True)
class CPCVSplit:
    test_groups: tuple[int, ...]
    train_idx: np.ndarray        # indeksy wierszy wejściowej ramki
    test_idx: np.ndarray
    purged_idx: np.ndarray       # usunięte z treningu przez nakładanie etykiet
    embargoed_idx: np.ndarray    # usunięte z treningu przez embargo


def assign_groups(ts: pl.Series, n_groups: int) -> np.ndarray:
    """Numer grupy (0..n_groups-1) dla każdego wiersza, blokami całych dni."""
    days = ts.dt.date()
    unique_days = days.unique().sort()
    if unique_days.len() < n_groups:
        raise ValueError(f"{unique_days.len()} dni to za mało na {n_groups} grup")
    chunks = np.array_split(np.arange(unique_days.len()), n_groups)
    day_to_group = {}
    for g, chunk in enumerate(chunks):
        for i in chunk:
            day_to_group[unique_days[int(i)]] = g
    return np.array([day_to_group[d] for d in days], dtype=np.int64)


def cpcv_splits(labels: pl.DataFrame, spec: CPCVSpec = CPCVSpec()) -> list[CPCVSplit]:
    """Wszystkie podziały CPCV dla etykiet z kolumnami `ts` i `t1`.

    Indeksy odnoszą się do kolejności wierszy w `labels` (nie sortujemy).
    """
    if labels.select((pl.col("t1") < pl.col("ts")).any()).item():
        raise ValueError("t1 < ts — etykieta rozstrzygnięta przed decyzją")

    ts = labels["ts"].to_numpy()
    t1 = labels["t1"].to_numpy()
    groups = assign_groups(labels["ts"], spec.n_groups)
    bounds = _group_bounds(labels["ts"], groups, spec.n_groups)

    splits = []
    for test_groups in itertools.combinations(range(spec.n_groups), spec.n_test_groups):
        is_test = np.isin(groups, test_groups)
        purged = np.zeros(len(ts), dtype=bool)
        embargoed = np.zeros(len(ts), dtype=bool)

        for g in test_groups:
            g_start, g_end = bounds[g]
            in_g = groups == g
            span_end = max(g_end, t1[in_g].max()) if in_g.any() else g_end

            overlaps = (ts <= span_end) & (t1 >= g_start)
            floor_start = _np_dt(add_business_days(_py_dt(g_start), -spec.purge_business_days))
            before = (ts >= floor_start) & (ts < g_start)
            purged |= overlaps | before

            emb_end = _np_dt(add_business_days(_py_dt(span_end), spec.embargo_business_days))
            embargoed |= (ts > span_end) & (ts <= emb_end)

        purged &= ~is_test
        embargoed &= ~is_test & ~purged
        is_train = ~is_test & ~purged & ~embargoed

        splits.append(CPCVSplit(
            test_groups=test_groups,
            train_idx=np.flatnonzero(is_train),
            test_idx=np.flatnonzero(is_test),
            purged_idx=np.flatnonzero(purged),
            embargoed_idx=np.flatnonzero(embargoed),
        ))
    return splits


def backtest_paths(spec: CPCVSpec = CPCVSpec()) -> list[list[int]]:
    """Ścieżki backtestu: path[g] = indeks podziału, z którego bierzemy grupę g.

    Grupa g jest testowa w `n_paths` podziałach; j-ta ścieżka bierze j-te
    z nich. Każda ścieżka pokrywa całą oś czasu dokładnie raz.
    """
    combos = list(itertools.combinations(range(spec.n_groups), spec.n_test_groups))
    per_group = [[i for i, c in enumerate(combos) if g in c] for g in range(spec.n_groups)]
    return [[per_group[g][j] for g in range(spec.n_groups)] for j in range(spec.n_paths)]


def _group_bounds(ts: pl.Series, groups: np.ndarray, n_groups: int
                  ) -> list[tuple[np.datetime64, np.datetime64]]:
    """[początek pierwszego dnia, koniec ostatniego dnia) dla każdej grupy."""
    days = ts.dt.date().to_numpy()
    out = []
    for g in range(n_groups):
        d = days[groups == g]
        start = np.datetime64(d.min(), "ms")
        end = np.datetime64(d.max(), "ms") + np.timedelta64(1, "D") - np.timedelta64(1, "ms")
        out.append((start, end))
    return out


def _py_dt(x: np.datetime64) -> dt.datetime:
    return dt.datetime.fromtimestamp(x.astype("datetime64[ms]").astype(np.int64) / 1000,
                                     tz=dt.timezone.utc)


def _np_dt(x: dt.datetime) -> np.datetime64:
    return np.datetime64(x.replace(tzinfo=None), "ms")
