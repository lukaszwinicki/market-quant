"""Przebieg V1a na harnessie — spina istniejące klocki, nic nowego nie liczy.

CO TU JEST, A CZEGO NIE MA

Moduł nie definiuje ani reguły, ani kosztów, ani kryteriów. Reguła jest
w `strategy/v1a.py`, koszty w `execution/`, metryki w `validation/`.
Tutaj jest wyłącznie KOLEJNOŚĆ: co trzeba sprawdzić, zanim cokolwiek
policzymy, i w jakiej kolejności nakłada się korekty na wynik.

Kolejność ma znaczenie i nie jest dowolna:

    1. `require_fresh_bars`  — partycja z wycinka cache cicho zaniża próbę
    2. `require_coverage`    — dziura w kalendarzu wygląda jak brak blackoutu
       (kalendarz, ADR-032 pkt 4) i jak stopa zerowa (stopy, ADR-035)
    3. `start_run`           — próba istnieje PRZED wynikiem (ADR-029)
    4. decyzje → transakcje  — `decision_frame` + `run_v1a`
    5. `apply_financing`     — swap jest kierunkowy, więc musi wejść przed
       jakąkolwiek statystyką (ADR-035)
    6. metryki i kontrole

Punkty 1 i 2 są przed 3 świadomie: nieudana konfiguracja nie ma zaśmiecać
`trials.jsonl`, bo każdy wpis `strategy` zjada limit prób i podnosi N w DSR.

WARIANTY

Siatka z ADR-028 to 7 wariantów, jeden parametr naraz. Raportowany wynik
to ZAWSZE baseline; pozostałe sześć służy wyłącznie PBO i testowi
płaskowyżu. Mimo to każdy liczy się do N (ADR-029) — policzony wariant to
wariant, który mógł wpłynąć na decyzję.

Warianty różnią się dwiema rzeczami: okresem kanału Donchiana (cecha) i
geometrią barier (etykieta). Cechy liczymy raz na każdą wartość kanału,
a pamięć symulatora dzielimy między warianty o tej samej geometrii —
etykieta jest deterministyczna w (symbol, moment, kierunek, geometria).

CPCV PRZY REGULE NIEUCZONEJ

V1a niczego nie dopasowuje, więc transakcje grupy g są identyczne
w każdym podziale, w którym g jest grupą testową. Pięć ścieżek backtestu
(ADR-031) zlewa się wtedy w jedną, równą pełnej próbie, i nie mierzy
niczego. Raportujemy więc rozrzut po 15 PODZIAŁACH oraz udział próby
zjadany przez purge i embargo — a o degeneracji ścieżek piszemy wprost,
zamiast pokazywać pięć identycznych liczb jako „rozkład".

BENCHMARK §12

Nie jest liczony. ADR-036 zablokował go brakiem rentowności 2-letnich,
ADR-038 wybrał zamiennik, ale kodu benchmarku nie ma. Każdy raport
powołujący się na §12 musi to mówić wprost — `render()` to robi.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import polars as pl

from ..data.calendar import require_coverage as require_calendar_coverage
from ..data.rates import require_coverage_for_decisions as require_rate_coverage
from ..execution.financing import apply_financing, markup_from, markup_grid_from
from ..execution.simulator import CostModel
from ..features.technical import compute_features
from ..labels.triple_barrier import effective_sample_size, overlap_fraction
from ..validation.benchmark import Comparison
from ..validation.control4 import Control4, render_section as _control4_section
from ..validation.bootstrap import BootstrapResult, block_bootstrap_expectancy, business_day
from ..validation.controls import (
    counts_from, empirical_p_value, permutation_max_drawdown, shift_features,
    shuffled_label_null,
)
from ..validation.cost_sensitivity import (
    CostScenario, MarkupScenario, cost_ladder, markup_ladder,
)
from ..validation.cpcv import CPCVSpec, cpcv_splits
from ..validation.dsr import DSRResult, deflated_sharpe, sharpe
from ..validation.gate0 import Check, breakdown, make_evaluator
from ..validation.pbo import PBOResult, pbo_cscv
from .v1a import Rules, V1aParams, decision_frame, run_v1a

UTC = dt.timezone.utc

# ADR-028: sąsiad poniżej tej części baseline'u oznacza szpikulec.
PLATEAU_MIN_SHARE = 0.5
# §10.3: rozkład wyniku w podokresach — ile podokresów badamy.
N_SUBPERIODS = 3


@dataclass(frozen=True)
class Window:
    """Trzy różne daty, których mylenie jest najłatwiejszym błędem runnera.

    `data_start`  — od kiedy czytamy bary. Rok 2015 jest tylko historią dla
                    cech: `vol_pct_252` potrzebuje 252 dni, więc pierwszy
                    handlowalny bar wypada ~rok po starcie danych.
    `trade_start` — pierwsza DECYZJA. Kalendarz i stopy muszą pokrywać
                    dopiero ten zakres; wymaganie pokrycia od `data_start`
                    wywracałoby przebieg na roku, w którym i tak nie
                    handlujemy.
    `split_end`   — granica splitu dla ADR-030: wejście jest dozwolone
                    tylko wtedy, gdy CAŁY horyzont mieści się przed nią.
    """
    data_start: dt.datetime
    trade_start: dt.datetime
    split_end: dt.datetime

    def __post_init__(self):
        # Strefa PRZED porównaniem: mieszanie naive z aware daje TypeError,
        # a chcemy komunikat mówiący, co jest nie tak.
        for name in ("data_start", "trade_start", "split_end"):
            if getattr(self, name).tzinfo is None:
                raise ValueError(f"{name} musi być tz-aware (UTC)")
        if not (self.data_start <= self.trade_start < self.split_end):
            raise ValueError("wymagane data_start <= trade_start < split_end")


@dataclass
class Variant:
    """Jeden wariant siatki: log decyzji dla KAŻDEGO bara plus transakcje."""
    params: V1aParams
    decisions: pl.DataFrame
    trades: pl.DataFrame

    @property
    def name(self) -> str:
        return self.params.name

    @property
    def expectancy(self) -> float:
        return float(self.trades["r"].mean()) if self.trades.height else float("nan")


# --- przygotowanie ------------------------------------------------------------

def preflight(events: pl.DataFrame, rates: pl.DataFrame, symbols: list[str],
              window: Window, rate_kind: str = "overnight") -> None:
    """Wszystko, co musi być prawdą, ZANIM powstanie wpis w `trials.jsonl`.

    Brak serii w kalendarzu wygląda w `blackout()` identycznie jak brak
    zdarzenia, a brak stopy wchodziłby do swapu jak zero. Oba tryby awarii
    są ciche, więc oba sprawdzamy jawnie.
    """
    require_calendar_coverage(events, symbols, window.trade_start, window.split_end)
    # Waluty biorą się z par przebiegu, nie z całej kohorty: przebieg na
    # dwóch parach nie potrzebuje stóp dla wszystkich sześciu walut.
    currencies = tuple(sorted({c for s in symbols for c in (s[:3], s[3:])}))
    require_rate_coverage(rates, currencies, rate_kind,
                          window.trade_start.date(), window.split_end.date())


def feature_sets(h1: dict[str, pl.DataFrame], grid: list[V1aParams]
                 ) -> dict[int, dict[str, pl.DataFrame]]:
    """Cechy per okres kanału Donchiana — raz na wartość, nie raz na wariant."""
    return {n: {s: compute_features(b, donchian=n) for s, b in h1.items()}
            for n in sorted({p.donchian_lookback for p in grid})}


def evaluators(grid: list[V1aParams], m1: dict[str, pl.DataFrame],
               costs: dict[str, CostModel], horizon_days: int) -> dict:
    """`evaluate` per geometria barier; warianty o tej samej geometrii dzielą pamięć.

    Etykieta zależy od (symbol, moment, kierunek) i od mnożników SL/TP —
    kanał Donchiana zmienia tylko to, KTÓRE momenty strategia wybierze.
    """
    out = {}
    for p in grid:
        key = (p.sl_multiple, p.tp_multiple, horizon_days)
        if key not in out:
            out[key] = make_evaluator(m1, costs, p.label_spec(horizon_days))
    return out


def run_variant(params: V1aParams, features: dict[str, pl.DataFrame], rules: Rules,
                events: pl.DataFrame, window: Window, evaluate,
                rates: pl.DataFrame, markup: float) -> Variant:
    """Jeden wariant od cech do transakcji z nałożonym finansowaniem."""
    frames = [
        decision_frame(f, symbol, params, rules, events, window.split_end)
        .filter(pl.col("ts") >= window.trade_start)
        for symbol, f in sorted(features.items())
    ]
    decisions, trades = run_v1a(frames, rules, evaluate)
    if trades.height:
        # Swap jest kierunkowy, więc musi wejść PRZED jakąkolwiek statystyką:
        # inaczej carry podszywa się pod sygnał (ADR-035).
        trades = apply_financing(trades, rates, markup)
    return Variant(params, decisions, trades)


# --- metryki ------------------------------------------------------------------

def daily_matrix(variants: list[Variant], value: str = "r"
                 ) -> tuple[list[dt.date], np.ndarray]:
    """(oś dni, macierz T × N) — suma `value` na dzień, wspólna oś wariantów.

    PBO porównuje warianty między sobą, więc muszą leżeć na tej samej osi
    czasu. Dzień bez transakcji wariantu to zero, nie brak.
    """
    per_variant = []
    for v in variants:
        if v.trades.height:
            d = pl.DataFrame({"d": business_day(v.trades["ts"]), "v": v.trades[value]})
            per_variant.append(d.group_by("d").agg(pl.col("v").sum().alias("s")))
        else:
            per_variant.append(pl.DataFrame(schema={"d": pl.Date, "s": pl.Float64}))

    days = sorted({d for f in per_variant for d in f["d"].to_list()})
    if not days:
        return [], np.zeros((0, len(variants)))
    axis = pl.DataFrame({"d": pl.Series(days, dtype=pl.Date)})
    cols = [axis.join(f, on="d", how="left").fill_null(0.0)["s"].to_numpy()
            for f in per_variant]
    return days, np.column_stack(cols).astype(float)


def split_expectancies(trades: pl.DataFrame, spec: CPCVSpec) -> list[float]:
    """Średnie R w części testowej każdego z 15 podziałów CPCV (ADR-031).

    Przy regule nieuczonej to rozrzut po podziałach osi czasu, a nie miara
    przeuczenia — patrz nagłówek modułu.
    """
    if trades.height < spec.n_groups:
        return []
    return [float(trades[s.test_idx]["r"].mean()) for s in cpcv_splits(trades, spec)]


def purge_shares(trades: pl.DataFrame, spec: CPCVSpec) -> tuple[float, float]:
    """(średni udział purge, średni udział embargo) w próbie treningowej."""
    if trades.height < spec.n_groups:
        return float("nan"), float("nan")
    splits = cpcv_splits(trades, spec)
    n = trades.height
    return (float(np.mean([len(s.purged_idx) for s in splits]) / n),
            float(np.mean([len(s.embargoed_idx) for s in splits]) / n))


def subperiod_expectancies(trades: pl.DataFrame, window: Window,
                           n: int = N_SUBPERIODS) -> list[tuple[str, int, float]]:
    """(etykieta, liczba transakcji, E[R]) dla `n` równych podokresów (§10.3)."""
    if not trades.height:
        return []
    t0, t1 = window.trade_start, window.split_end
    step = (t1 - t0) / n
    out = []
    for i in range(n):
        lo, hi = t0 + i * step, t0 + (i + 1) * step
        part = trades.filter(pl.col("ts").is_between(lo, hi, closed="left"))
        out.append((f"{lo:%Y-%m}..{hi:%Y-%m}", part.height,
                    float(part["r"].mean()) if part.height else float("nan")))
    return out


def plateau_check(variants: list[Variant]) -> Check:
    """ADR-028: każdy z 6 sąsiadów ma ten sam znak i ≥ 50% E[R] baseline'u."""
    base = next((v for v in variants if v.name == "baseline"), None)
    if base is None or not base.trades.height:
        return Check("płaskowyż (ADR-028)", False, "brak wyniku baseline")
    b = base.expectancy
    if b <= 0:
        return Check("płaskowyż (ADR-028)", False,
                     f"baseline {b:+.4f} R ≤ 0 — płaskowyż nie ma czego potwierdzać")
    bad = [f"{v.name} {v.expectancy:+.4f}"
           for v in variants if v.name != "baseline"
           and not (v.expectancy > 0 and v.expectancy >= PLATEAU_MIN_SHARE * b)]
    return Check("płaskowyż (ADR-028)", not bad,
                 f"baseline {b:+.4f} R, próg {PLATEAU_MIN_SHARE * b:+.4f} R; "
                 + (f"poniżej progu: {', '.join(bad)}" if bad else
                    "wszystkich 6 sąsiadów nad progiem"))


