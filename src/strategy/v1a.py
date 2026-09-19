"""Sygnał V1a i warunki NO TRADE (PROJECT_SPEC §7.1, §7.4, §8; ADR-030, 032, 033).

    LONG:   mom_480 > 0  i  donch_pos > 0,80
    SHORT:  mom_480 < 0  i  donch_pos < 0,20
    wejście rynkowe na zamknięciu bara H1, bariery 2 / 4 × atr_d1_14, 10 dni rob.

NO TRADE JEST STANEM DOMYŚLNYM

Każdy zamknięty bar H1 każdej pary dostaje wiersz w logu decyzji: akcję
(`enter` / `no_trade`) i powód. Wejście zdarza się tylko wtedy, gdy nie
zadziałał żaden powód. Powody (ADR-033), w kolejności raportowania:

    warmup          brak cech (rozgrzewka) — nie ma czego oceniać
    7_data_gap      luka > 2 barów H1 w ostatnich 480 (gdy rynek działał)
    no_signal       reguła nie daje kierunku
    1_blackout      zdarzenie HIGH: 30 min przed … 120 min po (ADR-032)
    2_vol_pct       vol_pct_252 > 0,95
    4_ccy_limit     |netto bloku walutowego| > 2 R po wejściu
    5_portfolio     suma otwartego ryzyka > 6 R po wejściu
    6_open_position para już ma otwartą pozycję
    8_rollover      decyzja w [16:45, 17:15] czasu Nowego Jorku
    9_friday        piątek od 15:00 czasu Nowego Jorku
    split_boundary  horyzont wychodzi poza split (ADR-030)
    no_fill         symulator nie ma danych w chwili decyzji / NO_DATA

Kolumna `reasons` zawiera WSZYSTKIE powody, `reason` — pierwszy.

STAN PORTFELA

Warunki 4–6 zależą od otwartych pozycji, więc decyzje są przetwarzane
sekwencyjnie po czasie; przy tym samym czasie pary alfabetycznie.
Pozycja zajmuje parę od wejścia do `t1` (wyjście z symulatora) — kolejne
wejście na parze jest możliwe przy decyzji PÓŹNIEJSZEJ niż `t1`. `t1`
jest znane dopiero po symulacji tej transakcji, ale decyzje po `t1` nie
widzą niczego, czego prawdziwy system by nie wiedział: w chwili t > t1
pozycja naprawdę już jest zamknięta.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Callable

import polars as pl

from ..data.calendar import blackout
from ..data.resample import decision_time_for_bar
from ..execution.simulator import market_closed_between
from ..labels.triple_barrier import LabelSpec, add_business_days

H1 = dt.timedelta(hours=1)
NY = "America/New_York"

REASON_ORDER = ("warmup", "7_data_gap", "no_signal", "1_blackout", "2_vol_pct",
                "4_ccy_limit", "5_portfolio", "6_open_position", "8_rollover",
                "9_friday", "split_boundary", "no_fill")


@dataclass(frozen=True)
class V1aParams:
    donchian_lookback: int = 55
    sl_multiple: float = 2.0
    tp_multiple: float = 4.0
    name: str = "baseline"

    def label_spec(self, horizon_business_days: int) -> LabelSpec:
        return LabelSpec(self.sl_multiple, self.tp_multiple, horizon_business_days)


@dataclass(frozen=True)
class Rules:
    mom_480_min: float = 0.0
    donch_pos_min: float = 0.80
    vol_pct_max: float = 0.95
    blackout_before_min: int = 30
    blackout_after_min: int = 120
    rollover_ny: tuple[dt.time, dt.time] = (dt.time(16, 45), dt.time(17, 15))
    friday_cutoff_ny: dt.time = dt.time(15, 0)
    max_gap_bars: int = 2
    gap_lookback_bars: int = 480
    max_net_block_r: float = 2.0
    max_portfolio_r: float = 6.0
    max_positions_per_symbol: int = 1
    horizon_business_days: int = 10
    blocks: dict[str, tuple[str, ...]] = field(default_factory=lambda: {
        "usd": ("USD",), "eur": ("EUR", "CHF"), "gbp": ("GBP",), "jpy": ("JPY",),
        "commodity": ("AUD", "NZD", "CAD")})


def rules_from(cfg: dict) -> Rules:
    """Wszystkie progi z configu — w kodzie są tylko wartości domyślne testów."""
    th = cfg["signal_v1a"]["frozen_thresholds"]
    bl, risk = cfg["blackout"], cfg["risk"]
    return Rules(
        mom_480_min=th["mom_480_min"], donch_pos_min=th["donch_pos_min"],
        vol_pct_max=th["vol_pct_max"],
        blackout_before_min=bl["window_before_minutes"],
        blackout_after_min=bl["window_after_minutes"],
        max_net_block_r=risk["max_net_risk_per_currency_R"],
        max_portfolio_r=risk["max_portfolio_risk_R"],
        max_positions_per_symbol=risk["max_positions_per_symbol"],
        horizon_business_days=cfg["labels"]["time_barrier_business_days"],
        blocks={k: tuple(v) for k, v in risk["currency_blocks"].items()},
    )


def grid_from(cfg: dict) -> list[V1aParams]:
    return [V1aParams(g["donchian_lookback"], g["sl_multiple"], g["tp_multiple"], g["name"])
            for g in cfg["signal_v1a"]["sensitivity_grid"]]


# --- warunki statyczne (per bar, bez stanu portfela) ---------------------------

def data_gap_flags(bar_ts: pl.Series, max_missing: int, lookback: int) -> pl.Series:
    """True, gdy w ostatnich `lookback` barach była luka > `max_missing` barów
    w czasie, gdy rynek działał (weekend i święta się nie liczą)."""
    ts = bar_ts.to_list()
    gap = [False] * len(ts)
    for i in range(1, len(ts)):
        missing = int((ts[i] - ts[i - 1]) / H1) - 1
        if missing > max_missing and not market_closed_between(ts[i - 1] + H1, ts[i]):
            gap[i] = True
    return (pl.Series("gap", gap).cast(pl.Int8)
            .rolling_max(window_size=lookback, min_samples=1).cast(pl.Boolean))


def decision_frame(features: pl.DataFrame, symbol: str, params: V1aParams,
                   rules: Rules, events: pl.DataFrame, split_end: dt.datetime
                   ) -> pl.DataFrame:
    """Jeden wiersz na zamknięty bar H1: moment decyzji, kierunek sygnału
    i wszystkie warunki niezależne od portfela."""
    donch = f"donch_pos_{params.donchian_lookback}"
    f = features.sort("ts")
    decision = f["ts"].map_elements(lambda t: decision_time_for_bar(t, 3600),
                                    return_dtype=pl.Datetime("us", "UTC")
                                    ).cast(pl.Datetime("ms", "UTC"))
    horizon_end = decision.map_elements(
        lambda t: add_business_days(t, rules.horizon_business_days),
        return_dtype=pl.Datetime("us", "UTC")).cast(pl.Datetime("ms", "UTC"))
    ny = decision.dt.convert_time_zone(NY)
    lo, hi = rules.rollover_ny

    long_ = (pl.col("mom_480") > rules.mom_480_min) & (pl.col(donch) > rules.donch_pos_min)
    short = (pl.col("mom_480") < -rules.mom_480_min) & (pl.col(donch) < 1 - rules.donch_pos_min)
    return f.select(
        decision.alias("ts"),
        pl.col("ts").alias("bar_ts"),
        pl.lit(symbol).alias("symbol"),
        pl.when(long_).then(pl.lit("long")).when(short).then(pl.lit("short"))
        .otherwise(None).alias("signal"),
        "atr_d1_14",
        pl.any_horizontal(pl.col("mom_480", donch, "atr_d1_14", "vol_pct_252").is_null())
        .alias("warmup"),
        data_gap_flags(f["ts"], rules.max_gap_bars, rules.gap_lookback_bars).alias("7_data_gap"),
        blackout(decision, symbol, events, rules.blackout_before_min,
                 rules.blackout_after_min).alias("1_blackout"),
        (pl.col("vol_pct_252") > rules.vol_pct_max).fill_null(False).alias("2_vol_pct"),
        ny.dt.time().is_between(lo, hi, closed="both").alias("8_rollover"),
        ((ny.dt.weekday() == 5) & (ny.dt.time() >= rules.friday_cutoff_ny)).alias("9_friday"),
        (horizon_end > split_end).alias("split_boundary"),
    )


# --- przebieg sekwencyjny ------------------------------------------------------

def _block_of(ccy: str, blocks: dict[str, tuple[str, ...]]) -> str:
    return next((b for b, cs in blocks.items() if ccy in cs), ccy)


def _exposure_delta(symbol: str, side: str, blocks) -> dict[str, float]:
    sign = 1.0 if side == "long" else -1.0
    d: dict[str, float] = {}
    for ccy, s in ((symbol[:3], sign), (symbol[3:], -sign)):
        b = _block_of(ccy, blocks)
        d[b] = d.get(b, 0.0) + s
    return d


def run_v1a(frames: list[pl.DataFrame], rules: Rules,
            evaluate: Callable[[pl.DataFrame], pl.DataFrame]
            ) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Przejdź decyzje wszystkich par po czasie. Zwraca (log decyzji, transakcje).

    `evaluate(events) -> labels` — ten sam symulator i etykietowanie co
    w kontroli losowej (np. `gate0.make_evaluator`), z geometrią barier
    wariantu.
    """
    static = [r for r in REASON_ORDER if r not in
              ("no_signal", "4_ccy_limit", "5_portfolio", "6_open_position", "no_fill")]
    dec = pl.concat(frames).sort("ts", "symbol")
    open_pos: list[dict] = []           # symbol, side, t1
    rows, trades = [], []

    for d in dec.iter_rows(named=True):
        t = d["ts"]
        open_pos = [p for p in open_pos if p["t1"] >= t]
        reasons = [r for r in static if d[r]]
        side = d["signal"]
        if side is None and not d["warmup"]:
            reasons.append("no_signal")
        if side is not None:
            if sum(p["symbol"] == d["symbol"] for p in open_pos) >= rules.max_positions_per_symbol:
                reasons.append("6_open_position")
            if len(open_pos) + 1 > rules.max_portfolio_r:
                reasons.append("5_portfolio")
            net: dict[str, float] = {}
            for p in open_pos + [{"symbol": d["symbol"], "side": side}]:
                for b, v in _exposure_delta(p["symbol"], p["side"], rules.blocks).items():
                    net[b] = net.get(b, 0.0) + v
            touched = _exposure_delta(d["symbol"], side, rules.blocks)
            if any(abs(net[b]) > rules.max_net_block_r for b in touched):
                reasons.append("4_ccy_limit")

        if not reasons:
            ev = pl.DataFrame([{"ts": t, "symbol": d["symbol"], "side": side,
                                "atr_d1_14": d["atr_d1_14"]}],
                              schema={"ts": pl.Datetime("ms", "UTC"), "symbol": pl.Utf8,
                                      "side": pl.Utf8, "atr_d1_14": pl.Float64})
            lab = evaluate(ev)
            if lab.height:
                trade = lab.row(0, named=True)
                trades.append(trade)
                open_pos.append({"symbol": d["symbol"], "side": side, "t1": trade["t1"]})
            else:
                reasons.append("no_fill")

        reasons.sort(key=REASON_ORDER.index)
        rows.append({"ts": t, "bar_ts": d["bar_ts"], "symbol": d["symbol"],
                     "signal": side, "action": "no_trade" if reasons else "enter",
                     "reason": reasons[0] if reasons else None,
                     "reasons": ",".join(reasons)})

    log = pl.DataFrame(rows, schema={
        "ts": pl.Datetime("ms", "UTC"), "bar_ts": pl.Datetime("ms", "UTC"),
        "symbol": pl.Utf8, "signal": pl.Utf8, "action": pl.Utf8,
        "reason": pl.Utf8, "reasons": pl.Utf8})
    return log, (pl.DataFrame(trades) if trades else pl.DataFrame())
