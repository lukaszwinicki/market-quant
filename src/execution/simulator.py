"""Symulator egzekucji — najważniejszy moduł projektu.

Asymetria, która uzasadnia priorytet: błąd w signal engine daje zły sygnał,
który zobaczysz w wynikach. Błąd tutaj daje **fałszywą pewność, że zły
sygnał jest dobry** — i nie zobaczysz go nigdy.

STRONY RYNKU

    Long:   wejście po ASK, wyjście po BID.
            SL trafiony gdy BID spadnie do poziomu.
            TP trafiony gdy BID wzrośnie do poziomu.

    Short:  wejście po BID, wyjście po ASK.
            SL trafiony gdy ASK wzrośnie do poziomu.
            TP trafiony gdy ASK spadnie do poziomu.

Z tego wynika asymetria rozszerzeń spreadu: skok spreadu rozjeżdża bid
i ask w przeciwne strony, więc ta sama szpilka wyrzuca długą pozycję
i nie rusza krótkiej (albo odwrotnie). Backtest na cenach mid tego nie
widzi w ogóle.

KOLEJNOŚĆ BARIER

Gdy w jednym barze cena dotyka SL i TP, z OHLC **nie da się** ustalić,
co nastąpiło pierwsze. Naiwna implementacja zakłada korzystną kolejność
i daje cichy, systematyczny bias optymistyczny.

Rozstrzygamy dwustopniowo:

1. Przebieg zgrubny po barach M1. Jeśli w danym barze osiągalna jest
   tylko jedna bariera — odpowiedź jest jednoznaczna, ticki niepotrzebne.
2. Dopiero gdy obie bariery mieszczą się w zakresie tego samego bara M1,
   schodzimy do ticków i ustalamy kolejność faktycznie.

Gdy ticki są niedostępne, stosujemy wariant PESYMISTYCZNY (SL pierwszy).
Nigdy optymistyczny.

LUKI

Jeśli bar otwiera się już za barierą (luka weekendowa, wznowienie po
przerwie), fill następuje po cenie OTWARCIA, a nie po poziomie bariery.
Stop nie chroni przez lukę — to jest realna strata ponad zakładane ryzyko.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import Enum
from typing import Callable

import polars as pl

UTC = dt.timezone.utc


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"


class ExitReason(str, Enum):
    STOP_LOSS = "sl"
    TAKE_PROFIT = "tp"
    TIME_BARRIER = "time"
    GAP_STOP = "gap_sl"          # luka przeskoczyła stop — strata > 1 R
    GAP_TARGET = "gap_tp"
    NO_DATA = "no_data"          # brak danych do końca horyzontu


@dataclass(frozen=True)
class CostModel:
    """Koszty transakcyjne. Broker-agnostyczny — patrz ADR-024."""

    pip: float
    min_roundturn_pips: float = 1.5      # podłoga detaliczna
    entry_slippage_x_spread: float = 0.5
    stop_slippage_x_spread: float = 1.0  # asymetryczne: stop realizuje się w ruchu

    @property
    def floor(self) -> float:
        return self.min_roundturn_pips * self.pip


@dataclass(frozen=True)
class Fill:
    time: dt.datetime
    price: float
    spread: float


@dataclass(frozen=True)
class TradeResult:
    side: Side
    entry: Fill
    exit: Fill
    reason: ExitReason
    gross: float          # ruch ceny w jednostkach ceny, przed kosztami
    cost: float           # spread + poślizg + ewentualna dopłata do podłogi
    net: float            # gross - cost
    risk: float           # |entry_intent - sl|, mianownik dla R
    ticks_scanned: int    # 0 = rozstrzygnięte na barach, >0 = schodziliśmy do ticków

    @property
    def r(self) -> float:
        return self.net / self.risk if self.risk else 0.0


def simulate_trade(
    side: Side,
    decision_time: dt.datetime,
    sl: float,
    tp: float,
    time_barrier: dt.datetime,
    m1: pl.DataFrame,
    cost: CostModel,
    load_ticks: Callable[[dt.datetime, dt.datetime], pl.DataFrame] | None = None,
) -> TradeResult | None:
    """Odegraj jedną transakcję na barach M1, schodząc do ticków gdy trzeba.

    `m1` musi obejmować przedział [decision_time, time_barrier].
    `load_ticks(start, end)` jest wołane WYŁĄCZNIE dla barów niejednoznacznych.
    Zwraca None, gdy w momencie decyzji nie ma danych — to poprawny wynik
    (NO TRADE), nie błąd.
    """
    window = m1.filter(
        (pl.col("ts") >= decision_time) & (pl.col("ts") <= time_barrier)
    ).sort("ts")
    if window.is_empty():
        return None

    first = window.row(0, named=True)
    if first["ts"] > decision_time + dt.timedelta(minutes=1):
        return None   # brak danych w momencie decyzji

    entry = _entry_fill(side, first, cost)
    risk = abs(entry.price - sl)
    if risk <= 0:
        raise ValueError("dystans stopu równy zeru")

    ex_fill, reason, scanned = _find_exit(
        side, window, sl, tp, time_barrier, cost, load_ticks
    )

    gross = (ex_fill.price - entry.price) if side is Side.LONG else (entry.price - ex_fill.price)
    cost_charged = _total_cost(entry, ex_fill, cost)

    return TradeResult(
        side=side, entry=entry, exit=ex_fill, reason=reason,
        gross=gross, cost=cost_charged, net=gross - cost_charged,
        risk=risk, ticks_scanned=scanned,
    )


def _entry_fill(side: Side, bar: dict, cost: CostModel) -> Fill:
    """Wejście po otwarciu pierwszego bara, po niekorzystnej stronie rynku."""
    spread = bar["ask_open"] - bar["bid_open"]
    slip = cost.entry_slippage_x_spread * spread
    price = bar["ask_open"] + slip if side is Side.LONG else bar["bid_open"] - slip
    return Fill(time=bar["ts"], price=price, spread=spread)


def _find_exit(side, window, sl, tp, time_barrier, cost, load_ticks):
    """Pierwsza dotknięta bariera. Zwraca (Fill, ExitReason, liczba_ticków)."""
    long = side is Side.LONG
    # Kolumny, po których pada decyzja — patrz nagłówek modułu.
    lo_col, hi_col, op_col = ("bid_low", "bid_high", "bid_open") if long else \
                             ("ask_low", "ask_high", "ask_open")

    for bar in window.iter_rows(named=True):
        op, lo, hi = bar[op_col], bar[lo_col], bar[hi_col]
        spread = bar["spread_max"]

        # --- luka: bar otwiera się już za barierą -------------------------
        # Luka: fill po cenie OTWARCIA, nie po poziomie bariery. Stop nie
        # chroni przez lukę — strata przekracza zakładane 1 R i tak ma być.
        if (op <= sl) if long else (op >= sl):
            return Fill(bar["ts"], op, spread), ExitReason.GAP_STOP, 0
        if (op >= tp) if long else (op <= tp):
            return Fill(bar["ts"], op, spread), ExitReason.GAP_TARGET, 0

        hit_sl = lo <= sl if long else hi >= sl
        hit_tp = hi >= tp if long else lo <= tp

        if hit_sl and hit_tp:
            # Niejednoznaczne — dopiero tutaj ticki mają sens.
            resolved, scanned = _resolve_on_ticks(
                side, bar, sl, tp, load_ticks
            )
            if resolved is ExitReason.TAKE_PROFIT:
                return Fill(bar["ts"], tp, spread), resolved, scanned
            return _stop_fill(side, bar["ts"], sl, spread, cost), resolved, scanned

        if hit_sl:
            return _stop_fill(side, bar["ts"], sl, spread, cost), ExitReason.STOP_LOSS, 0
        if hit_tp:
            return Fill(bar["ts"], tp, spread), ExitReason.TAKE_PROFIT, 0

    # --- bariera czasowa ---------------------------------------------------
    last = window.row(-1, named=True)
    if last["ts"] < time_barrier - dt.timedelta(minutes=1):
        reason = ExitReason.NO_DATA
    else:
        reason = ExitReason.TIME_BARRIER
    close_col = "bid_close" if long else "ask_close"
    return Fill(last["ts"], last[close_col], last["spread_close"]), reason, 0


def _stop_fill(side: Side, ts, level: float, spread: float, cost: CostModel) -> Fill:
    """Fill na stopie — poślizg w cenie, zawsze w niekorzystną stronę.

    Stop realizuje się dokładnie wtedy, gdy rynek się porusza, więc poślizg
    jest asymetryczny: na stopie zawsze przeciw nam, na TP nigdy za nas.
    Poślizg wchodzi w CENĘ, nie w koszt — inaczej byłby liczony dwa razy.
    """
    slip = cost.stop_slippage_x_spread * spread
    price = level - slip if side is Side.LONG else level + slip
    return Fill(ts, price, spread)


def _resolve_on_ticks(side, bar, sl, tp, load_ticks) -> tuple[ExitReason, int]:
    """Ustal, która bariera padła pierwsza. Bez ticków — pesymistycznie."""
    if load_ticks is None:
        return ExitReason.STOP_LOSS, 0

    start = bar["ts"]
    ticks = load_ticks(start, start + dt.timedelta(minutes=1))
    if ticks.is_empty():
        return ExitReason.STOP_LOSS, 0

    long = side is Side.LONG
    col = "bid" if long else "ask"
    px = ticks[col].to_numpy()

    for p in px:
        if long:
            if p <= sl:
                return ExitReason.STOP_LOSS, len(px)
            if p >= tp:
                return ExitReason.TAKE_PROFIT, len(px)
        else:
            if p >= sl:
                return ExitReason.STOP_LOSS, len(px)
            if p <= tp:
                return ExitReason.TAKE_PROFIT, len(px)

    # Ticki nie potwierdziły żadnej bariery mimo zakresu bara — pesymistycznie.
    return ExitReason.STOP_LOSS, len(px)


def _total_cost(entry: Fill, exit_: Fill, cost: CostModel) -> float:
    """Spread + poślizg, z dopłatą do podłogi detalicznej.

    Ceny fillów już zawierają spread (wejście po gorszej stronie, wyjście
    po gorszej stronie), więc implikowany koszt spreadu to pół spreadu
    z wejścia plus pół z wyjścia. Poślizg NIE jest tu doliczany — siedzi
    już w cenie fillu (`_stop_fill`). Podłoga z ADR-024 wchodzi dopiero
    wtedy, gdy rzeczywisty koszt był od niej niższy — a na majorsach jest
    tak prawie zawsze.
    """
    implied = 0.5 * entry.spread + 0.5 * exit_.spread
    return max(implied, cost.floor)
