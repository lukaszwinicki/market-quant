"""Bramka 0 — test negatywny infrastruktury (PROJECT_SPEC §15, config `gates.gate_0`).

Losowe wejścia, zrównoważone long/short per para, identyczne wyjście jak
strategia. Pod H₀ taka „strategia" nie ma przewagi, więc:

    E[R]            ≈ −E[koszt_R]
    E[R + koszt_R]  ≈ 0           (wynik brutto — przed kosztem)

Test sprawdza drugą równość: przedział bootstrapowy wyniku brutto musi
zawierać zero. Dodatnie brutto na losowych wejściach oznacza, że symulator
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
równość została potwierdzona. Dlatego stosowanie podłogi kosztu jest
sprawdzane wprost, transakcja po transakcji, a nie przez średnią.

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
        return pl.DataFrame(rows) if rows else pl.DataFrame()

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

def floor_violations(labels: pl.DataFrame, costs: dict[str, CostModel]) -> pl.DataFrame:
    """Transakcje, których efektywny koszt jest poniżej podłogi (ADR-024).

    koszt = cost_r × ryzyko, ryzyko = |fill wejścia − SL| — ten sam
    mianownik, którym symulator liczy R.
    """
    floors = pl.DataFrame({"symbol": list(costs),
                           "floor": [c.floor for c in costs.values()]})
    return (
        labels.join(floors, on="symbol", how="left")
        .with_columns((pl.col("cost_r") * (pl.col("entry_price") - pl.col("sl")).abs())
                      .alias("cost_px"))
        .filter(pl.col("floor").is_null()
                | (pl.col("cost_px") < pl.col("floor") * (1 - 1e-9)))
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
    gross: BootstrapResult           # R + koszt_R: pod H₀ zero
    net: BootstrapResult             # R: pod H₀ −koszt
    mean_cost_r: float
    resolution: float                # połowa CI brutto / średni koszt
    breakdown: pl.DataFrame          # per (symbol, kierunek)
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)


def breakdown(labels: pl.DataFrame) -> pl.DataFrame:
    return (
        labels.with_columns((pl.col("r") + pl.col("cost_r")).alias("gross_r"))
        .group_by("symbol", "side")
        .agg(pl.len().alias("n"),
             pl.col("r").mean().alias("mean_r"),
             pl.col("cost_r").mean().alias("mean_cost_r"),
             pl.col("gross_r").mean().alias("mean_gross_r"),
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
    lab = labels.with_columns((pl.col("r") + pl.col("cost_r")).alias("gross_r"))
    gross = block_bootstrap_expectancy(lab, block_days, n_boot, seed, value="gross_r")
    net = block_bootstrap_expectancy(lab, block_days, n_boot, seed, value="r")
    mean_cost = float(lab["cost_r"].mean())
    half = (gross.ci_high - gross.ci_low) / 2

    checks = [
        Check("losowe wejścia: brutto ≈ 0 (E[R] ≈ −koszt)",
              gross.ci_low <= 0.0 <= gross.ci_high,
              f"brutto {gross.expectancy:+.4f} R, CI95 [{gross.ci_low:+.4f}, "
              f"{gross.ci_high:+.4f}]; netto {net.expectancy:+.4f} R vs "
              f"−koszt {-mean_cost:+.4f} R"),
    ]

    bad = floor_violations(lab, costs)
    checks.append(Check(
        "podłoga min_roundturn_cost_pips stosowana",
        bad.is_empty(),
        f"{bad.height} z {lab.height} transakcji poniżej podłogi"))

    wrong = [f"{s}: {p['distinct']} różnych wartości, {p['negative']} < 0, "
             f"{p['crossed_bars']} barów ask_low < bid_low"
             for s, p in spreads.items()
             if p["distinct"] < MIN_DISTINCT_SPREADS or p["negative"] or p["crossed_bars"]]
    checks.append(Check(
        "spread z ticków bid/ask (nie średni, nie mid)",
        not wrong,
        "; ".join(wrong) if wrong else
        "wszystkie pary: spread nieujemny i zmienny, ask ≥ bid"))

    return Gate0Result(gross=gross, net=net, mean_cost_r=mean_cost,
                       resolution=half / mean_cost if mean_cost > 0 else float("inf"),
                       breakdown=breakdown(lab), checks=checks)
