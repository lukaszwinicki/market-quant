# PROGRESS.md — bieżący stan projektu market-quant

Log stanu: co jest zrobione, co pokazały ostatnie pomiary, co dalej.
**Nie jest źródłem prawdy** — w razie sprzeczności wygrywa
`docs/PROJECT_SPEC.md`, decyzje trwałe są w `docs/DECISIONS.md` jako ADR.
Ten plik, w przeciwieństwie do `CLAUDE.md`, **nie ładuje się automatycznie**
do kontekstu sesji — czytać jawnie na początku sesji dotyczącej danych,
strategii albo walidacji.

Ten plik ma zostać krótki (do ~120 linii), żeby dał się przeczytać w całości
na starcie sesji. Materiał zamknięty — inwentarz kodu, streszczenia ADR-041…044,
pomiary i notatki z dry runów — jest w `docs/PROGRESS_ARCHIVE.md`.

Każdą liczbę tutaj sprawdzać komendą, nie brać na wiarę. Notatki starzeją się
szybciej niż dysk.

---

## Stan (2026-09-21) — bramka 0 ZAMKNIĘTA

**Kod:** 536 testów, wszystkie komponenty do bramki 0 gotowe. Inwentarz
w archiwum. Brakuje: kontrola §10.2 nr 10, skrypty bramek 1–5, kohorta B,
`#9` dla kohorty B.

**Dane.** Bary H1 i M1 zbudowane dla **2015–2021**, sześć par kohorty A
(EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, EURJPY) — commit 8aec3f3. Partycje
2022+ świadomie NIE zbudowane: pobieranie trwa, powstałyby niepełne lata.

Pobieranie ticków leci w tle, wznawialne; front 2026-09-21 18:30 na
**2024-07-01**, czyli segment RESEARCH (do końca 2021) jest pokryty w całości.
Domyślny koniec downloadera to „dziś", więc dociąga też `validation`
(2022–2023) i hold-out (2024–2025) — pobranie plików na dysk nie łamie
pieczęci, bo tej pilnuje `load_h1`/`load_m1` (`SealedHoldoutError`). Tempo
zmierzone z mtime plików: ~46 dni danych na godzinę, czyli ok. 12 h do końca
hold-outu. Front:

```bash
for p in EURUSD GBPUSD USDJPY AUDUSD USDCAD EURJPY; do \
  printf "%-7s " $p; find data/raw/dukascopy/$p -type f | sed "s|.*$p/||" | sort | tail -1; done
```

Godzin `failed`: **60** po deduplikacji (manifest jest append-only, liczy się
ostatni status dla pary godzina+symbol), z tego **1 do końca 2021** — USDCAD
2021-10-05 02:00, jedna para, więc bramka 0 tego nie potrzebuje. Dociągnąć
na końcu: `download_ticks.py --retry-failed`. NIE uruchamiać, dopóki
downloader działa — oba procesy piszą do `data/raw/manifest.jsonl`.

**Raport jakości** (`reports/data_quality.md`): **PRZECHODZI**. Luki 0,01%
na każdej parze (3–6 barów z 43 634). Trzy godziny bez ticków u wszystkich
sześciu par naraz (2016-09-02 18:00, 2017-12-24 22:00, 2019-05-26 22:00) są
nadal WYKRYWANE, ale zaakceptowane jawnie wg ADR-045 — raport drukuje je
z powodem i dowodem. Godzina wykryta, a nieujęta na liście, blokuje jak dotąd.
Przeliczenie raportu bez przebudowy barów: `build_bars.py --report-only`.

---

## Bramka 0 — ZAMKNIĘTA, PRZECHODZI (2026-09-21)

Werdykt: run **`20260921T161726Z-1e142d`**, `gate0.py --end 2021-12-31`,
2015-01-01 → 2021-12-31, bez `--allow-stale-bars`, ziarno 0, 20 × 100 wejść
na (para, kierunek). Raport `runs/20260921T161726Z-1e142d/gate0.md`.
**Drzewo czyste, `git_commit` = `4df53af`**, `frozen_sha256` = `b77d0b69…`.
Wpis w `trials.jsonl` jako `kind="control"` — N w DSR nadal 1.

| Kryterium ADR-025 | Wynik |
|---|---|
| a. rachunek kosztu per transakcja (podłoga, spread raz) | ✅ 0 naruszeń na 23 758 |
| b. martyngał na syntetyku | ✅ |
| c. CI95 przed kosztem ∋ 0, połowa CI ≤ 0,05 R | ✅ +0,0005 R [−0,0180; +0,0192], połowa 0,0186 |
| spread z ticków, bid/ask osobno | ✅ |
| luki w danych H1 | ✅ 3 godziny zaakceptowane wg ADR-045, 0 nierozstrzygniętych |

Expectancy netto **−0,0110 R** [−0,0294; +0,0076], ujemne przy koszcie 1×, 2×
i 3×. Losowe wejścia nie mają przewagi — symulator nie pokazuje wycieku
z przyszłości. To jest treść bramki 0: aparatura mierzy uczciwie.

Wcześniejsze przebiegi tego samego pomiaru, zachowane w `trials.jsonl`:
`20260921T151443Z-187ab1` (przed ADR-045, werdykt blokowany wierszem
o lukach) i `20260921T160904Z-17fbe1` (po kodzie ADR-045, ale przed jego
commitem — `git_dirty`, dlatego powtórzony). `20260919T134506Z-c4710e` to
pierwszy przebieg, nieaktualny po ADR-026.

