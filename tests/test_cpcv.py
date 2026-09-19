"""Testy CPCV z purge/embargo.

Wszystko na syntetycznych etykietach, gdzie wiadomo, która obserwacja
przecieka do testu. Na prawdziwych danych widać tylko, że coś się zwraca.
"""
import datetime as dt

import numpy as np
import polars as pl
import pytest

from src.labels.triple_barrier import add_business_days
from src.validation.cpcv import (
    CPCVSpec, assign_groups, backtest_paths, cpcv_splits,
)

UTC = dt.timezone.utc
D0 = dt.datetime(2020, 1, 6, 10, tzinfo=UTC)     # poniedziałek


def business_days(n: int, start=D0) -> list[dt.datetime]:
    return [add_business_days(start, i) for i in range(n)]


def labels(ts: list[dt.datetime], t1: list[dt.datetime] | None = None,
           symbol: list[str] | None = None) -> pl.DataFrame:
    t1 = t1 if t1 is not None else [t + dt.timedelta(hours=1) for t in ts]
    return pl.DataFrame({
        "ts": pl.Series(ts, dtype=pl.Datetime("ms", "UTC")),
        "t1": pl.Series(t1, dtype=pl.Datetime("ms", "UTC")),
        "symbol": symbol or ["EURUSD"] * len(ts),
    })


def split_for(splits, test_groups):
    return next(s for s in splits if s.test_groups == test_groups)


# --- Kombinatoryka ----------------------------------------------------------

def test_six_groups_two_test_give_15_splits_and_5_paths():
    spec = CPCVSpec()
    assert spec.n_splits == 15
    assert spec.n_paths == 5
    lab = labels(business_days(120))
    assert len(cpcv_splits(lab, spec)) == 15


def test_each_path_covers_every_group_exactly_once():
    spec = CPCVSpec()
    combos = [s.test_groups for s in cpcv_splits(labels(business_days(120)), spec)]
    paths = backtest_paths(spec)
    assert len(paths) == 5
    used = set()
    for path in paths:
        assert len(path) == spec.n_groups
        for g, split_i in enumerate(path):
            assert g in combos[split_i], "ścieżka bierze grupę z podziału, w którym nie jest testowa"
            used.add((g, split_i))
    # każda para (grupa, podział testowy) użyta dokładnie raz
    assert len(used) == spec.n_splits * spec.n_test_groups


def test_invalid_spec_is_rejected():
    with pytest.raises(ValueError):
        CPCVSpec(n_groups=6, n_test_groups=6)
    with pytest.raises(ValueError):
        CPCVSpec(purge_business_days=-1)


# --- Grupy: całe dni, wszystkie pary razem ----------------------------------

def test_groups_are_contiguous_and_never_split_a_day():
    ts = [d + dt.timedelta(hours=h) for d in business_days(60) for h in (0, 5, 10)]
    g = assign_groups(pl.Series(ts, dtype=pl.Datetime("ms", "UTC")), 6)
    assert (np.diff(g) >= 0).all(), "grupy nie są ciągłe w czasie"
    by_day = {}
    for t, gi in zip(ts, g):
        by_day.setdefault(t.date(), set()).add(gi)
    assert all(len(v) == 1 for v in by_day.values()), "dzień rozcięty między grupy"


def test_all_pairs_from_same_day_land_in_same_group():
    days = business_days(60)
    ts = [d for d in days for _ in range(3)]
    sym = ["EURUSD", "USDJPY", "EURJPY"] * len(days)
    lab = labels(ts, symbol=sym)
    g = assign_groups(lab["ts"], 6)
    for i in range(0, len(ts), 3):
        assert g[i] == g[i + 1] == g[i + 2]


def test_too_few_days_is_rejected():
    with pytest.raises(ValueError):
        assign_groups(pl.Series(business_days(4), dtype=pl.Datetime("ms", "UTC")), 6)


# --- Rozłączność i kompletność ---------------------------------------------

def test_train_test_purged_embargoed_partition_the_sample():
    lab = labels(business_days(120))
    for s in cpcv_splits(lab):
        parts = [s.train_idx, s.test_idx, s.purged_idx, s.embargoed_idx]
        joined = np.concatenate(parts)
        assert len(joined) == len(set(joined.tolist())), "zbiory nie są rozłączne"
        assert set(joined.tolist()) == set(range(lab.height))


def test_no_training_label_overlaps_any_test_label_window():
    """Właściwość, dla której CPCV istnieje: przy długich, nakładających się
    etykietach żadna obserwacja treningowa nie może dzielić okna wynikowego
    z obserwacją testową."""
    ts = [d + dt.timedelta(hours=h) for d in business_days(150) for h in (0, 6)]
    t1 = [add_business_days(t, 10) for t in ts]
    lab = labels(ts, t1)
    ts_a, t1_a = lab["ts"].to_numpy(), lab["t1"].to_numpy()
    for s in cpcv_splits(lab):
        assert len(s.train_idx) > 0
        for i in s.train_idx:
            overlap = (ts_a[s.test_idx] <= t1_a[i]) & (t1_a[s.test_idx] >= ts_a[i])
            assert not overlap.any(), f"trening {i} nakłada się na test w {s.test_groups}"


