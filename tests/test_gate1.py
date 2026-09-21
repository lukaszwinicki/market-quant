"""Testy bramki 1 na danych syntetycznych — tam, gdzie znamy poprawną odpowiedź."""
import datetime as dt

import numpy as np
import polars as pl
import pytest

from src.execution.simulator import CostModel
from src.validation.gate1 import (
    INCONCLUSIVE, MIN_NULL_REPS, PASS, STOP, assess, breakdown, rep_means,
    summarize_null,
)

UTC = dt.timezone.utc
T0 = dt.datetime(2020, 1, 6, tzinfo=UTC)       # poniedziałek
PIP = 1e-4
COST = CostModel(pip=PIP, min_roundturn_pips=1.5)
RISK = 50 * PIP
COST_R = COST.floor / RISK                     # 1,5 pipsa / 50 pipsów = 0,03 R


def control_labels(mean_r: float, n_days=200, per_day=6, reps=40, sd=0.5,
                   seed=0, financing_r: float | None = None) -> pl.DataFrame:
    """Etykiety kontroli losowej o ZADANEJ średniej R i znanym koszcie.

    Średnia jest przesuwana na dokładnie `mean_r`, więc werdykt nie zależy
    od tego, co akurat wylosuje generator. Powtórzenia są przeplatane po
    wierszach, czyli każde obejmuje całą oś dni — tak jak w prawdziwej
    kontroli, gdzie każde losowanie chodzi po całym zakresie.
    """
    rng = np.random.default_rng(seed)
    days = [T0 + dt.timedelta(days=d) for d in range(n_days * 7 // 5 + 7)]
    days = [d for d in days if d.weekday() < 5][:n_days]
    ts = [d + dt.timedelta(hours=h) for d in days for h in range(per_day)]
    n = len(ts)
    r = rng.standard_normal(n) * sd
    r = r - r.mean() + mean_r
    out = pl.DataFrame({
        "ts": pl.Series(ts, dtype=pl.Datetime("ms", "UTC")),
        "symbol": ["EURUSD", "USDJPY"] * (n // 2),
        "side": (["long"] * 2 + ["short"] * 2) * (n // 4),
        "rep": [i % reps for i in range(n)],
        "r": r,
        "cost_r": np.full(n, COST_R),
        "y": (r > 0).astype(int),
    })
    if financing_r is not None:
        out = out.with_columns(pl.lit(financing_r).alias("financing_r"))
    return out


def check(res, prefix):
    return next(c for c in res.checks if c.name.startswith(prefix))


# --- rozkład zerowy ----------------------------------------------------------

def test_rep_means_are_the_per_repetition_means():
    lab = control_labels(-0.01, n_days=20, per_day=4, reps=5)
    means = rep_means(lab)
    assert len(means) == 5
    manual = [lab.filter(pl.col("rep") == i)["r"].mean() for i in range(5)]
    assert means == pytest.approx(manual)


def test_labels_without_rep_are_not_a_random_control():
    lab = control_labels(-0.01, n_days=20, per_day=4).drop("rep")
    with pytest.raises(ValueError, match="rep"):
        rep_means(lab)


def test_null_summary_counts_positive_repetitions():
    s = summarize_null(np.array([-0.2, -0.1, 0.0, 0.1]), n_trades=400)
    assert s.n_reps == 4 and s.positive_share == 0.25
    assert s.median == pytest.approx(-0.05)
    assert s.trades_per_rep == 100


def test_null_from_a_single_repetition_has_no_spread():
    s = summarize_null(np.array([-0.01]), n_trades=100)
    assert s.sd == 0.0 and not s.usable


# --- werdykt (ADR-046) --------------------------------------------------------

def test_random_control_losing_the_cost_passes():
    res = assess(control_labels(-COST_R), block_days=20, n_boot=2000, seed=0)
    assert res.verdict == PASS and res.passed
    assert res.net.expectancy == pytest.approx(-COST_R)
    assert res.mean_cost_r == pytest.approx(COST_R)


def test_significantly_positive_random_control_is_a_stop():
    """Losowe wejścia zarabiają istotnie — mierzymy nie to, co myślimy."""
    res = assess(control_labels(+0.10), block_days=20, n_boot=2000, seed=0)
    assert res.net.ci_low > 0
    assert res.verdict == STOP and not res.passed
    assert not check(res, "dodatni").passed


def test_slightly_positive_but_noisy_control_is_inconclusive_not_a_pass():
    """Średnia nad zerem mieści się w szumie: ani przejście, ani koniec projektu."""
    res = assess(control_labels(+0.005), block_days=20, n_boot=2000, seed=0)
    assert res.net.expectancy > 0 >= res.net.ci_low
    assert res.verdict == INCONCLUSIVE and not res.passed
    assert not check(res, "kontrola losowa nie zarabia").passed
    assert check(res, "dodatni").passed        # to NIE jest STOP


def test_too_few_repetitions_is_not_a_benchmark():
    """Ujemna średnia nie wystarcza: bez rozkładu bramka nie ma produktu."""
    res = assess(control_labels(-COST_R, reps=MIN_NULL_REPS - 1),
                 block_days=20, n_boot=2000, seed=0)
    assert res.net.expectancy < 0
    assert not check(res, "rozkład zerowy").passed
    assert res.verdict == INCONCLUSIVE and not res.passed


def test_verdict_is_computed_after_financing():
    """Swap jest kierunkowy i wchodzi przed statystyką (ADR-035).

    Ta sama kontrola przed finansowaniem zarabia istotnie, po nim traci —
    werdykt musi pochodzić z `r` już pomniejszonego o swap.
    """
    before = control_labels(+0.05)
    after = before.with_columns(pl.lit(0.08).alias("financing_r")).with_columns(
        (pl.col("r") - pl.col("financing_r")).alias("r"))

    assert assess(before, 20, 2000, 0).verdict == STOP
    res = assess(after, 20, 2000, 0)
    assert res.verdict == PASS
    assert res.mean_financing_r == pytest.approx(0.08)
    assert res.net.expectancy == pytest.approx(0.05 - 0.08)


# --- rozbicie ------------------------------------------------------------------

def test_breakdown_covers_every_pair_and_side():
    b = breakdown(control_labels(-0.01, financing_r=0.002))
    assert b.height == 4
    assert set(b["symbol"]) == {"EURUSD", "USDJPY"}
    assert b["n"].sum() == 1200
    assert b["mean_financing_r"].to_list() == pytest.approx([0.002] * 4)


def test_breakdown_works_without_financing_column():
    b = breakdown(control_labels(-0.01))
    assert b["mean_financing_r"].to_list() == pytest.approx([0.0] * 4)
