"""Bramka 0 — test negatywny infrastruktury (PROJECT_SPEC §15, config `gates.gate_0`).

Losowe wejścia, zrównoważone long/short per para, identyczne wyjście jak
strategia. Pod H₀ taka „strategia" nie ma przewagi, więc:

    E[R]            ≈ −E[koszt_R]
    E[R + koszt_R]  ≈ 0           (wynik brutto — przed kosztem)

Kryterium według ADR-025, trzy części:

    a. rachunek kosztu per transakcja — `cost_accounting_violations`
    b. test martyngałowy na syntetyku — uruchamiany przez skrypt
    c. CI95 wyniku przed kosztem ∋ 0 ORAZ połowa CI ≤ 0,05 R

Część c sprawdza drugą równość powyżej. Dodatnie brutto na losowych wejściach oznacza, że symulator
widzi przyszłość albo kolejność barier jest rozstrzygana na korzyść.
Ujemne — że koszt jest pobierany gdzieś jeszcze poza `cost` (np. drugi raz
w cenach fillów).

Poślizg siedzi w cenach fillów, a nie w `cost`, więc pod H₀ brutto wynosi
dokładnie −poślizg/ryzyko: ~0,005 R, o rząd wielkości poniżej szumu.

MOC TESTU

Przy barierach 2×/4× ATR dziennego koszt to ~0,01 R, a szum średniej R
z kilku lat danych jest rzędu ±0,05 R. Na prawdziwych danych test
„E[R] ≈ −koszt" NIE odróżni więc kosztu policzonego od pominiętego —
do tego służy test martyngałowy na syntetyku
(`tests/test_controls.py`), gdzie odpowiedź jest znana. Tu mierzymy tę
rozdzielczość jawnie (`resolution`) i raportujemy, zamiast udawać, że
równość została potwierdzona. Dlatego rachunek kosztu jest sprawdzany
wprost, transakcja po transakcji, a nie przez średnią.

ZRÓWNOWAŻENIE KIERUNKÓW

Tyle samo wejść long i short na każdej parze: dryf pary (EURUSD 2015 −10%)
znosi się w średniej zamiast udawać zysk albo stratę systemu.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import polars as pl

from ..execution.simulator import CostModel
from ..labels.triple_barrier import LabelSpec, add_business_days, label_events
from .bootstrap import BootstrapResult, block_bootstrap_expectancy
from .controls import Counts, candidate_events, random_entries

# ADR-025 c: szerszy CI to „nierozstrzygnięte", nie „przechodzi".
# Połowa progu bramki 2 (0,10 R).
MAX_HALF_CI_R = 0.05
# Tolerancja numeryczna tożsamości kosztu (w R).
ACCOUNTING_TOL_R = 1e-9
# Przerwa w danych dłuższa niż weekend ze świętem: koniec ciągłego pokrycia.
MAX_CONTIGUOUS_GAP = dt.timedelta(days=5)
# Spread „z ticków" ma rozkład, nie jedną wartość. Kilka różnych wartości
# oznacza spread stały albo uśredniony — zakazany (`use_average_spread`).
MIN_DISTINCT_SPREADS = 20


def label_spec_from(cfg: dict) -> LabelSpec:
    lab = cfg["labels"]
    return LabelSpec(sl_multiple=lab["sl_multiple"], tp_multiple=lab["tp_multiple"],
                     horizon_business_days=lab["time_barrier_business_days"])


def contiguous_end(bars: pl.DataFrame, start: dt.datetime) -> dt.datetime | None:
    """Ostatni bar przed pierwszą przerwą > 5 dni po `start`.

    Cache zawiera wyrywkowe lata (próbki z testów dekodera). Cechy liczone
    przez wieloletnią dziurę byłyby śmieciem, więc test kończy się tam,
    gdzie kończą się dane ciągłe.
    """
    ts = bars.filter(pl.col("ts") >= start)["ts"]
    if ts.is_empty():
        return None
    gaps = ts.diff() > MAX_CONTIGUOUS_GAP
    if not gaps.any():
        return ts[-1]
    return ts[int(gaps.arg_true()[0]) - 1]


def eligible_candidates(features: pl.DataFrame, symbol: str, start: dt.datetime,
                        end: dt.datetime, spec: LabelSpec) -> pl.DataFrame:
    """Momenty decyzji w [start, end], których CAŁY horyzont mieści się przed `end`.

    Transakcja ucięta przez koniec danych dałaby NO_DATA i wypadła — ale
    selektywnie (tylko te z końca próby), więc filtrujemy z góry.
    """
    c = candidate_events(features, symbol).filter(pl.col("ts") >= start)
    horizon_end = c["ts"].map_elements(
        lambda t: add_business_days(t, spec.horizon_business_days),
        return_dtype=pl.Datetime("us", "UTC"))
    return c.filter(horizon_end <= end)


def balanced_counts(symbols: list[str], n_per_side: int) -> Counts:
    return {(s, side): n_per_side for s in symbols for side in ("long", "short")}


def make_evaluator(m1: dict[str, pl.DataFrame], costs: dict[str, CostModel],
                   spec: LabelSpec) -> Callable[[pl.DataFrame], pl.DataFrame]:
    """`evaluate(events) -> labels` dla wielu par, z pamięcią wyników.

    Etykieta jest deterministyczna w (symbol, moment, kierunek), a
    powtórzenia losują z tej samej puli kandydatów — ta sama transakcja
    wraca wielokrotnie. Pamięć nie zmienia wyniku, tylko czas.
    """
    memo: dict[tuple[str, dt.datetime, str], dict | None] = {}
    # Kolejność kolumn wyniku. `label_events` przepisuje kolumny ZDARZENIA,
    # a strategia podaje je jako (ts, symbol, side, atr_d1_14), kontrola zaś
    # jako (ts, atr_d1_14, symbol, side). Memo jest dzielone między nimi, więc
    # bez tego kolejność kolumn zależałaby od tego, kto pierwszy trafił do
    # memo — a `pl.concat` powtórzeń kontroli porównuje kolejność, nie nazwy.
    order: list[str] = []

    def evaluate(events: pl.DataFrame) -> pl.DataFrame:
        rows = []
        for ev in events.iter_rows(named=True):
            key = (ev["symbol"], ev["ts"], ev["side"])
            if key not in memo:
                lab = label_events(pl.DataFrame([ev], schema=events.schema),
                                   m1[ev["symbol"]], costs[ev["symbol"]], spec)
                memo[key] = lab.row(0, named=True) if lab.height else None
            if memo[key] is not None:
                rows.append(memo[key])
        if not rows:
            return pl.DataFrame()
        if not order:
            order.extend(rows[0])
        expected = set(order)
        for r in rows:
            if r.keys() != expected:
                # Różny ZBIÓR kolumn to inne zdarzenia, nie inna kolejność.
                # Cicha projekcja gubiłaby kolumny, więc błąd jest głośny.
                raise ValueError(
                    "etykiety z różnymi kolumnami w jednym evaluate: "
                    f"{sorted(expected)} vs {sorted(r)}")
        return pl.DataFrame([{c: r[c] for c in order} for r in rows])

    evaluate.memo = memo      # do diagnostyki: ile unikalnych transakcji
    return evaluate


def run_random_control(candidates: pl.DataFrame, counts: Counts,
                       evaluate: Callable[[pl.DataFrame], pl.DataFrame],
                       n_reps: int, seed: int,
                       progress: Callable[[int, pl.DataFrame], None] | None = None,
                       ) -> pl.DataFrame:
    """Jak `controls.random_control`, ale zwraca wszystkie transakcje z kolumną `rep`.

    Ten sam strumień losowy co `random_control(seed=...)` — średnie per
    `rep` są identyczne.
    """
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n_reps):
        lab = evaluate(random_entries(candidates, counts, rng))
        if lab.height:
            out.append(lab.with_columns(pl.lit(i).alias("rep")))
        if progress:
            progress(i, lab)
    return pl.concat(out, how="vertical_relaxed") if out else pl.DataFrame()


# --- ocena ------------------------------------------------------------------

def cost_accounting_violations(labels: pl.DataFrame,
                               costs: dict[str, CostModel]) -> pl.DataFrame:
    """Transakcje łamiące rachunek kosztu (ADR-024, ADR-025 a).

        cost_r = max(spread_r, podłoga / ryzyko)
        r      = gross_r − (cost_r − spread_r)     — spread tylko raz

    ryzyko = |fill wejścia − SL| — ten sam mianownik, którym symulator
    liczy R. Symbol bez modelu kosztów też jest naruszeniem.
    """
    floors = pl.DataFrame({"symbol": list(costs),
                           "floor": [c.floor for c in costs.values()]})
    floor_r = pl.col("floor") / (pl.col("entry_price") - pl.col("sl")).abs()
    tol = ACCOUNTING_TOL_R
    return (
        labels.join(floors, on="symbol", how="left")
        .filter(
            pl.col("floor").is_null()
            | ((pl.col("cost_r") - pl.max_horizontal("spread_r", floor_r)).abs() > tol)
            | ((pl.col("r") - (pl.col("gross_r") - pl.col("cost_r") + pl.col("spread_r")))
               .abs() > tol)
        )
    )


def spread_profile(m1: pl.DataFrame, pip: float) -> dict:
    """Czy spread pochodzi z ticków: nieujemny, zmienny, bez wartości stałej."""
    s = m1["spread_close"]
    return {
        "bars": m1.height,
        "min_pips": float(s.min()) / pip,
        "median_pips": float(s.median()) / pip,
        "p99_pips": float(s.quantile(0.99)) / pip,
        "distinct": s.n_unique(),
        "zero_share": float((s == 0).mean()),     # rynek „zablokowany" — bywa realny
        "negative": int((s < 0).sum()),
        "crossed_bars": int((m1["ask_low"] < m1["bid_low"]).sum()),
    }


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


@dataclass
class Gate0Result:
    pre_cost: BootstrapResult        # R + koszt_R: pod H₀ zero
    net: BootstrapResult             # R: pod H₀ −koszt
    mean_cost_r: float
    half_ci: float                   # połowa CI95 wyniku przed kosztem
    resolution: float                # half_ci / średni koszt
    breakdown: pl.DataFrame          # per (symbol, kierunek)
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)


def breakdown(labels: pl.DataFrame) -> pl.DataFrame:
    return (
        labels.with_columns((pl.col("r") + pl.col("cost_r")).alias("pre_cost_r"))
        .group_by("symbol", "side")
        .agg(pl.len().alias("n"),
             pl.col("r").mean().alias("mean_r"),
             pl.col("cost_r").mean().alias("mean_cost_r"),
             pl.col("pre_cost_r").mean().alias("mean_pre_cost_r"),
             pl.col("y").mean().alias("hit_rate"),
             (pl.col("reason").is_in(["gap_sl", "gap_tp"])).mean().alias("gap_share"))
        .sort("symbol", "side")
    )


def assess(labels: pl.DataFrame, costs: dict[str, CostModel],
           spreads: dict[str, dict], block_days: int, n_boot: int,
           seed: int) -> Gate0Result:
    """Kryteria bramki 0 dotyczące symulatora i kosztów.

    Luki w danych (drugie kryterium bramki) ocenia raport jakości —
    patrz `QualityReport.passes_gate_0`, dołączany przez skrypt.
    """
    lab = labels.with_columns((pl.col("r") + pl.col("cost_r")).alias("pre_cost_r"))
    pre = block_bootstrap_expectancy(lab, block_days, n_boot, seed, value="pre_cost_r")
    net = block_bootstrap_expectancy(lab, block_days, n_boot, seed, value="r")
    mean_cost = float(lab["cost_r"].mean())
    half = (pre.ci_high - pre.ci_low) / 2

    bad = cost_accounting_violations(lab, costs)
    checks = [Check(
        "a. rachunek kosztu per transakcja (podłoga, spread raz)",
        bad.is_empty(),
        f"{bad.height} z {lab.height} transakcji łamie cost = max(spread, podłoga) "
        "lub r = gross − dopłata")]

    covers = pre.ci_low <= 0.0 <= pre.ci_high
    narrow = half <= MAX_HALF_CI_R
    verdict = ("" if covers and narrow else
               " — NIEROZSTRZYGNIĘTE: CI za szeroki, potrzeba więcej danych" if covers else
               " — bias wyniku przed kosztem")
    checks.append(Check(
        f"c. losowe wejścia: CI95 przed kosztem ∋ 0, połowa CI ≤ {MAX_HALF_CI_R} R",
        covers and narrow,
        f"przed kosztem {pre.expectancy:+.4f} R, CI95 [{pre.ci_low:+.4f}, "
        f"{pre.ci_high:+.4f}], połowa {half:.4f} R; netto {net.expectancy:+.4f} R "
        f"vs −koszt {-mean_cost:+.4f} R{verdict}"))

    wrong = [f"{s}: {p['distinct']} różnych wartości, {p['negative']} < 0, "
             f"{p['crossed_bars']} barów ask_low < bid_low"
             for s, p in spreads.items()
             if p["distinct"] < MIN_DISTINCT_SPREADS or p["negative"] or p["crossed_bars"]]
    checks.append(Check(
        "spread z ticków bid/ask (nie średni, nie mid)",
        not wrong,
        "; ".join(wrong) if wrong else
        "wszystkie pary: spread nieujemny i zmienny, ask ≥ bid"))

    return Gate0Result(pre_cost=pre, net=net, mean_cost_r=mean_cost, half_ci=half,
                       resolution=half / mean_cost if mean_cost > 0 else float("inf"),
                       breakdown=breakdown(lab), checks=checks)
