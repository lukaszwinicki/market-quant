"""Stopy procentowe — wejście do modelu finansowania (SPEC §9) i do
benchmarku carry + trend (§12).

CO JEST DOSTĘPNE, A CO NIE

Sprawdzone na FRED 2026-09-20 (skrypt `scripts/fetch_rates.py`):

* stopa overnight (call money) — OECD `IRSTCI01<ISO>M156N`, MIESIĘCZNA,
  komplet 132/132 miesiące 2015–2025 dla WSZYSTKICH sześciu walut
  kohorty A (USD, EUR, GBP, JPY, AUD, CAD);
* rentowność 2-letnia — TYLKO USD (`DGS2`). Dla EUR, GBP, JPY, AUD, CAD,
  NZD i CHF FRED jej NIE MA w żadnej częstotliwości. Wyszukiwanie po
  nazwie zwraca wyłącznie Turcję i Meksyk („6-month to 2-year”).
  Benchmark z §12 rankuje po `yield_2y`, więc bez innego źródła nie da
  się go policzyć zgodnie ze specyfikacją — patrz raport pokrycia;
* 3-miesięczny interbank — `IR3TIB01<ISO>M156N`, miesięczny, komplet dla
  ośmiu walut. Jedyna jednorodna seria terminowa, jaka na FRED jest.

OPÓŹNIENIE O MIESIĄC — NIE LOOK-AHEAD

Seria miesięczna dla stycznia to ŚREDNIA ze stycznia, a więc wielkość
znana dopiero po jego zakończeniu. Użycie jej do wyceny transakcji
ze stycznia byłoby zaglądaniem w przyszłość.

Dlatego `rate_on()` zwraca dla dnia d wartość z miesiąca POPRZEDZAJĄCEGO
miesiąc d. Stopa overnight jest publicznie obserwowalna na bieżąco, więc
średnia z miesiąca minionego jest w chwili decyzji faktycznie znana —
to wybór konserwatywny, nie przybliżenie.
"""

from __future__ import annotations

import datetime as dt

import polars as pl

SCHEMA: dict[str, pl.DataType] = {
    "date": pl.Date,
    "currency": pl.Utf8,
    "kind": pl.Utf8,          # overnight | interbank_3m | yield_2y
    "value": pl.Float64,      # procent rocznie, np. 5.33
    "series": pl.Utf8,        # identyfikator serii FRED
}

COHORT_A_CURRENCIES = ("USD", "EUR", "GBP", "JPY", "AUD", "CAD")
CARRY_CURRENCIES = ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "NZD", "CHF")

ISO = {"USD": "US", "EUR": "EZ", "GBP": "GB", "JPY": "JP",
       "AUD": "AU", "CAD": "CA", "NZD": "NZ", "CHF": "CH"}

OVERNIGHT = {c: f"IRSTCI01{i}M156N" for c, i in ISO.items()}
INTERBANK_3M = {c: f"IR3TIB01{i}M156N" for c, i in ISO.items()}
# Jedyna rentowność 2-letnia na FRED. Brak odpowiedników dla reszty walut
# jest ustaleniem, nie przeoczeniem — patrz nagłówek modułu.
YIELD_2Y = {"USD": "DGS2"}

KINDS = {"overnight": OVERNIGHT, "interbank_3m": INTERBANK_3M, "yield_2y": YIELD_2Y}


def empty() -> pl.DataFrame:
    return pl.DataFrame(schema=SCHEMA)


def _prev_month(d: dt.date) -> dt.date:
    """Pierwszy dzień miesiąca poprzedzającego miesiąc `d`."""
    return (d.replace(day=1) - dt.timedelta(days=1)).replace(day=1)


def rate_on(rates: pl.DataFrame, currency: str, day: dt.date,
            kind: str = "overnight") -> float:
    """Stopa roczna (w procentach) obowiązująca przy decyzji w dniu `day`.

    Dla serii miesięcznych bierze miesiąc POPRZEDNI — patrz nagłówek.
    Brak wartości to błąd, nie zero: zero udawałoby stopę zerową, a to
    wielkość, która wchodzi wprost do wyniku.
    """
    if kind not in KINDS:
        raise ValueError(f"nieznany rodzaj stopy: {kind}")
    cutoff = _prev_month(day)
    hit = (rates
           .filter((pl.col("currency") == currency) & (pl.col("kind") == kind)
                   & (pl.col("date") <= cutoff))
           .sort("date").tail(1))
    if hit.is_empty():
        raise KeyError(f"brak stopy {kind} dla {currency} na {day} "
                       f"(szukano wpisu <= {cutoff})")
    return float(hit["value"][0])


def differential(rates: pl.DataFrame, symbol: str, day: dt.date,
                 kind: str = "overnight") -> float:
    """Stopa bazowa minus kwotowana, w procentach rocznie.

    Dodatnia = waluta bazowa płaci więcej, czyli LONG na parze dostaje
    carry, a SHORT go płaci.
    """
    base, quote = symbol[:3], symbol[3:]
    return rate_on(rates, base, day, kind) - rate_on(rates, quote, day, kind)


def coverage_gaps(rates: pl.DataFrame, currencies: tuple[str, ...],
                  kind: str, start: dt.date, end: dt.date) -> list[tuple[str, int]]:
    """(waluta, liczba brakujących miesięcy) dla serii miesięcznych.

    Ta sama rola co `calendar.coverage_gaps()`: brak serii wygląda dalej
    w rachunku tak samo jak stopa zerowa, więc musi być wykryty tutaj.
    """
    want = set()
    d = start.replace(day=1)
    while d <= end:
        want.add((d.year, d.month))
        d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)

    out = []
    for ccy in currencies:
        have = {(r[0].year, r[0].month) for r in
                rates.filter((pl.col("currency") == ccy) & (pl.col("kind") == kind))
                .select("date").iter_rows()}
        if missing := want - have:
            out.append((ccy, len(missing)))
    return out


def require_coverage(rates: pl.DataFrame, currencies: tuple[str, ...], kind: str,
                     start: dt.date, end: dt.date) -> None:
    """Rzuć, jeśli którejkolwiek walucie brakuje miesięcy w zakresie."""
    if gaps := coverage_gaps(rates, currencies, kind, start, end):
        raise ValueError(
            f"niepełne stopy {kind}: "
            + ", ".join(f"{c} brakuje {n} mies." for c, n in gaps))
