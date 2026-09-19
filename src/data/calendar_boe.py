"""Źródło kalendarza: decyzje Bank of England (MPC), bankofengland.co.uk.

LISTA POSIEDZEŃ

Strona „Monetary policy summary and minutes” ładuje wyniki przez
`POST /_api/Search/RefreshContentPageSearchList` (parametry — z konfiguracji
tej strony, `CP.BOE.*`). Wynik: odnośniki do stron
`/monetary-policy-summary-and-minutes/<rok>/<slug>`. Posiedzenia planowe
mają slug `<miesiąc>-<rok>` albo `mpc-<miesiąc>-<rok>`. Inne slugi to
posiedzenia nadzwyczajne (`13march-2020`, „special … meeting on 19 march
2020”) — odpadają (ADR-032).

DATA — ZE STRONY POSIEDZENIA

„Published on 14 January 2016”. Musi to być czwartek — tak mówi źródło
godziny; inny dzień = błąd, nie zgadujemy.

GODZINA — Z `config/calendar_times.yaml` (BOE_RATE)

Strony posiedzeń i PDF-y nie podają godziny. Źródła konwencji:
    2016: „The MPC’s decisions on interest rates are announced on a Thursday
          at 12 noon.” (monetarypolicy/Pages/decisions.aspx, Wayback 2017-01)
    dziś: „The Monetary Policy summary and minutes are published at 12 noon
          on a Thursday eight times a year.”
Wyjątek: 08.05.2025 o 12:02 (dwie minuty ciszy, komunikat BoE z 06.05.2025)
— w oknie blackoutu 30/120 min bez znaczenia.
"""

from __future__ import annotations

import datetime as dt
import html as htmllib
import re

BASE = "https://www.bankofengland.co.uk"
LISTING_API = f"{BASE}/_api/Search/RefreshContentPageSearchList"
# Konfiguracja strony /monetary-policy-summary-and-minutes/monetary-policy-summary-and-minutes
LISTING_FORM = [
    ("Id", "{CE377CC8-BFBC-418B-B4D9-DBC1C64774A8}"),
    ("PageSize", "100"),
    ("OrderBy", "4"),
    ("ShowResultImage", "0"),
    ("ReleaseTypes[]", "09f8960ebc384e3589da5349744916ae"),
    ("Taxonomies[]", "36308a372d1e44ee94e6b5915796c531"),
    ("Taxonomies[]", "bdad2410fe554128b9f7d680d1066e43"),
    ("Taxonomies[]", "eb7acc623d7e4af88cb3a581a1ae1ea7"),
]

_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
_PAGE = re.compile(r'href="(/monetary-policy-summary-and-minutes/(\d{4})/([a-z0-9-]+))"')
_SCHEDULED = re.compile(rf"(?:mpc-)?({_MONTHS})-(\d{{4}})")
_PUBLISHED = re.compile(r"Published on (\d{1,2} [A-Z][a-z]+ \d{4})")


def listing_pages(results_html: str) -> tuple[list[str], list[str]]:
    """(URL-e posiedzeń planowych, URL-e pominięte jako nieplanowe)."""
    scheduled, other = set(), set()
    for path, year, slug in _PAGE.findall(results_html):
        m = _SCHEDULED.fullmatch(slug)
        (scheduled if m and m.group(2) == year else other).add(BASE + path)
    return sorted(scheduled), sorted(other)


def published_on(page_html: str, url: str) -> dt.date:
    text = re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", page_html)))
    m = _PUBLISHED.search(text)
    if not m:
        raise ValueError(f"{url}: brak „Published on …” — nie zgaduję")
    day = dt.datetime.strptime(m.group(1), "%d %B %Y").date()
    if day.weekday() != 3:
        raise ValueError(f"{url}: publikacja {day} nie w czwartek — konwencja godziny nie pasuje")
    return day