# --- kontrole §10.2 -----------------------------------------------------------

@dataclass
class Controls:
    random_null: np.ndarray = field(default_factory=lambda: np.empty(0))
    random_p: float = float("nan")
    shuffled_null: np.ndarray = field(default_factory=lambda: np.empty(0))
    shuffled_p: float = float("nan")
    pool_size: int = 0
    shifted_expectancy: float = float("nan")
    shifted_trades: int = 0
    observed_max_dd: float = float("nan")
    dd_null: np.ndarray = field(default_factory=lambda: np.empty(0))
    dd_p: float = float("nan")


def control_pool(candidates: pl.DataFrame, trades: pl.DataFrame, evaluate,
                 rates: pl.DataFrame, markup: float, per_group: int | None,
                 seed: int) -> tuple[pl.DataFrame, np.ndarray]:
    """Pula zdarzeń kandydujących z wynikiem + maska wyboru strategii (#2).

    Kontrola #2 pyta „czy WYBÓR jest lepszy niż losowy", więc pula musi
    zawierać transakcje strategii i zdarzenia, których strategia nie
    wzięła. Przy pełnej puli (oba kierunki × każdy zamknięty bar) to setki
    tysięcy symulacji, więc `per_group` ją przycina — ale wiersze wybrane
    przez strategię są dokładane ZAWSZE, inaczej maska nie miałaby sensu.
    """
    rng = np.random.default_rng(seed)
    taken = set(trades.select("symbol", "ts", "side").iter_rows())
    parts = []
    for side in ("long", "short"):
        for symbol in sorted(candidates["symbol"].unique().to_list()):
            pool = (candidates.filter(pl.col("symbol") == symbol)
                    .with_columns(pl.lit(side).alias("side")))
            keep = pl.Series("keep", [(symbol, t, side) in taken
                                      for t in pool["ts"].to_list()])
            if per_group is not None and pool.height > per_group:
                extra = np.flatnonzero(~keep.to_numpy())
                n_extra = max(0, per_group - int(keep.sum()))
                chosen = rng.choice(extra, size=min(n_extra, len(extra)), replace=False)
                mask = keep.to_numpy().copy()
                mask[chosen] = True
                pool = pool.filter(pl.Series(mask))
            parts.append(pool)
    events = pl.concat(parts).sort("ts", "symbol", "side")

    labels = evaluate(events)
    if not labels.height:
        return labels, np.zeros(0, dtype=bool)
    labels = apply_financing(labels, rates, markup)
    selected = np.array([(s, t, d) in taken for s, t, d
                         in labels.select("symbol", "ts", "side").iter_rows()])
    return labels, selected


