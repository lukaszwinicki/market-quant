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

## Stan (2026-09-21)

**Kod:** 528 testów, wszystkie komponenty do bramki 0 gotowe. Inwentarz
w archiwum. Brakuje: kontrola §10.2 nr 10, skrypty bramek 1–5, kohorta B,
`#9` dla kohorty B.

**Dane.** Bary H1 i M1 zbudowane dla **2015–2021**, sześć par kohorty A
(EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, EURJPY) — commit 8aec3f3. Partycje
2022+ świadomie NIE zbudowane: pobieranie trwa, powstałyby niepełne lata.

Pobieranie ticków leci w tle, wznawialne; front 2026-09-21 na **2024-05-20**,
czyli segment RESEARCH (do końca 2021) jest pokryty w całości. Front:

```bash
for p in EURUSD GBPUSD USDJPY AUDUSD USDCAD EURJPY; do \
  printf "%-7s " $p; find data/raw/dukascopy/$p -type f | sed "s|.*$p/||" | sort | tail -1; done
```

Godzin `failed`: **60** po deduplikacji (manifest jest append-only, liczy się
ostatni status dla pary godzina+symbol), z tego **1 do końca 2021** — USDCAD
2021-10-05 02:00, jedna para, więc bramka 0 tego nie potrzebuje. Dociągnąć
na końcu: `download_ticks.py --retry-failed`. NIE uruchamiać, dopóki
downloader działa — oba procesy piszą do `data/raw/manifest.jsonl`.

**Raport jakości** (`reports/data_quality.md`): luki 0,01% na każdej parze
(3–6 barów z 43 634), ale werdykt **NIE PRZECHODZI** z powodu 3 godzin
bez ticków u wszystkich sześciu par jednocześnie: 2016-09-02 18:00,
2017-12-24 22:00, 2019-05-26 22:00. Pliki na dysku mają 0 bajtów, downloader
nie zgłosił błędu — wygląda na puste odpowiedzi Dukascopy. Wiersz nie ma
mechanizmu ręcznej akceptacji, więc blokuje werdykt całej bramki.

---

## Bramka 0 — przebieg zamykający, NIEDOMKNIĘTA

Run `20260921T151443Z-187ab1` (2026-09-21), `gate0.py --end 2021-12-31`,
2015-01-01 → 2021-12-31, bez `--allow-stale-bars`, ziarno 0, 20 × 100 wejść
na (para, kierunek). Raport `runs/20260921T151443Z-187ab1/gate0.md`.
Wpis w `trials.jsonl` jako `kind="control"` — nie podnosi N.

| Kryterium ADR-025 | Wynik |
|---|---|
| a. rachunek kosztu per transakcja (podłoga, spread raz) | ✅ 0 naruszeń na 23 758 |
| b. martyngał na syntetyku | ✅ |
| c. CI95 przed kosztem ∋ 0, połowa CI ≤ 0,05 R | ✅ +0,0005 R [−0,0180; +0,0192], połowa 0,0186 |
| spread z ticków, bid/ask osobno | ✅ |
| luki w danych H1 | ❌ 3 godziny, patrz wyżej |

Expectancy netto **−0,0110 R** [−0,0294; +0,0076], ujemne przy koszcie 1×, 2×
i 3×. Losowe wejścia nie mają przewagi — symulator nie pokazuje wycieku
z przyszłości. Werdykt raportu to jednak **NIE PRZECHODZI**, wyłącznie
z powodu wiersza o lukach.

**Koszt: ADR-041 działa, potwierdzone.** Na CAŁYM zakresie średni `cost_r`
wychodzi 0,01156 R, czyli WIĘCEJ niż 0,0106 z pierwszego przebiegu — to nie
regresja. Na dokładnie tym samym oknie co pierwszy przebieg
(2015-01-01…2016-04-28, 4397 transakcji) koszt to **0,00906 R**, czyli
**−14,5%** i zgodnie z `reports/atr_sunday_stub.md`. Reszta to późniejsze
lata, gdzie spread jest większy w stosunku do zmienności: 2015 0,00909 →
2019 **0,01503** → 2021 0,01311.

---

## Otwarte kwestie blokujące bramkę 0

**1. ROZSTRZYGNIĘTE 2026-09-21: 237 transakcji „bez wyniku" to ostatni bar
tygodnia.** Raport `reports/gate0_dropped.md`. **215 z 237 (91%)** to bar
piątkowy, którego moment decyzji wypada po zamknięciu rynku o 17:00 czasu
Nowego Jorku: w czasie letnim bar 21:00 odpada w 100% przypadków, w zimowym
bar 22:00 — rozkład miesięczny zgadza się z datami zmiany czasu co do
przypadku. Dalsze 9 to zamknięcia świąteczne (24.12, 25.12, 31.12), 13 to
pojedyncze godziny cienkiej płynności (głównie 21:00 UTC w dzień powszedni).
**Z 3 godzin podejrzanych o awarię feedu nie pochodzi ANI JEDNA** — nie mają
barów H1, więc nigdy nie weszły do puli kandydatów.

