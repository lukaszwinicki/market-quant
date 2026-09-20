"""Kontrola #4 z §10.2 — „buy & hold / carry-only, musi zostać pobity".

Specyfikacja mieści tę kontrolę w jednym wierszu z ukośnikiem. ADR-044 czyta
ten ukośnik jako DWA ramiona o różnym statusie:

    4a  carry-only   ramię ROZSTRZYGAJĄCE
    4b  buy & hold   DIAGNOSTYKA, nie próg

RAMIĘ 4a — CARRY-ONLY

Konstrukcja identyczna z koszykiem §12 (`benchmark.py`): te same pięć walut
vs USD, te same pięć kotwic, ten sam moment rebalansu (fixing 16:00 Londyn,
ADR-043), ta sama jednostka R, ten sam rachunek kosztu i finansowania.
Jedyna różnica to wejście do rankingu: sam carry, bez zwrotu 3-miesięcznego.

To ABLACJA, nie inny benchmark. Ranking §12 jest zdominowany przez momentum
(ADR-039: człon zwrotu ma 4,2x większy rozrzut przekrojowy), więc pobicie
kontroli #5 mówi niewiele o tym, czy strategia bije carry. Dopiero ablacja to
mierzy — i ma przy tym ZERO parametrów swobodnych, bo znika nawet okno 63 dni.

Tydzień pomijany jest wedle tej samej reguły co w §12, łącznie z wymogiem
policzalnego momentum, którego carry-only nie używa. Celowo: oba ramiona mają
różnić się rankingiem, a nie próbą.

RAMIĘ 4b — BUY & HOLD

Long na każdej parze kohorty A, 1 R, wejście w pierwszym momencie rebalansu
okna, trzymane do końca. Raportowane per para i jako suma.

NIE jest progiem i NIE ma Sharpe'a. Dwa powody (ADR-044):

1. FX nie ma broniącego się kierunku pasywnego — long EURUSD jest równie
   arbitralny jak short, więc „przegrać z buy & hold" byłoby zdaniem o tym,
   w którą stronę poszedł dolar w tej próbie. Dlatego §10.2 czyni #9
   obowiązkowym na kohorcie B, gdzie dryf indeksów jest realny.
2. Każde R w projekcie jest przypisane do dnia WEJŚCIA (`daily_frames`).
   Jedna noga na parę wrzuca całe R w jeden dzień; jej Sharpe byłby
   artefaktem przypisania. Wycena dzienna dałaby z kolei serię gładką tam,
   gdzie strategia i koszyk są poszarpane — czyli faworyzowała benchmark.

4b realizuje zarazem §10.2 #9 dla kohorty A. Dla kohorty B #9 zostaje otwarte.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import polars as pl

from ..execution.simulator import CostModel
from .benchmark import (
    BenchmarkSpec, Comparison, _bar_at, _leg, compare, daily_series,
    mean_open_risk, rebalance_days, run_benchmark, usd_pairs,
)


@dataclass
class CarryOnly:
    """Ramię 4a — jedyne, które ma werdykt."""
    comparison: Comparison | None = None
    per_anchor: dict[int, float] = field(default_factory=dict)
    anchor_stats: list[dict] = field(default_factory=list)
    note: str = ""                      # dlaczego nie ma porównania

    @property
    def computed(self) -> bool:
        return self.comparison is not None

    @property
    def beaten(self) -> bool:
        """Pobity, gdy CI95 różnicy Sharpe'ów leży CAŁE powyżej zera."""
        return self.computed and self.comparison.ci_low > 0


@dataclass
class BuyAndHold:
    """Ramię 4b — diagnostyka. Bez werdyktu, bez Sharpe'a."""
    per_symbol: dict[str, float] = field(default_factory=dict)   # symbol → suma R
    trades: pl.DataFrame | None = None
    strategy_total_r: float = float("nan")

    @property
    def computed(self) -> bool:
        return bool(self.per_symbol)

    @property
    def total_r(self) -> float:
        """Suma równoważona: każda para po 1 R, więc zwykła suma."""
        return float(sum(self.per_symbol.values())) if self.per_symbol else 0.0


@dataclass
class Control4:
    carry_only: CarryOnly = field(default_factory=CarryOnly)
    buy_and_hold: BuyAndHold = field(default_factory=BuyAndHold)

    @property
    def computed(self) -> bool:
        return self.carry_only.computed


# --- 4a -----------------------------------------------------------------------

