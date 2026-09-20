"""Wynik przy 1×, 2× i 3× kosztach — raportowanie obowiązkowe (SPEC §9).

PO CO

Edge, który znika przy podwojeniu kosztów, nie jest edge'em: jest resztą
po modelu kosztów. Próg z §10.3 („expectancy > 0 przy 2× kosztach") jest
w spec-u osobną pozycją obok samego expectancy i musi być raportowany
przy KAŻDYM wyniku, nie tylko na bramce 2.

RACHUNEK

Etykieta niesie trzy składniki w jednostkach R (`labels/triple_barrier.py`):

    gross_r    wynik z cen fillów — spread i poślizg SĄ już w nim zawarte
    cost_r     max(spread_r, podłoga_R) — spread albo podłoga detaliczna
    spread_r   spread implikowany z cen fillów
    slip_r     poślizg zawarty w cenach fillów

Modelowany koszt całkowity przy 1× to `cost_r + slip_r`. W `gross_r` siedzi
już `spread_r + slip_r`. Przy mnożniku k obciążamy więc wynik różnicą:

    r(k) = gross_r − [ k·(cost_r + slip_r) − (spread_r + slip_r) ]

Dla k = 1 daje to `gross_r − (cost_r − spread_r)`, czyli dokładnie `r`
zapisane przez symulator — i to jest sprawdzane testem, bo pomyłka w tym
miejscu raz już się zdarzyła (spread liczony dwa razy, ADR-024).

CZEGO MNOŻNIK NIE OBEJMUJE

Finansowania (swap). Jest liczone osobno, od liczby dni trzymania, i ma
własny mnożnik — patrz `execution/financing.py`. Mnożenie go razem ze
spreadem sugerowałoby, że oba rosną z tego samego powodu; nie rosną.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

REQUIRED = ("gross_r", "cost_r", "spread_r", "slip_r")


@dataclass(frozen=True)
class CostScenario:
    multiplier: float
    expectancy: float        # średnie R na transakcję
    total_cost_r: float      # średni modelowany koszt w R
    n_trades: int
    positive: bool


def repriced(labels: pl.DataFrame, multiplier: float) -> pl.Series:
    """Kolumna `r` przeliczona przy `multiplier`× kosztach."""
    if multiplier <= 0:
        raise ValueError("mnożnik kosztu musi być dodatni")
    missing = [c for c in REQUIRED if c not in labels.columns]
    if missing:
        raise ValueError(f"etykiety bez składników kosztu: {missing}")
    modelled = pl.col("cost_r") + pl.col("slip_r")
    embedded = pl.col("spread_r") + pl.col("slip_r")
    return labels.select(
        (pl.col("gross_r") - (multiplier * modelled - embedded)).alias("r")
    )["r"]


def scenario(labels: pl.DataFrame, multiplier: float) -> CostScenario:
    r = repriced(labels, multiplier)
    mean = float(r.mean())
    cost = float((labels["cost_r"] + labels["slip_r"]).mean()) * multiplier
    return CostScenario(multiplier=multiplier, expectancy=mean, total_cost_r=cost,
                        n_trades=labels.height, positive=mean > 0)


def cost_ladder(labels: pl.DataFrame,
                multipliers: tuple[float, ...] = (1.0, 2.0, 3.0)
                ) -> list[CostScenario]:
    """Scenariusze dla mnożników z `costs.sensitivity_multipliers`."""
    if labels.is_empty():
        raise ValueError("brak etykiet")
    return [scenario(labels, m) for m in multipliers]


def survives_double_cost(labels: pl.DataFrame) -> bool:
    """Próg z §10.3: expectancy dodatnie przy 2× kosztach."""
    return scenario(labels, 2.0).positive


def render_markdown(ladder: list[CostScenario]) -> str:
    """Tabela do raportu przebiegu."""
    rows = "\n".join(
        f"| {s.multiplier:g}× | {s.expectancy:+.4f} | {s.total_cost_r:.4f} | "
        f"{'tak' if s.positive else 'NIE'} |" for s in ladder)
    return ("| Koszt | E[R] | modelowany koszt (R) | dodatnie |\n"
            "|---|---|---|---|\n" + rows)
