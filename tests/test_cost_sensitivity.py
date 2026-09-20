"""Wynik przy 1×, 2× i 3× kosztach (SPEC §9).

Najważniejszy test w pliku: przy 1× przeliczenie musi dać DOKŁADNIE to `r`,
które zapisał symulator. Rozjazd w tym miejscu znaczy, że spread albo
poślizg liczy się dwa razy — to już raz się zdarzyło (ADR-024).
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import polars as pl
import pytest

from src.execution.simulator import CostModel, ExitReason, Side, simulate_trade
from src.validation.cost_sensitivity import (
    cost_ladder, render_markdown, repriced, scenario, survives_double_cost,
)

UTC = dt.timezone.utc
T0 = dt.datetime(2020, 1, 6, 0, tzinfo=UTC)
PIP = 1e-4


def labels(gross, cost, spread, slip) -> pl.DataFrame:
    n = len(gross)
    return pl.DataFrame({
        "gross_r": gross, "cost_r": cost, "spread_r": spread, "slip_r": slip,
        "r": [g - (c - s) for g, c, s in zip(gross, cost, spread)],
        "ts": pl.Series([T0 + dt.timedelta(days=i) for i in range(n)],
                        dtype=pl.Datetime("ms", "UTC")),
    })


def test_multiplier_one_reproduces_the_simulator_result_exactly():
    lab = labels(gross=[0.30, -1.00, 0.05], cost=[0.012, 0.012, 0.030],
                 spread=[0.004, 0.004, 0.030], slip=[0.002, 0.006, 0.002])
    assert np.allclose(repriced(lab, 1.0).to_numpy(), lab["r"].to_numpy())


def test_doubling_charges_the_whole_modelled_cost_once_more():
    lab = labels(gross=[0.50], cost=[0.020], spread=[0.005], slip=[0.003])
    # koszt modelowany = cost_r + slip_r = 0,023
    assert repriced(lab, 2.0)[0] == pytest.approx(lab["r"][0] - 0.023)
    assert repriced(lab, 3.0)[0] == pytest.approx(lab["r"][0] - 2 * 0.023)


def test_reported_cost_scales_with_the_multiplier():
    lab = labels(gross=[0.5, 0.5], cost=[0.02, 0.02], spread=[0.005, 0.005],
                 slip=[0.003, 0.003])
    one, two, three = cost_ladder(lab)
    assert one.total_cost_r == pytest.approx(0.023)
    assert two.total_cost_r == pytest.approx(0.046)
    assert three.total_cost_r == pytest.approx(0.069)


def test_expectancy_falls_monotonically_with_cost():
    lab = labels(gross=[0.4, -0.2, 0.1], cost=[0.02] * 3, spread=[0.005] * 3,
                 slip=[0.003] * 3)
    e = [s.expectancy for s in cost_ladder(lab)]
    assert e[0] > e[1] > e[2]


def test_edge_that_does_not_survive_doubling_is_flagged():
    """Expectancy 0,01 R przy koszcie 0,023 R nie przeżywa podwojenia."""
    lab = labels(gross=[0.025], cost=[0.020], spread=[0.005], slip=[0.003])
    assert scenario(lab, 1.0).positive
    assert not survives_double_cost(lab)


def test_edge_far_above_cost_survives_tripling():
    lab = labels(gross=[0.30], cost=[0.020], spread=[0.005], slip=[0.003])
    assert all(s.positive for s in cost_ladder(lab))


def test_missing_cost_components_are_rejected():
    lab = labels(gross=[0.1], cost=[0.01], spread=[0.004], slip=[0.001]).drop("slip_r")
    with pytest.raises(ValueError, match="slip_r"):
        repriced(lab, 2.0)


def test_non_positive_multiplier_is_rejected():
    lab = labels(gross=[0.1], cost=[0.01], spread=[0.004], slip=[0.001])
    with pytest.raises(ValueError, match="dodatni"):
        repriced(lab, 0.0)


def test_empty_labels_are_rejected():
    lab = labels(gross=[], cost=[], spread=[], slip=[])
    with pytest.raises(ValueError, match="brak etykiet"):
        cost_ladder(lab)


def test_markdown_lists_every_multiplier():
    lab = labels(gross=[0.3], cost=[0.02], spread=[0.005], slip=[0.003])
    md = render_markdown(cost_ladder(lab))
    assert "1×" in md and "2×" in md and "3×" in md


# --- zgodność z symulatorem, nie tylko z arytmetyką -------------------------

def bars(n: int, price: float, spread: float) -> pl.DataFrame:
    """Płaskie bary M1 — transakcja kończy się barierą czasową."""
    return pl.DataFrame({
        "ts": pl.Series([T0 + dt.timedelta(minutes=i) for i in range(n)],
                        dtype=pl.Datetime("ms", "UTC")),
        "bid_open": [price] * n, "bid_high": [price] * n,
        "bid_low": [price] * n, "bid_close": [price] * n,
        "ask_open": [price + spread] * n, "ask_high": [price + spread] * n,
        "ask_low": [price + spread] * n, "ask_close": [price + spread] * n,
        "spread_max": [spread] * n, "spread_close": [spread] * n,
        "n_ticks": [1] * n,
    })


def test_slippage_reported_by_the_simulator_matches_the_entry_rule():
    """Wyjście na barierze czasowej: poślizg tylko z wejścia."""
    m1 = bars(120, 1.1000, 2 * PIP)
    res = simulate_trade(Side.LONG, T0, 1.0900, 1.2000,
                         T0 + dt.timedelta(minutes=119),
                         m1, CostModel(pip=PIP, min_roundturn_pips=1.5))
    assert res.reason is ExitReason.TIME_BARRIER
    assert res.slippage == pytest.approx(0.5 * 2 * PIP)


def test_repricing_a_simulated_trade_at_one_times_cost_is_identity():
    m1 = bars(120, 1.1000, 2 * PIP)
    res = simulate_trade(Side.LONG, T0, 1.0900, 1.2000,
                         T0 + dt.timedelta(minutes=119),
                         m1, CostModel(pip=PIP, min_roundturn_pips=1.5))
    lab = pl.DataFrame({
        "gross_r": [res.gross / res.risk],
        "cost_r": [res.cost / res.risk],
        "spread_r": [0.5 * (res.entry.spread + res.exit.spread) / res.risk],
        "slip_r": [res.slippage / res.risk],
    })
    assert repriced(lab, 1.0)[0] == pytest.approx(res.r)
