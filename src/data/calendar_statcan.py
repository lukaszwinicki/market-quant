"""Źródło kalendarza: CPI Kanady, Statistics Canada („The Daily”).

DATY

Kalendarz „Major economic releases” (`/n1/dai-quo/cal1-eng.htm`) ładuje
`/n1/dai-quo/ssi/homepage/schedule-key_indicators-eng.json`: każda
publikacja kluczowego wskaźnika od 2012 r., z datą i adresem komunikatu
w The Daily. Bierzemy pozycje „Consumer Price Index”.

GODZINA — Z KAŻDEJ PUBLIKACJI

JSON ma pole czasu `00:00:01` (tylko porządek). Godzinę podaje PDF
komunikatu (ten sam adres, `.pdf`), pierwsza strona:
„Released at 8:30 a.m. Eastern time in The Daily, Friday, February 19, 2016”.
Data w nagłówku musi się zgadzać z datą z JSON-a — inaczej błąd.

Strefa: „Eastern time” = America/Toronto, z DST dnia publikacji.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
ET = ZoneInfo("America/Toronto")
BASE = "https://www150.statcan.gc.ca/n1"
KEY_INDICATORS = f"{BASE}/dai-quo/ssi/homepage/schedule-key_indicators-eng.json"
TITLES = {"CA_CPI": "Consumer Price Index"}

# pypdf gubi część spacji — dopuszczamy ich brak między słowami.
_RELEASED = re.compile(
    r"Released\s*at\s*(\d{1,2}):(\d{2})\s*([ap])\.\s*m\.\s*Eastern\s*time\s*in\s*The\s*Daily,"
    r"\s*[A-Za-z]+,\s*([A-Za-z]+)\s*(\d{1,2}),\s*(\d{4})")


def releases(key_json: str, name: str) -> list[tuple[dt.date, str | None]]:
    """(dzień publikacji, URL PDF komunikatu) dla serii.

    Publikacje zapowiedziane mają pusty adres — URL None; wywołujący
    decyduje, czy taka data może być w badanym zakresie (nie może).
    """
    out = set()
    for e in json.loads(key_json):
        if e["title"].strip() == TITLES[name]:
            day = dt.date.fromisoformat(e["date"][:10])
            if not e["url"]:
                out.add((day, None))
            elif not e["url"].endswith("-eng.htm"):
                raise ValueError(f"{name} {day}: nieoczekiwany adres {e['url']!r}")
            else:
                out.add((day, BASE + e["url"].removesuffix(".htm") + ".pdf"))
    return sorted(out, key=lambda r: r[0])


def release_time_utc(first_page: str, day: dt.date, url: str) -> dt.datetime:
    """Moment publikacji z nagłówka PDF; data musi być `day`."""
    m = _RELEASED.search(first_page)
    if not m:
        raise ValueError(f"{url}: brak nagłówka „Released at … Eastern time” — nie zgaduję")
    hh, mm, ap, month, d, y = m.groups()
    got = dt.datetime.strptime(f"{month} {d} {y}", "%B %d %Y").date()
    if got != day:
        raise ValueError(f"{url}: nagłówek podaje {got}, kalendarz {day}")
    hour = int(hh) % 12 + (12 if ap == "p" else 0)
    return dt.datetime.combine(day, dt.time(hour, int(mm)), tzinfo=ET).astimezone(UTC)