# --- Purge: znane przypadki przecieku --------------------------------------

def _grid_with_probe(probe_ts, probe_t1):
    """120 dni roboczych z krótkimi etykietami + jedna sonda."""
    ts = business_days(120)
    lab = labels(ts + [probe_ts], [t + dt.timedelta(hours=1) for t in ts] + [probe_t1])
    return lab, lab.height - 1


def test_label_resolving_inside_test_group_is_purged():
    days = business_days(120)
    g = assign_groups(labels(days)["ts"], 6)
    first_g2 = days[int(np.argmax(g == 2))]
    probe = add_business_days(first_g2, -3)
    lab, i = _grid_with_probe(probe, add_business_days(first_g2, 2))
    s = split_for(cpcv_splits(lab), (2, 4))
    assert i in s.purged_idx
    assert i not in s.train_idx


def test_label_starting_just_before_test_is_purged_even_if_resolved_early():
    """Podłoga purge: 10 dni roboczych przed grupą testową, niezależnie od t1."""
    days = business_days(120)
    g = assign_groups(labels(days)["ts"], 6)
    first_g3 = days[int(np.argmax(g == 3))]
    probe = add_business_days(first_g3, -8)
    lab, i = _grid_with_probe(probe, probe + dt.timedelta(hours=1))
    s = split_for(cpcv_splits(lab), (0, 3))
    assert i in s.purged_idx


def test_label_far_before_test_stays_in_training():
    days = business_days(120)
    g = assign_groups(labels(days)["ts"], 6)
    first_g3 = days[int(np.argmax(g == 3))]
    probe = add_business_days(first_g3, -15)
    lab, i = _grid_with_probe(probe, probe + dt.timedelta(hours=1))
    s = split_for(cpcv_splits(lab), (0, 3))
    assert i in s.train_idx


def test_test_period_extends_to_latest_test_t1():
    """Grupa testowa kończy się dniem X, ale jej ostatnia etykieta
    rozstrzyga się 7 dni później. Obserwacja treningowa z dnia X+3 leży
    wewnątrz okna wynikowego testu — musi zniknąć, i to jako purge."""
    days = business_days(120)
    g = assign_groups(labels(days)["ts"], 6)
    last_g1 = days[int(np.flatnonzero(g == 1).max())]
    t1 = [t + dt.timedelta(hours=1) for t in days]
    t1[days.index(last_g1)] = add_business_days(last_g1, 7)
    probe = add_business_days(last_g1, 3)
    lab = labels(days + [probe], t1 + [probe + dt.timedelta(hours=1)])
    i = lab.height - 1
    s = split_for(cpcv_splits(lab), (1, 4))
    assert i in s.purged_idx


# --- Embargo ----------------------------------------------------------------

def test_label_shortly_after_test_is_embargoed():
    days = business_days(120)
    g = assign_groups(labels(days)["ts"], 6)
    last_g1 = days[int(np.flatnonzero(g == 1).max())]
    probe = add_business_days(last_g1, 3)
    lab, i = _grid_with_probe(probe, probe + dt.timedelta(hours=1))
    s = split_for(cpcv_splits(lab), (1, 4))
    assert i in s.embargoed_idx


def test_label_after_embargo_stays_in_training():
    days = business_days(120)
    g = assign_groups(labels(days)["ts"], 6)
    last_g1 = days[int(np.flatnonzero(g == 1).max())]
    probe = add_business_days(last_g1, 7)
    lab, i = _grid_with_probe(probe, probe + dt.timedelta(hours=1))
    s = split_for(cpcv_splits(lab), (1, 4))
    assert i in s.train_idx


def test_zero_purge_and_embargo_keeps_non_overlapping_neighbours():
    """Kontrola samego testu: bez purge/embargo i bez nakładania trening
    obejmuje wszystko poza testem."""
    lab = labels(business_days(120))
    spec = CPCVSpec(purge_business_days=0, embargo_business_days=0)
    for s in cpcv_splits(lab, spec):
        assert len(s.train_idx) + len(s.test_idx) == lab.height


# --- Walidacja wejścia ------------------------------------------------------

def test_t1_before_ts_is_rejected():
    ts = business_days(30)
    t1 = [t - dt.timedelta(hours=1) for t in ts]
    with pytest.raises(ValueError):
        cpcv_splits(labels(ts, t1))


def test_input_row_order_is_preserved_in_indices():
    """Indeksy odnoszą się do wierszy wejścia, nie do posortowanej kopii."""
    lab = labels(business_days(120))
    shuffled = lab.sample(fraction=1.0, shuffle=True, seed=1)
    a = cpcv_splits(lab)
    b = cpcv_splits(shuffled)
    for sa, sb in zip(a, b):
        ts_a = set(lab["ts"].gather(sa.test_idx).to_list())
        ts_b = set(shuffled["ts"].gather(sb.test_idx).to_list())
        assert ts_a == ts_b
