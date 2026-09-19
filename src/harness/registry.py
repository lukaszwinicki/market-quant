"""Rejestr prób i katalog uruchomienia (PROJECT_SPEC §11, §13, ADR-014).

Każde uruchomienie backtestu przechodzi przez `start_run()`. Nie ma innej
drogi do wyniku, więc nie ma jak pominąć wpisu w `trials.jsonl`.

DWA WPISY NA URUCHOMIENIE

    start  — zapisywany ZANIM wykona się jakikolwiek kod badawczy
    end    — zapisywany w `finally`: ok / error / interrupted

Wpis `start` jest tym, co liczy się jako próba. Uruchomienie przerwane
w połowie, po którym zobaczyłeś częściowe wyniki i coś zmieniłeś, JEST
próbą — gdyby wpis powstawał dopiero na końcu, taki przebieg zniknąłby
z licznika, a DSR dostałby zaniżone N. Zawyżone N jest konserwatywne,
zaniżone — nie.

ODTWARZALNOŚĆ

Wynik bez kodu i parametrów, które go dały, jest anegdotą. Każdy wpis
niesie hash commita, a jeśli drzewo robocze było brudne — hash różnicy,
której pełna treść ląduje w `runs/<id>/diff.patch`. Konfiguracja jest
kopiowana bajt w bajt, z sha256 całego pliku i osobno sekcji
`frozen: true`: porównanie `frozen_sha256` między wpisami pokazuje
od razu, które próby powstały na innej prerejestracji.

`trials.jsonl` jest wersjonowany, więc po pierwszym uruchomieniu drzewo
jest zawsze „brudne" — przez sam rejestr. Ten jeden plik jest wyłączony
z wykrywania zmian.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Any, Iterator

import yaml

UTC = dt.timezone.utc
ROOT = Path(__file__).resolve().parents[2]
TRIALS_FILE = "trials.jsonl"
CONFIG_REL = "config/v1_baseline.yaml"
PACKAGES = ("polars", "numpy", "pyarrow", "PyYAML")


@dataclass(frozen=True)
class GitState:
    commit: str
    dirty: bool
    diff: str                 # `git diff HEAD` bez trials.jsonl
    untracked: list[str]      # nowe pliki — `git diff` ich nie widzi

    @property
    def diff_sha256(self) -> str | None:
        if not self.dirty:
            return None
        h = hashlib.sha256(self.diff.encode())
        for name in self.untracked:
            h.update(name.encode())
        return h.hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    ).stdout


def git_state(repo: Path) -> GitState:
    """Stan repozytorium. Brak gita = błąd, nie „nieznany commit"."""
    exclude = f":(exclude){TRIALS_FILE}"
    commit = _git(repo, "rev-parse", "HEAD").strip()
    diff = _git(repo, "diff", "HEAD", "--binary", "--", ".", exclude)
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard",
                     "--", ".", exclude).split()
    return GitState(commit, bool(diff or untracked), diff, untracked)


def freeze_commit(repo: Path, config_rel: str) -> str | None:
    """Commit, który dodał plik konfiguracji — punkt zamrożenia (meta w YAML)."""
    out = _git(repo, "log", "--diff-filter=A", "--format=%H", "--", config_rel).split()
    return out[-1] if out else None


def frozen_sections(cfg: Any, path: str = "") -> dict[str, Any]:
    """Wszystkie poddrzewa oznaczone `frozen: true`, kluczowane ścieżką."""
    out: dict[str, Any] = {}
    if isinstance(cfg, dict):
        if cfg.get("frozen") is True:
            out[path or "."] = cfg
        for k, v in cfg.items():
            out.update(frozen_sections(v, f"{path}.{k}" if path else str(k)))
    return out


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      default=str, separators=(",", ":")).encode()


def _jsonable(obj: Any) -> Any:
    """numpy/datetime/Path → typy JSON. Wynik ma być czytelny bez numpy."""
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (dt.datetime, dt.date)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if hasattr(obj, "item") and callable(obj.item):     # skalary numpy
        return obj.item()
    if hasattr(obj, "tolist") and callable(obj.tolist):  # tablice numpy
        return obj.tolist()
    return obj