def run_controls(baseline: Variant, candidates: pl.DataFrame, evaluate,
                 rates: pl.DataFrame, markup: float, *, pool_per_group: int | None,
                 n_reps: int, seed: int) -> Controls:
    """Kontrole #1, #2, #3 i #7 z §10.2 na wariancie baseline.

    #1 i #2 są tu liczone na etykietach PO finansowaniu — rozkład zerowy
    musi żyć w tym samym świecie kosztów co wynik, z którym go porównujemy.
    #3 dolicza wywołujący (wymaga ponownego przebiegu na przesuniętych
    cechach), więc pola `shifted_*` uzupełnia się osobno.
    """
    c = Controls()
    if not baseline.trades.height:
        return c
    observed = baseline.expectancy

    # #1 — losowe wejścia, ta sama liczba na (para, kierunek) co strategia.
    from ..validation.gate0 import run_random_control
    counts = counts_from(baseline.trades)
    rnd = run_random_control(candidates, counts, evaluate, n_reps, seed)
    if rnd.height:
        rnd = apply_financing(rnd, rates, markup)
        means = (rnd.group_by("rep").agg(pl.col("r").mean().alias("m"))
                 .sort("rep")["m"].to_numpy())
        c.random_null, c.random_p = means, empirical_p_value(observed, means)

    # #2 — te same zdarzenia, wynik przetasowany wewnątrz (para, kierunek).
    pool, selected = control_pool(candidates, baseline.trades, evaluate,
                                  rates, markup, pool_per_group, seed)
    if pool.height and selected.any():
        c.pool_size = pool.height
        c.shuffled_null = shuffled_label_null(pool, selected, n_reps, seed)
        c.shuffled_p = empirical_p_value(observed, c.shuffled_null)

    # #7 — permutacja kolejności DNI, nie transakcji.
    if baseline.trades["ts"].dt.date().n_unique() >= 2:
        c.observed_max_dd, c.dd_null = permutation_max_drawdown(
            baseline.trades, n_reps=n_reps, seed=seed)
        c.dd_p = empirical_p_value(c.observed_max_dd, c.dd_null)
    return c


