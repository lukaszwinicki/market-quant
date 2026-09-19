"""Źródło kalendarza: CPI Japonii, Statistics Bureau (stat.go.jp).

HARMONOGRAM Z GODZINĄ

`/data/kouhyou/e-stat_cpi.xml` to plik harmonogramu publikacji (ten sam,
z którego korzysta e-Stat). Każda pozycja ma datę I GODZINĘ:

    <class_1 name="全国">                     ← Japonia (ogółem); drugi blok to
      <class_2 name="平成28年(2016年)1月分">     „東京都区部（中旬速報値）”, czyli
        …<release_year>2016</release_year>     wstępny odczyt dla Tokio — nie bierzemy
           <release_month>2</release_month>
           <release_day>26</release_day>
           <release_hour>8</release_hour>
           <release_minute>30</release_minute>

Plik bieżący obejmuje ~rok. Lata 2016–2021 mają własne pliki
`e-stat_cpi<rok>.xml`, dziś już niedostępne — czytane z kopii Wayback
(jak w `calendar_rba`). Dla 2022+ wystarczą kopie pliku bieżącego.

Bierzemy wyłącznie pozycje miesięczne (`class_2` kończące się na „月分”):
średnie roczne i za rok fiskalny bywają publikowane w osobnym terminie
(np. 2 i 30 marca 2018) i nie są odczytem miesięcznym.

Kodowanie XML: UTF-16. Strefa: Asia/Tokyo (bez czasu letniego).
"""

from __future__ import annotations

import datetime as dt
import re
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
TOKYO = ZoneInfo("Asia/Tokyo")
BASE = "https://www.stat.go.jp"
CURRENT_XML = f"{BASE}/data/kouhyou/e-stat_cpi.xml"
MIRROR = "https://web.archive.org/web/{stamp}id_/{url}"
JAPAN = "全国"

# Kopie harmonogramu w archiwum: roczne pliki (2016–2021) i bieżący plik
# w kolejnych latach. Każda kopia obejmuje około roku publikacji.
SCHEDULE_SNAPSHOTS: tuple[tuple[str, str], ...] = (
    ("20160223235012", f"{BASE}/data/kouhyou/e-stat_cpi2016.xml"),
    ("20170526041027", f"{BASE}/data/kouhyou/e-stat_cpi2017.xml"),
    ("20180705084337", f"{BASE}/data/kouhyou/e-stat_cpi2018.xml"),
    ("20190826024238", f"{BASE}/data/kouhyou/e-stat_cpi2019.xml"),
    ("20200806135244", f"{BASE}/data/kouhyou/e-stat_cpi2020.xml"),
    ("20210616085713", f"{BASE}/data/kouhyou/e-stat_cpi2021.xml"),
    ("20220116173241", CURRENT_XML),
    ("20221116111354", CURRENT_XML),
    ("20230205040435", CURRENT_XML),
    ("20231209081148", CURRENT_XML),
    ("20241220023234", CURRENT_XML),
    ("20251128213433", CURRENT_XML),
)

_BLOCK = re.compile(r'<class_1 name="([^"]*)">(.*?)(?=<class_1 name="|</e-stat>|\Z)', re.S)
_PERIOD = re.compile(r'<class_2 name="([^"]*)">(.*?)(?=<class_2 name="|</class_1>|\Z)', re.S)
# „平成28年(2016年)1月分”, „令和元年(2019年)5月分”, „2025年12月分” — miesiąc odniesienia.
# Klucz musi być rokiem i miesiącem, nie nazwą: ta sama publikacja nazywa się
# inaczej po zmianie ery (平成31年 → 令和元年 w maju 2019).
_MONTHLY = re.compile(r"(?:\((\d{4})年\)|(\d{4})年)(\d{1,2})月分")
_RELEASE = re.compile(
    r"<release_year>(\d+)</release_year>\s*<release_month>(\d+)</release_month>\s*"
    r"<release_day>(\d+)</release_day>\s*<release_hour>(\d+)</release_hour>\s*"
    r"<release_minute>(\d+)</release_minute>", re.S)


def snapshot_url(stamp: str, url: str) -> str:
    return MIRROR.format(stamp=stamp, url=url)


def decode(raw: bytes) -> str:
    """Harmonogram jest w UTF-16 (ze znacznikiem kolejności bajtów)."""
    for enc in ("utf-16", "utf-8", "shift_jis"):
        try:
            return raw.decode(enc)
        except UnicodeError:
            continue
    raise ValueError("nieznane kodowanie harmonogramu")


def release_times_utc(xml: str, url: str, series: str = JAPAN
                      ) -> dict[tuple[int, int], dt.datetime]:
    """{(rok, miesiąc odniesienia): moment publikacji UTC} z jednego harmonogramu.

    Kluczem jest okres, bo terminy bywają przesuwane: plik z 2017 r.
    zapowiadał odczyt za styczeń 2018 na 2 marca, a plik z 2018 r. podaje
    23 lutego. Wywołujący bierze termin z najnowszej kopii harmonogramu.
    """
    blocks = [body for name, body in _BLOCK.findall(xml) if name.startswith(series)]
    if not blocks:
        raise ValueError(f"{url}: brak bloku „{series}” — zmiana układu?")
    out: dict[tuple[int, int], dt.datetime] = {}
    for body in blocks:
        for period, entries in _PERIOD.findall(body):
            m = _MONTHLY.search(period)
            if not m:
                continue
            key = (int(m.group(1) or m.group(2)), int(m.group(3)))
            for y, mo, d, hh, mm in _RELEASE.findall(entries):
                local = dt.datetime(int(y), int(mo), int(d), int(hh), int(mm), tzinfo=TOKYO)
                out[key] = local.astimezone(UTC)
    if not out:
        raise ValueError(f"{url}: blok „{series}” bez terminów miesięcznych")
    return out
