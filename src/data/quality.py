"""Raport jakości danych — kryterium Bramki 0.

Zadaniem raportu NIE jest stwierdzić, że dane są ładne. Zadaniem jest
znaleźć powody, dla których nie wolno im ufać.

Najgroźniejszy scenariusz, przed którym ten moduł broni: serwer podczas
awarii zwraca pustą odpowiedź dla godziny, w której dane istnieją. Taki
plik trafia do cache jako "sprawdzone, brak danych" i luka staje się
niewidoczna — backtest po prostu nie handluje w tym czasie i nikt się
nie dowiaduje.

Wykrywamy to porównaniem między instrumentami: brak danych u WSZYSTKICH
sześciu par jednocześnie, w godzinie, która normalnie jest handlowa, to
podpis awarii feedu, a nie zamknięcia rynku.

Kalendarz handlu jest WYPROWADZANY z danych, nie zakładany. Zakodowanie
godzin sesji ukryłoby dokładnie te luki, które mamy znaleźć.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import polars as pl

from .dukascopy import pip_size

UTC = dt.timezone.utc

# Klasyfikacja komórek (dzień tygodnia, godzina UTC) jest TRÓJSTANOWA.
#
# Podział binarny ma dwie wady, obie wyszły w testach:
#
# 1. Próg liczony z tych samych danych, w których szukamy luk, sam się
#    unieważnia: systematyczna awaria spycha komórkę poniżej progu,
#    komórka przestaje być "handlowa" i luka znika z raportu.
# 2. Godziny otwarcia niedzielnego mają pokrycie ~50%, bo DST przesuwa
#    je między 21:00 a 22:00 UTC. Binarnie wpadają losowo po jednej
#    albo drugiej stronie.
#
# Rozkład pokrycia jest w praktyce dwumodalny: sobota ~0, środek tygodnia
# ~1. Cokolwiek pomiędzy jest samo w sobie informacją i trafia do osobnej
# sekcji raportu zamiast być wciskane w jedną z dwóch kategorii.
TRADING_CELL_MIN = 0.80      # powyżej: brak danych = prawdziwa luka
CLOSED_CELL_MAX = 0.20       # poniżej: rynek zamknięty, brak danych normalny

# Luka wewnątrz bara H1 uznawana za istotną.
MAX_GAP_SECONDS = 60

# Jedyne ZAKŁADANE zamknięcia rynku: 25.12 i 1.01 — rynek FX stoi w oba dni
# globalnie, a kalendarz tygodniowy tego nie wyprowadzi (to nie są stałe
# komórki dzień/godzina). Bez tego każdy rok dawał ~36 fałszywych "awarii".
# Lista celowo minimalna: Wielki Piątek i inne święta FX bywają otwarte,
# więc brak danych w nich MA się pokazać jako podejrzany.
MARKET_HOLIDAYS = {(12, 25), (1, 1)}
# Ciągły blok pustych godzin dłuższy niż to nie jest świętem, nawet jeśli
# dotyka 25.12 albo 1.01 — prawdziwa awaria przy święcie nie może się schować.
MAX_HOLIDAY_RUN_HOURS = 36


@dataclass
class QualityReport:
    symbol_coverage: pl.DataFrame          # per symbol: bary, luki, pokrycie
    suspected_outages: pl.DataFrame        # godziny puste u wszystkich symboli
    per_symbol_gaps: pl.DataFrame          # godziny brakujące u części symboli
    spread_stats: pl.DataFrame             # rozkład spreadu per symbol
    ambiguous_cells: pl.DataFrame | None = None   # granice DST i sesji
    invariant_errors: list[str] = field(default_factory=list)
    holiday_closures: pl.DataFrame | None = None  # 25.12 / 1.01 — nie awarie

    def passes_gate_0(self, max_gap_pct: float = 5.0) -> tuple[bool, list[str]]:
        """Kryterium z PROJECT_SPEC §15: luki > 5% barów na >= 2 parach = STOP."""
        reasons: list[str] = []

        bad = self.symbol_coverage.filter(pl.col("gap_pct") > max_gap_pct)
        if bad.height >= 2:
            names = ", ".join(bad["symbol"].to_list())
            reasons.append(
                f"luki > {max_gap_pct}% barów H1 na {bad.height} parach ({names})"
            )
        if self.invariant_errors:
            reasons.append(f"{len(self.invariant_errors)} naruszeń niezmienników barów")
        if self.suspected_outages.height:
            reasons.append(
                f"{self.suspected_outages.height} godzin podejrzanych o awarię feedu "
                "— wymagają ręcznego sprawdzenia przed akceptacją danych"
            )
        return (not reasons), reasons


def trading_cells(bars: pl.DataFrame) -> pl.DataFrame:
    """Wyprowadź z danych, które (dzień tygodnia, godzina UTC) są handlowe.

    Zwraca wszystkie komórki z udziałem obecności i flagą `is_trading`.
    """
    if bars.is_empty():
        return pl.DataFrame(schema={"weekday": pl.Int8, "hour": pl.Int8,
                                    "present": pl.UInt32, "total": pl.UInt32,
                                    "coverage": pl.Float64, "state": pl.Utf8,
                                    "is_trading": pl.Boolean})

    present = (
        bars.select(
            pl.col("ts").dt.weekday().cast(pl.Int8).alias("weekday"),
            pl.col("ts").dt.hour().cast(pl.Int8).alias("hour"),
            pl.col("ts").dt.date().alias("date"),
        )
        .unique()
        .group_by("weekday", "hour")
        .agg(pl.len().cast(pl.UInt32).alias("present"))
    )

    # Mianownik: ile razy dana komórka w ogóle wystąpiła w kalendarzu zakresu.
    lo, hi = bars["ts"].min(), bars["ts"].max()
    calendar = (
        pl.datetime_range(lo, hi, interval="1h", time_zone="UTC", eager=True)
        .alias("ts").to_frame()
        .with_columns(pl.col("ts").cast(pl.Datetime("ms", "UTC")))
        .select(
            pl.col("ts").dt.weekday().cast(pl.Int8).alias("weekday"),
            pl.col("ts").dt.hour().cast(pl.Int8).alias("hour"),
        )
        .group_by("weekday", "hour")
        .agg(pl.len().cast(pl.UInt32).alias("total"))
    )

    return (
        calendar.join(present, on=["weekday", "hour"], how="left")
        .with_columns(pl.col("present").fill_null(0))
        .with_columns((pl.col("present") / pl.col("total")).alias("coverage"))
        .with_columns(
            pl.when(pl.col("coverage") >= TRADING_CELL_MIN).then(pl.lit("trading"))
            .when(pl.col("coverage") <= CLOSED_CELL_MAX).then(pl.lit("closed"))
            .otherwise(pl.lit("ambiguous")).alias("state")
        )
        .with_columns((pl.col("state") == "trading").alias("is_trading"))
        .sort("weekday", "hour")
    )


def missing_trading_hours(
    bars: pl.DataFrame,
    cells: pl.DataFrame,
    span: tuple[dt.datetime, dt.datetime] | None = None,
) -> pl.DataFrame:
    """Godziny, które wg wyprowadzonego kalendarza powinny mieć dane, a nie mają.

    `span` pozwala narzucić zakres WSPÓLNY dla wszystkich symboli. Bez tego
    symbol, którego dane urywają się wcześniej, wygląda bezbłędnie — jego
    kalendarz kończy się razem z jego danymi i obcięcie nie jest luką.
    """
    if bars.is_empty() and span is None:
        return pl.DataFrame(schema={"ts": pl.Datetime("ms", "UTC")})

    lo, hi = span if span else (bars["ts"].min(), bars["ts"].max())
    expected = (
        pl.datetime_range(lo, hi, interval="1h", time_zone="UTC", eager=True)
        .alias("ts").to_frame()
        .with_columns(pl.col("ts").cast(pl.Datetime("ms", "UTC")))
        .with_columns(
            pl.col("ts").dt.weekday().cast(pl.Int8).alias("weekday"),
            pl.col("ts").dt.hour().cast(pl.Int8).alias("hour"),
        )
        .join(cells.filter("is_trading").select("weekday", "hour"),
              on=["weekday", "hour"], how="inner")
    )
    have = bars.select("ts") if not bars.is_empty() else pl.DataFrame(
        schema={"ts": pl.Datetime("ms", "UTC")})
    return expected.join(have, on="ts", how="anti").select("ts").sort("ts")


def split_holiday_closures(
    hours: list[dt.datetime],
) -> tuple[list[dt.datetime], list[dt.datetime]]:
    """Rozdziel godziny puste u wszystkich par na (awarie, święta).

    Świętem jest ciągły blok (krok 1h) dotykający daty z MARKET_HOLIDAYS
    i nie dłuższy niż MAX_HOLIDAY_RUN_HOURS. Blok obejmuje też wieczór
    31.12, bo rynek zamyka się o 17:00 czasu nowojorskiego.
    """
    runs: list[list[dt.datetime]] = []
    for h in sorted(hours):
        if runs and h - runs[-1][-1] == dt.timedelta(hours=1):
            runs[-1].append(h)
        else:
            runs.append([h])

    outages, holidays = [], []
    for run in runs:
        touches = any((h.month, h.day) in MARKET_HOLIDAYS for h in run)
        if touches and len(run) <= MAX_HOLIDAY_RUN_HOURS:
            holidays += run
        else:
            outages += run
    return outages, holidays


def build_report(bars_by_symbol: dict[str, pl.DataFrame]) -> QualityReport:
    """Zbuduj raport z barów H1 wszystkich symboli."""
    from .resample import validate_bars

    coverage_rows, spread_rows, ambiguous_rows = [], [], []
    missing_by_symbol: dict[str, set] = {}
    invariant_errors: list[str] = []

    # Kalendarz handlu wyprowadzamy z SUMY wszystkich symboli, a zakres dat
    # ze wspólnych krańców. Liczenie osobno per symbol dawało dwa błędy:
    # obcięta seria nie miała luk, a systematyczna awaria wypychała komórkę
    # poza kalendarz, przez co znikała z raportu.
    non_empty = [b for b in bars_by_symbol.values() if not b.is_empty()]
    if not non_empty:
        return QualityReport(pl.DataFrame(), pl.DataFrame(), pl.DataFrame(),
                             pl.DataFrame(), pl.DataFrame(), [])
    union_ts = pl.concat([b.select("ts") for b in non_empty]).unique().sort("ts")
    span = (union_ts["ts"].min(), union_ts["ts"].max())
    global_cells = trading_cells(union_ts)

    for symbol, bars in sorted(bars_by_symbol.items()):
        try:
            validate_bars(bars)
        except ValueError as exc:
            invariant_errors.append(f"{symbol}: {exc}")

        cells = trading_cells(bars)
        for r in cells.filter(pl.col("state") == "ambiguous").iter_rows(named=True):
            ambiguous_rows.append({"symbol": symbol, "weekday": r["weekday"],
                                   "hour": r["hour"], "coverage": r["coverage"]})
        missing = missing_trading_hours(bars, global_cells, span=span)
        missing_by_symbol[symbol] = set(missing["ts"].to_list())

        if not bars.is_empty():
            sc = bars["spread_close"]
            sm = bars["spread_max"]
            spread_rows.append({
                "symbol": symbol,
                "close_median": float(sc.median()),
                "close_p95": float(sc.quantile(0.95)),
                "max_median": float(sm.median()),
                "max_p95": float(sm.quantile(0.95)),
                "max_observed": float(sm.max()),
                "n_ticks_median": float(bars["n_ticks"].median()),
            })

    # Awaria feedu: godzina brakująca u WSZYSTKICH symboli naraz.
    outages: list[dt.datetime] = []
    holidays: list[dt.datetime] = []
    if len(missing_by_symbol) > 1:
        common = set.intersection(*missing_by_symbol.values())
        outages, holidays = split_holiday_closures(list(common))

    # Święta nie są lukami — rynek był zamknięty, nie było czego pobrać.
    holiday_set = set(holidays)
    for symbol, bars in sorted(bars_by_symbol.items()):
        missing_n = len(missing_by_symbol[symbol] - holiday_set)
        expected = bars.height + missing_n
        coverage_rows.append({
            "symbol": symbol,
            "bars": bars.height,
            "expected": expected,
            "missing": missing_n,
            "gap_pct": 100.0 * missing_n / expected if expected else 0.0,
            "first": bars["ts"].min(),
            "last": bars["ts"].max(),
        })

    return QualityReport(
        symbol_coverage=pl.DataFrame(coverage_rows),
        suspected_outages=pl.DataFrame({"ts": outages}),
        per_symbol_gaps=pl.DataFrame(
            [
                {"symbol": s, "ts": t}
                for s, ts in missing_by_symbol.items()
                for t in sorted(ts) if t not in set(outages) | holiday_set
            ],
            schema={"symbol": pl.Utf8, "ts": pl.Datetime("ms", "UTC")},
        ),
        spread_stats=pl.DataFrame(spread_rows),
        ambiguous_cells=pl.DataFrame(
            ambiguous_rows,
            schema={"symbol": pl.Utf8, "weekday": pl.Int8,
                    "hour": pl.Int8, "coverage": pl.Float64},
        ),
        invariant_errors=invariant_errors,
        holiday_closures=pl.DataFrame(
            {"ts": holidays}, schema={"ts": pl.Datetime("ms", "UTC")}),
    )


def render_markdown(report: QualityReport) -> str:
    """Raport w Markdown — wersjonowany w repo jako dowód dla Bramki 0."""
    ok, reasons = report.passes_gate_0()
    lines = [
        "# Raport jakości danych",
        "",
        f"> Wygenerowano: {dt.datetime.now(UTC):%Y-%m-%d %H:%M} UTC",
        f"> Bramka 0: **{'PRZECHODZI' if ok else 'NIE PRZECHODZI'}**",
        "",
    ]
    if reasons:
        lines += ["## Powody odrzucenia", ""] + [f"- {r}" for r in reasons] + [""]

    lines += ["## Pokrycie", "",
              "| Symbol | Bary H1 | Oczekiwane | Brakujące | Luki % | Od | Do |",
              "|---|---|---|---|---|---|---|"]
    for r in report.symbol_coverage.iter_rows(named=True):
        lines.append(
            f"| {r['symbol']} | {r['bars']:,} | {r['expected']:,} | {r['missing']:,} "
            f"| {r['gap_pct']:.2f} | {r['first']:%Y-%m-%d} | {r['last']:%Y-%m-%d} |"
        )

    lines += ["", "## Spread (w pipsach)", "",
              "| Symbol | close mediana | close p95 | max mediana | max p95 | max zaobserwowany | ticki/bar |",
              "|---|---|---|---|---|---|---|"]
    for r in report.spread_stats.iter_rows(named=True):
        # Pips zależy od symbolu: 1e-4 poza JPY, 1e-2 dla par z JPY.
        # Sztywna stała dawała dla EURJPY "90 pipsów" zamiast 0.9.
        pip = pip_size(r["symbol"])
        lines.append(
            f"| {r['symbol']} | {r['close_median']/pip:.2f} | {r['close_p95']/pip:.2f} "
            f"| {r['max_median']/pip:.2f} | {r['max_p95']/pip:.2f} "
            f"| {r['max_observed']/pip:.2f} | {r['n_ticks_median']:,.0f} |"
        )

    lines += ["", "## Podejrzenie awarii feedu", ""]
    if report.suspected_outages.is_empty():
        lines.append("Brak — żadna godzina handlowa nie jest pusta u wszystkich par naraz.")
    else:
        lines += [
            f"**{report.suspected_outages.height} godzin** bez danych u wszystkich par "
            "jednocześnie, mimo że wg wyprowadzonego kalendarza są handlowe.",
            "",
            "To podpis awarii feedu, nie zamknięcia rynku. Wymaga ręcznego sprawdzenia "
            "przed akceptacją danych — inaczej luka pozostanie niewidoczna dla backtestu.",
            "",
            "| Godzina UTC |", "|---|",
        ]
        for ts in report.suspected_outages["ts"].head(50):
            lines.append(f"| {ts:%Y-%m-%d %H:%M} |")
        if report.suspected_outages.height > 50:
            lines.append(f"| ... jeszcze {report.suspected_outages.height - 50} |")

    if report.holiday_closures is not None and not report.holiday_closures.is_empty():
        hol = report.holiday_closures.with_columns(pl.col("ts").dt.date().alias("d"))
        days = hol.group_by("d").agg(pl.len().alias("n")).sort("d")
        lines += ["", "## Zamknięcia świąteczne", "",
                  "Godziny puste u wszystkich par w blokach dotykających 25.12 albo 1.01 "
                  f"(≤ {MAX_HOLIDAY_RUN_HOURS} h). Nie liczone jako luki ani awarie.",
                  "", "| Data | Godzin |", "|---|---|"]
        for r in days.iter_rows(named=True):
            lines.append(f"| {r['d']:%Y-%m-%d} | {r['n']} |")

    if report.ambiguous_cells is not None and not report.ambiguous_cells.is_empty():
        lines += ["", "## Komórki niejednoznaczne", "",
                  "Pokrycie między 20% a 80% — ani stabilnie handlowe, ani zamknięte. "
                  "Typowo granica DST (otwarcie niedzielne przesuwa się między 21:00 "
                  "a 22:00 UTC), ale systematyczna awaria wygląda tak samo.",
                  "", "| Symbol | Dzień tyg. | Godz. UTC | Pokrycie |", "|---|---|---|---|"]
        for r in report.ambiguous_cells.head(30).iter_rows(named=True):
            lines.append(f"| {r['symbol']} | {r['weekday']} | {r['hour']:02d} "
                         f"| {100*r['coverage']:.0f}% |")

    if report.invariant_errors:
        lines += ["", "## Naruszenia niezmienników barów", ""]
        lines += [f"- {e}" for e in report.invariant_errors]

    return "\n".join(lines) + "\n"
