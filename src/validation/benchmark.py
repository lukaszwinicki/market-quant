"""Koszyk carry + trend — benchmark obowiązkowy §12, kontrola #5 z §10.2.

    Raz w tygodniu, waluty vs USD:
      ranking po (carry + zwrot 3-miesięczny)
      long top, short bottom
      równe ryzyko, sizing przez ATR
      brak stopów, rebalans tygodniowy

CO ROZSTRZYGNĘŁY ADR-y, A CZEGO NIE MA W SPEC

* **ADR-038** — `yield_2y` nie istnieje w jednej definicji dla ośmiu walut,
  więc carry mierzy `interbank_3m`; uniwersum to pięć walut kohorty A vs
  USD, long top-1 / short bottom-1.
* **ADR-039** — pięć nakładających się portfeli (kotwica pon–pt, wynik =
  średnia) zamiast jednego dnia rebalansu; `1 R = sl_multiple × atr_d1_14`,
  czyli TA SAMA jednostka co w strategii; koszty tylko przy ZMIANIE pozycji;
  blackout i warunki NO TRADE V1a NIE są przenoszone na koszyk; tydzień bez
  kompletu walut pomijany w całości.
* **ADR-040** — kontrolę #5 rozstrzyga różnica SHARPE'ów serii dziennych R,
  nie ich średnich, bo strategia trzyma ok. 2× większe otwarte ryzyko niż
  koszyk i różnica średnich faworyzowałaby ją bez żadnej przewagi.

JEDNOSTKA R, CZYLI NAJŁATWIEJSZY BŁĄD

Koszyk nie ma stopu, więc „1 R" trzeba mu nadać z zewnątrz. Naturalne
`1 × atr_d1_14` byłoby o połowę mniejsze niż R strategii (`2 × atr_d1_14`,
odległość do stopu) i **dwukrotnie zawyżałoby wynik koszyka** przy tej samej
ekspozycji. Kontrola #5 porównuje dwie serie w R, więc R musi znaczyć po
obu stronach to samo.

WALUTA, NIE PARA

Ranking dotyczy waluty względem USD. Dla par USD-bazowych (USDJPY, USDCAD)
long waluty to SHORT pary — i odwrotnie. Zwroty też liczymy na walucie:
`+3%` na USDJPY oznacza `−3%` dla JPY.

KSZTAŁT WYNIKU

Koszyk emituje transakcje w TYM SAMYM schemacie co strategia (`symbol`,
`ts`, `t1`, `side`, `gross_r`, `cost_r`, `spread_r`, `slip_r`, `r`,
`entry_price`, `sl`), żeby `apply_financing`, `cost_ladder`,
`markup_ladder`, bootstrap i oś dzienna działały na nim bez wyjątków.
`sl` jest syntetyczne: leży dokładnie `1 R` od wejścia, bo tylko tak
`apply_financing` odczyta właściwy mianownik. Koszyk stopu nie używa.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from ..data.rates import rate_on
from ..execution.simulator import CostModel
from ..features.technical import daily_bars
from .bootstrap import block_indices, daily_frames
from .dsr import sharpe

UTC = dt.timezone.utc
WEEK = dt.timedelta(days=7)
WEEKDAYS = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4}


@dataclass(frozen=True)
class BenchmarkSpec:
    currencies: tuple[str, ...]
    long_top_n: int = 1
    short_bottom_n: int = 1
    anchors: tuple[int, ...] = (0, 1, 2, 3, 4)
    lookback_business_days: int = 63
    carry_kind: str = "interbank_3m"
    r_multiple: float = 2.0            # = labels.sl_multiple
    # ADR-043: czas LOKALNY + strefa, nigdy stały offset. 16:00 w Londynie
    # to fixing WM/Reuters — 15:00 UTC latem, 16:00 UTC zimą.
    rebalance_time_local: dt.time = dt.time(16, 0)
    rebalance_timezone: str = "Europe/London"

    def moment_on(self, day: dt.date) -> dt.datetime:
        """Chwila rebalansu w dniu `day`, w UTC.

        Godzina jest lokalna, więc przeliczenie musi iść przez strefę —
        stały offset przesuwałby moment o godzinę przez pół roku.
        """
        local = dt.datetime.combine(day, self.rebalance_time_local,
                                    tzinfo=ZoneInfo(self.rebalance_timezone))
        return local.astimezone(UTC)


def spec_from(cfg: dict) -> BenchmarkSpec:
    """Cały koszyk z konfiguracji — w kodzie są tylko wartości domyślne testów."""
    b = cfg["validation"]["benchmark_carry_trend"]
    return BenchmarkSpec(
        currencies=tuple(b["currencies"]),
        long_top_n=b["long_top_n"], short_bottom_n=b["short_bottom_n"],
        anchors=tuple(WEEKDAYS[a] for a in b["rebalance_anchors"]),
        lookback_business_days=b["momentum_lookback_business_days"],
        carry_kind=b["carry_measure"],
        r_multiple=cfg["labels"]["sl_multiple"],
        rebalance_time_local=dt.time.fromisoformat(b["rebalance_time_local"]),
        rebalance_timezone=b["rebalance_timezone"],
    )


def usd_pairs(symbols: list[str], currencies: tuple[str, ...]
              ) -> dict[str, tuple[str, bool]]:
    """waluta → (para z USD, czy waluta jest walutą BAZOWĄ pary).

    Brak pary dla którejkolwiek waluty jest błędem, nie pominięciem: koszyk
    czterech walut to inny koszyk niż pięciu (ADR-039).
    """
    out = {}
    for ccy in currencies:
        for s in symbols:
            if s == ccy + "USD":
                out[ccy] = (s, True)
            elif s == "USD" + ccy:
                out[ccy] = (s, False)
        if ccy not in out:
            raise ValueError(f"{ccy}: brak pary z USD wśród {symbols}")
    return out


# --- ranking ------------------------------------------------------------------

def rebalance_days(anchor: int, start: dt.datetime, end: dt.datetime) -> list[dt.date]:
    """Kolejne dni tygodnia `anchor` (0 = poniedziałek) w [start, end]."""
    d = start.date()
    d += dt.timedelta(days=(anchor - d.weekday()) % 7)
    out = []
    while d <= end.date():
        out.append(d)
        d += WEEK
    return out


def momentum(d1: pl.DataFrame, day: dt.date, lookback: int,
             is_base: bool) -> float | None:
    """Zwrot WALUTY vs USD w procentach, z barów dziennych `bid_close`.

    Bid po obu stronach: to sygnał, nie fill, więc liczy się jedna spójna
    strona rynku, a nie mid (którego w tym projekcie nie ma nigdzie).
    """
    past = d1.filter(pl.col("ts").dt.date() <= day)
    if past.height <= lookback:
        return None
    now = past["bid_close"][-1]
    then = past["bid_close"][-1 - lookback]
    if then <= 0:
        return None
    ret = (now / then - 1.0) * 100.0
    return ret if is_base else -ret


def ranking(day: dt.date, d1: dict[str, pl.DataFrame], rates: pl.DataFrame,
            pairs: dict[str, tuple[str, bool]], spec: BenchmarkSpec
            ) -> dict[str, float] | None:
    """Wynik rankingu per waluta albo None, gdy tydzień jest niepełny.

    Suma jest DOSŁOWNA, jak w §12: carry w punktach procentowych rocznie plus
    zwrot trzymiesięczny w procentach. Zmierzone (ADR-039): człon zwrotu ma
    ok. 4× większy rozrzut przekrojowy, więc ranking jest zdominowany przez
    momentum, a carry rozstrzyga głównie remisy. To jest zapisane, nie
    poprawiane — każda normalizacja byłaby wielkością dobraną przez nas.
    """
    scores = {}
    for ccy, (sym, is_base) in pairs.items():
        mom = momentum(d1[sym], day, spec.lookback_business_days, is_base)
        if mom is None:
            return None
        try:
            carry = (rate_on(rates, ccy, day, spec.carry_kind)
                     - rate_on(rates, "USD", day, spec.carry_kind))
        except KeyError:
            return None
        scores[ccy] = carry + mom
    return scores


def legs(scores: dict[str, float], spec: BenchmarkSpec) -> dict[str, str]:
    """waluta → 'long' / 'short' dla skrajów rankingu; remisy po nazwie waluty."""
    order = sorted(scores, key=lambda c: (-scores[c], c))
    return ({c: "long" for c in order[:spec.long_top_n]}
            | {c: "short" for c in order[len(order) - spec.short_bottom_n:]})


def pair_side(currency_side: str, is_base: bool) -> str:
    """Long waluty na parze USD-bazowej to short pary."""
    if is_base:
        return currency_side
    return "short" if currency_side == "long" else "long"


# --- egzekucja ----------------------------------------------------------------

def _bar_at(h1: pl.DataFrame, moment: dt.datetime) -> dict | None:
    """Ostatni bar H1 ZAMKNIĘTY nie później niż `moment`.

    Bar o etykiecie T zamyka się o T+1h, więc szukamy etykiety ≤ moment − 1h.
    Nigdy ręcznej arytmetyki w drugą stronę.
    """
    cut = moment - dt.timedelta(hours=1)
    past = h1.filter(pl.col("ts") <= cut)
    return past.row(-1, named=True) if past.height else None


def _fill(bar: dict, side: str, cost: CostModel) -> tuple[float, float]:
    """(cena fillu po niekorzystnej stronie z poślizgiem, spread bara).

    Ta sama konwencja co `simulator._entry_fill`: wchodzimy i wychodzimy po
    gorszej stronie rynku, poślizg siedzi W CENIE i nie jest odejmowany drugi
    raz od `gross`.

    Mnożnik poślizgu jest po OBU stronach `entry_slippage_x_spread`, bo
    koszyk wychodzi zleceniem rynkowym przy rebalansie, a nie stopem.
    `stop_slippage_x_spread` jest wyższy właśnie dlatego, że stop realizuje
    się w ruchu — tu takiego zlecenia nie ma (ADR-039: brak stopów).
    """
    spread = bar["ask_close"] - bar["bid_close"]
    slip = cost.entry_slippage_x_spread * spread
    price = (bar["ask_close"] + slip) if side == "long" else (bar["bid_close"] - slip)
    return price, spread


def _leg(symbol: str, side: str, entry_bar: dict, exit_bar: dict, atr: float,
         cost: CostModel, spec: BenchmarkSpec) -> dict:
    """Jedna pozycja koszyka od otwarcia do zamknięcia, w schemacie transakcji.

    Rachunek kosztu jest identyczny z symulatorem i z ADR-024:
    `cost_r = max(spread_r, podłoga/ryzyko)`, `r = gross_r − dopłata`.
    Spread nie może zostać policzony dwa razy — ten błąd już raz się zdarzył.
    """
    risk = spec.r_multiple * atr
    entry_px, entry_spread = _fill(entry_bar, side, cost)
    exit_side = "short" if side == "long" else "long"
    exit_px, exit_spread = _fill(exit_bar, exit_side, cost)

    gross = (exit_px - entry_px) if side == "long" else (entry_px - exit_px)
    implied = 0.5 * entry_spread + 0.5 * exit_spread
    top_up = max(0.0, cost.floor - implied)
    slip = cost.entry_slippage_x_spread * (entry_spread + exit_spread)
    sign = 1.0 if side == "long" else -1.0
    return {
        "symbol": symbol, "side": side,
        "ts": entry_bar["ts"] + dt.timedelta(hours=1),
        "t1": exit_bar["ts"] + dt.timedelta(hours=1),
        "entry_price": entry_px,
        "sl": entry_px - sign * risk,          # syntetyczne: |entry − sl| = 1 R
        "gross_r": gross / risk,
        "cost_r": (implied + top_up) / risk,
        "spread_r": implied / risk,
        "slip_r": slip / risk,
        "r": (gross - top_up) / risk,
    }


def run_anchor(anchor: int, h1: dict[str, pl.DataFrame], d1: dict[str, pl.DataFrame],
               rates: pl.DataFrame, costs: dict[str, CostModel],
               pairs: dict[str, tuple[str, bool]], spec: BenchmarkSpec,
               start: dt.datetime, end: dt.datetime
               ) -> tuple[pl.DataFrame, dict]:
    """Jeden podportfel: rebalans co tydzień w dniu `anchor`.

    Pozycja, która zostaje w koszyku z tym samym kierunkiem, NIE jest
    przehandlowana ani przeskalowana — stąd „znikomy obrót" z ADR-019.
    Zamknięta jest dopiero wtedy, gdy wypada z rankingu albo zmienia stronę.
    """
    days = rebalance_days(anchor, start, end)
    open_legs: dict[str, dict] = {}        # waluta → {bar wejścia, atr, side}
    trades, skipped = [], 0

    def close(ccy: str, bar: dict) -> None:
        st = open_legs.pop(ccy)
        sym, is_base = pairs[ccy]
        trades.append(_leg(sym, pair_side(st["side"], is_base), st["bar"], bar,
                           st["atr"], costs[sym], spec))

    for day in days:
        moment = spec.moment_on(day)
        bars = {c: _bar_at(h1[pairs[c][0]], moment) for c in pairs}
        scores = ranking(day, d1, rates, pairs, spec)
        usable = (scores is not None
                  and all(b is not None and b.get("atr_d1_14") for b in bars.values()))
        if not usable:
            # Tydzień pomijany W CAŁOŚCI (ADR-039): ranking czterech walut to
            # inny koszyk, a nie ten sam z dziurą. Otwarte pozycje zostają.
            skipped += 1
            continue

        want = legs(scores, spec)
        for ccy in list(open_legs):
            if want.get(ccy) != open_legs[ccy]["side"]:
                close(ccy, bars[ccy])
        for ccy, side in want.items():
            if ccy not in open_legs:
                open_legs[ccy] = {"side": side, "bar": bars[ccy],
                                  "atr": bars[ccy]["atr_d1_14"]}

    # Koniec okresu zamyka wszystko na ostatnim znanym barze.
    for ccy in list(open_legs):
        last = _bar_at(h1[pairs[ccy][0]], end)
        if last is None:
            open_legs.pop(ccy)
        else:
            close(ccy, last)

    frame = pl.DataFrame(trades) if trades else pl.DataFrame()
    return frame, {"anchor": anchor, "n_rebalances": len(days),
                   "n_skipped": skipped, "n_trades": frame.height}


def run_benchmark(h1: dict[str, pl.DataFrame], rates: pl.DataFrame,
                  costs: dict[str, CostModel], symbols: list[str],
                  spec: BenchmarkSpec, start: dt.datetime, end: dt.datetime
                  ) -> tuple[dict[int, pl.DataFrame], list[dict]]:
    """Pięć nakładających się podportfeli (ADR-039), po jednym na kotwicę."""
    pairs = usd_pairs(symbols, spec.currencies)
    d1 = {sym: daily_bars(h1[sym].sort("ts")) for sym, _ in pairs.values()}
    per_anchor, stats = {}, []
    for a in spec.anchors:
        frame, st = run_anchor(a, h1, d1, rates, costs, pairs, spec, start, end)
        per_anchor[a] = frame
        stats.append(st)
    return per_anchor, stats


# --- porównanie ze strategią (kontrola #5) ------------------------------------

@dataclass(frozen=True)
class Comparison:
    strategy_sharpe: float
    benchmark_sharpe: float
    difference: float
    ci_low: float
    ci_high: float
    strategy_mean_daily_r: float
    benchmark_mean_daily_r: float
    strategy_open_risk_r: float
    benchmark_open_risk_r: float
    n_days: int
    n_reps: int

    @property
    def beaten(self) -> bool:
        """ADR-040: koszyk jest pobity, gdy CI95 różnicy leży w całości > 0."""
        return self.ci_low > 0.0


def mean_open_risk(trades: pl.DataFrame) -> float:
    """Średnie jednocześnie otwarte ryzyko w R, liczone po czasie.

    Wielkość, którą Sharpe normalizuje — i dokładnie dlatego musi być
    raportowana osobno (ADR-040 pkt 4). Strategia i koszyk chodzą na
    różnych budżetach; bezskalowe kryterium nie może tego ukryć.
    """
    if trades.height == 0:
        return 0.0
    span = (trades["t1"].max() - trades["ts"].min()).total_seconds()
    if span <= 0:
        return 0.0
    held = sum((b - a).total_seconds()
               for a, b in trades.select("ts", "t1").iter_rows())
    return held / span


def daily_series(strategy: pl.DataFrame, per_anchor: dict[int, pl.DataFrame]
                 ) -> tuple[list[dt.date], np.ndarray, np.ndarray]:
    """(oś dni, dzienne R strategii, dzienne R koszyka) na WSPÓLNEJ osi.

    Jedna oś dla obu serii jest warunkiem, żeby dało się je odjąć —
    `daily_totals` budowałby dwie różne. Koszyk to ŚREDNIA z podportfeli
    (ADR-039): każdy trzyma piątą część kapitału, więc uśredniamy, a nie
    sumujemy.
    """
    frames = [strategy] + [per_anchor[a] for a in sorted(per_anchor)]
    days, matrix = daily_frames(frames, "r")
    if not days:
        return [], np.zeros(0), np.zeros(0)
    return days, matrix[:, 0], matrix[:, 1:].mean(axis=1)


def compare(strategy_daily: np.ndarray, benchmark_daily: np.ndarray,
            strategy_trades: pl.DataFrame, benchmark_trades: list[pl.DataFrame],
            block_days: int = 20, n_reps: int = 10_000, seed: int = 0
            ) -> Comparison:
    """Różnica Sharpe'ów serii dziennych R z przedziałem ufności (ADR-040).

    Obie serie muszą już leżeć na TEJ SAMEJ osi dni — daje ją `daily_series()`.
    Bloki bootstrapu są losowane RAZ i stosowane do OBU serii: strategia
    i koszyk handlują te same pary w tych samych dniach, więc niezależne
    losowanie zerwałoby ich korelację dzienną i rozdęło przedział różnicy
    ponad to, co jest w danych.
    """
    s = np.asarray(strategy_daily, dtype=float)
    b = np.asarray(benchmark_daily, dtype=float)
    if s.shape != b.shape or s.ndim != 1:
        raise ValueError(f"serie muszą być jednowymiarowe i tej samej długości: "
                         f"{s.shape} vs {b.shape}")

    idx = block_indices(len(s), block_days, n_reps, np.random.default_rng(seed))
    diffs = np.array([_sharpe_or_nan(s[take]) - _sharpe_or_nan(b[take])
                      for take in idx])
    diffs = diffs[~np.isnan(diffs)]
    if not len(diffs):
        raise ValueError("każda replikacja dała nieokreślony Sharpe")
    lo, hi = np.percentile(diffs, [2.5, 97.5])

    s_sr, b_sr = _sharpe_or_nan(s), _sharpe_or_nan(b)
    return Comparison(
        strategy_sharpe=s_sr, benchmark_sharpe=b_sr, difference=s_sr - b_sr,
        ci_low=float(lo), ci_high=float(hi),
        strategy_mean_daily_r=float(s.mean()), benchmark_mean_daily_r=float(b.mean()),
        strategy_open_risk_r=mean_open_risk(strategy_trades),
        benchmark_open_risk_r=float(np.mean([mean_open_risk(f)
                                             for f in benchmark_trades])),
        n_days=len(s), n_reps=len(diffs),
    )


def _sharpe_or_nan(x: np.ndarray) -> float:
    try:
        return sharpe(x)
    except ValueError:
        return float("nan")
