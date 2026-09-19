"""Źródło kalendarza: publikacje danych z USA przez FRED/ALFRED.

DATA — Z DANYCH, NIE Z HARMONOGRAMU

`fred/release/dates` zwraca też dni rewizji i poprawek (13 dat w roku
zamiast 12, GDP 13–16 zamiast 4). Zamiast tego bierzemy z ALFRED
(`output_type=4`, initial release only) dzień PIERWSZEJ publikacji każdego
okresu referencyjnego. To dokładnie główna publikacja miesiąca, a dla GDP
— odczyt wstępny (advance), bo nowy kwartał pojawia się pierwszy raz
właśnie w nim.

Każda seria jest sprawdzana, czy należy do oczekiwanej publikacji FRED
(`series/release`). Identyfikatory publikacji znalezione przez
`fred/releases` 2026-09-19.

GODZINA — Z `config/calendar_times.yaml`

FRED nie podaje godziny. Bierzemy ją z prerejestrowanej tabeli potwierdzonej
przez użytkownika (ADR-032). Seria bez `verified: true` nie daje zdarzeń.

Klucz API nigdy nie trafia do `source`, cache ani logów.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc

# nazwa serii kalendarza → (seria FRED, id publikacji FRED).
# US_PCE, US_GDP_ADVANCE (`bea`), US_CPI, US_NFP (`bls`), US_RETAIL_SALES (`census`):
# zdarzenia z godziną każdej publikacji; tutaj tylko sprawdzenie dat krzyżowo.
SERIES: dict[str, tuple[str, int]] = {
    "US_CPI": ("CPIAUCSL", 10),
    "US_NFP": ("PAYEMS", 50),
    "US_PCE": ("PCEPI", 54),
    "US_RETAIL_SALES": ("RSAFS", 9),
    "US_GDP_ADVANCE": ("GDPC1", 53),
}
FROM_OTHER_SOURCE = {"US_PCE", "US_GDP_ADVANCE", "US_CPI", "US_NFP", "US_RETAIL_SALES"}


def first_release_dates(observations: list[dict]) -> list[dt.date]:
    """Dni pierwszej publikacji okresów (odpowiedź `output_type=4`).

    Okres bez wartości (".") też ma datę publikacji — wtedy wyszła
    informacja o braku danych, a rynek i tak na nią czekał; liczymy go.
    """
    return sorted({dt.date.fromisoformat(o["realtime_start"]) for o in observations})


def release_time(entry: dict, name: str) -> tuple[dt.time, ZoneInfo]:
    """Godzina i strefa z `calendar_times.yaml`. Niepotwierdzona = błąd."""
    if not entry.get("verified"):
        raise PermissionError(f"{name}: godzina niepotwierdzona (verified: false)")
    if not entry.get("local_time") or not entry.get("quote"):
        raise ValueError(f"{name}: potwierdzona godzina wymaga local_time i cytatu ze źródła")
    hh, mm = map(int, entry["local_time"].split(":"))
    return dt.time(hh, mm), ZoneInfo(entry["timezone"])


def events_for(name: str, dates: list[dt.date], at: dt.time, tz: ZoneInfo,
               start: dt.date, end: dt.date) -> list[dict]:
    """Wiersze kalendarza. Strefa lokalna → UTC z DST daty publikacji."""
    series_id, _ = SERIES[name]
    return [{
        "timestamp_utc": dt.datetime.combine(d, at, tzinfo=tz).astimezone(UTC),
        "currency": "USD", "name": name, "rank": "HIGH",
        "source": f"https://alfred.stlouisfed.org/series?seid={series_id}",
    } for d in dates if start <= d <= end]
