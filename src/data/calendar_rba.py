"""Źródło kalendarza: decyzje Reserve Bank of Australia, rba.gov.au.

DOSTĘP PRZEZ ARCHIWUM

rba.gov.au odpowiada skryptom 403 (każdy adres, także RSS). Strony są więc
czytane z kopii Wayback Machine (`web.archive.org/web/<znacznik>id_/<adres>`),
czyli z wiernego zapisu strony oficjalnej wraz z datą zapisu. Archiwum ma tu
przewagę: harmonogram zapisany PRZED rokiem dowodzi, że posiedzenie było
zaplanowane z wyprzedzeniem (ADR-032), czego dzisiejsza strona nie pokazuje.

DATY DECYZJI

`monetary-policy/int-rate-decisions/<rok>/` — lista komunikatów, jeden na
decyzję (`/media-releases/<rok>/mr-YY-NN.html`), z datą jako treścią odnośnika.
Lista zawiera też decyzje nadzwyczajne (19.03.2020).

HARMONOGRAM I GODZINA — DWA UKŁADY, OBA ZAPISANE PRZED ROKIEM

    do 2023   `calendar-<rok>-text.html`: „The Reserve Bank Board will meet on
              the following days, with a media release issued at 2.30 pm:
              Tuesday, 4 February …” (dzień bez roku — rok z adresu)
    od 2024   `calendar-2024.html` / `calendar.html`: pozycja na posiedzenie,
              „Monetary Policy Decision Statement Media Release 6 February 2024
              2.30 pm AEDT” (godzina i skrót strefy przy każdej dacie)

ROK 2018 NIE MA ZAPISU HARMONOGRAMU w archiwum. Dla niego bierzemy daty
z listy decyzji, ale każdy komunikat musi zawierać „At its meeting today”
— zwrot, którego komunikat nadzwyczajny (mr-20-08, 19.03.2020) nie ma.
Skrypt wypisuje to jako wyjątek; reszta lat jest rozstrzygana harmonogramem.

Strefa: czas Sydney (Australia/Sydney) — w układzie od 2024 skrót AEST/AEDT
ze strony jest sprawdzany z tym, co daje strefa w dniu posiedzenia.
"""

from __future__ import annotations

import datetime as dt
import html as htmllib
import re
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
SYDNEY = ZoneInfo("Australia/Sydney")
BASE = "https://www.rba.gov.au"
MIRROR = "https://web.archive.org/web/{stamp}id_/{url}"

# Znaczniki zapisów Wayback: harmonogram roku R zapisany przed R (albo na
# jego początku). 2018 nie ma żadnego zapisu — patrz NO_SCHEDULE.
SCHEDULE_SNAPSHOTS: dict[int, tuple[str, str]] = {
    2016: ("20151219031744", "schedules-events/calendar-2016-text.html"),
    2017: ("20161220154322", "schedules-events/calendar-2017-text.html"),
    2019: ("20181029140247", "schedules-events/calendar-2019-text.html"),
    2020: ("20191120102448", "schedules-events/calendar-2020-text.html"),
    2021: ("20210419173932", "schedules-events/calendar-2021-text.html"),
    2022: ("20220124231110", "schedules-events/calendar-2022-text.html"),
    2023: ("20230129013856", "schedules-events/calendar-2023-text.html"),
    2024: ("20231107065258", "schedules-events/calendar-2024.html"),
    2025: ("20240831034217", "schedules-events/calendar.html"),
}
NO_SCHEDULE = (2018,)
DECISIONS_SNAPSHOT = "2026"          # „najbliższy zapis z 2026” — lista pełna
REGULAR_MEETING = "At its meeting today"

_MONTHS = ("January|February|March|April|May|June|July|August|September|October|"
           "November|December")
_DECISION = re.compile(rf'href="(/media-releases/\d{{4}}/mr-\d\d-\d+\.html)"[^>]*>\s*'
                       rf'(\d{{1,2}} (?:{_MONTHS}) \d{{4}})\s*<')
_TEXT_SCHEDULE = re.compile(
    r"The Reserve Bank Board will meet on the following days, with a media release "
    r"issued at (\d{1,2})\.(\d{2}) (am|pm):(.*?)(?:Chart Pack|Minutes|Statement on|$)", re.S)
