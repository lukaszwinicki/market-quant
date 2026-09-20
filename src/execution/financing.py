"""Finansowanie pozycji dla kohorty A — swap FX (SPEC §9, ADR-035).

DLACZEGO TO NIE JEST DROBIAZG

Bramka 0 zmierzyła koszt spreadu na 0,0106 R. Różnica stóp EUR/USD sięgała
w badanym okresie 2,8 punktu procentowego, co przy stopie ~1,1% ceny
i dziesięciu dniach trzymania daje rzędu 0,07 R — kilka razy więcej niż
spread i większość progu bramki 2 (0,10 R).

Gorzej: swap jest KIERUNKOWY. Long dostaje to, co short płaci. Pominięcie
go nie zmniejsza po prostu wyniku, tylko dokłada stałą przewagę jednej
stronie każdej pary — dokładnie ten kształt, który kontrola #8 ma wykrywać
jako fałszywy edge. Model, który w latach 2017–2019 kupował AUD za JPY,
zarabiałby na carry i wyglądałby jak sygnał.

WZÓR (z `config/v1_baseline.yaml`, `costs.financing.formula`)

    Koszt_R = (stawka_roczna × dni) / (365 × stop_jako_ułamek_ceny)

Procent ryzyka skraca się — dlatego wynik jest w R i nie zależy od `r%`.

    stawka_roczna = marża + (kwotowana − bazowa)   dla longa
                    marża + (bazowa − kwotowana)   dla shorta

Marżę płacą OBIE strony: broker bierze ją w jedną i w drugą. Różnica stóp
jest symetryczna, marża nie — i to ona sprawia, że carry nie jest darmowy.

POTRÓJNY SWAP W ŚRODĘ

Rollover o 17:00 NY przesuwa datę waluty o dzień roboczy. W środę przesuwa
ją przez weekend, więc nalicza się trzy dni. Sobota i niedziela nie mają
rolloveru. Pełny tydzień to 1+1+3+1+1 = 7 dni, czyli tyle, ile dni
kalendarzowych — i tak ma być.

STOPA JEST Z MIESIĄCA POPRZEDNIEGO

Patrz `data/rates.py`: seria miesięczna dla stycznia to średnia ze stycznia,
znana dopiero po jego końcu. Bierzemy stopę obowiązującą w chwili DECYZJI
i trzymamy ją przez całą transakcję — horyzont to 10 dni roboczych, więc
zmiana stóp w środku okna jest drugiego rzędu, a wariant „stopa z dnia
rozstrzygnięcia" zaglądałby w przyszłość.
"""

from __future__ import annotations

import datetime as dt

import polars as pl

from ..data.rates import differential

UTC = dt.timezone.utc

# Rollover o 17:00 Nowy Jork. Trzymamy jedną godzinę UTC zamiast strefy,
# bo przesunięcie DST (21:00 vs 22:00 UTC) zmienia wynik tylko wtedy, gdy
# wejście albo wyjście wypada dokładnie w tej godzinie — a wtedy i tak
# liczy się data waluty, której z barów nie odtworzymy.
ROLLOVER_UTC = dt.time(21, 0)

WEDNESDAY = 2
TRIPLE = 3


def rollover_days(entry: dt.datetime, exit_: dt.datetime) -> int:
    """Dni finansowania między wejściem a wyjściem, ze środą liczoną potrójnie.

    Liczymy momenty rolloveru ściśle po `entry` i nie później niż `exit_`.
    Sobota i niedziela nie mają rolloveru — ich dni waluty niesie środa.
    """
    if exit_ < entry:
        raise ValueError("wyjście przed wejściem")
    days = 0
    d = entry.date()
    while True:
        roll = dt.datetime.combine(d, ROLLOVER_UTC, tzinfo=UTC)
        if roll > exit_:
            break
        if roll > entry:
            wd = d.weekday()
            if wd == WEDNESDAY:
                days += TRIPLE
            elif wd < 5:
                days += 1
        d += dt.timedelta(days=1)
    return days


