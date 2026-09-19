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
import gzip
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html import unescape as html_unescape
from pathlib import Path

import polars as pl
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import calendar_abs as abs_  # noqa: E402
from src.data import calendar_bea as bea  # noqa: E402
from src.data import calendar_bls as bls  # noqa: E402
from src.data import calendar_boc as boc  # noqa: E402
from src.data import calendar_boe as boe  # noqa: E402
from src.data import calendar_boj as boj  # noqa: E402
from src.data import calendar_census as census  # noqa: E402
from src.data import calendar_ecb as ecb  # noqa: E402
from src.data import calendar_eurostat as eurostat  # noqa: E402
from src.data import calendar_fomc as fomc  # noqa: E402
from src.data import calendar_fred as fred  # noqa: E402
from src.data import calendar_jp as jp  # noqa: E402
from src.data import calendar_ons as ons  # noqa: E402
from src.data import calendar_rba as rba  # noqa: E402
from src.data import calendar_statcan as statcan  # noqa: E402
from src.data.calendar import (  # noqa: E402
    CALENDAR_SCHEMA, coverage_gaps, load_calendar, release_time, validate_calendar,
)

UTC = dt.timezone.utc
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "calendar"
OUT = ROOT / "data" / "calendar"
USER_AGENT = "Mozilla/5.0 (market-quant research; schedule only)"
PAUSE_S = 1.0
EUROSTAT_PAUSE_S = 2.5          # ec.europa.eu odpowiada 429 po kilkunastu szybkich zapytaniach

log = logging.getLogger("fetch_calendar")


TRANSIENT_STATUS = {429, 502, 503, 504}     # limit tempa albo chwilowa awaria serwisu


def urlopen_retry(req: urllib.request.Request, timeout: int = 60) -> bytes:
    """Treść odpowiedzi; przy limicie tempa albo zerwanym połączeniu ponawia z odczekaniem."""
    for wait in (15, 30, 60, 120, 300, 0):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError) as e:
            transient = (isinstance(e, TimeoutError)
                         or isinstance(getattr(e, "reason", None),
                                       (ConnectionRefusedError, TimeoutError))
                         or getattr(e, "code", None) in TRANSIENT_STATUS)
            if not wait or not transient:
                raise
            log.info("%s — ponawiam za %ds", e, wait)
            time.sleep(wait)
    raise RuntimeError("nieosiągalne")


def fetch_bytes(url: str, cache: Path) -> bytes:
    """Plik binarny (PDF) z cache albo z sieci (i do cache)."""
    path = cache / re.sub(r"[^A-Za-z0-9._-]", "_", url.split("://", 1)[1])
    if path.exists():
        return path.read_bytes()
    data = urlopen_retry(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}))
    if data[:2] == b"\x1f\x8b":          # kopie z Wayback bywają spakowane gzipem
        data = gzip.decompress(data)
    if not data:
        raise RuntimeError(f"{url}: pusta odpowiedź")
    cache.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    time.sleep(PAUSE_S)
    return data


def fetch(url: str, cache: Path, pause: float = PAUSE_S) -> str:
    """Strona z cache albo z sieci (i do cache). Pusta odpowiedź = błąd."""
    name = re.sub(r"[^A-Za-z0-9._-]", "_", url.split("://", 1)[1])
    path = cache / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    raw = urlopen_retry(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}),
                        timeout=30)
    # Kopie z Wayback (`…id_/…`) wracają w oryginalnej postaci, czyli często gzipem.
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    html = raw.decode("utf-8", errors="replace")
    if not html.strip():
        raise RuntimeError(f"{url}: pusta odpowiedź")
    cache.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    time.sleep(pause)
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


def plain_text(html_text: str) -> str:
    """Tekst strony bez znaczników — dla źródeł, które dają to samo w HTML i w PDF."""
    body = re.sub(r"<(script|style)\b.*?</\1>", " ", html_text, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html_unescape(re.sub(r"<[^>]+>", " ", body)))


