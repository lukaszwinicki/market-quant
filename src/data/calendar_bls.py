"""Źródło kalendarza: publikacje BLS (CPI, Employment Situation), bls.gov.

Roczne kalendarze „Schedule of Releases for <rok>” (`/schedule/<rok>_sched.htm`)
mają jeden wiersz na publikację: data, godzina, opis. Godzina jest więc
podana dla KAŻDEJ publikacji — ważne, bo w BEA okazało się, że stała
godzina jest błędna (ADR-032).

bls.gov odrzuca zapytania skryptów (403). Strony roczne zapisuje ręcznie
użytkownik do `data/raw/calendar/bls/` — źródło pozostaje oficjalne,
zmienia się tylko to, kto pobiera. Skrypt nie łączy się z bls.gov.

Strefa: godziny BLS są w czasie wschodnim USA; przeliczenie przez
`America/New_York` z DST daty publikacji. Daty sprawdzane krzyżowo
z ALFRED (pierwsza publikacja okresu).
"""

from __future__ import annotations

import datetime as dt
import html as htmllib
import re
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
NY = ZoneInfo("America/New_York")
BASE = "https://www.bls.gov"
TITLES = {"US_CPI": "Consumer Price Index", "US_NFP": "Employment Situation"}

_ROW = re.compile(
    r'<td class="date-cell">(.*?)</td>\s*<td class="time-cell">(.*?)</td>\s*'
    r'<td class="desc-cell">(.*?)</td>', re.S)


def schedule_url(year: int) -> str:
    return f"{BASE}/schedule/{year}_sched.htm"


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def schedule_rows(html: str) -> list[tuple[str, str, str, str]]:
    """(data, godzina, tytuł publikacji, opis) — tytuł to pogrubiona nazwa."""
    out = []
    for d, t, desc in _ROW.findall(html):
        strong = re.search(r"<strong>(.*?)</strong>", desc, re.S)
        out.append((_text(d), _text(t), _text(strong.group(1)) if strong else "", _text(desc)))
    return out


def release_times_utc(html: str, name: str) -> list[dt.datetime]:
    """Momenty publikacji serii z jednej strony rocznej.

    Wiersz bez godziny (np. święto) albo z godziną nieczytelną = błąd dla
    wierszy tej serii — nie zgadujemy.
    """
    out = []
    for day, at, title, desc in schedule_rows(html):
        if title != TITLES[name]:
            continue
        m = re.fullmatch(r"(\d{1,2}):(\d{2})\s*([AP])M", at.replace(".", "").upper())
        if not m:
            raise ValueError(f"{name} {day}: godzina {at!r} nieczytelna — nie zgaduję")
        hh = int(m.group(1)) % 12 + (12 if m.group(3) == "P" else 0)
        d = dt.datetime.strptime(day.split(", ", 1)[1], "%B %d, %Y")
        out.append(d.replace(hour=hh, minute=int(m.group(2)), tzinfo=NY).astimezone(UTC))
    return out
