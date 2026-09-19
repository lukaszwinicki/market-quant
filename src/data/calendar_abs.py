"""Źródło kalendarza: CPI Australii, Australian Bureau of Statistics.

Produkt „Consumer Price Index, Australia” (6401.0) — kwartalny do września
2025, od października 2025 pełny miesięczny (ten sam produkt). Osobny
„Monthly CPI Indicator” (2022–2025) to inny produkt i nie wchodzi.

DWA UKŁADY STRON, OBA Z GODZINĄ KAŻDEJ PUBLIKACJI

    ausstats (do 06.2020)   lista „Past Releases” produktu 6401.0,
                            strona wydania: „Released at 11:30 AM (CANBERRA TIME) 27/04/2016”
    abs.gov.au (od 09.2019) lista „View all releases”,
                            strona wydania: „Release date and time 25/10/2023 11:30am AEDT”

Wydania z obu układów (09.2019–06.2020) muszą dać ten sam moment — inaczej
błąd. „CANBERRA TIME” = Australia/Sydney; skrót AEST/AEDT z nowego układu
musi się zgadzać ze strefą w dniu publikacji.
"""

from __future__ import annotations

import datetime as dt
import html as htmllib
import re
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
CANBERRA = ZoneInfo("Australia/Sydney")
BASE = "https://www.abs.gov.au"
PRODUCT = "/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia"
NEW_LIST = BASE + PRODUCT
OLD_LIST = (f"{BASE}/AUSSTATS/abs@.nsf/second+level+view?ReadForm&prodno=6401.0"
            "&tabname=Past%20Future%20Issues")

_NEW_LINK = re.compile(rf'href="({re.escape(PRODUCT)}/[a-z]{{3}}-(?:quarter-)?\d{{4}})"')
_OLD_LINK = re.compile(r"href='(allprimarymainfeatures/[0-9A-F]{32}\?opendocument)'>\s*"
                       r"Consumer Price Index, Australia\s+([A-Z][a-z]{2} \d{4})\s*</a>")
_NEW_TIME = re.compile(r"Release date and time\s+(\d{2}/\d{2}/\d{4})\s+(\d{1,2}):(\d{2})\s*"
                       r"([ap])m\s+(AEST|AEDT)")
_OLD_TIME = re.compile(r"Released at (\d{1,2}):(\d{2}) ([AP])M \(CANBERRA TIME\) (\d{2}/\d{2}/\d{4})")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def new_release_urls(list_html: str) -> list[str]:
    return sorted({BASE + p for p in _NEW_LINK.findall(list_html)})


def old_release_urls(list_html: str) -> list[tuple[str, str]]:
    """(URL wydania, okres referencyjny „Mar 2016”) z listy ausstats."""
    return sorted({(f"{BASE}/AUSSTATS/abs@.nsf/{p}", period)
                   for p, period in _OLD_LINK.findall(list_html)})


def _at(day: str, hh: str, mm: str, ampm: str) -> dt.datetime:
    d = dt.datetime.strptime(day, "%d/%m/%Y").date()
    hour = int(hh) % 12 + (12 if ampm.lower() == "p" else 0)
    return dt.datetime.combine(d, dt.time(hour, int(mm)), tzinfo=CANBERRA)


def new_release_time_utc(page_html: str, url: str) -> dt.datetime:
    m = _NEW_TIME.search(_text(page_html))
    if not m:
        raise ValueError(f"{url}: brak „Release date and time …” — nie zgaduję")
    day, hh, mm, ampm, zone = m.groups()
    local = _at(day, hh, mm, ampm)
    if local.tzname() != zone:
        raise ValueError(f"{url}: strona podaje {zone}, a {local.date()} w Canberze to {local.tzname()}")
    return local.astimezone(UTC)


def old_release_time_utc(page_html: str, url: str) -> dt.datetime:
    m = _OLD_TIME.search(_text(page_html))
    if not m:
        raise ValueError(f"{url}: brak „Released at … (CANBERRA TIME)” — nie zgaduję")
    hh, mm, ampm, day = m.groups()
    return _at(day, hh, mm, ampm).astimezone(UTC)