def shifted_baseline(params: V1aParams, features: dict[str, pl.DataFrame],
                     rules: Rules, events: pl.DataFrame, window: Window,
                     evaluate, rates: pl.DataFrame, markup: float) -> Variant:
    """Kontrola #3: ten sam przebieg na cechach starszych o bar.

    `shift_features` nie rusza `atr_d1_14` — przesunięcie normalizatora
    zmieniłoby geometrię transakcji, a nie treść sygnału.
    """
    donch = f"donch_pos_{params.donchian_lookback}"
    shifted = {s: shift_features(f.sort("ts"), 1,
                                 [c for c in ("mom_24", "mom_120", "mom_480", donch,
                                              "vol_pct_252") if c in f.columns])
               for s, f in features.items()}
    return run_variant(params, shifted, rules, events, window, evaluate, rates, markup)


# --- ocena --------------------------------------------------------------------

@dataclass
class Benchmark:
    """Kontrola #5: koszyk §12 policzony wg ADR-038/039/040, albo jego brak."""
    comparison: Comparison | None = None
    per_anchor: dict[int, float] = field(default_factory=dict)   # kotwica → E[R]
    anchor_stats: list[dict] = field(default_factory=list)

    @property
    def computed(self) -> bool:
        return self.comparison is not None


@dataclass
class Assessment:
    baseline: Variant
    variants: list[Variant]
    bootstrap: BootstrapResult
    costs: list[CostScenario]
    markups: list[MarkupScenario]
    dsr: DSRResult
    pbo: PBOResult | None
    split_r: list[float]
    purge_share: float
    embargo_share: float
    subperiods: list[tuple[str, int, float]]
    per_symbol: pl.DataFrame
    overlap: float
    effective_n: int
    controls: Controls
    benchmark: Benchmark
    control4: Control4
    checks: list[Check]

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)


