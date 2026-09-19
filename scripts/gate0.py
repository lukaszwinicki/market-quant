#!/usr/bin/env python
"""Bramka 0: losowe wejścia na prawdziwych danych kohorty A — test negatywny.

Każde uruchomienie jest próbą w `trials.jsonl` (przez `start_run`).

    python scripts/gate0.py                         # research split, dane ciągłe
    python scripts/gate0.py --n-per-side 100 --reps 20
    python scripts/gate0.py --end 2016-12-31

Zakres domyślny: split `research`, obcięty do wspólnego końca ciągłych
danych wszystkich par (pobieranie wciąż trwa). Wynik: `runs/<id>/gate0.md`,
`labels.parquet` i metryki we wpisie `end`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

import polars as pl
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dukascopy import pip_size  # noqa: E402
from src.data.quality import build_report  # noqa: E402
from src.features.technical import compute_features  # noqa: E402
from src.harness.market import cost_model_for, load_h1, load_m1  # noqa: E402
from src.harness.registry import start_run  # noqa: E402
from src.validation.gate0 import (  # noqa: E402
    Check, Gate0Result, assess, balanced_counts, contiguous_end, eligible_candidates,
    label_spec_from, make_evaluator, run_random_control, spread_profile,
)

UTC = dt.timezone.utc
ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "v1_baseline.yaml"

log = logging.getLogger("gate0")

# ADR-025 b: jedyne miejsce, gdzie koszt jest rozróżnialny od szumu.
MARTINGALE_TEST = "tests/test_controls.py::test_random_entries_on_random_walk_lose_exactly_the_cost"


def martingale_check() -> Check:
    """Uruchom test martyngałowy na bieżącym kodzie — dowód w raporcie bramki."""
    out = subprocess.run([sys.executable, "-m", "pytest", "-q", MARTINGALE_TEST],
                         cwd=ROOT, capture_output=True, text=True)
    last = (out.stdout.strip().splitlines() or ["brak wyjścia"])[-1]
    return Check("b. martyngał (syntetyk): E[R] = −koszt przy koszcie 0,5 R",
                 out.returncode == 0, f"`{MARTINGALE_TEST.split('::')[1]}`: {last}")


def day(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(str(s)).replace(tzinfo=UTC)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", nargs="*")
    ap.add_argument("--start", type=day)
    ap.add_argument("--end", type=day)
    ap.add_argument("--n-per-side", type=int, default=100,
                    help="wejść na (para, kierunek) w jednym powtórzeniu")
    ap.add_argument("--reps", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--boot-reps", type=int, help="domyślnie validation.bootstrap")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        datefmt="%H:%M:%S")

    cfg = yaml.safe_load(CONFIG.read_text())
    symbols = args.symbols or cfg["instruments"]["cohort_a"]["symbols"]
    research = cfg["data"]["splits"]["research"]
    start = args.start or day(research["start"])
    split_end = day(research["end"]) + dt.timedelta(days=1) - dt.timedelta(minutes=1)
    boot = cfg["validation"]["bootstrap"]
    spec = label_spec_from(cfg)

    # Koniec wspólny dla wszystkich par: ta sama oś dni w bootstrapie
    # i ten sam okres w porównaniu między parami.
    h1 = {s: load_h1(s, start, args.end or split_end, cfg) for s in symbols}
    ends = {s: contiguous_end(b, start) for s, b in h1.items()}
    if any(e is None for e in ends.values()):
        log.error("brak danych: %s", [s for s, e in ends.items() if e is None])
        return 2
    end = min(ends.values())

    params = {
        "symbols": symbols, "start": start, "end": end,
        "n_per_side": args.n_per_side, "reps": args.reps, "seed": args.seed,
        "boot_reps": args.boot_reps or boot["replications"],
        "block_days": boot["block_days"],
        "label_spec": asdict(spec),
    }
    with start_run("gate0: random-entry negative test on cohort A", params,
                   kind="control") as run:
        log.info("run %s: %s, %s → %s", run.run_id, ",".join(symbols),
                 start.date(), end.date())
        martingale = martingale_check()
        log.info("martyngał: %s", "OK" if martingale.passed else "NIE PRZESZEDŁ")
        costs = {s: cost_model_for(s, cfg) for s in symbols}
        h1 = {s: b.filter(pl.col("ts") <= end) for s, b in h1.items()}

        cands, m1, spreads = [], {}, {}
        for s in symbols:
            c = eligible_candidates(compute_features(h1[s]), s, start, end, spec)
            m1[s] = load_m1(s, start, end, cfg)
            spreads[s] = spread_profile(m1[s], pip_size(s))
            cands.append(c)
            log.info("%s: %d kandydatów, %d barów M1", s, c.height, m1[s].height)
        candidates = pl.concat(cands)

        evaluate = make_evaluator(m1, costs, spec)
        t0 = time.monotonic()

        def progress(i: int, lab: pl.DataFrame) -> None:
            log.info("rep %d/%d: n=%d, mean R %+.4f, unikalnych transakcji %d, %.0f s",
                     i + 1, args.reps, lab.height, lab["r"].mean() if lab.height else float("nan"),
                     len(evaluate.memo), time.monotonic() - t0)

        labels = run_random_control(candidates, balanced_counts(symbols, args.n_per_side),
                                    evaluate, args.reps, args.seed, progress)
        labels.write_parquet(run.dir / "labels.parquet")

        result = assess(labels, costs, spreads, params["block_days"],
                        params["boot_reps"], args.seed)
        result.checks.insert(1, martingale)
        n_dropped = sum(v is None for v in evaluate.memo.values())
        quality_ok, quality_reasons = build_report(h1).passes_gate_0()

        (run.dir / "gate0.md").write_text(
            render(run.run_id, params, result, spreads, quality_ok, quality_reasons,
                   len(evaluate.memo), n_dropped), encoding="utf-8")

        passed = result.passed and quality_ok
        run.record(
            passed=passed, data_quality_passed=quality_ok,
            pre_cost_r=result.pre_cost.expectancy,
            pre_cost_ci=[result.pre_cost.ci_low, result.pre_cost.ci_high],
            half_ci=result.half_ci,
            net_r=result.net.expectancy, net_ci=[result.net.ci_low, result.net.ci_high],
            mean_cost_r=result.mean_cost_r, resolution=result.resolution,
            n_trades=result.pre_cost.n_trades, n_unique_trades=len(evaluate.memo),
            n_unique_dropped=n_dropped, n_days=result.pre_cost.n_days,
            checks={c.name: c.passed for c in result.checks},
        )
        print((run.dir / "gate0.md").read_text(encoding="utf-8"))
    return 0 if passed else 1


def render(run_id: str, params: dict, res: Gate0Result, spreads: dict[str, dict],
           quality_ok: bool, quality_reasons: list[str], n_unique: int,
           n_dropped: int) -> str:
    ok = res.passed and quality_ok
    g, n = res.pre_cost, res.net
    lines = [
        "# Bramka 0 — test negatywny (losowe wejścia)",
        "",
        f"> Run: `{run_id}` · {params['start']:%Y-%m-%d} → {params['end']:%Y-%m-%d} · "
        f"{', '.join(params['symbols'])}",
        f"> {params['reps']} powtórzeń × {params['n_per_side']} wejść na (para, kierunek); "
        f"{g.n_trades} transakcji, {n_unique} unikalnych ({n_dropped} bez wyniku: "
        f"NO_DATA lub brak danych w chwili decyzji), {g.n_days} dni roboczych",
        f"> Werdykt: **{'PRZECHODZI' if ok else 'NIE PRZECHODZI'}**",
        "",
        "## Kryteria (ADR-025)",
        "",
        "| Kryterium | Wynik | Szczegóły |",
        "|---|---|---|",
    ]
    for c in res.checks:
        lines.append(f"| {c.name} | {'✅' if c.passed else '❌'} | {c.detail} |")
    lines.append(f"| luki w danych H1 (raport jakości) | {'✅' if quality_ok else '❌'} | "
                 f"{'; '.join(quality_reasons) or 'bez zastrzeżeń'} |")
    lines += [
        "",
        "## Expectancy",
        "",
        f"Bootstrap blokowy po {params['block_days']} dni roboczych, "
        f"{params['boot_reps']} powtórzeń.",
        "",
        "| | E[R] | CI95 | SE |",
        "|---|---|---|---|",
        f"| netto (R) | {n.expectancy:+.4f} | [{n.ci_low:+.4f}, {n.ci_high:+.4f}] | {n.se:.4f} |",
        f"| przed kosztem (R + koszt) | {g.expectancy:+.4f} | [{g.ci_low:+.4f}, {g.ci_high:+.4f}] | {g.se:.4f} |",
        f"| koszt | {res.mean_cost_r:.4f} | | |",
        "",
        f"**Rozdzielczość:** połowa CI przed kosztem = {res.resolution:.1f}× średni koszt. "
        + ("Część c NIE odróżnia kosztu policzonego od pominiętego — to rozstrzygają "
           "części a i b."
           if res.resolution >= 1 else
           "Test odróżnia koszt policzony od pominiętego."),
        "",
        "## Per para i kierunek",
        "",
        "| Para | Kierunek | n | E[R] | koszt | przed kosztem | trafienia TP | luki |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in res.breakdown.iter_rows(named=True):
        lines.append(f"| {r['symbol']} | {r['side']} | {r['n']} | {r['mean_r']:+.4f} | "
                     f"{r['mean_cost_r']:.4f} | {r['mean_pre_cost_r']:+.4f} | "
                     f"{r['hit_rate']:.3f} | {r['gap_share']:.3f} |")
    lines += [
        "",
        "Pojedyncze wiersze są silnie autokorelowane (nakładanie się okien) — "
        "informacyjnie, bez testów istotności.",
        "",
        "## Spread M1 (pipsy)",
        "",
        "| Para | min | mediana | p99 | różnych wartości | udział 0 | ujemnych |",
        "|---|---|---|---|---|---|---|",
    ]
    for s, p in spreads.items():
        lines.append(f"| {s} | {p['min_pips']:.2f} | {p['median_pips']:.2f} | "
                     f"{p['p99_pips']:.2f} | {p['distinct']} | {p['zero_share']:.4f} | "
                     f"{p['negative']} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
