"""Kalendarz wydarzeń makro i blackout (PROJECT_SPEC §5.2, §7.2, ADR-005, ADR-032).

ZAWARTOŚĆ

Wyłącznie harmonogram: `(timestamp_utc, currency, name, rank, source)`.
Żadnych wartości — actual/consensus/previous nie mają darmowego archiwum
point-in-time i są zakazane w V1. Kolumna z wartością = odrzucenie pliku.

POCHODZENIE (ADR-032)

Każdy wiersz pochodzi ze strony oficjalnej, parsowanej automatycznie,
z URL-em w `source`. Terminów nie wpisuje się ręcznie ani z pamięci LLM:
model, którego dane treningowe obejmują okres testu, „zna" kalendarz
razem z tym, co się po nim działo. Tylko zdarzenia PLANOWANE — decyzja
nadzwyczajna nie była znana z wyprzedzeniem.

POKRYCIE

Brak zdarzeń w kalendarzu wygląda dokładnie tak samo jak brak blackoutu.
Seria, której nie pobrano, po cichu zamieniłaby blackout w no-op i
backtest handlowałby w publikacjach. Dlatego `coverage_gaps()` wymaga
każdej serii HIGH dla walut pary w każdym roku okresu — zanim kalendarz
trafi do backtestu.

OKNO (ADR-032)

Wejście w chwili t jest zablokowane, gdy dla którejkolwiek waluty pary
istnieje zdarzenie HIGH o czasie e: e − 30 min ≤ t ≤ e + 120 min.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

UTC = dt.timezone.utc

CALENDAR_SCHEMA: dict[str, pl.DataType] = {
    "timestamp_utc": pl.Datetime("ms", "UTC"),
    "currency": pl.Utf8,
    "name": pl.Utf8,
    "rank": pl.Utf8,
    "source": pl.Utf8,
}
RANKS = ("HIGH",)
FORBIDDEN_COLUMNS = {"actual", "consensus", "forecast", "previous", "surprise",
                     "value", "revised", "estimate"}

# Lista zamknięta rangi HIGH (§7.2, config `blackout.high_impact_events`),
# rozpisana na serie per waluta. Tylko waluty, które występują w kohortach.
HIGH_SERIES: dict[str, tuple[str, ...]] = {
    "USD": ("FOMC", "US_CPI", "US_NFP", "US_PCE", "US_RETAIL_SALES", "US_GDP_ADVANCE"),
    "EUR": ("ECB_RATE", "ECB_PRESS_CONF", "EA_HICP_FLASH"),
    "GBP": ("BOE_RATE", "UK_CPI", "UK_LABOUR"),
    "JPY": ("BOJ_RATE", "JP_CPI"),
    "AUD": ("RBA_RATE", "AU_CPI"),
    "CAD": ("BOC_RATE", "CA_CPI"),
    "NZD": ("RBNZ_RATE", "NZ_CPI"),
    "CHF": ("SNB_RATE", "CH_CPI"),
}


def pair_currencies(symbol: str) -> tuple[str, str]:
    if len(symbol) != 6:
        raise ValueError(f"{symbol}: blackout walutowy tylko dla par FX")
    return symbol[:3], symbol[3:]


def validate_calendar(events: pl.DataFrame) -> pl.DataFrame:
    """Sprawdź schemat i zawartość; zwróć ramkę posortowaną po czasie."""
    cols = {c.lower() for c in events.columns}
    if bad := cols & FORBIDDEN_COLUMNS:
        raise ValueError(f"kalendarz zawiera wartości {sorted(bad)} — zakazane (ADR-005)")
    missing = set(CALENDAR_SCHEMA) - set(events.columns)
    if missing:
        raise ValueError(f"brak kolumn {sorted(missing)}")
    extra = set(events.columns) - set(CALENDAR_SCHEMA)
    if extra:
        raise ValueError(f"nieznane kolumny {sorted(extra)} — tylko harmonogram")
    if events.schema["timestamp_utc"] != CALENDAR_SCHEMA["timestamp_utc"]:
        raise ValueError(f"timestamp_utc musi być {CALENDAR_SCHEMA['timestamp_utc']}, "
                         f"jest {events.schema['timestamp_utc']}")
    if events.select(pl.all().is_null().any()).row(0) != (False,) * events.width:
        raise ValueError("puste pola w kalendarzu")
    known = {(c, n) for c, ns in HIGH_SERIES.items() for n in ns}
    pairs = set(events.select("currency", "name").unique().iter_rows())
    if unknown := pairs - known:
        raise ValueError(f"serie spoza listy zamkniętej: {sorted(unknown)}")
    if bad_rank := set(events["rank"].unique()) - set(RANKS):
        raise ValueError(f"nieznana ranga {sorted(bad_rank)}")
    if not events["source"].str.starts_with("https://").all():
        raise ValueError("każdy wiersz musi mieć URL źródła (https://)")
    dup = events.select("timestamp_utc", "currency", "name").is_duplicated()
    if dup.any():
        raise ValueError(f"{int(dup.sum())} zduplikowanych zdarzeń")
    return events.select(list(CALENDAR_SCHEMA)).sort("timestamp_utc")


def release_time(entry: dict, name: str) -> tuple[dt.time, ZoneInfo]:
    """Godzina i strefa z `config/calendar_times.yaml` — dla źródeł, które
    podają tylko datę (ADR-032). Niepotwierdzona przez użytkownika = błąd."""
    if not entry.get("verified"):
        raise PermissionError(f"{name}: godzina niepotwierdzona (verified: false)")
    if not entry.get("local_time") or not entry.get("quote"):
        raise ValueError(f"{name}: potwierdzona godzina wymaga local_time i cytatu ze źródła")
    hh, mm = map(int, entry["local_time"].split(":"))
    return dt.time(hh, mm), ZoneInfo(entry["timezone"])


def load_calendar(paths: list[Path]) -> pl.DataFrame:
    """Scal pliki Parquet ze źródeł i zwaliduj całość."""
    if not paths:
        return pl.DataFrame(schema=CALENDAR_SCHEMA)
    return validate_calendar(pl.concat([pl.read_parquet(p) for p in paths]))


def coverage_gaps(events: pl.DataFrame, currencies: list[str],
                  start: dt.datetime, end: dt.datetime) -> list[tuple[str, str, int]]:
    """(waluta, seria, rok) bez ani jednego zdarzenia w [start, end].

    Pusta lista = kalendarz nadaje się do backtestu tego okresu.
    Rok liczony częściowo na krańcach okresu — jeśli okres obejmuje
    tylko fragment roku, wymagane jest zdarzenie w tym fragmencie
    dopiero wtedy, gdy fragment ma co najmniej 92 dni (kwartalne CPI).
    """
    have = set(
        events.filter(pl.col("timestamp_utc").is_between(start, end))
        .select("currency", "name", pl.col("timestamp_utc").dt.year().alias("y"))
        .unique().iter_rows()
    )
    gaps = []
    for y in range(start.year, end.year + 1):
        y0 = max(start, dt.datetime(y, 1, 1, tzinfo=UTC))
        y1 = min(end, dt.datetime(y + 1, 1, 1, tzinfo=UTC))
        if (y1 - y0).days < 92:
            continue
        for c in currencies:
            for name in HIGH_SERIES[c]:
                if (c, name, y) not in have:
                    gaps.append((c, name, y))
    return gaps


def require_coverage(events: pl.DataFrame, symbols: list[str],
                     start: dt.datetime, end: dt.datetime) -> None:
    """Przerwij, jeśli kalendarz nie pokrywa wszystkich serii HIGH okresu.

    Brak serii wygląda w `blackout()` identycznie jak brak zdarzenia, więc
    przebieg na dziurawym kalendarzu po cichu handlowałby w publikacjach
    (ADR-032 pkt 4). Wołane przez przebiegi, które używają blackoutu —
    zanim policzą cokolwiek.
    """
    currencies = sorted({c for s in symbols for c in pair_currencies(s)})
    gaps = coverage_gaps(events, currencies, start, end)
    if not gaps:
        return
    per_series: dict[tuple[str, str], list[int]] = {}
    for currency, name, year in gaps:
        per_series.setdefault((currency, name), []).append(year)
    opis = "; ".join(f"{c} {n}: {years}" for (c, n), years in sorted(per_series.items()))
    raise ValueError(f"kalendarz nie pokrywa {len(per_series)} serii w okresie "
                     f"{start:%Y-%m-%d}..{end:%Y-%m-%d} — {opis}")


def blackout(decision_ts: pl.Series, symbol: str, events: pl.DataFrame,
             before_min: int, after_min: int) -> pl.Series:
    """True, gdy e − before ≤ t ≤ e + after dla zdarzenia HIGH waluty pary.

    Równoważnie: istnieje e ∈ [t − after, t + before]. Wyszukiwanie
    binarne po posortowanych czasach zdarzeń — bez pętli po barach.
    """
    ccy = pair_currencies(symbol)
    e = (events.filter(pl.col("currency").is_in(ccy) & (pl.col("rank") == "HIGH"))
         ["timestamp_utc"].sort().to_numpy())
    t = decision_ts.cast(pl.Datetime("ms", "UTC")).to_numpy()
    if len(e) == 0:
        return pl.Series("blackout", np.zeros(len(t), dtype=bool))
    lo = t - np.timedelta64(after_min, "m")
    hi = t + np.timedelta64(before_min, "m")
    i = np.searchsorted(e, lo, side="left")
    hit = (i < len(e)) & (e[np.minimum(i, len(e) - 1)] <= hi)
    return pl.Series("blackout", hit)