def pdf_first_page(url: str, cache: Path, pages: int = 1) -> str:
    import io

    from pypdf import PdfReader

    logging.getLogger("pypdf").setLevel(logging.ERROR)
    reader = PdfReader(io.BytesIO(fetch_bytes(url, cache)))
    return " ".join(p.extract_text() for p in reader.pages[:pages])


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


def fetch_post(url: str, form: list[tuple[str, str]], cache: Path) -> str:
    """Odpowiedź POST (formularz) z cache albo z sieci. Nazwa cache z treści formularza."""
    import hashlib

    body = urllib.parse.urlencode(form)
    digest = hashlib.sha256(body.encode()).hexdigest()[:16]
    path = cache / (re.sub(r"[^A-Za-z0-9._-]", "_", url.split("://", 1)[1]) + f"_{digest}.json")
    if path.exists():
        return path.read_text(encoding="utf-8")
    req = urllib.request.Request(url, data=body.encode(), headers={
        "User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"})
    text = urlopen_retry(req).decode("utf-8", errors="replace")
    if not text.strip():
        raise RuntimeError(f"{url}: pusta odpowiedź")
    cache.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    time.sleep(PAUSE_S)
    return text


def release_times_cfg() -> dict:
    return yaml.safe_load((ROOT / "config" / "calendar_times.yaml").read_text())["release_times"]


def build_boe(years: range) -> pl.DataFrame:
    """Decyzje BoE: daty ze stron posiedzeń MPC, godzina z calendar_times.yaml."""
    cache = RAW / "boe"
    scheduled, skipped = set(), set()
    for page in range(1, 50):
        results = json.loads(fetch_post(boe.LISTING_API, boe.LISTING_FORM + [("Page", str(page))],
                                        cache))["Results"]
        if 'href="' not in results:
            break
        s, o = boe.listing_pages(results)
        scheduled |= set(s)
        skipped |= set(o)
    for url in sorted(skipped):
        if any(f"/{y}/" in url for y in years):
            log.info("BoE: pomijam nieplanowe %s", url)
    days = {}
    for url in sorted(scheduled):
        year = int(url.rsplit("/", 2)[1])
        if years.start <= year <= years.stop - 1:
            day = boe.published_on(fetch(url, cache), url)
            if day.strftime("%B").lower() not in url.rsplit("/", 1)[1]:
                raise RuntimeError(f"{url}: publikacja {day} w innym miesiącu niż posiedzenie")
            if day in days:
                raise RuntimeError(f"BoE {day}: dwie strony — {days[day]}, {url}")
            days[day] = url
    try:
        at, tz = release_time(release_times_cfg()["BOE_RATE"], "BOE_RATE")
    except PermissionError as e:
        log.warning("%s — pomijam %d posiedzeń", e, len(days))
        return pl.DataFrame(schema=CALENDAR_SCHEMA)
    rows = [{"timestamp_utc": dt.datetime.combine(d, at, tzinfo=tz).astimezone(UTC),
             "currency": "GBP", "name": "BOE_RATE", "rank": "HIGH", "source": url}
            for d, url in sorted(days.items())]
    counts = pl.Series([d.year for d in days]).value_counts()
    log.info("BoE BOE_RATE: %d posiedzeń, per rok %s", len(rows), dict(sorted(counts.iter_rows())))
    return pl.DataFrame(rows, schema=CALENDAR_SCHEMA)


