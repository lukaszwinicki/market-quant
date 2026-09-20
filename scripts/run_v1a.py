#!/usr/bin/env python
"""Przebieg V1a na segmencie RESEARCH — siatka 7 wariantów (ADR-028).

Każde uruchomienie jest próbą STRATEGII w `trials.jsonl`: dokłada 7 do N
w DSR i do limitu prób (ADR-029). Nie uruchamiać dla samego sprawdzenia,
czy skrypt działa — do tego są testy na syntetyku.

    python scripts/run_v1a.py                       # cały research
    python scripts/run_v1a.py --end 2017-12-31      # krótszy zakres
    python scripts/run_v1a.py --control-reps 500

Zakres nigdy nie wychodzi poza `data.splits.research`. Hold-outu pilnuje
`load_m1`/`load_h1` (`SealedHoldoutError`) — nie obchodzić.

Wynik: `runs/<id>/v1a.md`, `trades.parquet`, `decisions.parquet` oraz
metryki w `metrics.json` i we wpisie `end`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.calendar import load_calendar  # noqa: E402
from src.execution.financing import apply_financing, markup_from  # noqa: E402
from src.harness.market import (  # noqa: E402
    cost_model_for, load_h1, load_m1, require_fresh_bars,
)
from src.harness.registry import ROOT as REPO, TRIALS_FILE, n_trials, start_run  # noqa: E402
from src.strategy.runner import (  # noqa: E402
    Benchmark, Window, assess, evaluators, feature_sets, preflight, render,
    run_controls, run_variant, shifted_baseline,
)
from src.strategy.v1a import grid_from, rules_from  # noqa: E402
from src.validation.benchmark import (  # noqa: E402
    compare, daily_series, run_benchmark, spec_from,
)
from src.validation.cpcv import CPCVSpec  # noqa: E402
from src.validation.gate0 import eligible_candidates, label_spec_from  # noqa: E402

UTC = dt.timezone.utc
ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "v1_baseline.yaml"
CALENDAR = ROOT / "data" / "calendar"
RATES = ROOT / "data" / "rates" / "fred.parquet"

# Rok rozgrzewki: `vol_pct_252` wymaga 252 dni, więc pierwszy handlowalny
# bar wypada ~rok po starcie danych. Kalendarz i stopy muszą pokrywać
# dopiero okres decyzji, nie okres rozgrzewki.
DEFAULT_TRADE_START = dt.datetime(2016, 1, 1, tzinfo=UTC)

log = logging.getLogger("v1a")


def day(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(str(s)).replace(tzinfo=UTC)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", nargs="*")
    ap.add_argument("--trade-start", type=day, default=DEFAULT_TRADE_START,
                    help="pierwsza decyzja (domyślnie 2016-01-01)")
    ap.add_argument("--end", type=day, help="koniec zakresu; nie poza research")
    ap.add_argument("--control-reps", type=int, default=200,
                    help="powtórzeń kontroli #1, #2 i #7")
    ap.add_argument("--pool-per-group", type=int, default=3000,
                    help="przycięcie puli kontroli #2 na (para, kierunek); "
                         "0 = pełna pula")
    ap.add_argument("--boot-reps", type=int, help="domyślnie validation.bootstrap")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--allow-stale-bars", action="store_true",
                    help="policz mimo partycji zbudowanych z wycinka cache "
                         "(wynik NIE jest wynikiem badawczym)")
    ap.add_argument("--no-benchmark", action="store_true",
                    help="pomiń kontrolę #5 (koszyk §12). Raport oznaczy werdykt "
                         "jako NIEPEŁNY — do użytku tylko przy diagnostyce")
    ap.add_argument("--dry-run", metavar="KATALOG", type=Path,
                    help="sprawdzenie okablowania: przebieg zapisuje się do "
                         "KATALOGU i NIE dopisuje próby do trials.jsonl, "
                         "więc nie podnosi N w DSR ani nie zjada limitu prób. "
                         "Wynik nie jest wynikiem badawczym")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        datefmt="%H:%M:%S")

    cfg = yaml.safe_load(CONFIG.read_text())
    symbols = args.symbols or cfg["instruments"]["cohort_a"]["symbols"]
    research = cfg["data"]["splits"]["research"]
    data_start = day(research["start"])
    research_end = (day(research["end"]) + dt.timedelta(days=1)
                    - dt.timedelta(minutes=1))
    split_end = min(args.end, research_end) if args.end else research_end
    window = Window(data_start, args.trade_start, split_end)

    boot = cfg["validation"]["bootstrap"]
    cp = cfg["validation"]["cpcv"]
    cpcv = CPCVSpec(cp["n_groups"], cp["n_test_groups"],
                    cp["purge_business_days"], cp["embargo_business_days"])
    rules = rules_from(cfg)
    grid = grid_from(cfg)
    spec = label_spec_from(cfg)
    markup = markup_from(cfg)

    events = load_calendar(sorted(CALENDAR.glob("*.parquet")))
    rates = pl.read_parquet(RATES)

    # Wszystko, co może unieważnić przebieg, PRZED `start_run` — nieudana
    # konfiguracja nie ma zjadać limitu prób ani podnosić N w DSR.
    preflight(events, rates, symbols, window, cfg["costs"]["financing"]
              ["cohort_a_rate_kind"])
    if not args.allow_stale_bars:
        require_fresh_bars(symbols, window.data_start, window.split_end)

    params = {
        "symbols": symbols,
        "data_start": window.data_start, "trade_start": window.trade_start,
        "split_end": window.split_end,
        "variants": [v.name for v in grid],
        "control_reps": args.control_reps, "pool_per_group": args.pool_per_group,
        "boot_reps": args.boot_reps or boot["replications"],
        "block_days": boot["block_days"], "seed": args.seed,
        "markup_annual_pct": markup,
        "n_events": events.height,
    }

    # Dry-run pisze do własnego katalogu i własnego `trials.jsonl`, więc
    # sprawdzenie okablowania nie podnosi N w DSR. Rejestr badawczy zostaje
    # nietknięty — to jedyna różnica, reszta przebiegu jest identyczna.
    sink = {}
    if args.dry_run:
        args.dry_run.mkdir(parents=True, exist_ok=True)
        sink = {"runs_dir": args.dry_run / "runs",
                "trials_path": args.dry_run / "trials.jsonl"}
        params["dry_run"] = True
        log.warning("DRY RUN → %s; trials.jsonl repozytorium NIE jest dotykane",
                    args.dry_run)

    with start_run("V1a: sensitivity grid on the research split", params,
                   kind="strategy", n_variants=len(grid), **sink) as run:
        t0 = time.monotonic()
        log.info("run %s: %s, decyzje %s → %s", run.run_id, ",".join(symbols),
                 window.trade_start.date(), window.split_end.date())

        h1 = {s: load_h1(s, window.data_start, window.split_end, cfg) for s in symbols}
        m1 = {s: load_m1(s, window.data_start, window.split_end, cfg) for s in symbols}
        costs = {s: cost_model_for(s, cfg) for s in symbols}
        features = feature_sets(h1, grid)
        evals = evaluators(grid, m1, costs, rules.horizon_business_days)
        log.info("cechy dla kanałów %s, %d geometrii barier",
                 sorted(features), len(evals))

        variants = []
        for p in grid:
            ev = evals[(p.sl_multiple, p.tp_multiple, rules.horizon_business_days)]
            v = run_variant(p, features[p.donchian_lookback], rules, events,
                            window, ev, rates, markup)
            variants.append(v)
            log.info("wariant %s: %d transakcji, E[R] %+.4f, %.0f s", p.name,
                     v.trades.height, v.expectancy, time.monotonic() - t0)

        base = variants[0]
        if base.name != "baseline":
            raise ValueError("pierwszy wariant siatki musi być baseline (ADR-028)")

        # Kontrole liczymy na geometrii baseline'u i na tej samej puli
        # kandydatów, z której korzystałaby strategia.
        base_eval = evals[(base.params.sl_multiple, base.params.tp_multiple,
                           rules.horizon_business_days)]
        candidates = pl.concat([
            eligible_candidates(features[base.params.donchian_lookback][s], s,
                                window.trade_start, window.split_end, spec)
            for s in symbols])
        log.info("kandydatów do kontroli: %d", candidates.height)

        controls = run_controls(
            base, candidates, base_eval, rates, markup,
            pool_per_group=args.pool_per_group or None,
            n_reps=args.control_reps, seed=args.seed)

        shifted = shifted_baseline(base.params, features[base.params.donchian_lookback],
                                   rules, events, window, base_eval, rates, markup)
        controls.shifted_expectancy = shifted.expectancy
        controls.shifted_trades = shifted.trades.height
        log.info("kontrole gotowe, %.0f s", time.monotonic() - t0)

        # Kontrola #5: koszyk carry + trend (§12, ADR-038/039/040). Liczony
        # w TYM przebiegu, bo porównanie wymaga wspólnej osi dni; koszyk sam
        # w sobie jest wejściem niezależnym od sygnału, więc nie podnosi N.
        benchmark = Benchmark()
        if not args.no_benchmark:
            bspec = spec_from(cfg)
            # Koszyk potrzebuje `atr_d1_14`, więc dostaje ramki z cechami,
            # a nie surowe bary. ATR nie zależy od kanału Donchiana, więc
            # którakolwiek ramka siatki daje te same wartości.
            bars = features[base.params.donchian_lookback]
            per_anchor, anchor_stats = run_benchmark(
                bars, rates, costs, symbols, bspec, window.trade_start,
                window.split_end)
            per_anchor = {a: (apply_financing(f, rates, markup) if f.height else f)
                          for a, f in per_anchor.items()}
            _, strat_daily, bench_daily = daily_series(base.trades, per_anchor)
            benchmark = Benchmark(
                comparison=compare(strat_daily, bench_daily, base.trades,
                                   list(per_anchor.values()),
                                   block_days=params["block_days"],
                                   n_reps=params["boot_reps"], seed=args.seed),
                per_anchor={a: (float(f["r"].mean()) if f.height else float("nan"))
                            for a, f in per_anchor.items()},
                anchor_stats=anchor_stats)
            log.info("koszyk §12: ΔSharpe %+.4f, CI95 [%+.4f, %+.4f], %.0f s",
                     benchmark.comparison.difference, benchmark.comparison.ci_low,
                     benchmark.comparison.ci_high, time.monotonic() - t0)

        result = assess(variants, cfg, window, n_trials(REPO / TRIALS_FILE), controls,
                        block_days=params["block_days"], boot_reps=params["boot_reps"],
                        seed=args.seed, cpcv=cpcv, benchmark=benchmark)

        base.trades.write_parquet(run.dir / "trades.parquet")
        base.decisions.write_parquet(run.dir / "decisions.parquet")
        (run.dir / "v1a.md").write_text(render(run.run_id, params, result),
                                        encoding="utf-8")

        run.record(
            passed_computed_criteria=result.passed,
            benchmark_section_12_computed=benchmark.computed,   # ADR-038/039/040
            expectancy_r=result.bootstrap.expectancy,
            expectancy_ci=[result.bootstrap.ci_low, result.bootstrap.ci_high],
            t_stat=result.bootstrap.t_stat,
            dsr=result.dsr.dsr, sharpe=result.dsr.sharpe,
            sharpe_benchmark=result.dsr.sharpe_benchmark,
            n_trials=result.dsr.n_trials, effective_n=result.effective_n,
            overlap_fraction=result.overlap,
            pbo=result.pbo.pbo if result.pbo else None,
            n_trades=base.trades.height, n_decisions=base.decisions.height,
            variants={v.name: v.expectancy for v in variants},
            cost_ladder={f"{s.multiplier:g}x": s.expectancy for s in result.costs},
            markup_ladder={f"{s.markup_annual_pct:g}%": s.expectancy
                           for s in result.markups},
            subperiods={lab: m for lab, _, m in result.subperiods},
            split_r_median=float(np.median(result.split_r)) if result.split_r else None,
            control_random_p=controls.random_p,
            control_shuffled_p=controls.shuffled_p,
            control_shifted_expectancy=controls.shifted_expectancy,
            control_dd_p=controls.dd_p,
            checks={c.name: c.passed for c in result.checks},
        )
        print((run.dir / "v1a.md").read_text(encoding="utf-8"))
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