_TEXT_DAY = re.compile(rf"[A-Z][a-z]+day,?\s+(\d{{1,2}})\s+({_MONTHS})")
_LISTING = re.compile(
    rf"Monetary Policy Decision Statement Media Release (\d{{1,2}} (?:{_MONTHS}) \d{{4}}) "
    rf"(\d{{1,2}})\.(\d{{2}}) (am|pm) (AEST|AEDT)")


def mirror(stamp: str, path: str) -> str:
    return MIRROR.format(stamp=stamp, url=f"{BASE}/{path}")


def decisions_url(year: int) -> str:
    return mirror(DECISIONS_SNAPSHOT, f"monetary-policy/int-rate-decisions/{year}/")


def schedule_url(year: int) -> str:
    stamp, path = SCHEDULE_SNAPSHOTS[year]
    return mirror(stamp, path)


def release_url(path: str) -> str:
    return BASE + path


def _text(fragment: str) -> str:
    fragment = re.sub(r"<(script|style)\b.*?</\1>", " ", fragment, flags=re.S | re.I)
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def decision_dates(page_html: str, year: int, url: str) -> dict[dt.date, str]:
    """{dzień decyzji: adres komunikatu} ze strony rocznej."""
    out = {}
    for path, day in _DECISION.findall(page_html):
        d = dt.datetime.strptime(day, "%d %B %Y").date()
        if d.year != year:
            raise ValueError(f"{url}: decyzja {d} na stronie roku {year}")
        out[d] = release_url(path)
    if not out:
        raise ValueError(f"{url}: brak decyzji na stronie — zmiana układu?")
    return out


def _hour(hh: str, mm: str, ampm: str) -> dt.time:
    return dt.time(int(hh) % 12 + (12 if ampm == "pm" else 0), int(mm))


def scheduled_times(schedule_html: str, year: int, url: str) -> dict[dt.date, dt.datetime]:
    """{dzień: moment ogłoszenia UTC} z harmonogramu zapisanego przed rokiem."""
    text = _text(schedule_html)
    out: dict[dt.date, dt.datetime] = {}

    if listing := _LISTING.findall(text):                             # układ od 2024
        # Strona pokazuje też rok poprzedni (zapis z sierpnia) — bierzemy żądany.
        for day, hh, mm, ampm, zone in listing:
            d = dt.datetime.strptime(day, "%d %B %Y").date()
            if d.year != year:
                continue
            local = dt.datetime.combine(d, _hour(hh, mm, ampm), tzinfo=SYDNEY)
            if local.tzname() != zone:
                raise ValueError(f"{url}: {d} podane jako {zone}, w Sydney to {local.tzname()}")
            out[d] = local.astimezone(UTC)
    elif m := _TEXT_SCHEDULE.search(text):                            # układ do 2023
        at = _hour(m.group(1), m.group(2), m.group(3))
        for day, month in _TEXT_DAY.findall(m.group(4)):
            d = dt.datetime.strptime(f"{day} {month} {year}", "%d %B %Y").date()
            out[d] = dt.datetime.combine(d, at, tzinfo=SYDNEY).astimezone(UTC)
    if not out:
        raise ValueError(f"{url}: brak posiedzeń roku {year} w harmonogramie — nie zgaduję")
    return out


def announced_at(page_html: str, url: str) -> dt.time:
    """Godzina ogłoszenia ze zdania na stronie rocznej decyzji (dla roku bez harmonogramu):
    „…explained in a media release announcing the decision at 2.30 pm…”."""
    m = re.search(r"announcing the decision at (\d{1,2})\.(\d{2})\s*(am|pm)?", _text(page_html))
    if not m:
        raise ValueError(f"{url}: brak zdania z godziną ogłoszenia — nie zgaduję")
    return _hour(m.group(1), m.group(2), m.group(3) or "pm")


def release_mirror(url: str, stamp: str = DECISIONS_SNAPSHOT) -> str:
    """Adres kopii komunikatu w archiwum (rba.gov.au blokuje skrypty)."""
    return MIRROR.format(stamp=stamp, url=url)


def is_regular_meeting(release_html: str) -> bool:
    """Czy komunikat mówi o zwykłym posiedzeniu („At its meeting today”)."""
    return REGULAR_MEETING.lower() in _text(release_html).lower()
