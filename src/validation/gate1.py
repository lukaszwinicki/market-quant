"""Bramka 1 — rozkład zerowy z kontroli losowej (PROJECT_SPEC §15, ADR-013).

Kryterium bramki brzmi: **STOP, jeśli kontrola losowa daje dodatnie
expectancy**. Produktem bramki nie jest jednak sam werdykt, tylko ROZKŁAD
ZEROWY: rozrzut średnich R z wielu niezależnych losowań. Bez niego wynik
strategii jest liczbą bez skali (ADR-013).

CZYM TO SIĘ RÓŻNI OD BRAMKI 0

Bramka 0 pyta o SYMULATOR: czy wynik PRZED kosztem jest zerowy (ADR-025 c).
Bramka 1 pyta o wynik NETTO tej samej kontroli — czyli o to, czy losowe
wejścia po kosztach i po finansowaniu nie zarabiają. Ten sam przebieg
odpowiadałby na oba pytania, ale dają one różne werdykty: dodatnie brutto
oznacza wyciek z przyszłości, dodatnie netto oznacza dodatkowo, że
„strategia" bez żadnej informacji zarabia — czyli mierzymy nie to, co
myślimy.

FINANSOWANIE JEST W ŚRODKU

Rozkład zerowy musi żyć w tym samym świecie kosztów co wynik, z którym go
porównujemy (tak samo jak kontrola #1 w `strategy/runner.py`). Swap jest
kierunkowy, więc musi wejść przed jakąkolwiek statystyką (ADR-035).
`r` przed finansowaniem zostaje odtwarzalne jako `r + financing_r`, więc
raport pokazuje obie liczby bez drugiego liczenia.

TRZY STANY WERDYKTU (ADR-046)

    STOP              dolny koniec CI95 netto > 0 — kontrola zarabia istotnie
    NIEROZSTRZYGNIĘTE średnia ≥ 0, ale CI95 zawiera 0 — za mało danych
    PRZECHODZI        średnia < 0 i CI95 nie leży w całości powyżej zera

Stan środkowy istnieje, bo przy koszcie ~0,01 R i szumie ~0,01 R sama
losowość wyrzuca punktową średnią nad zero w kilkunastu procentach
przypadków (ADR-025, „MOC TESTU"). Automatyczny STOP kończyłby wtedy
projekt na podstawie szumu, a automatyczne przejście chowałoby prawdziwy
błąd symulatora. Rozstrzygnięcie stanu środkowego jest decyzją człowieka,
nie skryptu.

CZEGO TEN ROZKŁAD NIE JEST

Nie jest rozkładem zerowym bramki 2. Rozrzut średnich skaluje się jak
1/√(liczba transakcji w powtórzeniu), a bramka 2 porównuje strategię
z kontrolą o TEJ SAMEJ liczbie transakcji co strategia (§10.2 #1) —
tę liczbę zna dopiero przebieg V1a i liczy ją sam (`run_controls`).
Tutaj liczebność jest deklarowana z góry i zrównoważona kierunkowo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

from .bootstrap import BootstrapResult, block_bootstrap_expectancy
from .gate0 import Check

# Rozkład z kilku powtórzeń nie ma ogonów, a p-value ma ziarnistość
# 1/(1 + liczba powtórzeń). Poniżej tego progu „rozkład zerowy" jest nazwą
# na kilka liczb.
MIN_NULL_REPS = 30

PASS = "PRZECHODZI"
INCONCLUSIVE = "NIEROZSTRZYGNIĘTE"
STOP = "STOP"


def rep_means(labels: pl.DataFrame, value: str = "r") -> np.ndarray:
    """Średnia `value` w każdym powtórzeniu kontroli — to jest rozkład zerowy.

    Wymaga kolumny `rep` z `run_random_control`. Powtórzenia bez ani jednej
    rozstrzygniętej transakcji nie istnieją w ramce i nie ma ich w wyniku.
    """
    if "rep" not in labels.columns:
        raise ValueError("etykiety bez kolumny `rep` — to nie jest kontrola losowa")
    return (labels.group_by("rep").agg(pl.col(value).mean().alias("m"))
            .sort("rep")["m"].to_numpy())


@dataclass
class NullSummary:
    n_reps: int
    trades_per_rep: float
    mean: float
    sd: float
    q025: float
    median: float
    q975: float
    positive_share: float      # udział powtórzeń ze średnią > 0

    @property
    def usable(self) -> bool:
        return self.n_reps >= MIN_NULL_REPS and self.sd > 0


def summarize_null(means: np.ndarray, n_trades: int) -> NullSummary:
    m = np.asarray(means, dtype=float)
    m = m[~np.isnan(m)]
    if m.size == 0:
        raise ValueError("pusty rozkład zerowy")
    lo, med, hi = np.percentile(m, [2.5, 50, 97.5])
    return NullSummary(
        n_reps=int(m.size), trades_per_rep=n_trades / m.size,
        mean=float(m.mean()), sd=float(m.std(ddof=1)) if m.size > 1 else 0.0,
        q025=float(lo), median=float(med), q975=float(hi),
        positive_share=float((m > 0).mean()),
    )


def breakdown(labels: pl.DataFrame) -> pl.DataFrame:
    """Per (para, kierunek): średnie R, koszt, finansowanie, trafienia.

    Informacyjnie — wiersze są silnie autokorelowane (okna się nakładają),
    a kryterium bramki dotyczy całej próby.
    """
    fin = (pl.col("financing_r") if "financing_r" in labels.columns
           else pl.lit(0.0)).alias("financing_r")
    return (
        labels.with_columns(fin)
        .group_by("symbol", "side")
        .agg(pl.len().alias("n"),
             pl.col("r").mean().alias("mean_r"),
             pl.col("cost_r").mean().alias("mean_cost_r"),
             pl.col("financing_r").mean().alias("mean_financing_r"),
             pl.col("y").mean().alias("hit_rate"))
        .sort("symbol", "side")
    )


@dataclass
class Gate1Result:
    net: BootstrapResult             # R po koszcie i po finansowaniu
    null: NullSummary
    mean_cost_r: float
    mean_financing_r: float
    verdict: str
    breakdown: pl.DataFrame
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.verdict == PASS


def assess(labels: pl.DataFrame, block_days: int, n_boot: int,
           seed: int) -> Gate1Result:
    """Kryterium bramki 1 na etykietach kontroli losowej (po finansowaniu).

    `labels` to wynik `run_random_control` z kolumną `rep`, przepuszczony
    przez `apply_financing`. Bootstrap blokowy liczy CI dla całej próby
    (dzień jako blok — §10.2 #6), a `rep_means` daje rozkład zerowy.
    """
    net = block_bootstrap_expectancy(labels, block_days, n_boot, seed, value="r")
    null = summarize_null(rep_means(labels), labels.height)
    mean_cost = float(labels["cost_r"].mean())
    mean_fin = (float(labels["financing_r"].mean())
                if "financing_r" in labels.columns else 0.0)

    stop = net.ci_low > 0
    negative = net.expectancy < 0
    checks = [
        Check("kontrola losowa nie zarabia: E[R] netto < 0",
              negative,
              f"netto {net.expectancy:+.4f} R, koszt {mean_cost:.4f} R, "
              f"finansowanie {mean_fin:+.4f} R (dodatnie = koszt)"),
        Check("dodatni wynik nie jest istotny: dolny koniec CI95 ≤ 0",
              not stop,
              f"CI95 [{net.ci_low:+.4f}, {net.ci_high:+.4f}], SE {net.se:.4f}, "
              f"{net.n_trades} transakcji w {net.n_days} dniach"),
        Check(f"rozkład zerowy nadaje się na benchmark: ≥ {MIN_NULL_REPS} "
              "powtórzeń, niezerowy rozrzut",
              null.usable,
              f"{null.n_reps} powtórzeń, SD {null.sd:.4f} R, "
              f"{null.trades_per_rep:.0f} transakcji na powtórzenie"),
    ]

    verdict = STOP if stop else PASS if all(c.passed for c in checks) else INCONCLUSIVE
    return Gate1Result(net=net, null=null, mean_cost_r=mean_cost,
                       mean_financing_r=mean_fin, verdict=verdict,
                       breakdown=breakdown(labels), checks=checks)
