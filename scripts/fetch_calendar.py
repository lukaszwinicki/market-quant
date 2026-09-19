#!/usr/bin/env python
"""Pobierz kalendarz wydarzeń makro ze źródeł oficjalnych (ADR-032).

    python scripts/fetch_calendar.py                    # wszystkie źródła
    python scripts/fetch_calendar.py --sources fomc --years 2015 2025

Surowe strony trafiają do `data/raw/calendar/<źródło>/` i nie są pobierane
ponownie — wynik da się odtworzyć bez sieci. Wynik: `data/calendar/<źródło>.parquet`,
zwalidowany (`validate_calendar`). Na końcu raport pokrycia serii HIGH
dla walut kohorty A.

Zaimplementowane źródła: fomc, fred (dane USA; wymaga FRED_API_KEY w
środowisku albo w `.env`, oraz potwierdzonych godzin w
`config/calendar_times.yaml`). Pozostałe serie — patrz „Stan” w CLAUDE.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import polars as pl
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import calendar_bea as bea  # noqa: E402
from src.data import calendar_bls as bls  # noqa: E402
from src.data import calendar_boc as boc  # noqa: E402
from src.data import calendar_census as census  # noqa: E402
from src.data import calendar_ecb as ecb  # noqa: E402
from src.data import calendar_fomc as fomc  # noqa: E402
from src.data import calendar_fred as fred  # noqa: E402
from src.data import calendar_statcan as statcan  # noqa: E402
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


def fetch_bytes(url: str, cache: Path) -> bytes:
    """Plik binarny (PDF) z cache albo z sieci (i do cache)."""
    path = cache / re.sub(r"[^A-Za-z0-9._-]", "_", url.split("://", 1)[1])
    if path.exists():
        return path.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    if not data:
        raise RuntimeError(f"{url}: pusta odpowiedź")
    cache.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    time.sleep(PAUSE_S)
    return data


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


def fred_key() -> str:
    """Klucz z środowiska albo z `.env`. Nigdy nie wypisywany."""
    if key := os.environ.get("FRED_API_KEY"):
        return key
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("FRED_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    raise RuntimeError("brak FRED_API_KEY (środowisko albo .env)")


def fred_get(endpoint: str, cache: Path, **params) -> dict:
    """Zapytanie FRED z cache. Nazwa pliku cache i log bez klucza."""
    tag = endpoint.replace("/", "_") + "_" + "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
    path = cache / (re.sub(r"[^A-Za-z0-9._-]", "_", tag) + ".json")
    if path.exists():
        return json.loads(path.read_text())
    q = urllib.parse.urlencode({"api_key": fred_key(), "file_type": "json", **params})
    with urllib.request.urlopen(f"https://api.stlouisfed.org/fred/{endpoint}?{q}", timeout=30) as r:
        data = json.load(r)
    cache.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    time.sleep(PAUSE_S)
    return data


def build_fred(years: range) -> pl.DataFrame:
    cache = RAW / "fred"
    times = yaml.safe_load((ROOT / "config" / "calendar_times.yaml").read_text())
    times = times["fred_release_times"]
    start, end = dt.date(years.start, 1, 1), dt.date(years.stop - 1, 12, 31)
    rows = []
    for name, (series_id, release_id) in fred.SERIES.items():
        if name in fred.FROM_OTHER_SOURCE:
            continue
        rel = fred_get("series/release", cache, series_id=series_id)["releases"][0]
        if rel["id"] != release_id:
            raise RuntimeError(f"{series_id}: publikacja {rel['id']}, oczekiwana {release_id}")
        obs = fred_get("series/observations", cache, series_id=series_id,
                       realtime_start=f"{years.start - 1}-01-01", realtime_end="9999-12-31",
                       output_type=4, observation_start=f"{years.start - 1}-01-01")["observations"]
        dates = fred.first_release_dates(obs)
        try:
            at, tz = fred.release_time(times[name], name)
        except PermissionError as e:
            log.warning("%s — pomijam (%d dat czeka na godzinę)", e,
                        sum(start <= d <= end for d in dates))
            continue
        rows += fred.events_for(name, dates, at, tz, start, end)
        log.info("FRED %s: %d publikacji", name, sum(start <= d <= end for d in dates))
    return pl.DataFrame(rows, schema=CALENDAR_SCHEMA)


def alfred_first_releases(name: str, years: range) -> list[dt.date]:
    series_id, _ = fred.SERIES[name]
    obs = fred_get("series/observations", RAW / "fred", series_id=series_id,
                   realtime_start=f"{years.start - 1}-01-01", realtime_end="9999-12-31",
                   output_type=4, observation_start=f"{years.start - 1}-01-01")["observations"]
    return fred.first_release_dates(obs)


def build_bea(years: range) -> pl.DataFrame:
    """PCE i GDP advance z bea.gov — godzina z embarga każdego komunikatu."""
    cache = RAW / "bea"
    start, end = dt.date(years.start, 1, 1), dt.date(years.stop - 1, 12, 31)
    rows = []
    for name in bea.PRODUCTS:
        found: dict[str, str] = {}
        for page in range(200):
            listing = bea.archive_rows(fetch(bea.archive_url(name, page), cache))
            if not listing:
                break
            for url, year, title in listing:
                if years.start <= year <= years.stop - 1 and bea.wanted(name, title):
                    found[url] = title
            if min(y for _, y, _ in listing) < years.start:
                break
        events = []
        for url in sorted(found):
            t = bea.embargo_time_utc(fetch(url, cache), url)
            if start <= t.date() <= end:
                events.append({"timestamp_utc": t, "currency": "USD", "name": name,
                               "rank": "HIGH", "source": url})

        # Krzyżowo z ALFRED: te same dni co pierwsze publikacje okresów.
        bea_days = {e["timestamp_utc"].date() for e in events}
        alfred = {d for d in alfred_first_releases(name, years) if start <= d <= end}
        if bea_days != alfred:
            raise RuntimeError(
                f"{name}: BEA vs ALFRED — tylko BEA: {sorted(bea_days - alfred)}, "
                f"tylko ALFRED: {sorted(alfred - bea_days)}")
        hours = pl.Series([e["timestamp_utc"] for e in events]).dt.strftime("%H:%M")
        log.info("BEA %s: %d publikacji, godziny UTC %s", name, len(events),
                 dict(sorted(hours.value_counts().iter_rows())))
        rows += events
    return pl.DataFrame(rows, schema=CALENDAR_SCHEMA)


def check_against_alfred(name: str, events: list[dict], years: range) -> None:
    """Dni publikacji muszą się zgadzać z ALFRED co do dnia — inaczej błąd."""
    start, end = dt.date(years.start, 1, 1), dt.date(years.stop - 1, 12, 31)
    days = {e["timestamp_utc"].astimezone(bls.NY).date() for e in events}
    alfred = {d for d in alfred_first_releases(name, years) if start <= d <= end}
    if days != alfred:
        raise RuntimeError(f"{name}: źródło vs ALFRED — tylko źródło: {sorted(days - alfred)}, "
                           f"tylko ALFRED: {sorted(alfred - days)}")


def build_bls(years: range) -> pl.DataFrame:
    """CPI i NFP z rocznych kalendarzy BLS zapisanych ręcznie (bls.gov: 403)."""
    cache = RAW / "bls"
    pages = {}
    for y in years:
        url = bls.schedule_url(y)
        path = cache / re.sub(r"[^A-Za-z0-9._-]", "_", url.split("://", 1)[1])
        if not path.exists():
            raise RuntimeError(f"brak {path} — bls.gov blokuje skrypty; zapisz {url} "
                               "w przeglądarce jako HTML")
        pages[y] = (url, path.read_text(encoding="utf-8", errors="replace"))
    rows = []
    for name in bls.TITLES:
        events = [{"timestamp_utc": t, "currency": "USD", "name": name, "rank": "HIGH",
                   "source": url}
                  for y, (url, html) in pages.items()
                  for t in bls.release_times_utc(html, name) if t.year == y]
        check_against_alfred(name, events, years)
        hours = pl.Series([e["timestamp_utc"].astimezone(bls.NY).strftime("%H:%M")
                           for e in events])
        log.info("BLS %s: %d publikacji, godziny ET %s", name, len(events),
                 dict(sorted(hours.value_counts().iter_rows())))
        rows += events
    return pl.DataFrame(rows, schema=CALENDAR_SCHEMA)


def build_census(years: range) -> pl.DataFrame:
    """Sprzedaż detaliczna: PDF-y archiwalne do 2019, kalendarze roczne od 2020."""
    import io

    from pypdf import PdfReader

    # pypdf ostrzega o czcionkach CFF bez fontTools — dotyczy glifów spoza
    # nagłówka; nagłówek i tak jest weryfikowany regexem i datą z ALFRED.
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    cache = RAW / "census"
    times = []
    old = [y for y in years if y < census.FIRST_LISTVIEW_YEAR]
    if old:
        # Miesiąc danych poprzedza publikację o ~2 tygodnie: dane z XII roku
        # poprzedniego wychodzą w styczniu pierwszego roku zakresu.
        first = f"{(old[0] - 1) % 100:02d}12"
        last = f"{old[-1] % 100:02d}12"
        for url in census.historic_pdf_urls(fetch(census.HISTORIC_PAGE, cache), first, last):
            pdf = PdfReader(io.BytesIO(fetch_bytes(url, cache)))
            t = census.pdf_release_time_utc(pdf.pages[0].extract_text(), url)
            if t.year in old:
                times.append((t, url))
    for y in (y for y in years if y >= census.FIRST_LISTVIEW_YEAR):
        url = census.listview_url(y)
        times += [(t, url) for t in census.listview_times_utc(fetch(url, cache)) if t.year == y]

    events = [{"timestamp_utc": t, "currency": "USD", "name": "US_RETAIL_SALES",
               "rank": "HIGH", "source": url} for t, url in sorted(times)]
    check_against_alfred("US_RETAIL_SALES", events, years)
    hours = pl.Series([e["timestamp_utc"].astimezone(census.NY).strftime("%H:%M")
                       for e in events])
    log.info("Census US_RETAIL_SALES: %d publikacji, godziny ET %s", len(events),
             dict(sorted(hours.value_counts().iter_rows())))
    return pl.DataFrame(events, schema=CALENDAR_SCHEMA)


def build_ecb(years: range) -> pl.DataFrame:
    """Decyzje EBC i konferencje — konferencja z komunikatu, decyzja wg ecb.pr220627."""
    cache = RAW / "ecb"
    rows = []
    for y in years:
        meetings = 0
        for day, url in ecb.decision_releases(fetch(ecb.index_url(y), cache)):
            if day.year != y:
                continue
            times = ecb.meeting_times_utc(fetch(url, cache), day, url)
            if times is None:
                log.info("EBC %s: bez konferencji — pomijam (%s)", day, url)
                continue
            decision, conf = times
            rows += [
                {"timestamp_utc": decision, "currency": "EUR", "name": "ECB_RATE",
                 "rank": "HIGH", "source": url},
                {"timestamp_utc": conf, "currency": "EUR", "name": "ECB_PRESS_CONF",
                 "rank": "HIGH", "source": url},
            ]
            meetings += 1
        log.info("EBC %d: %d posiedzeń z konferencją", y, meetings)
    return pl.DataFrame(rows, schema=CALENDAR_SCHEMA)


def build_boc(years: range) -> pl.DataFrame:
    """Decyzje BoC: daty i godziny z rocznych harmonogramów, sprawdzane z komunikatami."""
    cache = RAW / "boc"
    decisions, schedules = {}, {}
    for page in range(1, 200):
        d, s = boc.listing_links(fetch(boc.listing_url(page), cache))
        if not d:
            raise RuntimeError(f"BoC: strona listy {page} bez decyzji — zmiana układu?")
        decisions.update(d)
        schedules.update(s)
        # Harmonogram na rok R wychodzi latem roku R − 1.
        if min(d).year < years.start - 1:
            break
    parsed = []
    for url, published in sorted(schedules.items(), key=lambda kv: kv[1]):
        if published[0] >= years.start - 1:
            dates, at = boc.schedule_dates(fetch(url, cache), url)
            parsed.append((published, dates, at, url))
    rows = [{"timestamp_utc": t, "currency": "CAD", "name": "BOC_RATE", "rank": "HIGH",
             "source": url}
            for t, url in boc.scheduled_times_utc(parsed, decisions)
            if years.start <= t.year <= years.stop - 1]
    hours = pl.Series([r["timestamp_utc"].astimezone(boc.ET).strftime("%Y %H:%M") for r in rows])
    log.info("BoC BOC_RATE: %d decyzji, rok i godzina ET %s", len(rows),
             dict(sorted(hours.value_counts().iter_rows())))
    return pl.DataFrame(rows, schema=CALENDAR_SCHEMA)


def pdf_first_page(url: str, cache: Path) -> str:
    import io

    from pypdf import PdfReader

    logging.getLogger("pypdf").setLevel(logging.ERROR)
    return PdfReader(io.BytesIO(fetch_bytes(url, cache))).pages[0].extract_text()


def build_statcan(years: range) -> pl.DataFrame:
    """CPI Kanady: daty z kalendarza wskaźników, godzina z nagłówka każdego PDF."""
    cache = RAW / "statcan"
    key = fetch(statcan.KEY_INDICATORS, cache)
    rows = []
    for name in statcan.TITLES:
        events = []
        for day, url in statcan.releases(key, name):
            if years.start <= day.year <= years.stop - 1:
                if url is None:
                    raise RuntimeError(f"StatCan {name} {day}: publikacja bez komunikatu")
                t = statcan.release_time_utc(pdf_first_page(url, cache), day, url)
                events.append({"timestamp_utc": t, "currency": "CAD", "name": name,
                               "rank": "HIGH", "source": url})
        hours = pl.Series([e["timestamp_utc"].astimezone(statcan.ET).strftime("%H:%M")
                           for e in events])
        log.info("StatCan %s: %d publikacji, godziny ET %s", name, len(events),
                 dict(sorted(hours.value_counts().iter_rows())))
        rows += events
    return pl.DataFrame(rows, schema=CALENDAR_SCHEMA)


SOURCES = {"fomc": build_fomc, "fred": build_fred, "bea": build_bea, "bls": build_bls,
           "census": build_census, "ecb": build_ecb, "boc": build_boc, "statcan": build_statcan}


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
