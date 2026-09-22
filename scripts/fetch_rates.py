#!/usr/bin/env python
"""Pobierz stopy procentowe z FRED i zbuduj raport pokrycia.

    .venv/bin/python scripts/fetch_rates.py
    .venv/bin/python scripts/fetch_rates.py --years 2015 2025

Wynik:
    data/rates/fred.parquet        wszystkie serie, schemat `src/data/rates.py`
    data/raw/rates/*.json          cache surowych odpowiedzi (powtórka bez sieci)
    reports/rates_coverage.md      co jest, czego nie ma i co z tego wynika

Klucz `FRED_API_KEY` z `.env` albo ze środowiska; nigdy nie trafia do cache,
logów ani do wyniku.

UWAGA NA §12. Benchmark carry + trend rankuje waluty po rentowności
2-letniej. FRED ma ją WYŁĄCZNIE dla USD. Skrypt tego nie obchodzi i nie
podstawia zamiennika — wypisuje brak w raporcie, bo podmiana serii
w benchmarku obowiązkowym jest decyzją na ADR, nie szczegółem pobierania.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.rates import (  # noqa: E402
    CARRY_CURRENCIES, COHORT_A_CURRENCIES, KINDS, SCHEMA, coverage_gaps,
)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "rates"
OUT = ROOT / "data" / "rates"
REPORT = ROOT / "reports" / "rates_coverage.md"
PAUSE_S = 0.5

log = logging.getLogger("fetch_rates")


def fred_key() -> str:
    """Klucz ze środowiska albo z `.env`. Nigdy nie wypisywany."""
    import os
    if key := os.environ.get("FRED_API_KEY"):
        return key
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("FRED_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    raise RuntimeError("brak FRED_API_KEY (środowisko albo .env)")


def fred_get(endpoint: str, **params) -> dict:
    """Zapytanie FRED z cache. Nazwa pliku cache bez klucza."""
    tag = endpoint.replace("/", "_") + "_" + "_".join(
        f"{k}-{v}" for k, v in sorted(params.items()))
    path = RAW / (re.sub(r"[^A-Za-z0-9._-]", "_", tag) + ".json")
    if path.exists():
        return json.loads(path.read_text())
    q = urllib.parse.urlencode({"api_key": fred_key(), "file_type": "json", **params})
    with urllib.request.urlopen(
            f"https://api.stlouisfed.org/fred/{endpoint}?{q}", timeout=30) as r:
        data = json.load(r)
    RAW.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    time.sleep(PAUSE_S)
    return data


def observations(series_id: str, start: dt.date, end: dt.date) -> list[tuple[dt.date, float]]:
    """(data, wartość) z pominięciem kropek — FRED tak oznacza brak odczytu."""
    obs = fred_get("series/observations", series_id=series_id,
                   observation_start=start.isoformat(),
                   observation_end=end.isoformat())["observations"]
    return [(dt.date.fromisoformat(o["date"]), float(o["value"]))
            for o in obs if o["value"] not in (".", "")]


def build(start: dt.date, end: dt.date) -> pl.DataFrame:
    rows = []
    for kind, registry in KINDS.items():
        for ccy, series_id in registry.items():
            try:
                data = observations(series_id, start, end)
            except urllib.error.HTTPError as e:      # noqa: F821 (urllib.error via request)
                log.warning("%s (%s %s): %s", series_id, ccy, kind, e)
                continue
            log.info("%-14s %s %-13s %d obserwacji", series_id, ccy, kind, len(data))
            rows += [{"date": d, "currency": ccy, "kind": kind,
                      "value": v, "series": series_id} for d, v in data]
    return pl.DataFrame(rows, schema=SCHEMA) if rows else pl.DataFrame(schema=SCHEMA)


def render(rates: pl.DataFrame, start: dt.date, end: dt.date) -> str:
    months = (end.year - start.year) * 12 + (end.month - start.month) + 1
    lines = [
        "# Pokrycie stóp procentowych",
        "",
        f"> Wygenerowano: {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC · "
        f"źródło FRED · {start} → {end} ({months} miesięcy)",
        "",
        "## Serie",
        "",
        "| Rodzaj | Waluta | Seria | Obserwacji | Od | Do |",
        "|---|---|---|---|---|---|",
    ]
    for kind in KINDS:
        part = rates.filter(pl.col("kind") == kind)
        for ccy in CARRY_CURRENCIES:
            one = part.filter(pl.col("currency") == ccy)
            if one.is_empty():
                lines.append(f"| {kind} | {ccy} | — | **brak** | | |")
            else:
                lines.append(f"| {kind} | {ccy} | `{one['series'][0]}` | {one.height} | "
                             f"{one['date'].min()} | {one['date'].max()} |")
    lines += ["", "## Luki w kohorcie A (USD, EUR, GBP, JPY, AUD, CAD)", ""]
    for kind in ("overnight", "interbank_3m"):
        gaps = coverage_gaps(rates, COHORT_A_CURRENCIES, kind, start, end)
        lines.append(f"- `{kind}`: " + (
            ", ".join(f"{c} brakuje {n} mies." for c, n in gaps) if gaps
            else f"**komplet** — {months}/{months} miesięcy dla każdej waluty"))

    missing_2y = [c for c in CARRY_CURRENCIES
                  if rates.filter((pl.col("kind") == "yield_2y")
                                  & (pl.col("currency") == c)).is_empty()]
    lines += [
        "",
        "## Benchmark carry + trend (SPEC §12) — NIE DA SIĘ POLICZYĆ ZGODNIE ZE SPEC",
        "",
        "Benchmark rankuje waluty po `yield_2y`. FRED nie ma tej serii dla: "
        + ", ".join(f"**{c}**" for c in missing_2y) + ".",
        "",
        "Wyszukiwanie po nazwie („2-Year Government Benchmark Bond Yield”, "
        "„2-year government bond yield”) zwraca wyłącznie Turcję i Meksyk "
        "(„6-month to 2-year”) oraz serie niezwiązane. To nie jest kwestia "
        "identyfikatora — tych danych na FRED nie ma.",
        "",
        "Jedyna jednorodna seria terminowa dla wszystkich ośmiu walut to "
        "`interbank_3m` (OECD, miesięczna). Podmiana `yield_2y` → `interbank_3m` "
        "zmienia benchmark obowiązkowy, więc wymaga ADR-u, a nie decyzji w skrypcie. "
        "Alternatywa: inne źródło (OECD.Stat, Investing.com, dane banków centralnych) "
        "— osobny odcinek pracy, porównywalny z kalendarzem.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    # OD 2014, nie 2015: `rate_on()` czyta miesiąc poprzedzający dzień
    # decyzji, więc przebieg startujący 2015-01-01 potrzebuje grudnia 2014
    # (ADR-047). Pobranie od roku splitu zostawia pierwszy miesiąc bez stopy.
    ap.add_argument("--years", nargs=2, type=int, default=[2014, 2025],
                    metavar=("OD", "DO"))
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s",
                        datefmt="%H:%M:%S")

    start = dt.date(args.years[0], 1, 1)
    end = dt.date(args.years[1], 12, 31)

    rates = build(start, end)
    if rates.is_empty():
        log.error("nie pobrano żadnej serii")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    rates.sort("kind", "currency", "date").write_parquet(OUT / "fred.parquet")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(render(rates, start, end), encoding="utf-8")

    log.info("%d wierszy → %s", rates.height, OUT / "fred.parquet")
    log.info("raport: %s", REPORT)

    gaps = coverage_gaps(rates, COHORT_A_CURRENCIES, "overnight", start, end)
    if gaps:
        log.warning("luki overnight w kohorcie A: %s", gaps)
        return 1
    log.info("overnight dla kohorty A: komplet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