Werdykt: gubienie zależy wyłącznie od znacznika czasu wejścia, nie od
przyszłego przebiegu ceny — nie ma look-aheadu ani biasu optymistycznego.
Ostrzeżenie ADR-026 się nie realizuje.

Ujawnia natomiast lukę w regułach: nic nie blokuje decyzji po piątkowym
zamknięciu, więc kandydat powstaje i znika po cichu z braku danych. To odbicie
sytuacji, którą ADR-042 rozstrzygnął dla otwarcia niedzielnego — patrz
punkt 4 w „Co dalej".

Metoda na przyszłość: `evaluate.memo` (`src/validation/gate0.py:114`) trzyma
transakcje bez etykiety jako wartości `None`, więc listy NIE trzeba odtwarzać
przez powtórzenie losowania. UWAGA: kolumna „luki" w raporcie bramki 0 to
`gap_share` (`src/validation/gate0.py:244`) — udział transakcji domkniętych
**luką cenową** przez SL/TP, a NIE udział transakcji bez wyniku.

**2. Brak ADR-u o ręcznej akceptacji 3 godzin bez danych.** Raport jakości
nie ma mechanizmu akceptacji, więc albo powstaje ADR (kryterium akceptacji
+ ślad w raporcie), albo bramka 0 zostaje formalnie otwarta. Najpierw ADR,
potem kod — jak przy ADR-025 i ADR-044.

**3. Pomiar z `reports/atr_sunday_stub.md` nie powtórzony** na pełnym
zakresie. Raport jest z 2015-01…2016-04, bary są już z 2015–2021. Mechanizm
jest strukturalny, więc to weryfikacja, nie niepewność.

---

## Co dalej — kolejność

**1. ADR o 3 godzinach bez danych** (2016-09-02 18:00, 2017-12-24 22:00,
2019-05-26 22:00): kryterium ręcznej akceptacji + ślad w raporcie jakości,
potem kod, potem domknięcie bramki 0 (werdykt w `docs/DECISIONS.md`).
Najpierw ADR, potem kod — jak przy ADR-025 i ADR-044.

**2. ADR o piątkowym zamknięciu** — jawny warunek NO TRADE dla decyzji
wypadających po zamknięciu rynku, odbicie ADR-042 dla otwarcia niedzielnego.
Zaczepiony o moment decyzji, nie o bar; granica jako 17:00 czasu lokalnego
Nowego Jorku, nigdy stały offset UTC (ADR-034 pkt 4) — inaczej rozjedzie się
z czasem letnim. Uzasadnienie i pomiar: `reports/gate0_dropped.md`.
Dotyczy V1a, nie unieważnia bramki 0 (w kontroli losowej skutek to 1%
transakcji znikających bez biasu).

**3. Powtórzenie pomiaru niedzielnych kikutów** na 2015–2021.

**4. Dopiero po bramce 0: `scripts/run_v1a.py` BEZ `--dry-run`.** To
PRAWDZIWA próba — dokłada 7 do N w DSR i do limitu 50 prób, nieodwracalnie.
Uruchamiać raz i tylko za zgodą użytkownika. Wcześniej zmierzyć czas dry
runem na pełnym roku z prawdziwymi kontrolami
(`--control-reps 200 --pool-per-group 3000`): dry run na 4 miesiącach
z obciętymi kontrolami trwał ~25 s, ale kontrole rosną z liczbą transakcji
RAZY liczba powtórzeń, więc ekstrapolacja z niego jest bezwartościowa.
Potem bramka 1.

**5. Zostaje kontrola §10.2 nr 10** (rozkład zerowy per kohorta — w dużej
części czeka na kohortę B), **#9 dla kohorty B** i skrypty bramek 1–5.
Z tego bez nowych danych da się zrobić `scripts/gate1.py`: kryterium bramki 1
brzmi „kontrola losowa daje dodatnie expectancy = STOP", a sama kontrola już
istnieje (`src/validation/controls.py`, `gate0.run_random_control`). Wzorzec:
`scripts/gate0.py` — `preflight()` i `require_fresh_bars()` PRZED `start_run`,
`kind="control"`, raport `runs/<id>/gate1.md`.

Czego NIE robić: kohorty B (bramka 2 może zakończyć projekt), optymalizacji
`run_v1a` (nie wiadomo jeszcze, czy jest za wolny), uruchamiania V1a przed
zamknięciem bramki 0.

---

## Uwaga do `trials.jsonl`

Pierwszy wpis (`20260919T134506Z-c4710e`) powstał przed ADR-029 i nie ma pola
`kind`, więc `n_trials()` liczy go jako próbę strategii (N = 1), choć był
kontrolą. Zachowawczo — zawyża N, nie zaniża. `scripts/gate0.py` deklaruje
już `kind="control"`.