def build_ons(years: range) -> pl.DataFrame:
    """UK CPI i rynek pracy: kalendarz ONS z godziną każdej publikacji (od 02.2016)."""
    cache = RAW / "ons"
    times = release_times_cfg()
    rows = []
    for name in ons.KEYWORDS:
        events = []
        for y in years:
            items, page = [], 1
            while True:
                html = fetch(ons.calendar_url(name, y, page), cache)
                items += ons.calendar_items(html)
                if len(items) >= ons.result_count(html) or page >= 20:
                    break
                page += 1
            if len(items) != ons.result_count(html):
                raise RuntimeError(f"ONS {name} {y}: {len(items)} pozycji z {ons.result_count(html)}")
            events += [{"timestamp_utc": t, "currency": "GBP", "name": name, "rank": "HIGH",
                        "source": url} for t, url in ons.release_times_utc(items, name)]
        if years.start <= ons.FIRST_CALENDAR_DAY.year <= years.stop - 1:
            url = ons.JAN_2016_BULLETINS[name]
            day = ons.bulletin_release_date(fetch(url, cache), url)
            if day >= ons.FIRST_CALENDAR_DAY:
                raise RuntimeError(f"{url}: {day} — biuletyn miał być sprzed kalendarza")
            try:
                at, tz = release_time(times["ONS_BULLETIN"], "ONS_BULLETIN")
                events.append({"timestamp_utc": dt.datetime.combine(day, at, tzinfo=tz)
                               .astimezone(UTC), "currency": "GBP", "name": name,
                               "rank": "HIGH", "source": url})
            except PermissionError as e:
                log.warning("%s — brak publikacji %s z %s", e, name, day)
        per_year = pl.Series([e["timestamp_utc"].year for e in events]).value_counts()
        if short := sorted((y, n) for y, n in per_year.iter_rows() if n != 12):
            log.warning("ONS %s: lata bez 12 publikacji (rok, liczba): %s", name, short)
        hours = pl.Series([e["timestamp_utc"].astimezone(ons.LONDON).strftime("%Y %H:%M")
                           for e in events])
        log.info("ONS %s: %d publikacji, rok i godzina Londyn %s", name, len(events),
                 dict(sorted(hours.value_counts().iter_rows())))
        rows += events
    return pl.DataFrame(rows, schema=CALENDAR_SCHEMA)


def build_abs(years: range) -> pl.DataFrame:
    """CPI Australii: godzina z każdej strony wydania (ausstats do 06.2020, nowy układ od 09.2019)."""
    cache = RAW / "abs"
    first = years.start - 1                      # wydanie za IV kw. wychodzi w styczniu
    by_period: dict[tuple[str, int], tuple[dt.datetime, str]] = {}

    def add(period: tuple[str, int], t: dt.datetime, url: str) -> None:
        if period in by_period and by_period[period][0] != t:
            raise RuntimeError(f"ABS {period}: {by_period[period]} vs {t} {url}")
        by_period.setdefault(period, (t, url))

    for url in abs_.new_release_urls(fetch(abs_.NEW_LIST, cache)):
        mon, year = url.rsplit("/", 1)[1][:3], int(url[-4:])
        if year >= first:
            add((mon, year), abs_.new_release_time_utc(fetch(url, cache), url), url)
    # Stare adresy okresów, które ma już nowy serwis, przekierowują na niego —
    # nie ma czego porównywać, więc ausstats tylko dla wcześniejszych wydań.
    for url, period in abs_.old_release_urls(fetch(abs_.OLD_LIST, cache)):
        mon, year = period[:3].lower(), int(period[-4:])
        if year >= first and (mon, year) not in by_period:
            add((mon, year), abs_.old_release_time_utc(fetch(url, cache), url), url)

    events = [{"timestamp_utc": t, "currency": "AUD", "name": "AU_CPI", "rank": "HIGH",
               "source": url} for t, url in sorted(by_period.values())
              if years.start <= t.year <= years.stop - 1]
    hours = pl.Series([e["timestamp_utc"].astimezone(abs_.CANBERRA).strftime("%Y %H:%M")
                       for e in events])
    log.info("ABS AU_CPI: %d publikacji, rok i godzina Canberra %s", len(events),
             dict(sorted(hours.value_counts().iter_rows())))
    return pl.DataFrame(events, schema=CALENDAR_SCHEMA)


