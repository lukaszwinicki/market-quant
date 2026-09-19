"""Źródło kalendarza: UK CPI i rynek pracy, Office for National Statistics.

KALENDARZ PUBLIKACJI (od 02.2016)

`/releasecalendar?keywords=…&release-type=type-published&after-…&before-…`
— jedna pozycja na publikację, z atrybutami `data-gtm-release-title`,
`-url`, `-date` (RRRRMMDD) i `-time` (HH:MM, czas Londynu). Godzina jest
więc podana dla KAŻDEJ publikacji — i to ważne: w 2020 ONS przeniósł
publikacje rynkowe z 9:30 na 7:00.

Bierzemy tylko główne publikacje miesięczne, po pełnym tytule:
    UK_CPI      „UK consumer price inflation: Jan 2016”,
                „Consumer price inflation, UK: August 2026”
    UK_LABOUR   „Labour market statistics: February 2016”,
                „UK labour market: March 2024”, „UK Labour Market April 2024”
Odpadają m.in. „… time series”, „Labour market in the regions of the UK”.

STYCZEŃ 2016 — Z BIULETYNÓW

Kalendarz ONS zaczyna się od lutego 2016. Publikacje ze stycznia 2016 mają
datę w biuletynie („Release date: 19 January 2016”), bez godziny — godzina
z `config/calendar_times.yaml` (ONS_BULLETIN), potwierdzona przez użytkownika.
"""

from __future__ import annotations

import datetime as dt
import html as htmllib
import re
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
LONDON = ZoneInfo("Europe/London")
BASE = "https://www.ons.gov.uk"
KEYWORDS = {"UK_CPI": "consumer price inflation", "UK_LABOUR": "labour market"}
# Publikacje sprzed kalendarza: biuletyny ze stycznia 2016.
JAN_2016_BULLETINS = {
    "UK_CPI": f"{BASE}/economy/inflationandpriceindices/bulletins/consumerpriceinflation/"
              "december2015",
    "UK_LABOUR": f"{BASE}/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/"
                 "bulletins/uklabourmarket/january2016",
}
FIRST_CALENDAR_DAY = dt.date(2016, 2, 1)

_M = (r"(?:January|February|March|April|May|June|July|August|September|October|November|"
      r"December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)")
TITLES = {
    "UK_CPI": re.compile(rf"(?:UK consumer price inflation|Consumer price inflation, UK)"
                         rf"\s*:?\s*{_M}\s+\d{{4}}", re.I),
    "UK_LABOUR": re.compile(rf"(?:UK labour market(?: statistics)?|Labour market statistics)"
                            rf"\s*:?\s*{_M}\s+\d{{4}}", re.I),
}
_ITEM = re.compile(
    r'data-gtm-release-title\s*=\s*"([^"]*)"\s*data-gtm-release-url="([^"]*)"\s*'
    r'data-gtm-release-date="(\d{8})"\s*data-gtm-release-time="([^"]*)"')
_COUNT = re.compile(r"Published\s*\((\d+)\)")
_RELEASE_DATE = re.compile(r"Release date:\s*(\d{1,2} [A-Z][a-z]+ \d{4})")


def calendar_url(name: str, year: int, page: int) -> str:
    kw = KEYWORDS[name].replace(" ", "+")
    return (f"{BASE}/releasecalendar?keywords={kw}&release-type=type-published"
            f"&after-day=01&after-month=01&after-year={year}"
            f"&before-day=31&before-month=12&before-year={year}"
            f"&sort=date-oldest&limit=100&page={page}")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def result_count(html: str) -> int:
    m = _COUNT.search(_text(html))
    return int(m.group(1)) if m else 0


def calendar_items(html: str) -> list[tuple[str, str, dt.date, str]]:
    """(tytuł, URL, dzień, godzina HH:MM) ze strony wyników."""
    out = []
    for title, url, day, at in _ITEM.findall(html):
        # Tytuł podwójnie zakodowany, słowa z zapytania w <em> — tag usuwany
        # bez spacji, inaczej „inflation</em>, UK” da „inflation , UK”.
        title = htmllib.unescape(htmllib.unescape(title))
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", title)).strip()
        out.append((title, BASE + url, dt.datetime.strptime(day, "%Y%m%d").date(), at))
    return out


def release_times_utc(items: list[tuple[str, str, dt.date, str]], name: str
                      ) -> list[tuple[dt.datetime, str]]:
    """(moment UTC, URL) dla głównych publikacji serii. Brak godziny = błąd."""
    out = []
    for title, url, day, at in items:
        if not TITLES[name].fullmatch(title):
            continue
        m = re.fullmatch(r"(\d{2}):(\d{2})", at)
        if not m:
            raise ValueError(f"{name} {day} ({url}): godzina {at!r} nieczytelna — nie zgaduję")
        local = dt.datetime.combine(day, dt.time(int(m.group(1)), int(m.group(2))), tzinfo=LONDON)
        out.append((local.astimezone(UTC), url))
    return sorted(set(out))


def bulletin_release_date(html: str, url: str) -> dt.date:
    m = _RELEASE_DATE.search(_text(html))
    if not m:
        raise ValueError(f"{url}: brak „Release date: …” — nie zgaduję")
    return dt.datetime.strptime(m.group(1), "%d %B %Y").date()
