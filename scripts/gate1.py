#!/usr/bin/env python
"""Bramka 1: rozkład zerowy z kontroli losowej na kohorcie A (PROJECT_SPEC §15).

Kryterium: **STOP, jeśli kontrola losowa daje dodatnie expectancy**.
Operacjonalizacja i trzy stany werdyktu — `src/validation/gate1.py` i ADR-046.
Produktem bramki jest rozkład zerowy (`null.parquet`), nie sam werdykt.

Każde uruchomienie jest przebiegiem `kind="control"` w `trials.jsonl`:
logowane, ale NIE podnosi N w DSR ani limitu prób (ADR-029). Nie ma trybu
„na sucho" — sprawdzanie okablowania robią testy na syntetyku
(`tests/test_gate1.py`).

    python scripts/gate1.py                         # research split, dane ciągłe
    python scripts/gate1.py --reps 200 --n-per-side 100
    python scripts/gate1.py --end 2016-12-31

Wynik: `runs/<id>/gate1.md`, `labels.parquet`, `null.parquet`.

Uwaga: w przeciwieństwie do `run_v1a.py` ten przebieg NIE sprawdza pokrycia
kalendarza makro. Wejścia są losowe, więc blackout (§7.2) ich nie dotyczy —
dziura w kalendarzu nie może tu niczego przemilczeć. Stopy procentowe
sprawdzamy, bo wchodzą do finansowania każdej transakcji (ADR-035).
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
import time
from dataclasses import asdict
from pathlib import Path

import polars as pl
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.rates import require_coverage_for_decisions as require_rate_coverage  # noqa: E402
from src.execution.financing import apply_financing, markup_from  # noqa: E402
from src.features.technical import compute_features  # noqa: E402
from src.harness.market import (  # noqa: E402
    cost_model_for, load_h1, load_m1, require_fresh_bars,
)
from src.harness.registry import start_run  # noqa: E402
from src.validation.gate0 import (  # noqa: E402
    balanced_counts, contiguous_end, eligible_candidates, label_spec_from,
    make_evaluator, run_random_control,
)
from src.validation.gate1 import (  # noqa: E402
    PASS, STOP, Gate1Result, assess, rep_means,
)

UTC = dt.timezone.utc
ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "v1_baseline.yaml"
RATES = ROOT / "data" / "rates" / "fred.parquet"

EXIT = {PASS: 0, STOP: 1}       # cokolwiek innego: NIEROZSTRZYGNIĘTE → 3

log = logging.getLogger("gate1")


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
    ap.add_argument("--reps", type=int, default=200,
                    help="powtórzeń — tyle punktów ma rozkład zerowy")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--boot-reps", type=int, help="domyślnie validation.bootstrap")
    ap.add_argument("--allow-stale-bars", action="store_true",
                    help="policz mimo partycji niezgodnych z cache ticków "
                         "(wynik NIE zamyka bramki)")
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
    markup = markup_from(cfg)
    rate_kind = cfg["costs"]["financing"]["cohort_a_rate_kind"]

    # Wszystko, co może unieważnić przebieg, PRZED `start_run` — nieudana
    # konfiguracja nie ma zaśmiecać `trials.jsonl`. Partycja zbudowana
    # z wycinka cache wygląda jak poprawne dane i cicho zaniża próbę
    # (`src/data/provenance.py`); brak stopy wszedłby do swapu jak zero.
    rates = pl.read_parquet(RATES)
    currencies = tuple(sorted({c for s in symbols for c in (s[:3], s[3:])}))
    require_rate_coverage(rates, currencies, rate_kind, start.date(),
                          (args.end or split_end).date())
    if not args.allow_stale_bars:
        require_fresh_bars(symbols, start, args.end or split_end)

    # Koniec wspólny dla wszystkich par: ta sama oś dni w bootstrapie.
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
        "markup_annual_pct": markup, "rate_kind": rate_kind,
        "label_spec": asdict(spec),
    }
    with start_run("gate1: null distribution from the random control on cohort A",
                   params, kind="control") as run:
        log.info("run %s: %s, %s → %s", run.run_id, ",".join(symbols),
                 start.date(), end.date())
        costs = {s: cost_model_for(s, cfg) for s in symbols}
        h1 = {s: b.filter(pl.col("ts") <= end) for s, b in h1.items()}

        cands, m1 = [], {}
        for s in symbols:
            c = eligible_candidates(compute_features(h1[s]), s, start, end, spec)
            m1[s] = load_m1(s, start, end, cfg)
            cands.append(c)
            log.info("%s: %d kandydatów, %d barów M1", s, c.height, m1[s].height)
        candidates = pl.concat(cands)

        evaluate = make_evaluator(m1, costs, spec)
        t0 = time.monotonic()

        def progress(i: int, lab: pl.DataFrame) -> None:
            if i % 10 == 0 or i + 1 == args.reps:
                log.info("rep %d/%d: n=%d, mean R %+.4f, unikalnych transakcji %d, %.0f s",
                         i + 1, args.reps, lab.height,
                         lab["r"].mean() if lab.height else float("nan"),
                         len(evaluate.memo), time.monotonic() - t0)

        labels = run_random_control(candidates, balanced_counts(symbols, args.n_per_side),
                                    evaluate, args.reps, args.seed, progress)
        if not labels.height:
            log.error("kontrola nie dała ani jednej rozstrzygniętej transakcji")
            return 2

        # Swap jest kierunkowy, więc wchodzi PRZED jakąkolwiek statystyką
        # (ADR-035). `r` sprzed finansowania zostaje jako `r + financing_r`.
        labels = apply_financing(labels, rates, markup)
        labels.write_parquet(run.dir / "labels.parquet")

        result = assess(labels, params["block_days"], params["boot_reps"], args.seed)
        null = rep_means(labels)
        pl.DataFrame({"rep": range(len(null)), "mean_r": null}).write_parquet(
            run.dir / "null.parquet")
        n_dropped = sum(v is None for v in evaluate.memo.values())

        (run.dir / "gate1.md").write_text(
            render(run.run_id, params, result, len(evaluate.memo), n_dropped),
            encoding="utf-8")

        run.record(
            verdict=result.verdict, passed=result.passed,
            net_r=result.net.expectancy,
            net_ci=[result.net.ci_low, result.net.ci_high],
            net_se=result.net.se,
            mean_cost_r=result.mean_cost_r, mean_financing_r=result.mean_financing_r,
            null_mean=result.null.mean, null_sd=result.null.sd,
            null_q025=result.null.q025, null_q975=result.null.q975,
            null_positive_share=result.null.positive_share,
            null_reps=result.null.n_reps, trades_per_rep=result.null.trades_per_rep,
            n_trades=result.net.n_trades, n_days=result.net.n_days,
            n_unique_trades=len(evaluate.memo), n_unique_dropped=n_dropped,
            checks={c.name: c.passed for c in result.checks},
        )
        print((run.dir / "gate1.md").read_text(encoding="utf-8"))
    return EXIT.get(result.verdict, 3)


def render(run_id: str, params: dict, res: Gate1Result, n_unique: int,
           n_dropped: int) -> str:
    net, null = res.net, res.null
    lines = [
        "# Bramka 1 — rozkład zerowy z kontroli losowej",
        "",
        f"> Run: `{run_id}` · {params['start']:%Y-%m-%d} → {params['end']:%Y-%m-%d} · "
        f"{', '.join(params['symbols'])}",
        f"> {params['reps']} powtórzeń × {params['n_per_side']} wejść na "
        f"(para, kierunek); {net.n_trades} transakcji, {n_unique} unikalnych "
        f"({n_dropped} bez wyniku), {net.n_days} dni roboczych",
        f"> Werdykt: **{res.verdict}**",
        "",
        "## Kryterium (§15, ADR-046)",
        "",
        "| Warunek | Wynik | Szczegóły |",
        "|---|---|---|",
    ]
    for c in res.checks:
        lines.append(f"| {c.name} | {'✅' if c.passed else '❌'} | {c.detail} |")
    lines += [
        "",
        "Werdykt `NIEROZSTRZYGNIĘTE` (średnia ≥ 0, ale CI95 zawiera 0) nie jest "
        "przejściem ani STOP-em: przy koszcie rzędu 0,01 R sama losowość "
        "wyrzuca średnią nad zero na tyle często, że automatyczna decyzja "
        "byłaby decyzją szumu. Rozstrzyga człowiek — po dołożeniu danych "
        "albo powtórzeń.",
        "",
        "## Expectancy netto (po koszcie i po finansowaniu)",
        "",
        f"Bootstrap blokowy po {params['block_days']} dni roboczych, "
        f"{params['boot_reps']} powtórzeń.",
        "",
        "| | E[R] | CI95 | SE |",
        "|---|---|---|---|",
        f"| netto (R) | {net.expectancy:+.4f} | [{net.ci_low:+.4f}, "
        f"{net.ci_high:+.4f}] | {net.se:.4f} |",
        "",
        f"Średni koszt {res.mean_cost_r:.4f} R, średni koszt finansowania "
        f"{res.mean_financing_r:+.4f} R (dodatnie = koszt; marża "
        f"{params['markup_annual_pct']:g}% "
        f"rocznie, stopy `{params['rate_kind']}`). Bez finansowania wynik "
        f"netto to {net.expectancy + res.mean_financing_r:+.4f} R — ta liczba "
        "jest porównywalna z raportem bramki 0.",
        "",
        "## Rozkład zerowy",
        "",
        "| powtórzeń | transakcji na powtórzenie | średnia | SD | 2,5% | mediana | 97,5% | udział dodatnich |",
        "|---|---|---|---|---|---|---|---|",
        f"| {null.n_reps} | {null.trades_per_rep:.0f} | {null.mean:+.4f} | "
        f"{null.sd:.4f} | {null.q025:+.4f} | {null.median:+.4f} | "
        f"{null.q975:+.4f} | {null.positive_share:.3f} |",
        "",
        "Pełny rozkład: `null.parquet` (jedna średnia na powtórzenie).",
        "",
        "**To nie jest rozkład zerowy bramki 2.** SD skaluje się jak "
        "1/√(liczba transakcji w powtórzeniu), a bramka 2 porównuje strategię "
        "z kontrolą o tej samej liczebności co strategia (§10.2 #1) — tę liczy "
        "sam przebieg V1a. Tutaj liczebność jest deklarowana z góry "
        "i zrównoważona kierunkowo, żeby dryf par nie udawał wyniku.",
        "",
        "Wejścia losowe nie respektują blackoutu makro (§7.2) ani limitu "
        "jednej pozycji na parę — tak samo jak kontrola #1 w przebiegu V1a, "
        "z którą ten rozkład ma być porównywalny.",
        "",
        "## Per para i kierunek",
        "",
        "| Para | Kierunek | n | E[R] | koszt | finansowanie | trafienia TP |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in res.breakdown.iter_rows(named=True):
        lines.append(f"| {r['symbol']} | {r['side']} | {r['n']} | {r['mean_r']:+.4f} | "
                     f"{r['mean_cost_r']:.4f} | {r['mean_financing_r']:+.4f} | "
                     f"{r['hit_rate']:.3f} |")
    lines += [
        "",
        "Wiersze są silnie autokorelowane (okna się nakładają) — "
        "informacyjnie, bez testów istotności.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
