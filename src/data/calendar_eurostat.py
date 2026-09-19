"""Źródło kalendarza: szybki szacunek inflacji strefy euro (HICP flash), Eurostat.

DLACZEGO SONDOWANIE ADRESÓW

Kalendarz Eurostatu (`o/calendars/eventsJson`) zwraca zdarzenia dopiero od
2025 r., lista komunikatów to aplikacja JS, a jej odpowiednik portletowy
(`/products-euro-indicators/product?p_p_id=…`) odpowiada skryptom 403.
Każdy komunikat ma za to trwały adres z datą w identyfikatorze:

    https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-29022016-ap
    → <title>Euro area annual inflation down to -0.2% - Products Euro Indicators…

Adres bez komunikatu zwraca stronę logowania (<title>EU Login</title>), więc
istnienie publikacji rozstrzyga sam serwis. Sondujemy dni robocze od 24. dnia
miesiąca do 7. dnia następnego: do ok. 2019 r. flash wychodził ostatniego dnia
miesiąca odniesienia (29.02.2016), później w pierwszych dniach następnego
(3.02.2021).

FLASH KONTRA ODCZYT FINALNY

Tytuły są rozłączne: flash — „Euro area annual inflation …”, odczyt finalny
(w połowie miesiąca, poza oknem sondowania) — „Annual inflation … in the euro
area”. Wymagamy wzorca flash; inne tytuły w oknie są pomijane.

GODZINA

Komunikat podaje tylko datę. Godzina (11:00 CET) jest prerejestrowana
w `config/calendar_times.yaml` (EA_HICP_FLASH) — kalendarz Eurostatu 2025
podaje `11:00`, a na tickach EURUSD największy ruch M1 dnia 29.02.2016 wypada
o 10:00 UTC, czyli 11:00 CET.
"""

from __future__ import annotations

import datetime as dt
import html as htmllib
import re

BASE = "https://ec.europa.eu/eurostat/web/products-euro-indicators/w"
FLASH_TITLE = re.compile(r"Euro area annual inflation\b", re.I)
MISSING_TITLE = "EU Login"
_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
# Sondowane dni: koniec miesiąca odniesienia i początek następnego.
FROM_DAY_OF_MONTH = 24
TO_DAY_OF_MONTH = 7


def release_url(day: dt.date) -> str:
    return f"{BASE}/2-{day:%d%m%Y}-ap"


def candidate_days(start: dt.date, end: dt.date) -> list[dt.date]:
    """Dni robocze okna sondowania w zakresie [start, end]."""
    out, day = [], start
    while day <= end:
        if day.weekday() < 5 and (day.day >= FROM_DAY_OF_MONTH or day.day <= TO_DAY_OF_MONTH):
            out.append(day)
        day += dt.timedelta(days=1)
    return out


def page_title(page_html: str) -> str | None:
    """Tytuł komunikatu albo None, gdy pod adresem nie ma publikacji."""
    m = _TITLE.search(page_html)
    if not m:
        return None
    title = re.sub(r"\s+", " ", htmllib.unescape(m.group(1))).strip()
    if title.startswith(MISSING_TITLE):
        return None
    return title.split(" - Products Euro Indicators")[0].strip()


def is_flash(title: str) -> bool:
    return bool(FLASH_TITLE.match(title))
