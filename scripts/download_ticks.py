#!/usr/bin/env python
"""Pobierz tickowe archiwum Dukascopy dla kohorty A.

Symbole i zakres dat czytane z config/v1_baseline.yaml — skrypt nie ma
własnych wartości domyślnych dla niczego, co jest prerejestrowane.

Przebieg jest wznawialny: przerwij Ctrl+C i uruchom ponownie.

    python scripts/download_ticks.py --end 2015-02-01   # próbny miesiąc
    python scripts/download_ticks.py                    # pełny zakres
    python scripts/download_ticks.py --retry-failed     # ponów nieudane
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.download import download_range, failed_hours  # noqa: E402

UTC = dt.timezone.utc
ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "v1_baseline.yaml"


def parse_date(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s).replace(tzinfo=UTC)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cohort", default="cohort_a", choices=["cohort_a", "cohort_b"])
    ap.add_argument("--symbols", nargs="*", help="nadpisz listę z konfiguracji")
    ap.add_argument("--start", type=parse_date, help="domyślnie: splits.research.start")
    ap.add_argument("--end", type=parse_date, help="domyślnie: dziś 00:00 UTC")
    ap.add_argument("--cache", type=Path, default=ROOT / "data" / "raw" / "dukascopy")
    ap.add_argument("--manifest", type=Path, default=ROOT / "data" / "raw" / "manifest.jsonl")
    ap.add_argument("--workers", type=int, default=4,
                    help="feed bywa niestabilny — nie podnoś bez potrzeby")
    ap.add_argument("--retry-failed", action="store_true",
                    help="ponów wyłącznie godziny oznaczone jako failed")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    symbols = args.symbols or cfg["instruments"][args.cohort]["symbols"]
    start = args.start or parse_date(cfg["data"]["splits"]["research"]["start"])
    end = args.end or dt.datetime.now(UTC).replace(
        hour=0, minute=0, second=0, microsecond=0)

    if args.retry_failed:
        pending = failed_hours(args.manifest)
        if not pending:
            logging.info("Brak nieudanych godzin w manifeście.")
            return 0
        logging.info("Ponawiam %d nieudanych godzin", len(pending))
        # download_range pomija to, co jest już w cache, więc wystarczy
        # przepuścić pełny zakres dla dotkniętych symboli.
        symbols = sorted({s for s, _ in pending})
        start = min(h for _, h in pending)
        end = max(h for _, h in pending) + dt.timedelta(hours=1)

    hours = int((end - start).total_seconds() // 3600) * len(symbols)
    logging.info("Symbole: %s", ", ".join(symbols))
    logging.info("Zakres : %s -> %s  (%d godzin do sprawdzenia)",
                 start.date(), end.date(), hours)
    logging.info("Cache  : %s", args.cache)

    counts = download_range(
        symbols, start, end, args.cache, args.manifest, workers=args.workers,
    )

    logging.info("ZAKOŃCZONE: %s", counts)
    if counts["failed"]:
        logging.warning("%d godzin nieudanych — uruchom ponownie z --retry-failed",
                        counts["failed"])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