def assess(variants: list[Variant], cfg: dict, window: Window, n_trials: int,
           controls: Controls, *, block_days: int, boot_reps: int, seed: int,
           cpcv: CPCVSpec, benchmark: Benchmark | None = None,
           control4: Control4 | None = None) -> Assessment:
    """Metryki bramki 2. Bez `benchmark` albo `control4` werdykt jest NIEPEŁNY."""
    benchmark = benchmark or Benchmark()
    control4 = control4 or Control4()
    base = next(v for v in variants if v.name == "baseline")
    trades = base.trades
    if not trades.height:
        raise ValueError("baseline nie zawarł ani jednej transakcji")

    th = cfg["validation"]["acceptance_thresholds"]
    boot = block_bootstrap_expectancy(trades, block_days, boot_reps, seed)
    ladder = cost_ladder(trades, tuple(cfg["costs"]["sensitivity_multipliers"]))
    marks = markup_ladder(trades, markup_from(cfg), markup_grid_from(cfg))

    # N do DSR i wariancja Sharpe'a MIĘDZY wariantami — dokładnie ta
    # wielkość, którą deflacja ma ukarać (López de Prado 2014).
    sharpes = [sharpe(v.trades["r"].to_numpy()) for v in variants if v.trades.height > 1]
    var_trials = float(np.var(sharpes, ddof=1)) if len(sharpes) > 1 else 0.0
    eff_n = effective_sample_size(trades)
    dsr = deflated_sharpe(trades["r"].to_numpy(), n_trials, var_trials, n_obs=eff_n)

    _, matrix = daily_matrix(variants)
    pbo = None
    if matrix.size and matrix.shape[1] >= 2 and matrix.shape[0] >= 32:
        pbo = pbo_cscv(matrix)

    per_symbol = breakdown(trades)
    n_positive = int(
        trades.group_by("symbol").agg(pl.col("r").mean().alias("m"))
        .filter(pl.col("m") > 0).height)
    subs = subperiod_expectancies(trades, window)
    subs_positive = sum(1 for _, n, m in subs if n and m > 0)
    purged, embargoed = purge_shares(trades, cpcv)

    checks = [
        Check(f"expectancy netto ≥ {th['expectancy_net_R_min']:+.2f} R",
              boot.expectancy >= th["expectancy_net_R_min"],
              f"{boot.expectancy:+.4f} R, CI95 [{boot.ci_low:+.4f}, {boot.ci_high:+.4f}]"),
        Check(f"t ≥ {th['t_stat_min']}", boot.t_stat >= th["t_stat_min"],
              f"t = {boot.t_stat:.2f} (bootstrap blokowy, {block_days} dni)"),
        Check(f"DSR ≥ {th['deflated_sharpe_min']} (ADR-027)",
              dsr.dsr >= th["deflated_sharpe_min"],
              f"DSR = {dsr.dsr:.3f}, SR {dsr.sharpe:+.4f} vs SR*₀ "
              f"{dsr.sharpe_benchmark:+.4f}, N = {n_trials}, n_eff = {eff_n}"),
        Check(f"PBO ≤ {th['pbo_max']}", pbo is not None and pbo.pbo <= th["pbo_max"],
              f"PBO = {pbo.pbo:.3f} z {pbo.n_strategies} wariantów"
              if pbo else "za mało dni albo wariantów na CSCV"),
        Check(f"dodatnie przy {th['positive_at_cost_multiple']:g}× kosztach",
              next(s.positive for s in ladder
                   if s.multiplier == th["positive_at_cost_multiple"]),
              " · ".join(f"{s.multiplier:g}×: {s.expectancy:+.4f}" for s in ladder)),
        Check("dodatnie na CAŁEJ osi marży (ADR-037)",
              all(s.positive for s in marks),
              " · ".join(f"{s.markup_annual_pct:g}%: {s.expectancy:+.4f}"
                         for s in marks)),
        Check(f"≥ {th['min_instruments_positive']} par dodatnich",
              n_positive >= th["min_instruments_positive"],
              f"{n_positive} z {trades['symbol'].n_unique()}"),
        Check(f"≥ {th['min_subperiods_positive']} podokresy dodatnie",
              subs_positive >= th["min_subperiods_positive"],
              " · ".join(f"{lab}: {m:+.4f}" for lab, _, m in subs)),
        plateau_check(variants),
        benchmark_check(benchmark),
        control4_check(control4),
    ]

    return Assessment(
        baseline=base, variants=variants, bootstrap=boot, costs=ladder, markups=marks,
        dsr=dsr, pbo=pbo, split_r=split_expectancies(trades, cpcv),
        purge_share=purged, embargo_share=embargoed, subperiods=subs,
        per_symbol=per_symbol, overlap=overlap_fraction(trades), effective_n=eff_n,
        controls=controls, benchmark=benchmark, control4=control4, checks=checks,
    )


def benchmark_check(b: Benchmark) -> Check:
    """Kontrola #5 (ADR-040): CI95 różnicy Sharpe'ów w całości powyżej zera.

    Nie policzony koszyk to NIE jest zaliczona kontrola. Brak liczby zostaje
    brakiem, a nie domyślnym „przeszło" — ADR-036 pkt 1.
    """
    if not b.computed:
        return Check("kontrola #5: koszyk carry + trend (§12) pobity", False,
                     "NIE POLICZONY — werdykt bramki 2 jest niepełny (ADR-036)")
    c = b.comparison
    return Check(
        "kontrola #5: koszyk carry + trend (§12) pobity", c.beaten,
        f"ΔSharpe {c.difference:+.4f}, CI95 [{c.ci_low:+.4f}, {c.ci_high:+.4f}]; "
        f"strategia {c.strategy_sharpe:+.4f} przy {c.strategy_open_risk_r:.2f} R "
        f"otwartego ryzyka, koszyk {c.benchmark_sharpe:+.4f} przy "
        f"{c.benchmark_open_risk_r:.2f} R")


