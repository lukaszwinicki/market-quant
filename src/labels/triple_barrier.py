"""Etykietowanie metodą triple barrier (PROJECT_SPEC §7, ADR-008).

    y = 1  TP trafione przed SL
    y = 0  SL trafione pierwsze ALBO bariera czasowa (konserwatywnie)

`t1` — NAJWAŻNIEJSZE POLE

Każda etykieta niesie moment, w którym została ROZSTRZYGNIĘTA. Bez tego
purging jest niewykonalny, a purging jest przy tym targecie obowiązkowy,
nie opcjonalny.

Powód: transakcja o 10:00 i o 11:00, obie z horyzontem 10 dni, dzielą
niemal całe okno wynikowe. Ich etykiety są silnie skorelowane. Zwykły
k-fold na takich danych daje wyniki zawyżone o rząd wielkości, bo fold
treningowy zawiera obserwacje, których wynik rozstrzyga się wewnątrz
foldu testowego.

Zmierzyliśmy to empirycznie: 1152 losowe transakcje w miesiącu danych
dały ~5 nienakładających się okien pięciodniowych. Iluzja dużej próby
jest tu bardzo silna.

SPLĄTANIE ETYKIETY Z CECHĄ

Bariery są w jednostkach `atr_d1_14`. Gdyby ATR był jednocześnie cechą
predykcyjną, model mógłby nauczyć się geometrii barier zamiast sygnału:
prawdopodobieństwo trafienia bariery zależy od `bariera/sigma`, więc obie
strony równania zawierałyby tę samą wielkość.

Dlatego `atr_d1_14` i `atr_h1_14` są normalizatorami, NIE cechami.
Pilnuje tego `MODELING_FEATURES` i test `test_atr_is_not_a_modeling_feature`.

BAZOWE PRAWDOPODOBIEŃSTWA

Przy RR 1:2 pod błądzeniem losowym P(TP pierwsze) ~ 1/3, a próg opłacalności
z kosztami to ~0.35. Model musi stabilnie bić 0.35, nie "mieć accuracy 60%".
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import polars as pl

from ..data.resample import slice_window
from ..execution.simulator import (
    CostModel, ExitReason, Side, TradeResult, simulate_trade,
)

# Cechy, które wolno podać modelowi. ATR jest świadomie poza listą —
# patrz "SPLĄTANIE ETYKIETY Z CECHĄ" w nagłówku modułu.
MODELING_FEATURES = ["mom_24", "mom_120", "mom_480", "donch_pos_55", "vol_pct_252"]

# Wyniki traktowane jako y=1. Luka ponad TP też jest trafieniem celu.
WIN_REASONS = {ExitReason.TAKE_PROFIT, ExitReason.GAP_TARGET}

# Wyniki, dla których etykieta jest NIEOKREŚLONA — wykluczamy z próby,
# nie etykietujemy zerem. Zero udawałoby przegraną, która się nie zdarzyła.
UNDEFINED_REASONS = {ExitReason.NO_DATA}


@dataclass(frozen=True)
class LabelSpec:
    sl_multiple: float = 2.0
    tp_multiple: float = 4.0
    horizon_business_days: int = 10


def add_business_days(t: dt.datetime, n: int) -> dt.datetime:
    """Przesuń o n dni roboczych, pomijając soboty i niedziele.

    Świadomie bez kalendarza świąt: rynek FX w święta bywa otwarty, a
    zakodowanie listy świąt wprowadziłoby założenie, którego nie chcemy.
    Brak danych i tak obsługuje symulator (ExitReason.NO_DATA).
    Ujemne n przesuwa wstecz (okno purge przed grupą testową CPCV).
    """
    out = t
    step = dt.timedelta(days=1 if n >= 0 else -1)
    left = abs(n)
    while left > 0:
        out += step
        if out.weekday() < 5:
            left -= 1
    return out


def barriers(entry_ref: float, atr_d1: float, side: Side, spec: LabelSpec
             ) -> tuple[float, float]:
    """Poziomy (SL, TP) wokół ceny referencyjnej."""
    if atr_d1 is None or atr_d1 <= 0:
        raise ValueError("atr_d1_14 musi być dodatnie")
    if side is Side.LONG:
        return entry_ref - spec.sl_multiple * atr_d1, entry_ref + spec.tp_multiple * atr_d1
    return entry_ref + spec.sl_multiple * atr_d1, entry_ref - spec.tp_multiple * atr_d1


def label_events(
    events: pl.DataFrame,
    m1: pl.DataFrame,
    cost: CostModel,
    spec: LabelSpec = LabelSpec(),
    load_ticks=None,
) -> pl.DataFrame:
    """Rozstrzygnij etykiety dla zdarzeń kandydujących.

    `events` musi mieć kolumny: ts (moment decyzji), side, atr_d1_14
    oraz dowolne cechy do przeniesienia.

    Zwraca ramkę z `t1` (moment rozstrzygnięcia), `y`, `r` i powodem wyjścia.
    Zdarzenia o nieokreślonej etykiecie są POMIJANE, nie zerowane.
    """
    if events.is_empty():
        return _empty_labels(events)

    if not m1.get_column("ts").is_sorted():
        m1 = m1.sort("ts")
    rows = []

    for ev in events.iter_rows(named=True):
        side = ev["side"] if isinstance(ev["side"], Side) else Side(ev["side"])
        atr_d1 = ev["atr_d1_14"]
        if atr_d1 is None:
            continue                      # brak zmienności dziennej => brak barier

        # Symulator dostaje wyłącznie okno [decyzja, bariera czasowa] —
        # nie widzi niczego po horyzoncie i nie filtruje całej historii.
        t_end = add_business_days(ev["ts"], spec.horizon_business_days)
        window = slice_window(m1, ev["ts"], t_end)
        if window.is_empty():
            continue
        row = window.row(0, named=True)
        ref = row["ask_open"] if side is Side.LONG else row["bid_open"]

        sl, tp = barriers(ref, atr_d1, side, spec)

        res: TradeResult | None = simulate_trade(
            side, ev["ts"], sl, tp, t_end, window, cost, load_ticks
        )
        if res is None or res.reason in UNDEFINED_REASONS:
            continue

        rows.append({
            **{k: v for k, v in ev.items() if k != "side"},
            "side": side.value,
            "t1": res.exit.time,           # moment rozstrzygnięcia — dla purge
            "y": int(res.reason in WIN_REASONS),
            "r": res.r,
            "reason": res.reason.value,
            "sl": sl,
            "tp": tp,
            "entry_price": res.entry.price,
            "exit_price": res.exit.price,
            "cost_r": res.cost / res.risk,
            # Składniki do kontroli rachunku kosztu (ADR-025 a):
            # r = gross_r − (cost_r − spread_r), cost_r = max(spread_r, podłoga_R)
            "gross_r": res.gross / res.risk,
            "spread_r": 0.5 * (res.entry.spread + res.exit.spread) / res.risk,
        })

    return pl.DataFrame(rows) if rows else _empty_labels(events)


def _empty_labels(events: pl.DataFrame) -> pl.DataFrame:
    base = {c: events.schema.get(c, pl.Float64) for c in events.columns if c != "side"}
    return pl.DataFrame(schema={
        **base,
        "side": pl.Utf8, "t1": pl.Datetime("ms", "UTC"), "y": pl.Int64,
        "r": pl.Float64, "reason": pl.Utf8, "sl": pl.Float64, "tp": pl.Float64,
        "entry_price": pl.Float64, "exit_price": pl.Float64, "cost_r": pl.Float64,
        "gross_r": pl.Float64, "spread_r": pl.Float64,
    })


def overlap_fraction(labels: pl.DataFrame) -> float:
    """Udział etykiet, których okno wynikowe zachodzi na następną etykietę.

    Diagnostyka, nie filtr. Wartość bliska 1 oznacza, że nominalna liczba
    obserwacji jest wielokrotnie większa od efektywnej — i że bez purge
    z embargo każdy wynik walidacji będzie zawyżony.
    """
    if labels.height < 2:
        return 0.0
    df = labels.sort("ts")
    overlapping = df.select(
        (pl.col("t1") > pl.col("ts").shift(-1)).sum()
    ).item()
    return overlapping / (df.height - 1)


def effective_sample_size(labels: pl.DataFrame) -> int:
    """Liczba NIENAKŁADAJĄCYCH SIĘ etykiet — zachłannie od najwcześniejszej.

    To jest liczba, którą należy podstawiać do testów istotności, a nie
    `labels.height`. Różnica bywa rzędu wielkości.
    """
    if labels.is_empty():
        return 0
    n, last_end = 0, None
    for ts, t1 in labels.sort("ts").select("ts", "t1").iter_rows():
        if last_end is None or ts >= last_end:
            n += 1
            last_end = t1
    return n