def build_rba(years: range) -> pl.DataFrame:
    """Decyzje RBA: daty z listy komunikatów, planowość i godzina z harmonogramu."""
    cache = RAW / "rba"
    rows = []
    for y in years:
        page_url = rba.decisions_url(y)
        page = fetch(page_url, cache)
        decisions = rba.decision_dates(page, y, page_url)
        if y in rba.NO_SCHEDULE:
            # Rok bez zapisu harmonogramu: planowość z treści każdego komunikatu.
            at = rba.announced_at(page, page_url)
            times, skipped = {}, []
            for day, url in sorted(decisions.items()):
                if rba.is_regular_meeting(fetch(rba.release_mirror(url), cache)):
                    times[day] = dt.datetime.combine(day, at, tzinfo=rba.SYDNEY).astimezone(UTC)
                else:
                    skipped.append(day)
            log.warning("RBA %d: brak zapisu harmonogramu — planowość z treści komunikatów "
                        "(„%s”), pominięte: %s", y, rba.REGULAR_MEETING, skipped or "brak")
        else:
            url = rba.schedule_url(y)
            times = rba.scheduled_times(fetch(url, cache), y, url)
            if missing := sorted(set(times) - set(decisions)):
                raise RuntimeError(f"RBA {y}: harmonogram ma {missing} bez komunikatu decyzji")
            for day in sorted(set(decisions) - set(times)):
                log.info("RBA %d: pomijam nieplanowe %s (%s)", y, day, decisions[day])
        rows += [{"timestamp_utc": t, "currency": "AUD", "name": "RBA_RATE", "rank": "HIGH",
                  "source": decisions[d]} for d, t in sorted(times.items())]
    hours = pl.Series([r["timestamp_utc"].astimezone(rba.SYDNEY).strftime("%Y %H:%M")
                       for r in rows])
    log.info("RBA RBA_RATE: %d decyzji, rok i godzina Sydney %s", len(rows),
             dict(sorted(hours.value_counts().iter_rows())))
    return pl.DataFrame(rows, schema=CALENDAR_SCHEMA)


def build_jp(years: range) -> pl.DataFrame:
    """CPI Japonii: daty i godziny z plików harmonogramu Statistics Bureau."""
    cache = RAW / "jp"
    # Kopie w kolejności rosnącej daty zapisu: późniejsza poprawia przesunięty termin.
    times: dict[str, dt.datetime] = {}
    for stamp, url in sorted(jp.SCHEDULE_SNAPSHOTS):
        snapshot = jp.snapshot_url(stamp, url)
        times |= jp.release_times_utc(jp.decode(fetch_bytes(snapshot, cache)), snapshot)
    events = [{"timestamp_utc": t, "currency": "JPY", "name": "JP_CPI", "rank": "HIGH",
               "source": jp.CURRENT_XML} for t in sorted(times.values())
              if years.start <= t.astimezone(jp.TOKYO).year <= years.stop - 1]
    per_year = pl.Series([e["timestamp_utc"].astimezone(jp.TOKYO).year for e in events]).value_counts()
    if short := sorted((y, n) for y, n in per_year.iter_rows() if n != 12):
        log.warning("Statistics Bureau JP_CPI: lata bez 12 publikacji: %s", short)
    hours = pl.Series([e["timestamp_utc"].astimezone(jp.TOKYO).strftime("%H:%M") for e in events])
    log.info("Statistics Bureau JP_CPI: %d publikacji, godziny Tokio %s", len(events),
             dict(sorted(hours.value_counts().iter_rows())))
    return pl.DataFrame(events, schema=CALENDAR_SCHEMA)


