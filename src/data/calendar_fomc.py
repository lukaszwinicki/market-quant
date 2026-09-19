"""Źródło kalendarza: posiedzenia FOMC (federalreserve.gov).

Dwa kroki, oba na stronach oficjalnych:

1. Lista posiedzeń — `fomchistorical{rok}.htm` (lata starsze) albo
   `fomccalendars.htm` (ostatnie ~5 lat). Każde posiedzenie to blok
   z opisem („January 26-27 Meeting”, „March 15 (unscheduled)”) i linkiem
   do komunikatu `monetaryYYYYMMDDa.htm`.
2. Czas zdarzenia — z samego komunikatu: „For release at 2:00 p.m. EST”.
   Godzina i strefa pochodzą ze źródła, nie z założonej konwencji (ADR-032).

Pomijane są bloki nadzwyczajne i nie-decyzyjne: unscheduled, cancelled,
notation vote, conference call. Nie były znane z wyprzedzeniem albo
nie są decyzją o stopach.
"""

from __future__ import annotations

import datetime as dt
import re

UTC = dt.timezone.utc
BASE = "https://www.federalreserve.gov"
SKIP_MARKERS = ("unscheduled", "cancelled", "notation vote", "conference call")

_STATEMENT = re.compile(r'href="(/newsevents/pressreleases/monetary(\d{8})a\.htm)"')
_H5 = re.compile(r"<h5[^>]*>(.*?)</h5>", re.S)
_DATE_CELL = re.compile(r'class="[^"]*fomc-meeting__date[^"]*"[^>]*>(.*?)</div>', re.S)
_RELEASE = re.compile(
    r"For release at\s+(\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?\s*(EST|EDT)", re.I)
_OFFSET = {"EST": -5, "EDT": -4}


def calendar_url(year: int, current_first_year: int) -> str:
    """Strona z listą posiedzeń roku. Nowsze lata są na stronie zbiorczej."""
    if year >= current_first_year:
        return f"{BASE}/monetarypolicy/fomccalendars.htm"
    return f"{BASE}/monetarypolicy/fomchistorical{year}.htm"


def _blocks(html: str) -> list[tuple[str, str]]:
    """(opis posiedzenia, HTML bloku) — dla obu układów strony."""
    # Strona zbiorcza ma komórki dat; nagłówki h5 bywają na niej w innych
    # miejscach, więc komórki mają pierwszeństwo.
    marks = [(m.start(), m.group(1)) for m in _DATE_CELL.finditer(html)]
    if not marks:
        marks = [(m.start(), m.group(1)) for m in _H5.finditer(html)]
    out = []
    for k, (pos, label) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(html)
        out.append((re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", label)).strip(),
                    html[pos:end]))
    return out


def scheduled_statements(html: str, year: int) -> list[tuple[str, str]]:
    """(opis, URL komunikatu) planowanych posiedzeń w roku `year`."""
    out = []
    for label, block in _blocks(html):
        if any(m in label.lower() for m in SKIP_MARKERS):
            continue
        m = _STATEMENT.search(block)
        if m and m.group(2).startswith(str(year)):
            out.append((label, BASE + m.group(1)))
    return out


def release_time_utc(html: str, url: str) -> dt.datetime:
    """Moment publikacji z komunikatu. Data z URL, godzina i strefa z treści."""
    m = _RELEASE.search(html)
    if not m:
        raise ValueError(f"{url}: brak 'For release at ...' — nie zgaduję godziny")
    hh, mm, ap, tz = int(m.group(1)), int(m.group(2)), m.group(3).lower(), m.group(4).upper()
    hh = hh % 12 + (12 if ap == "p" else 0)
    ymd = re.search(r"monetary(\d{8})a\.htm", url).group(1)
    local = dt.datetime.strptime(ymd, "%Y%m%d").replace(hour=hh, minute=mm)
    return (local - dt.timedelta(hours=_OFFSET[tz])).replace(tzinfo=UTC)
