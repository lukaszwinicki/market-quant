"""Dane i koszty dla harnessu — jedyna droga od Parquetu do symulatora.

PIECZĘĆ HOLD-OUTU

Hold-out 2024-2025 jest otwierany dokładnie raz, na bramce 4. Pilnujemy
tego w miejscu, przez które przechodzi każdy odczyt M1: zakres dotykający
`data.splits.sealed_holdout` jest odrzucany, chyba że wywołujący jawnie
poda `unseal=True`. Dotyczy to też transakcji z końca 2023 r., których
horyzont 10 dni sięga w styczeń 2024 — ich rozstrzygnięcie to już ceny
z hold-outu.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from ..data.dukascopy import pip_size
from ..data.resample import BAR_SCHEMA
from ..execution.simulator import CostModel

UTC = dt.timezone.utc
ROOT = Path(__file__).resolve().parents[2]
BARS_M1 = ROOT / "data" / "bars" / "m1"


class SealedHoldoutError(RuntimeError):
    """Próba odczytu zapieczętowanego hold-outu przed bramką 4."""


def sealed_range(cfg: dict) -> tuple[dt.datetime, dt.datetime]:
    """[początek, koniec) hold-outu. Koniec wyłączny: dzień po `end`."""
    s = cfg["data"]["splits"]["sealed_holdout"]
    start = dt.datetime.fromisoformat(str(s["start"])).replace(tzinfo=UTC)
    end = dt.datetime.fromisoformat(str(s["end"])).replace(tzinfo=UTC)
    return start, end + dt.timedelta(days=1)


def load_m1(symbol: str, start: dt.datetime, end: dt.datetime, cfg: dict, *,
            root: Path = BARS_M1, unseal: bool = False) -> pl.DataFrame:
    """Bary M1 symbolu o etykiecie w [start, end], posortowane po `ts`.

    Czyta tylko partycje lat, które zakres obejmuje.
    """
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start i end muszą być tz-aware (UTC)")
    s0, s1 = sealed_range(cfg)
    if not unseal and start < s1 and end >= s0:
        raise SealedHoldoutError(
            f"{symbol} [{start:%Y-%m-%d}, {end:%Y-%m-%d}] dotyka hold-outu "
            f"[{s0:%Y-%m-%d}, {s1:%Y-%m-%d}) — zapieczętowany do bramki 4")

    files = [p for y in range(start.year, end.year + 1)
             if (p := root / f"symbol={symbol}" / f"year={y}" / "bars.parquet").exists()]
    if not files:
        return pl.DataFrame(schema=BAR_SCHEMA)
    return (
        pl.scan_parquet(files, hive_partitioning=False)
        .filter(pl.col("ts").is_between(start, end, closed="both"))
        .sort("ts")
        .collect()
    )


def is_cross(symbol: str) -> bool:
    """Para bez USD. Podłoga kosztu dla crossów jest wyższa (ADR-024)."""
    return "USD" not in symbol


def cost_model_for(symbol: str, cfg: dict) -> CostModel:
    """Model kosztów symbolu wprost z konfiguracji — bez wartości w kodzie."""
    c = cfg["costs"]
    floor = c["min_roundturn_cost_pips"]["fx_crosses" if is_cross(symbol) else "fx_majors"]
    return CostModel(
        pip=pip_size(symbol),
        min_roundturn_pips=floor,
        entry_slippage_x_spread=c["slippage_entry_x_spread"],
        stop_slippage_x_spread=c["slippage_stop_x_spread"],
    )
