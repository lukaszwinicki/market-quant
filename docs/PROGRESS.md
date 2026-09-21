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

## Stan (2026-09-21) — bramka 0 ZAMKNIĘTA, skrypt bramki 1 gotowy

**Kod:** 547 testów. Inwentarz w archiwum. Brakuje: kontrola §10.2 nr 10,
skrypty bramek 2–5, kohorta B, `#9` dla kohorty B.

**Dane.** Bary H1 i M1 zbudowane dla **2015–2021**, sześć par kohorty A
(EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, EURJPY) — commit 8aec3f3. Partycje
2022+ świadomie NIE zbudowane: pobieranie trwa, powstałyby niepełne lata.

Pobieranie ticków leci w tle, wznawialne; front 2026-09-21 19:04 na
**2024-07-22** — segment RESEARCH jest pokryty w całości. Downloader dociąga
też `validation` (2022–2023) i hold-out (2024–2025); pliki na dysku nie łamią
pieczęci, bo tej pilnuje `load_h1`/`load_m1` (`SealedHoldoutError`). Front:

```bash
for p in EURUSD GBPUSD USDJPY AUDUSD USDCAD EURJPY; do \
  printf "%-7s " $p; find data/raw/dukascopy/$p -type f | sed "s|.*$p/||" | sort | tail -1; done
```

Godzin `failed`: **67** (2026-09-21 19:20, po deduplikacji — manifest jest
append-only, liczy się ostatni status pary godzina+symbol), z tego **1 do
końca 2021**: USDCAD 2021-10-05 02:00, jedna para, więc bramka 0 tego nie
potrzebuje. Dociągnąć na końcu: `download_ticks.py --retry-failed`.
NIE uruchamiać, dopóki downloader działa — oba procesy piszą do manifestu.

**Raport jakości** (`reports/data_quality.md`): **PRZECHODZI**. Luki 0,01%
na parę (3–6 barów z 43 634). Trzy godziny bez ticków u wszystkich sześciu
par naraz są nadal WYKRYWANE, ale zaakceptowane jawnie wg ADR-045; godzina
wykryta, a nieujęta na liście, blokuje jak dotąd. Przeliczenie raportu bez
przebudowy barów: `build_bars.py --report-only`.

---

## Bramka 0 — ZAMKNIĘTA, PRZECHODZI (2026-09-21)

Werdykt: run **`20260921T161726Z-1e142d`**, `gate0.py --end 2021-12-31`,
2015-01-01 → 2021-12-31, bez `--allow-stale-bars`, ziarno 0, 20 × 100 wejść
na (para, kierunek). Raport `runs/20260921T161726Z-1e142d/gate0.md`.
**Drzewo czyste, `git_commit` = `4df53af`**, `frozen_sha256` = `b77d0b69…`.
Wpis w `trials.jsonl` jako `kind="control"` — N w DSR nadal 1.

Wszystkie kryteria ADR-025 przeszły (c: CI95 przed kosztem +0,0005 R
[−0,0180; +0,0192], połowa CI 0,0186 ≤ 0,05 R), a do tego spread z ticków
i luki H1. Expectancy netto **−0,0110 R** [−0,0294; +0,0076], średni koszt
**0,01156 R**, ujemne przy koszcie 1×, 2× i 3×. Losowe wejścia nie mają
przewagi — symulator nie pokazuje wycieku z przyszłości. To jest treść
bramki 0: aparatura mierzy uczciwie.

Wcześniejsze przebiegi, rozbicie kosztu po latach i dwie kwestie
rozstrzygnięte przy zamykaniu bramki (237 transakcji „bez wyniku" → warunek
`9_friday`; 3 godziny bez danych → ADR-045): `docs/PROGRESS_ARCHIVE.md`.

---

## Powtórzenie pomiaru niedzielnych kikutów — ZROBIONE (2026-09-21)

`reports/atr_sunday_stub.md` §9, pełny segment RESEARCH, sześć par. **Pomiar,
nie próba.** ADR-041 potwierdzone na 7 latach (deflacja ATR14 −10,3…−11,9%,
zawyżenie `cost_r` +16,0%); **żadna liczba nie rusza decyzji ani pieczęci**.

