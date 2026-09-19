#!/usr/bin/env python
"""Pobierz kalendarz wydarzeń makro ze źródeł oficjalnych (ADR-032).

    python scripts/fetch_calendar.py                    # wszystkie źródła
    python scripts/fetch_calendar.py --sources fomc --years 2015 2025

Surowe strony trafiają do `data/raw/calendar/<źródło>/` i nie są pobierane
ponownie — wynik da się odtworzyć bez sieci. Wynik: `data/calendar/<źródło>.parquet`,
zwalidowany (`validate_calendar`). Na końcu raport pokrycia serii HIGH
dla walut kohorty A.

Zaimplementowane źródła: fomc. Pozostałe serie — patrz „Stan” w CLAUDE.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import re
import sys
import time
import urllib.request
from pathlib import Path

import polars as pl
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import calendar_fomc as fomc  # noqa: E402
from src.data.calendar import (  # noqa: E402
    CALENDAR_SCHEMA, coverage_gaps, load_calendar, validate_calendar,
)

UTC = dt.timezone.utc
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "calendar"
OUT = ROOT / "data" / "calendar"
USER_AGENT = "Mozilla/5.0 (market-quant research; schedule only)"
PAUSE_S = 1.0

log = logging.getLogger("fetch_calendar")


def fetch(url: str, cache: Path) -> str:
    """Strona z cache albo z sieci (i do cache). Pusta odpowiedź = błąd."""
    name = re.sub(r"[^A-Za-z0-9._-]", "_", url.split("://", 1)[1])
    path = cache / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", errors="replace")
    if not html.strip():
        raise RuntimeError(f"{url}: pusta odpowiedź")
    cache.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    time.sleep(PAUSE_S)
    return html


def build_fomc(years: range) -> pl.DataFrame:
    cache = RAW / "fomc"
    current = fetch(f"{fomc.BASE}/monetarypolicy/fomccalendars.htm", cache)
    panel_years = [int(y) for y in re.findall(r"(\d{4}) FOMC Meetings", current)]
    first_current = min(panel_years)
    rows = []
    for y in years:
        html = fetch(fomc.calendar_url(y, first_current), cache)
        meetings = fomc.scheduled_statements(html, y)
        if not meetings:
            raise RuntimeError(f"FOMC {y}: brak planowanych posiedzeń na stronie")
        for label, url in meetings:
            t = fomc.release_time_utc(fetch(url, cache), url)
            rows.append({"timestamp_utc": t, "currency": "USD", "name": "FOMC",
                         "rank": "HIGH", "source": url})
        log.info("FOMC %d: %d posiedzeń", y, len(meetings))
    return pl.DataFrame(rows, schema=CALENDAR_SCHEMA)


SOURCES = {"fomc": build_fomc}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sources", nargs="*", choices=sorted(SOURCES), default=sorted(SOURCES))
    ap.add_argument("--years", nargs=2, type=int, metavar=("OD", "DO"))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        datefmt="%H:%M:%S")

    cfg = yaml.safe_load((ROOT / "config" / "v1_baseline.yaml").read_text())
    splits = cfg["data"]["splits"]
    # Pierwszy rok HANDLU, nie danych: `vol_pct_252` wymaga 252 dni, więc
    # rok startu danych to wyłącznie rozgrzewka cech — V1a w nim nie wchodzi
    # i blackout nie ma czego blokować. (FOMC 2015 nie podaje też godziny.)
    y0, y1 = args.years or (int(str(splits["research"]["start"])[:4]) + 1,
                            int(str(splits["sealed_holdout"]["end"])[:4]))

    OUT.mkdir(parents=True, exist_ok=True)
    for name in args.sources:
        events = validate_calendar(SOURCES[name](range(y0, y1 + 1)))
        events.write_parquet(OUT / f"{name}.parquet")
        log.info("%s: %d zdarzeń → %s", name, events.height, OUT / f"{name}.parquet")

    # Pokrycie dla walut kohorty A — dopóki są luki, blackout nie jest kompletny.
    currencies = sorted({s[i:i + 3] for s in cfg["instruments"]["cohort_a"]["symbols"]
                         for i in (0, 3)})
    all_events = load_calendar(sorted(OUT.glob("*.parquet")))
    gaps = coverage_gaps(all_events, currencies,
                         dt.datetime(y0, 1, 1, tzinfo=UTC), dt.datetime(y1, 12, 31, tzinfo=UTC))
    missing = sorted({(c, n) for c, n, _ in gaps})
    log.info("pokrycie: %d serii brakuje w całości lub w części lat", len(missing))
    for c, n in missing:
        yrs = [y for cc, nn, y in gaps if (cc, nn) == (c, n)]
        log.info("  %s %-16s brak w: %s", c, n,
                 "wszystkich latach" if len(yrs) == y1 - y0 + 1 else yrs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
