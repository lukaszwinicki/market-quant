"""Źródło kalendarza: decyzje Bank of Japan, boj.or.jp.

GODZINA — Z PROTOKOŁU, BO BoJ NIE PODAJE GODZINY OGŁOSZENIA

Do 2015 r. lista komunikatów podawała „(Announced at 12:17 p.m.)”; od 2016
już nie (sprawdzone na stronach EN i JP, w komunikatach i harmonogramach).
Metadane PDF-a nie są publikacją: dla 29.01.2016 `ModDate` to 13:59 JST,
a rynek ruszył o 12:38.

Bierzemy więc godzinę ZAKOŃCZENIA posiedzenia z nagłówka protokołu
(`mpmsche_minu/minu_<rok>/g<RRMMDD>.pdf`, od 2018 `.htm`):

    „A Monetary Policy Meeting … was held … on Thursday, January 28, 2016,
     from 2:00 p.m. to 3:46 p.m., and on Friday, January 29, from 9:00 a.m.
     to 12:31 p.m.”

Komunikat wychodzi krótko po zakończeniu. Zmierzone na M1 USDJPY (2016):
29.01 koniec 12:31 → szczyt 12:38; 15.03 12:28 → 12:35; 28.04 11:54 → 12:01,
czyli +7 min. Okno blackoutu (−30/+120 min, ADR-032) obejmuje publikację
z zapasem, więc nie przesuwamy znacznika o zmierzone opóźnienie — to byłoby
dopasowanie do danych okresu testu.

Protokół wychodzi ok. miesiąc po posiedzeniu, więc sama minuta jest znana
ex post; data posiedzenia jest ogłaszana z rocznym wyprzedzeniem, a blackout
tylko blokuje wejścia (nie podpowiada kierunku).

Strefa: Asia/Tokyo (bez czasu letniego).
"""

from __future__ import annotations

import datetime as dt
import html as htmllib
import re
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
TOKYO = ZoneInfo("Asia/Tokyo")
BASE = "https://www.boj.or.jp"

# Protokoły do 2017 r. są w PDF, od 2018 w HTML — nagłówek jest ten sam.
_ROW = re.compile(r'<a href="(/en/mopo/mpmsche_minu/minu_(\d{4})/g(\d{6})\.(pdf|htm))"[^>]*>(.*?)</a>',
                  re.S)
_HEADER = re.compile(r"A Monetary Policy Meeting.{0,800}?(?=Policy Board Members Present)", re.S)
#  „Wednesday , September 20, 2017” — w niektórych protokołach spacja przed przecinkiem
_DAY = re.compile(r"[A-Z][a-z]+day\s*,\s*([A-Z][a-z]+)\s+(\d{1,2})(?:\s*,\s*(\d{4}))?")
_TO = re.compile(r"to\s+(\d{1,2}):(\d{2})\s*([ap])\.m\.")


def minutes_index_url(year: int) -> str:
    return f"{BASE}/en/mopo/mpmsche_minu/minu_{year}/index.htm"


def minutes_links(index_html: str) -> list[tuple[dt.date, str]]:
    """(dzień decyzji wg adresu, URL protokołu) — adres ma postać g<RRMMDD>."""
    out = {}
    for path, _, stamp, _suffix, title in _ROW.findall(index_html):
        if "Meeting on" not in htmllib.unescape(re.sub(r"<[^>]+>", " ", title)):
            continue
        day = dt.datetime.strptime(stamp, "%y%m%d").date()
        out[day] = BASE + path
    return sorted(out.items())


# Posiedzenie nadzwyczajne rozpoznaje protokół: „Remarks on the Purpose of This
# Unscheduled Monetary Policy Meeting” (22.05.2020) albo wniosek, by posiedzenie
# „be brought forward” (16.03.2020, przyspieszone z 18–19.03). W latach 2016–2025
# żaden inny protokół tych zwrotów nie zawiera.
UNSCHEDULED = ("Unscheduled Monetary Policy Meeting", "brought forward")


def is_unscheduled(minutes_text: str) -> bool:
    text = re.sub(r"\s+", " ", minutes_text)
    return any(marker in text for marker in UNSCHEDULED)


def adjournment_utc(minutes_text: str, day: dt.date, url: str) -> dt.datetime:
    """Koniec ostatniego dnia posiedzenia (moment UTC).

    Nagłówek wymienia każdy dzień z godzinami „from … to …”; bierzemy
    ostatnią godzinę zakończenia i sprawdzamy, że ostatni wymieniony dzień
    to `day` (dzień z adresu protokołu).

    Planowość rozstrzyga `is_unscheduled` (ADR-032).
    """
    text = re.sub(r"\s+", " ", minutes_text)
    header = _HEADER.search(text)
    if not header:
        raise ValueError(f"{url}: brak nagłówka z godzinami posiedzenia — nie zgaduję")
    days, ends = _DAY.findall(header.group(0)), _TO.findall(header.group(0))
    if not days or not ends:
        raise ValueError(f"{url}: nagłówek bez dat albo bez godzin zakończenia")
    month, dom, year = days[-1]
    year = year or next((y for _, _, y in days if y), "")   # rok bywa tylko przy pierwszym dniu
    if not year:
        raise ValueError(f"{url}: nagłówek bez roku posiedzenia")
    got = dt.datetime.strptime(f"{month} {dom} {year}", "%B %d %Y").date()
    if got != day:
        raise ValueError(f"{url}: protokół kończy się {got}, adres wskazuje {day}")
    hh, mm, ampm = ends[-1]
    at = dt.time(int(hh) % 12 + (12 if ampm == "p" else 0), int(mm))
    return dt.datetime.combine(day, at, tzinfo=TOKYO).astimezone(UTC)