def financing_r(side: str, days: int, stop_pct: float, diff_pct: float,
                markup_annual_pct: float) -> float:
    """Koszt finansowania w R. Dodatni = obciąża wynik, ujemny = carry dopłaca.

    `diff_pct`  — stopa bazowa minus kwotowana, w procentach rocznie
    `stop_pct`  — dystans stopu jako UŁAMEK ceny wejścia (0,011 = 1,1%)
    """
    if stop_pct <= 0:
        raise ValueError("stop musi być dodatnim ułamkiem ceny")
    if markup_annual_pct < 0:
        raise ValueError("marża brokera nie może być ujemna")
    if side not in ("long", "short"):
        raise ValueError(f"nieznany kierunek: {side}")

    carry = diff_pct if side == "long" else -diff_pct
    annual_pct = markup_annual_pct - carry
    return (annual_pct / 100.0) * days / (365.0 * stop_pct)


def apply_financing(labels: pl.DataFrame, rates: pl.DataFrame,
                    markup_annual_pct: float) -> pl.DataFrame:
    """Dołóż kolumnę `financing_r` i odejmij ją od `r`.

    Wymaga kolumn: symbol, ts, t1, side, entry_price, sl. `r` przed
    korektą pozostaje odtwarzalne jako `r + financing_r`.

    Brak stopy dla którejkolwiek waluty jest błędem, nie zerem — zero
    udawałoby świat bez różnicy stóp (patrz `rates.rate_on`).
    """
    required = ("symbol", "ts", "t1", "side", "entry_price", "sl", "r")
    if missing := [c for c in required if c not in labels.columns]:
        raise ValueError(f"etykiety bez kolumn: {missing}")
    if labels.is_empty():
        return labels.with_columns(pl.lit(0.0).alias("financing_r"))

    # Różnica stóp jest stała w obrębie (para, miesiąc decyzji) — liczymy ją
    # raz na taką parę zamiast raz na transakcję.
    cache: dict[tuple[str, int, int], float] = {}
    out: list[float] = []
    units: list[float] = []
    for row in labels.iter_rows(named=True):
        day = row["ts"].date()
        key = (row["symbol"], day.year, day.month)
        if key not in cache:
            cache[key] = differential(rates, row["symbol"], day)
        risk = abs(row["entry_price"] - row["sl"])
        if risk <= 0:
            raise ValueError(f"zerowy dystans stopu: {row['symbol']} {row['ts']}")
        days = rollover_days(row["ts"], row["t1"])
        stop_pct = risk / abs(row["entry_price"])
        out.append(financing_r(
            side=row["side"], days=days, stop_pct=stop_pct,
            diff_pct=cache[key], markup_annual_pct=markup_annual_pct,
        ))
        # Koszt w R przypadający na JEDEN punkt procentowy stawki rocznej.
        # Dzięki niemu marżę da się przeliczyć bez ponownego chodzenia po
        # stopach — wzór jest w niej liniowy (ADR-037, oś wrażliwości).
        units.append(days / (365.0 * stop_pct) / 100.0)

    return labels.with_columns(
        pl.Series("financing_r", out, dtype=pl.Float64),
        pl.Series("fin_unit_r", units, dtype=pl.Float64),
    ).with_columns((pl.col("r") - pl.col("financing_r")).alias("r"))


def markup_from(cfg: dict) -> float:
    """Marża brokera dla kohorty A, w procentach rocznie, wprost z configu."""
    return float(cfg["costs"]["financing"]["cohort_a_markup_annual_pct"])


def markup_grid_from(cfg: dict) -> tuple[float, ...]:
    """Oś wrażliwości na marżę (ADR-037). Wynik punktowy nie wystarcza."""
    return tuple(float(x) for x in
                 cfg["costs"]["financing"]["cohort_a_markup_sensitivity"])


def refinanced(labels: pl.DataFrame, base_markup: float,
               markup: float) -> pl.Series:
    """Kolumna `r` przy innej marży, bez ponownego czytania stóp.

    Stawka roczna wchodzi we wzór liniowo, a `fin_unit_r` to koszt w R na
    jeden punkt procentowy — więc zmiana marży to dodanie różnicy razy ta
    jednostka. Carry i liczba dni zostają takie, jakie były.
    """
    for col in ("r", "financing_r", "fin_unit_r"):
        if col not in labels.columns:
            raise ValueError(f"etykiety bez kolumny `{col}` — najpierw apply_financing()")
    delta = (markup - base_markup) * pl.col("fin_unit_r")
    return labels.select((pl.col("r") - delta).alias("r"))["r"]