def run_carry_only(h1: dict[str, pl.DataFrame], rates: pl.DataFrame,
                   costs: dict[str, CostModel], symbols: list[str],
                   spec: BenchmarkSpec, start: dt.datetime, end: dt.datetime
                   ) -> tuple[dict[int, pl.DataFrame], list[dict]]:
    """Koszyk §12 z rankingiem po samym carry (ADR-044 pkt 4a).

    `spec` jest specyfikacją koszyka §12 — ablacja nakładana jest tutaj, żeby
    wołający nie mógł przez pomyłkę policzyć #4a na innych parametrach niż #5.
    """
    return run_benchmark(h1, rates, costs, symbols, spec.carry_only(), start, end)


def compare_carry_only(strategy_trades: pl.DataFrame,
                       per_anchor: dict[int, pl.DataFrame], *,
                       block_days: int, n_reps: int, seed: int
                       ) -> tuple[Comparison | None, str]:
    """(porównanie albo None, powód). Kryterium to samo co przy kontroli #5.

    Świadomie TA SAMA statystyka (ADR-040): dwie kontrole na dwóch skalach
    zapraszałyby do wybrania tej, która lepiej wypadnie.

    Zwraca None, gdy oś dzienna jest krótsza niż dwa bloki bootstrapu.
    Ranking po samym carry jest STABILNY — stopy zmieniają się raz na
    miesiąc — więc carry-only przebudowuje pozycje rzadko i na krótkim
    oknie potrafi nie mieć z czego próbkować. To właściwość tego ramienia,
    nie zła konfiguracja przebiegu, więc kończy się zapisanym brakiem
    liczby, a nie wyjątkiem. (Kontrola #5 zachowuje się inaczej celowo:
    tam za krótka oś znaczy, że za krótkie jest całe okno przebiegu.)
    """
    days, strat_daily, carry_daily = daily_series(strategy_trades, per_anchor)
    if len(days) < 2 * block_days:
        return None, (f"oś dzienna ma {len(days)} dni, a bootstrap blokowy "
                      f"potrzebuje co najmniej {2 * block_days}; ranking po "
                      f"samym carry jest stabilny, więc to ramię handluje "
                      f"rzadko")
    return compare(strat_daily, carry_daily, strategy_trades,
                   list(per_anchor.values()), block_days=block_days,
                   n_reps=n_reps, seed=seed), ""


# --- 4b -----------------------------------------------------------------------

def buy_and_hold_legs(h1: dict[str, pl.DataFrame], costs: dict[str, CostModel],
                      symbols: list[str], spec: BenchmarkSpec,
                      start: dt.datetime, end: dt.datetime) -> pl.DataFrame:
    """Jedna długa pozycja na parę, od pierwszego rebalansu do końca okna.

    Moment wejścia bierzemy z kalendarza rebalansów kotwicy poniedziałkowej,
    żeby buy & hold wchodził w tej samej konwencji czasowej co reszta
    (fixing 16:00 Londyn, ADR-043), a nie o dowolnej godzinie.

    Para bez bara w momencie wejścia albo bez bara na końcu okna jest
    POMIJANA i nie wchodzi do sumy — cicha noga o zerowym R udawałaby parę,
    która nic nie zarobiła.
    """
    days = rebalance_days(0, start, end)
    if not days:
        return pl.DataFrame()

    trades = []
    for sym in symbols:
        bars = h1.get(sym)
        if bars is None or not bars.height:
            continue
        entry = next((b for b in (_bar_at(bars, spec.moment_on(d)) for d in days)
                      if b is not None and b.get("atr_d1_14")), None)
        if entry is None:
            continue
        exit_bar = _bar_at(bars, end)
        if exit_bar is None or exit_bar["ts"] <= entry["ts"]:
            continue
        trades.append(_leg(sym, "long", entry, exit_bar, entry["atr_d1_14"],
                           costs[sym], spec))
    return pl.DataFrame(trades) if trades else pl.DataFrame()


def summarize_buy_and_hold(trades: pl.DataFrame, strategy_trades: pl.DataFrame
                           ) -> BuyAndHold:
    """Suma R per para obok sumarycznego R strategii. Bez werdyktu."""
    if not trades.height:
        return BuyAndHold()
    per = {row["symbol"]: float(row["r"])
           for row in trades.select("symbol", "r").iter_rows(named=True)}
    total = float(strategy_trades["r"].sum()) if strategy_trades.height else 0.0
    return BuyAndHold(per_symbol=per, trades=trades, strategy_total_r=total)


