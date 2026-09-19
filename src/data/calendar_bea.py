"""Źródło kalendarza: publikacje BEA (PCE i GDP advance), bea.gov.

GODZINA Z KAŻDEJ PUBLIKACJI

Godzina publikacji BEA zmieniała się w okresie testu: Personal Income and
Outlays za styczeń 2016 wyszedł o 10:00 EST, dziś harmonogram podaje 8:30.
Jedna „stała” godzina byłaby błędna, więc czytamy ją z nagłówka każdego
komunikatu: „EMBARGOED UNTIL RELEASE AT 10:00 A.M. EST, Friday, February
26, 2016” (od ~2021: „EMBARGOED FOR RELEASE: 8:30 A.M. EDT, …”). Pole `<time>` z listy archiwum to znacznik CMS, nie embargo —
nie jest używane.

KTÓRE PUBLIKACJE

    US_PCE          „Personal Income and Outlays[,:] <miesiąc> <rok>” (i łączony
                    tytuł z 2019); bez „Data Update” (brak komunikatu i embarga)
    US_GDP_ADVANCE  tytuł GDP z „Advance Estimate” albo „Initial Estimate”
                    (2019: odczyt wstępny po shutdownie nazwano initial)

Daty są sprawdzane krzyżowo z ALFRED (pierwsza publikacja okresu) —
rozbieżność przerywa budowę kalendarza.
"""

from __future__ import annotations

import datetime as dt
import html as htmllib
import re

UTC = dt.timezone.utc
BASE = "https://www.bea.gov"
PRODUCTS = {"US_PCE": 476, "US_GDP_ADVANCE": 451}

_ROW = re.compile(r'<a href="(/news/(\d{4})/[^"]+)"[^>]*>([^<]+)</a>')
_EMBARGO = re.compile(
    r"EMBARGOED\s+(?:UNTIL\s+(?:RELEASE\s+)?AT|FOR\s+RELEASE:?(?:\s+AT)?)\s+"
    r"(\d{1,2}):(\d{2})\s*([AP])\.?\s*M\.?\s*"
    r"\(?(EST|EDT|ET)\)?\s*,?\s*(?:\w+day,?\s*)?([A-Z][a-z]+\.?\s+\d{1,2},\s*\d{4})", re.I)
_OFFSET = {"EST": -5, "EDT": -4}


def archive_url(name: str, page: int) -> str:
    return f"{BASE}/news/archive?field_related_product_target_id={PRODUCTS[name]}&page={page}"


def wanted(name: str, title: str) -> bool:
    t = title.strip()
    if "data update" in t.lower():
        return False                      # wydanie danych bez komunikatu i embarga
    if name == "US_PCE":
        # „…, May 2016”, „…: May 2020”, 2019: „Personal Income, February 2019;
        # Personal Outlays, January 2019” (po shutdownie).
        low = t.lower()
        return (re.match(r"personal income and outlays\s*[,:]", low) is not None
                or (low.startswith("personal income") and "personal outlays" in low))
    return (("gdp" in t.lower() or "gross domestic product" in t.lower())
            and re.search(r"\((advance|initial) estimate\)|advance estimate|initial estimate",
                          t, re.I) is not None)


def archive_rows(html: str) -> list[tuple[str, int, str]]:
    """(URL, rok z URL, tytuł) z jednej strony archiwum."""
    return [(BASE + u, int(y), htmllib.unescape(t).strip()) for u, y, t in _ROW.findall(html)]


def embargo_time_utc(html: str, url: str) -> dt.datetime:
    """Moment publikacji z nagłówka embarga. Brak nagłówka = błąd, nie zgadywanie."""
    text = re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", html)))
    m = _EMBARGO.search(text)
    if not m:
        raise ValueError(f"{url}: brak nagłówka EMBARGOED — nie zgaduję godziny")
    hh, mm, ap, tz, day = m.groups()
    hh = int(hh) % 12 + (12 if ap.upper() == "P" else 0)
    tz = tz.upper()
    if tz == "ET":
        raise ValueError(f"{url}: strefa 'ET' bez EST/EDT — nieobsługiwane")
    # „September 30”, „Sept. 30”, „Sep 30” — miesiąc po trzech pierwszych literach.
    month, rest = day.split(None, 1)
    d = dt.datetime.strptime(f"{month[:3]} {rest}", "%b %d, %Y")
    local = d.replace(hour=hh, minute=int(mm))
    return (local - dt.timedelta(hours=_OFFSET[tz])).replace(tzinfo=UTC)