Jedno doprecyzowanie operacyjne: margines progu `min_h1_bars` to **11–20**,
nie 9–20 jak podaje ADR-041 („na tej próbie") — na 7 latach są trzy Boże
Narodzenia po 10 barów. Próg 12 zostaje w środku przepaści, nowy ADR
niepotrzebny, ale **nie wolno zejść poniżej 11**, powołując się na ADR-041.

---

## Bramka 1 — skrypt gotowy, NIEURUCHOMIONA (2026-09-21)

`scripts/gate1.py` + `src/validation/gate1.py` + `tests/test_gate1.py`
(11 testów na syntetyku, każdy sprawdzony przez zepsucie kodu).
**ADR-046** operacjonalizuje „dodatnie expectancy": trzy stany werdyktu
(STOP, gdy dolny koniec CI95 > 0; NIEROZSTRZYGNIĘTE, gdy średnia ≥ 0,
ale CI95 zawiera 0; PRZECHODZI, gdy średnia < 0), expectancy liczona po
koszcie i po finansowaniu, produktem bramki jest `null.parquet`.

Okablowanie sprawdzone na prawdziwym wycinku (2 pary, pół roku) poza
rejestrem — cała ścieżka przechodzi. Uruchomienie właściwe: `kind="control"`,
**nie podnosi N w DSR**, domyślnie 200 powtórzeń × 100 wejść na
(para, kierunek) na całym segmencie RESEARCH. Czeka na decyzję użytkownika.

---

## Ile potrwa przebieg V1a — ZMIERZONE (2026-09-21)

Dry run, pełny rok decyzji (2016), prawdziwe kontrole `--control-reps 200
--pool-per-group 3000`: **3 min 17 s**, 735 MB RAM. Rozkład: 7 wariantów 13 s,
kontrole #1/#2/#7 + przesunięte cechy **160 s**, koszyk §12 10 s, kontrola #4
11 s, reszta 3 s. Zmierzona osobno faza wariantów na całym segmencie
RESEARCH: **67 s** (baseline 889 transakcji).

Ekstrapolacja na pełny przebieg: koszt kontroli #1 rośnie liniowo z liczbą
transakcji (200 × 142 → 200 × 889 etykietowań), ale **kontrola #2 nie rośnie
wcale** — `--pool-per-group 3000` tnie ją do 12 × 3000 niezależnie od zakresu.
Doliczając droższe etykietowanie na 7-letnich ramkach M1 (3,4 ms vs 2,5 ms):
**ok. 15 minut, z zapasem 10–25.** RAM rzędu 3–4 GB przy 10 GB wolnych.

**Wniosek: `run_v1a.py` NIE wymaga optymalizacji.** To minuty, nie godziny.

**Podgląd wyniku — do wiadomości.** Pomiar zaczął się jako dry run na CAŁYM
segmencie RESEARCH, przerwany po fazie wariantów; zdążył wypisać expectancy
trzech z siedmiu wariantów (baseline, D−, D+). Asystent te liczby widział,
użytkownik nie, `trials.jsonl` jest nietknięty i **N w DSR się nie zmienia**:
dry run nie loguje próby, a podglądnięta została dokładnie ta sama robota,
którą zaloguje przebieg właściwy (ten sam kod, dane i ziarno) — nie jest to
osobna próba. **Warunek: nic nie zostaje zmienione w reakcji na te liczby.**
Zmiana parametru, konfiguracji albo reguły przed przebiegiem właściwym byłaby
decyzją podjętą pod wpływem wyniku i wymaga ADR, który to nazywa. Liczby są
do odtworzenia na żądanie — świadomie nie wpisane tutaj.

---

## Co dalej — kolejność

**1. Bramka 1** (`scripts/gate1.py`, patrz wyżej). Nie jest próbą, nie zużywa
limitu, nie zależy od V1a. Daje rozkład zerowy, którego bramka 2 i tak
będzie potrzebowała.

**2. `scripts/run_v1a.py` BEZ `--dry-run`** — odblokowane po zamknięciu
bramki 0. **To PRAWDZIWA próba**: dokłada 7 do N w DSR i do limitu 50 prób,
nieodwracalnie. Uruchamiać raz i tylko za wyraźną zgodą użytkownika.
Czas przebiegu jest już zmierzony (wyżej), więc nie ma po co robić kolejnego
dry runu.

**3. Zostaje** kontrola §10.2 nr 10 (rozkład zerowy per kohorta — w dużej
części czeka na kohortę B), `#9` dla kohorty B i skrypty bramek 2–5.

Czego NIE robić: kohorty B (bramka 2 może zakończyć projekt), optymalizacji
`run_v1a` (zmierzone — jest szybki), uruchamiania V1a bez zgody użytkownika,
dotykania hold-outu 2024–2025.

---

## Uwaga do `trials.jsonl`

Pierwszy wpis (`20260919T134506Z-c4710e`) powstał przed ADR-029 i nie ma pola
`kind`, więc `n_trials()` liczy go jako próbę strategii (N = 1), choć był
kontrolą. Zachowawczo — zawyża N, nie zaniża. `scripts/gate0.py` deklaruje
już `kind="control"`.
