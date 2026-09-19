"""Źródło kalendarza: decyzje Bank of Canada, bankofcanada.ca.

LISTA KOMUNIKATÓW

`/press/press-releases/?mt_page=N` — lista komunikatów prasowych, od
najnowszych. Z niej dwa rodzaje linków:

    decyzje        `/<rok>/<mies>/fad-press-release-RRRR-MM-DD/`
    harmonogramy   `/<rok>/<mies>/…schedule…/` — raz w roku (lipiec/sierpień),
                   daty decyzji na rok następny i potwierdzenie pozostałych
                   w roku bieżącym, z godziną ogłoszeń.

DATY I GODZINY — Z HARMONOGRAMÓW

Część o decyzjach kończy się zdaniem z godziną: „All interest rate
announcements will take place at 09:45 (ET)” (wcześniej „will be made at
10:00 (ET)”). Komunikat z 07.2020 zamiast tego: „The Bank is also reviewing
the publication time of its interest rate announcements, which is currently
10:00 (ET)” — komunikat z 07.2021 potwierdza 10:00 dla reszty 2021, więc
przegląd niczego nie zmienił. Wszystkie daty PRZED tym zdaniem to decyzje;
rok = ostatni czterocyfrowy rok wymieniony przed datą („for 2016 are…”,
„remainder of 2022:”).

Godzina daty = godzina z NAJPÓŹNIEJSZEGO harmonogramu, który tę datę
wymienia. Ma to znaczenie: harmonogram z 08.2024 przesunął pozostałe decyzje
2024 (wrzesień–grudzień) na 09:45, a styczeń–lipiec 2024 były o 10:00.

Tylko daty z harmonogramu (ADR-032): cięcia nadzwyczajne (13 i 27.03.2020)
odpadają. Każda data harmonogramu musi mieć komunikat decyzji — inaczej błąd
(przełożone posiedzenie wyszłoby tu na jaw).

Strefa: „(ET)” = America/Toronto, z DST daty decyzji.
"""

from __future__ import annotations

import datetime as dt
import html as htmllib
import re
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
ET = ZoneInfo("America/Toronto")
BASE = "https://www.bankofcanada.ca"

_LINK = re.compile(rf'{re.escape(BASE)}/(\d{{4}})/(\d{{2}})/([a-z0-9-]+)/')
_FAD = re.compile(r"fad-press-release-(\d{4})-(\d{2})-(\d{2})")
_TIME = re.compile(r"(?:announcements will (?:be made|take place) at|which is currently) "
                   r"(\d{1,2}):(\d{2}) \(ET\)")
_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_DATE = re.compile(rf"Wednesday,? (?:(\d{{1,2}}) ({_MONTHS})|({_MONTHS}) (\d{{1,2}}))")
_YEAR = re.compile(r"\b(20\d\d)\b")


def listing_url(page: int) -> str:
    return f"{BASE}/press/press-releases/?mt_page={page}"


def _text(fragment: str) -> str:
    fragment = re.sub(r"<(script|style)\b.*?</\1>", " ", fragment, flags=re.S | re.I)
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def listing_links(html: str) -> tuple[dict[dt.date, str], dict[str, tuple[int, int]]]:
    """({data decyzji: URL}, {URL harmonogramu: (rok, miesiąc publikacji)})."""
    decisions, schedules = {}, {}
    for m in _LINK.finditer(html):
        url, slug = m.group(0), m.group(3)
        if f := _FAD.fullmatch(slug):
            decisions[dt.date(*map(int, f.groups()))] = url
        elif "schedule" in slug:
            schedules[url] = (int(m.group(1)), int(m.group(2)))
    return decisions, schedules


def schedule_dates(html: str, url: str) -> tuple[list[dt.date], dt.time]:
    """Daty decyzji z harmonogramu i godzina ogłoszeń (ET)."""
    text = _text(html)
    start = text.find("The Bank of Canada today")
    t = _TIME.search(text, max(start, 0))
    if start < 0 or not t:
        raise ValueError(f"{url}: brak zdania z godziną ogłoszeń — nie zgaduję")
    section = text[start:t.start()]
    out = []
    for m in _DATE.finditer(section):
        years = _YEAR.findall(section[:m.start()])
        if not years:
            raise ValueError(f"{url}: data {m.group(0)!r} bez roku przed nią")
        day, month = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        out.append(dt.datetime.strptime(f"{day} {month} {years[-1]}", "%d %B %Y").date())
    if not out:
        raise ValueError(f"{url}: brak dat decyzji")
    return out, dt.time(int(t.group(1)), int(t.group(2)))


def scheduled_times_utc(schedules: list[tuple[tuple[int, int], list[dt.date], dt.time, str]],
                        decisions: dict[dt.date, str]) -> list[tuple[dt.datetime, str]]:
    """(moment decyzji UTC, URL komunikatu decyzji) dla dat z harmonogramów.

    `schedules`: ((rok, miesiąc publikacji), daty, godzina, URL). Godzina daty
    z najpóźniej opublikowanego harmonogramu, który ją wymienia. Data bez
    komunikatu decyzji — błąd, chyba że jeszcze nie nadeszła.
    """
    at: dict[dt.date, tuple[tuple[int, int], dt.time]] = {}
    for published, dates, time, url in schedules:
        for d in dates:
            if (d.year, d.month) <= published:
                raise ValueError(f"{url}: data {d} nie później niż publikacja {published}")
            if d not in at or at[d][0] < published:
                at[d] = (published, time)
    newest = max(decisions, default=dt.date.min)
    if missing := sorted(d for d in at if d not in decisions and d <= newest):
        raise ValueError(f"daty z harmonogramu bez komunikatu decyzji: {missing}")
    return sorted(
        (dt.datetime.combine(d, t, tzinfo=ET).astimezone(UTC), decisions[d])
        for d, (_, t) in at.items() if d in decisions)