# --- raport -------------------------------------------------------------------

def render_section(c4: Control4) -> list[str]:
    """Sekcja raportu dla kontroli #4. Oba ramiona, z ich statusem."""
    lines = ["## Kontrola #4 — carry-only i buy & hold (§10.2, ADR-044)", ""]

    if not c4.carry_only.computed:
        why = f" Powód: {c4.carry_only.note}." if c4.carry_only.note else ""
        lines += ["Ramię 4a (carry-only) **nie zostało policzone** w tym "
                  f"przebiegu, więc werdykt bramki 2 jest niepełny (ADR-044).{why}",
                  ""]
        if c4.buy_and_hold.computed:
            lines += _buy_and_hold_lines(c4.buy_and_hold)
        return lines

    cmp_ = c4.carry_only.comparison
    verdict = "POBITY" if c4.carry_only.beaten else "NIE POBITY"
    lines += [
        f"### 4a — carry-only (ramię rozstrzygające)",
        "",
        f"Werdykt: **{verdict}** — ΔSharpe {cmp_.difference:+.4f}, "
        f"CI95 [{cmp_.ci_low:+.4f}, {cmp_.ci_high:+.4f}] "
        f"({cmp_.n_days} dni, {cmp_.n_reps} replikacji; te same bloki dla obu serii).",
        "",
        "| | Sharpe | średnie dzienne R | średnie otwarte ryzyko |",
        "|---|---|---|---|",
        f"| V1a | {cmp_.strategy_sharpe:+.4f} | {cmp_.strategy_mean_daily_r:+.4f} | "
        f"{cmp_.strategy_open_risk_r:.2f} R |",
        f"| carry-only | {cmp_.benchmark_sharpe:+.4f} | "
        f"{cmp_.benchmark_mean_daily_r:+.4f} | {cmp_.benchmark_open_risk_r:.2f} R |",
        "",
        "Ablacja koszyka §12: ta sama konstrukcja, ranking bez członu momentum "
        "(ADR-044). Ranking §12 jest zdominowany przez momentum — 4,2× większy "
        "rozrzut przekrojowy (ADR-039) — więc dopiero to ramię mierzy, czy "
        "strategia bije sam carry. Zero parametrów swobodnych.",
        "",
    ]

    if c4.carry_only.per_anchor:
        lines += ["| Kotwica | E[R] na transakcję | pominiętych tygodni |",
                  "|---|---|---|"]
        names = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek"]
        skipped = {s["anchor"]: s["n_skipped"] for s in c4.carry_only.anchor_stats}
        for a, er in sorted(c4.carry_only.per_anchor.items()):
            lines.append(f"| {names[a]} | {er:+.4f} | {skipped.get(a, '—')} |")
        lines.append("")

    lines += _buy_and_hold_lines(c4.buy_and_hold)
    return lines


def _buy_and_hold_lines(bh: BuyAndHold) -> list[str]:
    lines = ["### 4b — buy & hold (diagnostyka, NIE próg)", ""]
    if not bh.computed:
        return lines + ["Nie policzone.", ""]

    lines += ["| Para | suma R (long, całe okno) |", "|---|---|"]
    for sym, r in sorted(bh.per_symbol.items()):
        lines.append(f"| {sym} | {r:+.3f} |")
    lines += [
        f"| **razem** | **{bh.total_r:+.3f}** |",
        f"| *V1a, dla porównania* | *{bh.strategy_total_r:+.3f}* |",
        "",
        "**Bez werdyktu i bez Sharpe'a, celowo.** FX nie ma broniącego się "
        "kierunku pasywnego — long jest tak samo arbitralny jak short, więc "
        "poprzeczka zależałaby od tego, w którą stronę poszedł dolar w tej "
        "próbie. Dodatkowo jedna noga na parę wrzuca całe R w dzień wejścia, "
        "więc jej Sharpe byłby artefaktem przypisania (ADR-044). To ramię "
        "mierzy, ile z wyniku dałby sam statyczny dryf kierunkowy — tę samą "
        "kwestię, co kontrola #8, widzianą od zewnątrz.",
        "",
        "Realizuje §10.2 #9 („buy & hold per instrument”) dla kohorty A. "
        "Dla kohorty B #9 zostaje otwarte jako próg.",
        "",
    ]
    return lines