def append_trial(path: Path, record: dict) -> None:
    """Dopisz jedną linię. Blokada + fsync: dwa procesy nie przeplotą wpisów,
    a wpis przeżywa awarię procesu tuż po zapisie."""
    line = json.dumps(_jsonable(record), ensure_ascii=False, sort_keys=True) + "\n"
    with open(path, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def read_trials(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def n_trials(path: Path) -> int:
    """Liczba prób = liczba rozpoczętych uruchomień, także przerwanych.

    Bez filtrowania po statusie i celu: każde kryterium wykluczające
    byłoby ręcznym pominięciem (`manual_skip_allowed: false`).
    """
    return len({r["run_id"] for r in read_trials(path) if r["event"] == "start"})


@dataclass
class Run:
    run_id: str
    dir: Path
    params: dict
    metrics: dict = field(default_factory=dict)

    def record(self, **metrics: Any) -> None:
        """Metryki trafią do wpisu `end` i do `runs/<id>/metrics.json`."""
        self.metrics.update(metrics)


def _new_run_id(now: dt.datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)


@contextlib.contextmanager
def start_run(
    purpose: str,
    params: dict | None = None,
    *,
    repo: Path = ROOT,
    config_rel: str = CONFIG_REL,
    runs_dir: Path | None = None,
    trials_path: Path | None = None,
) -> Iterator[Run]:
    """Otwórz uruchomienie: katalog, kopia konfiguracji, wpis `start`.

        with start_run("gate0 random control", {"seed": 1, "n_reps": 200}) as run:
            ...
            run.record(mean_r=-0.08, n=1234)

    `purpose` jest wymagany — za pół roku lista hashów bez opisu nic nie
    powie. Wyjątek z ciała jest zapisywany w `end` i propagowany dalej.
    """
    if not purpose.strip():
        raise ValueError("purpose nie może być pusty")
    params = dict(params or {})
    runs_dir = runs_dir or repo / "runs"
    trials_path = trials_path or repo / TRIALS_FILE

    git = git_state(repo)
    config_path = repo / config_rel
    config_bytes = config_path.read_bytes()
    cfg = yaml.safe_load(config_bytes)

    now = dt.datetime.now(UTC)
    run_id = _new_run_id(now)
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    manifest = {
        "event": "start",
        "run_id": run_id,
        "ts_utc": now.isoformat(),
        "purpose": purpose,
        "params": params,
        "git_commit": git.commit,
        "git_dirty": git.dirty,
        "git_diff_sha256": git.diff_sha256,
        "git_untracked": git.untracked,
        "config_path": config_rel,
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "config_freeze_commit": freeze_commit(repo, config_rel),
        "frozen_sha256": hashlib.sha256(_canonical(frozen_sections(cfg))).hexdigest(),
        "argv": sys.argv,
        "python": platform.python_version(),
        "packages": {p: _version(p) for p in PACKAGES},
    }

    shutil.copyfile(config_path, run_dir / Path(config_rel).name)
    if git.dirty:
        (run_dir / "diff.patch").write_text(git.diff, encoding="utf-8")
    (run_dir / "run.json").write_text(
        json.dumps(_jsonable(manifest), indent=2, ensure_ascii=False), encoding="utf-8")

    # Od tej chwili próba istnieje — niezależnie od tego, co stanie się dalej.
    append_trial(trials_path, manifest)

    run = Run(run_id=run_id, dir=run_dir, params=params)
    t0 = time.monotonic()
    status, error = "ok", None
    try:
        yield run
    except KeyboardInterrupt:
        status, error = "interrupted", "KeyboardInterrupt"
        raise
    except BaseException as e:
        status, error = "error", f"{type(e).__name__}: {e}"
        raise
    finally:
        end = {
            "event": "end",
            "run_id": run_id,
            "ts_utc": dt.datetime.now(UTC).isoformat(),
            "status": status,
            "error": error,
            "duration_s": round(time.monotonic() - t0, 3),
            "metrics": run.metrics,
        }
        (run_dir / "metrics.json").write_text(
            json.dumps(_jsonable(end), indent=2, ensure_ascii=False), encoding="utf-8")
        append_trial(trials_path, end)


def _version(pkg: str) -> str | None:
    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:
        return None