def control4_check(c4: Control4) -> Check:
    """Kontrola #4 (ADR-044): rozstrzyga RAMIĘ CARRY-ONLY, nie buy & hold.

    Buy & hold jest diagnostyką — FX nie ma broniącego się kierunku
    pasywnego, więc poprzeczka zależałaby od tego, w którą stronę poszedł
    dolar w próbie. Jak przy kontroli #5, brak liczby zostaje brakiem.
    """
    name = "kontrola #4: carry-only pobity (ADR-044)"
    if not c4.carry_only.computed:
        why = f" ({c4.carry_only.note})" if c4.carry_only.note else ""
        return Check(name, False,
                     f"NIE POLICZONA — werdykt bramki 2 jest niepełny "
                     f"(ADR-044){why}")
    c = c4.carry_only.comparison
    return Check(
        name, c4.carry_only.beaten,
        f"ΔSharpe {c.difference:+.4f}, CI95 [{c.ci_low:+.4f}, {c.ci_high:+.4f}]; "
        f"strategia {c.strategy_sharpe:+.4f} przy {c.strategy_open_risk_r:.2f} R "
        f"otwartego ryzyka, carry-only {c.benchmark_sharpe:+.4f} przy "
        f"{c.benchmark_open_risk_r:.2f} R")


# --- raport -------------------------------------------------------------------

# ADR-036 pkt 1 i ADR-038 pkt 6: milczenie o benchmarku jest gorsze niż brak
# liczby. Jedno z tych zdań trafia do KAŻDEGO raportu; oba są przypięte testem.
BENCHMARK_NOTE = (
    "**Benchmark obowiązkowy z §12 (koszyk carry + trend, kontrola #5) NIE ZOSTAŁ "
    "POLICZONY.** Rentowności 2-letnich nie ma w jednej definicji dla ośmiu walut "
    "(ADR-036, `reports/yield2y_sources.md`); ADR-038 wybrał zamiennik — carry "
    "mierzone `interbank_3m` na pięciu walutach kohorty A — ale kodu benchmarku "
    "jeszcze nie ma. Werdykt bramki 2 bez tej kontroli jest NIEPEŁNY."
)

BENCHMARK_NARROWED = (
    "**Koszyk §12 jest ZAWĘŻONY względem specyfikacji** (ADR-038): carry mierzy "
    "`interbank_3m`, nie `yield_2y` — tej serii nie ma w jednej definicji dla "
    "ośmiu walut (`reports/yield2y_sources.md`); uniwersum to pięć walut kohorty "
    "A vs USD zamiast ośmiu, bo NZDUSD i USDCHF nie są pobierane, a CHF jest "
    "wykluczony w sekcji `instruments` z `frozen: true`. Nogi: long top-1, "
    "short bottom-1. Prior z literatury dotyczy koszyków G10 i stosuje się do "
    "tego koszyka słabiej."
)

MISSING_CONTROLS = (
    "Nie jest liczona kontrola §10.2 nr 10 (rozkład zerowy per kohorta). "
    "Kontrola nr 9 (buy & hold per instrument) jest policzona dla kohorty A "
    "jako ramię 4b (ADR-044); dla kohorty B zostaje otwarta."
)


def decision_summary(decisions: pl.DataFrame) -> pl.DataFrame:
    """Ile barów dostało który powód — log decyzji w jednej tabeli.

    `n` liczy bary, w których powód był PIERWSZY wg priorytetu ADR-033;
    `n_any` — w których zadziałał w ogóle. Obie kolumny są potrzebne, bo
    warunek o niskim priorytecie potrafi zniknąć z tabeli mimo że działa na
    każdym barze, który obejmuje: `10_sunday_open` (ADR-042) stoi po
    `no_signal` i limitach ekspozycji, więc pierwszym powodem bywa rzadko.
    """
    if not decisions.height:
        return pl.DataFrame(schema={"reason": pl.Utf8, "n": pl.UInt32,
                                    "share": pl.Float64, "n_any": pl.UInt32})
    first = (decisions
             .with_columns(pl.col("reason").fill_null("enter"))
             .group_by("reason").len().rename({"len": "n"})
             .with_columns((pl.col("n") / decisions.height).alias("share")))

    # Bar bez powodu ma `reasons` puste — odsiewane PRZED split, żeby explode
    # nie musiał rozstrzygać, czym jest pusta lista (empty_as_null).
    any_ = (decisions.filter(pl.col("reasons") != "")
            .select(pl.col("reasons").str.split(","))
            .explode("reasons", empty_as_null=False)
            .group_by("reasons").len()
            .rename({"reasons": "reason", "len": "n_any"}))

    return (first.join(any_, on="reason", how="full", coalesce=True)
            .with_columns(pl.col("n").fill_null(0), pl.col("n_any").fill_null(0),
                          pl.col("share").fill_null(0.0))
            .sort("n_any", "n", descending=True))


