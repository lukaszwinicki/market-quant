"""Źródło kalendarza: decyzje EBC i konferencje prasowe, ecb.europa.eu.

LISTA POSIEDZEŃ

Roczne fragmenty `press/govcdec/mopo/<rok>/html/index_include.en.html`
(ładowane przez stronę „Monetary policy decisions”). Bierzemy komunikaty
„Monetary policy decisions” z `/press/pr/`, które zapowiadają konferencję
prasową („press conference starting at 14:30 CET today”). Posiedzenia
nadzwyczajne (np. ad hoc 15.06.2022) mają inne tytuły i nie mają
konferencji — odpadają (ADR-032).

GODZINY — ZE ŹRÓDEŁ

    ECB_PRESS_CONF  z KAŻDEGO komunikatu: „press conference starting at HH:MM CET”
    ECB_RATE        komunikat nie podaje godziny decyzji. Źródło:
                    ecb.pr220627 — „Starting from 21 July, monetary policy
                    decisions will be published at 14:15 CET (instead of
                    13:45). The press conferences will begin at 14:45 CET
                    (instead of 14:30).”
                    Spójność sprawdzana: konferencja 14:30 ⇔ decyzja 13:45,
                    14:45 ⇔ 14:15. Inna kombinacja = błąd.

„CET” = CZAS LOKALNY FRANKFURTU (Europe/Berlin), także latem

EBC pisze „CET” cały rok. Rozstrzygnięte na tickach EURUSD (2016): największe
ruchy M1 w dni decyzji letnich — 08.09 o 11:45 UTC (= 13:45 CEST), 21.07
i 02.06 o 12:30–12:43 UTC (konferencja 14:30 CEST); zimą 10.03 o 12:45 UTC
(= 13:45 CET). Dosłowne UTC+1 latem dałoby godzinę później.
"""

from __future__ import annotations

import datetime as dt
import html as htmllib
import re
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
FRANKFURT = ZoneInfo("Europe/Berlin")
BASE = "https://www.ecb.europa.eu"
TIMES_SOURCE = f"{BASE}/press/pr/date/2022/html/ecb.pr220627~73acedf868.en.html"
# (godzina konferencji ze źródła) → godzina decyzji wg ecb.pr220627
DECISION_FOR_CONFERENCE = {dt.time(14, 30): dt.time(13, 45), dt.time(14, 45): dt.time(14, 15)}

_ITEM = re.compile(r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", re.S)
_CONF = re.compile(r"press conference starting at (\d{1,2})[:.](\d{2}) CES?T", re.I)


def index_url(year: int) -> str:
    return f"{BASE}/press/govcdec/mopo/{year}/html/index_include.en.html"


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def decision_releases(index_html: str) -> list[tuple[dt.date, str]]:
    """(data, URL komunikatu) dla pozycji „Monetary policy decisions”."""
    out = []
    for d, dd in _ITEM.findall(index_html):
        title = _text(dd)
        link = re.search(r'href="(/press/pr/[^"]+\.en\.html)"', dd)
        if link and title.lower().startswith("monetary policy decisions"):
            out.append((dt.datetime.strptime(_text(d), "%d %B %Y").date(), BASE + link.group(1)))
    return sorted(set(out))


def meeting_times_utc(release_html: str, day: dt.date, url: str
                      ) -> tuple[dt.datetime, dt.datetime] | None:
    """(decyzja, konferencja) w UTC albo None, gdy komunikat nie zapowiada
    konferencji (posiedzenie bez konferencji = nie-planowe)."""
    m = _CONF.search(_text(release_html))
    if not m:
        return None
    conf = dt.time(int(m.group(1)), int(m.group(2)))
    if conf not in DECISION_FOR_CONFERENCE:
        raise ValueError(f"{url}: konferencja o {conf} — brak źródła godziny decyzji")
    local = lambda t: dt.datetime.combine(day, t, tzinfo=FRANKFURT).astimezone(UTC)  # noqa: E731
    return local(DECISION_FOR_CONFERENCE[conf]), local(conf)