**Koszt: ADR-041 działa, potwierdzone.** Na CAŁYM zakresie średni `cost_r`
wychodzi 0,01156 R, czyli WIĘCEJ niż 0,0106 z pierwszego przebiegu — to nie
regresja. Na dokładnie tym samym oknie co pierwszy przebieg
(2015-01-01…2016-04-28, 4397 transakcji) koszt to **0,00906 R**, czyli
**−14,5%** i zgodnie z `reports/atr_sunday_stub.md`. Reszta to późniejsze
lata, gdzie spread jest większy w stosunku do zmienności: 2015 0,00909 →
2019 **0,01503** → 2021 0,01311.

---

## Kwestie rozstrzygnięte przy zamykaniu bramki 0

Dwie: **237 transakcji „bez wyniku"** to w 91% bar piątkowy po zamknięciu
rynku (objęty warunkiem `9_friday`, nowy ADR niepotrzebny), oraz **3 godziny
bez danych** — ADR-045, zaimplementowane. Pełny zapis obu, z metodą i
pułapkami (`evaluate.memo`, `gap_share` ≠ transakcje bez wyniku):
`docs/PROGRESS_ARCHIVE.md`.

---

## Powtórzenie pomiaru niedzielnych kikutów — ZROBIONE (2026-09-21)

`reports/atr_sunday_stub.md` §9, pełny segment RESEARCH 2015-01-01 →
2021-12-31, sześć par. **Pomiar, nie próba** — bez `start_run`, N w DSR bez
zmian. **ADR-041 potwierdzone, żadna liczba nie rusza decyzji ani pieczęci.**

| | 2015-01…2016-04 | 2015–2021 |
|---|---|---|
| niedziel będących kikutem | 69/69 na parę | **363–364/363–364 na parę** |
| deflacja ATR14 (parowana) | −10,7…−11,8% | **−10,3…−11,9%** |
| udział TP | 10,2% → 6,5% | **9,0% → 5,9%** (−35,1% wzgl.) |
| zawyżenie `cost_r` | +16,8% | **+16,0%** |

Ramię „przed ADR-041" to funkcja wyjęta z commita `e5e9f0e~1`, sprawdzona co
do wartości na syntetyku i na EURUSD 2017–2018. Kontrola negatywna (oba
ramiona z tej samej funkcji) daje dokładnie zero różnicy.

Zgodność z bramką 0: ramię „po naprawie" daje `cost_r` 0,01143, bramka 0
zmierzyła 0,01156 — dwie różne drogi losowania, różnica 1,1%.

**Dwa doprecyzowania, oba bez skutków decyzyjnych:**
1. Kikut niedzielny ma 3 bary latem (237 niedziel, otwarcie 21:00 UTC) i **2
   zimą** (125 niedziel, otwarcie 22:00 UTC) — mediana 3 to przykrywała.
2. Margines progu `min_h1_bars` to **11–20**, nie 9–20 jak podaje ADR-041
   (tam z zastrzeżeniem „na tej próbie"). Na 7 latach są trzy Boże Narodzenia
   po 10 barów. Próg 12 zostaje w środku przepaści; **nowy ADR niepotrzebny**,
   ale nie wolno zejść poniżej 11, powołując się na zakres z ADR-041.

---

## Co dalej — kolejność

**1. `scripts/run_v1a.py` BEZ `--dry-run`** — bramka 0 jest zamknięta, więc
to jest odblokowane. **Ale to PRAWDZIWA próba**: dokłada 7 do N w DSR
i do limitu 50 prób, nieodwracalnie. Uruchamiać raz i tylko za wyraźną zgodą
użytkownika. Wcześniej zmierzyć czas dry runem na pełnym roku z prawdziwymi
kontrolami
(`--control-reps 200 --pool-per-group 3000`): dry run na 4 miesiącach
z obciętymi kontrolami trwał ~25 s, ale kontrole rosną z liczbą transakcji
RAZY liczba powtórzeń, więc ekstrapolacja z niego jest bezwartościowa.
Potem bramka 1.

**2. Zostaje kontrola §10.2 nr 10** (rozkład zerowy per kohorta — w dużej
części czeka na kohortę B), **#9 dla kohorty B** i skrypty bramek 1–5.
Z tego bez nowych danych da się zrobić `scripts/gate1.py`: kryterium bramki 1
brzmi „kontrola losowa daje dodatnie expectancy = STOP", a sama kontrola już
istnieje (`src/validation/controls.py`, `gate0.run_random_control`). Wzorzec:
`scripts/gate0.py` — `preflight()` i `require_fresh_bars()` PRZED `start_run`,
`kind="control"`, raport `runs/<id>/gate1.md`.

Czego NIE robić: kohorty B (bramka 2 może zakończyć projekt), optymalizacji
`run_v1a` (nie wiadomo jeszcze, czy jest za wolny), uruchamiania V1a bez
zgody użytkownika (patrz punkt 1), dotykania hold-outu 2024–2025.

---

## Uwaga do `trials.jsonl`

Pierwszy wpis (`20260919T134506Z-c4710e`) powstał przed ADR-029 i nie ma pola
`kind`, więc `n_trials()` liczy go jako próbę strategii (N = 1), choć był
kontrolą. Zachowawczo — zawyża N, nie zaniża. `scripts/gate0.py` deklaruje
już `kind="control"`.