def render(run_id: str, params: dict, a: Assessment) -> str:
    """Raport przebiegu. Zawiera zapis o nieliczonym benchmarku §12."""
    from ..validation.cost_sensitivity import render_markdown, render_markup_markdown

    c, base = a.controls, a.baseline
    lines = [
        "# V1a — przebieg na segmencie RESEARCH",
        "",
        f"> Run: `{run_id}` · {params['trade_start']:%Y-%m-%d} → "
        f"{params['split_end']:%Y-%m-%d} · {', '.join(params['symbols'])}",
        f"> Dane od {params['data_start']:%Y-%m-%d} (rok rozgrzewki cech, bez decyzji)",
        f"> {len(a.variants)} wariantów siatki (ADR-028), N w DSR = {a.dsr.n_trials} "
        f"(ADR-029); raportowany jest baseline",
        f"> Werdykt liczonych kryteriów: "
        f"**{'PRZECHODZI' if a.passed else 'NIE PRZECHODZI'}** — niepełny, patrz niżej",
        "",
        *(["**DRY RUN — sprawdzenie okablowania.** Przebieg nie został dopisany "
           "do `trials.jsonl`, więc NIE jest próbą i nie podnosi N w DSR. "
           "Ten wynik nie jest wynikiem badawczym.", ""]
          if params.get("dry_run") else []),
        BENCHMARK_NARROWED if a.benchmark.computed else BENCHMARK_NOTE,
        "",
        MISSING_CONTROLS,
        "",
        "## Kryteria bramki 2" + ("" if a.benchmark.computed else " (bez kontroli #5)"),
        "",
        "| Kryterium | Wynik | Szczegóły |",
        "|---|---|---|",
    ]
    for chk in a.checks:
        lines.append(f"| {chk.name} | {'✅' if chk.passed else '❌'} | {chk.detail} |")

    lines += [
        "",
        "## Próba",
        "",
        f"- transakcji baseline: **{base.trades.height}**, "
        f"efektywnych (nienakładających się): **{a.effective_n}**, "
        f"nakładanie {a.overlap:.1%}",
        "- do testów istotności wchodzi n_eff, nie liczba wierszy",
        "",
        "## Log decyzji (każdy zamknięty bar H1, ADR-033)",
        "",
        "| Powód | barów (pierwszy) | udział | barów (zadziałał) |",
        "|---|---|---|---|",
    ]
    for r in decision_summary(base.decisions).iter_rows(named=True):
        # `enter` to brak powodu, więc druga kolumna go nie dotyczy
        any_cell = "—" if r["reason"] == "enter" else str(r["n_any"])
        lines.append(f"| `{r['reason']}` | {r['n']} | {r['share']:.3%} "
                     f"| {any_cell} |")
    lines += [
        "",
        "„Pierwszy” to powód o najwyższym priorytecie ADR-033; „zadziałał” — "
        "ile barów warunek obejmował niezależnie od priorytetu. Warunek "
        "o niskim priorytecie może mieć zero w pierwszej kolumnie i tysiące "
        "w drugiej.",
    ]

    lines += [
        "",
        "## Koszt 1×, 2×, 3× (§9)",
        "",
        render_markdown(a.costs),
        "",
        "Finansowanie jest w każdym scenariuszu ODEJMOWANE, ale nie skalowane "
        "mnożnikiem — swap rośnie z dni trzymania i różnicy stóp, a nie "
        "z warunków brokera na spreadzie (ADR-035, ADR-037).",
        "",
        "## Oś marży swapu (ADR-037, OBOWIĄZKOWA)",
        "",
        render_markup_markdown(a.markups),
        "",
        "Marża jest jedyną liczbą w modelu kosztów bez sparsowanego źródła. "
        "Werdykt zależny wyłącznie od wartości punktowej jest nieważny.",
        "",
        "## Warianty siatki (ADR-028)",
        "",
        "| Wariant | Donchian | SL | TP | n | E[R] |",
        "|---|---|---|---|---|---|",
    ]
    for v in a.variants:
        p = v.params
        lines.append(f"| {p.name} | {p.donchian_lookback} | {p.sl_multiple:g} | "
                     f"{p.tp_multiple:g} | {v.trades.height} | {v.expectancy:+.4f} |")

    lines += [
        "",
        "## CPCV (ADR-031)",
        "",
        f"6 grup, 2 testowe → {len(a.split_r)} podziałów. Purge zjada średnio "
        f"{a.purge_share:.1%} próby, embargo {a.embargo_share:.1%}.",
        "",
        "**Pięć ścieżek backtestu jest tu zdegenerowane.** V1a niczego nie "
        "dopasowuje, więc transakcje danej grupy są identyczne w każdym podziale, "
        "w którym jest ona grupą testową — każda ścieżka odtwarza pełną próbę. "
        "Poniżej rozrzut po PODZIAŁACH, który mierzy zależność wyniku od okresu, "
        "a nie przeuczenie.",
        "",
    ]
    if a.split_r:
        arr = np.array(a.split_r)
        lines += [f"- E[R] w częściach testowych: mediana {np.median(arr):+.4f}, "
                  f"min {arr.min():+.4f}, max {arr.max():+.4f}, "
                  f"dodatnich {int((arr > 0).sum())}/{len(arr)}", ""]

    lines += [
        "## Podokresy (§10.3)",
        "",
        "| Okres | n | E[R] |",
        "|---|---|---|",
    ]
    for lab, n, m in a.subperiods:
        lines.append(f"| {lab} | {n} | {m:+.4f} |")

    lines += [
        "",
        "## Per para i kierunek (kontrola #8)",
        "",
        "| Para | Kierunek | n | E[R] | koszt | przed kosztem | trafienia TP | luki |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in a.per_symbol.iter_rows(named=True):
        lines.append(f"| {r['symbol']} | {r['side']} | {r['n']} | {r['mean_r']:+.4f} | "
                     f"{r['mean_cost_r']:.4f} | {r['mean_pre_cost_r']:+.4f} | "
                     f"{r['hit_rate']:.3f} | {r['gap_share']:.3f} |")

    lines += [
        "",
        "## Kontrole §10.2",
        "",
        "| # | Kontrola | Wynik |",
        "|---|---|---|",
        f"| 1 | losowe wejścia, ta sama liczba na (para, kierunek) | "
        f"E[R] strategii {base.expectancy:+.4f} vs mediana losowych "
        f"{np.median(c.random_null):+.4f}, p = {c.random_p:.4f} |"
        if c.random_null.size else "| 1 | losowe wejścia | nie policzono |",
        f"| 2 | przetasowane wyniki (pula {c.pool_size} zdarzeń) | "
        f"mediana rozkładu zerowego {np.median(c.shuffled_null):+.4f}, "
        f"p = {c.shuffled_p:.4f} |"
        if c.shuffled_null.size else "| 2 | przetasowane wyniki | nie policzono |",
        f"| 3 | cechy starsze o bar — wynik NIE MOŻE rosnąć | "
        f"{c.shifted_expectancy:+.4f} R na {c.shifted_trades} transakcjach "
        f"({'OK' if c.shifted_expectancy <= base.expectancy else 'ROŚNIE — sprawdź off-by-one'}) |",
        f"| 7 | permutacja kolejności DNI | max DD {c.observed_max_dd:.2f} R, "
        f"p = {c.dd_p:.4f} (duże p = obsunięcie typowe) |"
        if c.dd_null.size else "| 7 | permutacja dni | nie policzono |",
        "",
        "Rozkład zerowy kontroli #2 jest wyśrodkowany na średniej PULI, nie na "
        "zerze — pytanie brzmi „czy wybór jest lepszy niż losowy”, a nie „czy "
        "wynik jest dodatni”.",
        "",
        *_benchmark_section(a.benchmark),
        *_control4_section(a.control4),
    ]
    return "\n".join(lines) + "\n"


def _benchmark_section(b: Benchmark) -> list[str]:
    """Sekcja kontroli #5 — z obowiązkami raportowymi z ADR-040 pkt 4 i 5."""
    if not b.computed:
        return ["## Kontrola #5 — koszyk carry + trend (§12)", "", BENCHMARK_NOTE, ""]
    c = b.comparison
    lines = [
        "## Kontrola #5 — koszyk carry + trend (§12)",
        "",
        f"Werdykt: **{'POBITY' if c.beaten else 'NIE POBITY'}** — "
        f"ΔSharpe {c.difference:+.4f}, CI95 [{c.ci_low:+.4f}, {c.ci_high:+.4f}] "
        f"({c.n_days} dni, {c.n_reps} replikacji; te same bloki dla obu serii).",
        "",
        "| | Sharpe | średnie dzienne R | średnie otwarte ryzyko |",
        "|---|---|---|---|",
        f"| V1a | {c.strategy_sharpe:+.4f} | {c.strategy_mean_daily_r:+.4f} | "
        f"{c.strategy_open_risk_r:.2f} R |",
        f"| koszyk §12 | {c.benchmark_sharpe:+.4f} | {c.benchmark_mean_daily_r:+.4f} | "
        f"{c.benchmark_open_risk_r:.2f} R |",
        "",
        "Kryterium jest bezskalowe (Sharpe), bo obie serie chodzą na różnych "
        "budżetach ryzyka — kolumna „otwarte ryzyko” pokazuje, jak bardzo. "
        "Porównanie średnich dziennych R faworyzowałoby stronę o większej "
        "ekspozycji bez żadnej przewagi (ADR-040).",
        "",
        "### Per kotwica rebalansu (ADR-039, ADR-040 pkt 5)",
        "",
        "| Kotwica | E[R] na transakcję | rebalansów | pominiętych tygodni | transakcji |",
        "|---|---|---|---|---|",
    ]
    names = {0: "poniedziałek", 1: "wtorek", 2: "środa", 3: "czwartek", 4: "piątek"}
    for st in b.anchor_stats:
        a_id = st["anchor"]
        lines.append(f"| {names.get(a_id, a_id)} | {b.per_anchor.get(a_id, float('nan')):+.4f} "
                     f"| {st['n_rebalances']} | {st['n_skipped']} | {st['n_trades']} |")
    lines += [
        "",
        "Rozrzut między kotwicami to JEDYNA kontrola wrażliwości, jaką ten koszyk "
        "ma — V1a ma siatkę z ADR-028, koszyk nie ma nic. Wynik koszyka jest "
        "średnią z pięciu podportfeli, każdy z piątą częścią kapitału.",
        "",
    ]
    return lines