def build_boj(years: range) -> pl.DataFrame:
    """Decyzje BoJ: dzień z listy protokołów, godzina = koniec posiedzenia z protokołu."""
    cache = RAW / "boj"
    rows = []
    for y in years:
        url = boj.minutes_index_url(y)
        meetings = boj.minutes_links(fetch(url, cache))
        if not meetings:
            raise RuntimeError(f"BoJ {y}: brak protokołów na {url}")
        for day, minutes in meetings:
            if day.year != y:
                continue
            text = (plain_text(fetch(minutes, cache)) if minutes.endswith(".htm")
                    else pdf_first_page(minutes, cache, pages=3))
            if boj.is_unscheduled(text):
                log.info("BoJ %d: pomijam nadzwyczajne %s", y, minutes)
                continue
            t = boj.adjournment_utc(text, day, minutes)
            rows.append({"timestamp_utc": t, "currency": "JPY", "name": "BOJ_RATE",
                         "rank": "HIGH", "source": minutes})
        planned = sum(1 for r in rows if r["timestamp_utc"].astimezone(boj.TOKYO).year == y)
        if planned != 8:
            log.warning("BoJ %d: %d planowych posiedzeń zamiast 8", y, planned)
    hours = pl.Series([r["timestamp_utc"].astimezone(boj.TOKYO).strftime("%H:%M") for r in rows])
    log.info("BoJ BOJ_RATE: %d decyzji, koniec posiedzenia (Tokio) %s", len(rows),
             dict(sorted(hours.value_counts().iter_rows())))
    return pl.DataFrame(rows, schema=CALENDAR_SCHEMA)


def fetch_title(url: str, cache: Path, pause: float = PAUSE_S) -> str | None:
    """Sam tytuł strony, zapisany w cache zamiast całej strony.

    Sondowanie Eurostatu to ponad tysiąc adresów po ~170 kB; z komunikatu
    i tak potrzebny jest wyłącznie tytuł, a plik „brak publikacji” to jedno
    słowo. Strony z komunikatem zostają w cache w całości.
    """
    path = cache / (re.sub(r"[^A-Za-z0-9._-]", "_", url.split("://", 1)[1]) + ".title")
    if path.exists():
        text = path.read_text(encoding="utf-8")
        return text or None
    title = eurostat.page_title(fetch(url, cache, pause=pause))
    cache.mkdir(parents=True, exist_ok=True)
    path.write_text(title or "", encoding="utf-8")
    if not title:                      # strona logowania — nie trzymamy jej kopii
        (cache / re.sub(r"[^A-Za-z0-9._-]", "_", url.split("://", 1)[1])).unlink(missing_ok=True)
    return title


def build_eurostat(years: range) -> pl.DataFrame:
    """HICP flash: data z adresu komunikatu, godzina z calendar_times.yaml."""
    cache = RAW / "eurostat"
    start = dt.date(years.start, 1, 1) - dt.timedelta(days=8)   # okno sięga poprzedniego miesiąca
    end = dt.date(years.stop - 1, 12, 31) + dt.timedelta(days=8)
    found: dict[dt.date, str] = {}
    for day in eurostat.candidate_days(start, end):
        title = fetch_title(eurostat.release_url(day), cache, pause=EUROSTAT_PAUSE_S)
        if title and eurostat.is_flash(title):
            found[day] = title
    try:
        at, tz = release_time(release_times_cfg()["EA_HICP_FLASH"], "EA_HICP_FLASH")
    except PermissionError as e:
        log.warning("%s — pomijam %d publikacji", e, len(found))
        return pl.DataFrame(schema=CALENDAR_SCHEMA)
    rows = [{"timestamp_utc": dt.datetime.combine(d, at, tzinfo=tz).astimezone(UTC),
             "currency": "EUR", "name": "EA_HICP_FLASH", "rank": "HIGH",
             "source": eurostat.release_url(d)}
            for d in sorted(found) if years.start <= d.year <= years.stop - 1]
    per_year = pl.Series([r["timestamp_utc"].year for r in rows]).value_counts()
    if short := sorted((y, n) for y, n in per_year.iter_rows() if n != 12):
        log.warning("Eurostat EA_HICP_FLASH: lata bez 12 publikacji: %s", short)
    log.info("Eurostat EA_HICP_FLASH: %d publikacji", len(rows))
    return pl.DataFrame(rows, schema=CALENDAR_SCHEMA)


SOURCES = {"fomc": build_fomc, "fred": build_fred, "bea": build_bea, "bls": build_bls,
           "census": build_census, "ecb": build_ecb, "boc": build_boc, "statcan": build_statcan,
           "boe": build_boe, "ons": build_ons, "abs": build_abs, "rba": build_rba, "jp": build_jp, "boj": build_boj, "eurostat": build_eurostat}


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
