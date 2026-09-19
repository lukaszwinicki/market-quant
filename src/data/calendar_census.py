"""Źródło kalendarza: sprzedaż detaliczna (Advance Monthly Sales for Retail
and Food Services), census.gov.

Dwa oficjalne źródła, oba z godziną KAŻDEJ publikacji:

    2020+       roczne kalendarze wskaźników
                `economic-indicators/calendar-listview-<rok>.html`
                — wiersz: nazwa, data, godzina
    2016–2019   te strony nie istnieją (serwer zwraca ogólną stronę);
                zamiast nich archiwalne komunikaty PDF
                `www2.census.gov/retail/releases/historical/marts/advYYMM.pdf`
                (YYMM = miesiąc DANYCH) — nagłówek „FOR IMMEDIATE RELEASE
                FRIDAY, FEBRUARY 12, 2016, AT 8:30 A.M. EST”, od XII 2016
                „FOR RELEASE AT 8:30 AM EST, FRIDAY, JANUARY 13, 2017”

Daty sprawdzane krzyżowo z ALFRED (pierwsza publikacja okresu).
"""

from __future__ import annotations

import datetime as dt
import html as htmllib
import re
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
NY = ZoneInfo("America/New_York")
PROGRAM = "Advance Monthly Sales for Retail and Food Services"
FIRST_LISTVIEW_YEAR = 2020        # starsze lata: strona nie istnieje (sprawdzone 2026-09-19)
HISTORIC_PAGE = "https://www.census.gov/retail/marts/historic_releases.html"

_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
# Dwa układy komunikatu. Oba zakotwiczone w „IMMEDIATE RELEASE” / „FOR RELEASE AT”,
# żeby nie złapać zdania o NASTĘPNEJ publikacji („scheduled for release on
# September 14, 2018 at 8:30 a.m.”), które stoi w tym samym tekście.
_DATE = r"([A-Z]+\.?\s+\d{1,2},\s*\d{4})"
_TIME = r"(\d{1,2}):(\d{2})\s*([AP])\.?\s*M\.?\s*(EST|EDT)"
_PDF_OLD = re.compile(r"IMMEDIATE\s+RELEASE\s+(?:[A-Z]+DAY,?\s*)?" + _DATE + r",?\s*AT\s+" + _TIME)
_PDF_NEW = re.compile(r"FOR\s+RELEASE\s+AT\s+" + _TIME + r",?\s*(?:[A-Z]+DAY,?\s*)?" + _DATE)
_OFFSET = {"EST": -5, "EDT": -4}


def listview_url(year: int) -> str:
    return f"https://www.census.gov/economic-indicators/calendar-listview-{year}.html"


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def listview_times_utc(html: str) -> list[dt.datetime]:
    """Momenty publikacji sprzedaży detalicznej z rocznego kalendarza."""
    out = []
    for row in _ROW.findall(html):
        cells = [_text(c) for c in _CELL.findall(row)]
        if len(cells) < 3 or cells[0] != PROGRAM:
            continue
        m = re.fullmatch(r"(\d{1,2}):(\d{2})\s*([AP])M", cells[2].upper())
        if not m:
            raise ValueError(f"{cells[1]}: godzina {cells[2]!r} nieczytelna — nie zgaduję")
        hh = int(m.group(1)) % 12 + (12 if m.group(3) == "P" else 0)
        d = dt.datetime.strptime(cells[1], "%B %d, %Y")
        out.append(d.replace(hour=hh, minute=int(m.group(2)), tzinfo=NY).astimezone(UTC))
    return out


def historic_pdf_urls(html: str, first_yymm: str, last_yymm: str) -> list[str]:
    """Linki `advYYMM.pdf` w zakresie miesięcy danych (YYMM, włącznie)."""
    found = set(re.findall(r'href="(https://www2\.census\.gov/retail/releases/historical/'
                           r'marts/adv(\d{4})\.pdf)"', html))
    return sorted(u for u, yymm in found if first_yymm <= yymm <= last_yymm)


def pdf_release_time_utc(first_page_text: str, url: str) -> dt.datetime:
    text = re.sub(r"\s+", " ", first_page_text)
    if m := _PDF_OLD.search(text):             # do XI 2016
        day, hh, mm, ap, tz = m.groups()
    elif m := _PDF_NEW.search(text):           # od XII 2016
        hh, mm, ap, tz, day = m.groups()
    else:
        raise ValueError(f"{url}: brak nagłówka 'RELEASE … h:mm A.M. EST' — nie zgaduję")
    month, rest = day.split(None, 1)
    d = dt.datetime.strptime(f"{month[:3].title()} {rest}", "%b %d, %Y")
    hh = int(hh) % 12 + (12 if ap.upper() == "P" else 0)
    local = d.replace(hour=hh, minute=int(mm))
    return (local - dt.timedelta(hours=_OFFSET[tz.upper()])).replace(tzinfo=UTC)
