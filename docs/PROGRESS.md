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

**1. 237 transakcji „bez wyniku" to ostatni bar
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

To NIE jest luka w regułach. Warunek `9_friday` („piątek po 15:00 NY",
`config/v1_baseline.yaml:357`, `src/strategy/v1a.py:161`) obejmuje wszystkie
te decyzje — wypadają o 17:00–18:00 czasu NY. Widać je w bramce 0 tylko
dlatego, że kontrola losowa świadomie NIE stosuje warunków NO TRADE: testuje
symulator, nie strategię, więc losuje też z barów, których V1a nigdy nie
zagra. Dla bramki 0 to kierunek zachowawczy. **Nowy ADR niepotrzebny.**

Metoda na przyszłość: `evaluate.memo` (`src/validation/gate0.py:114`) trzyma
transakcje bez etykiety jako wartości `None`, więc listy NIE trzeba odtwarzać
przez powtórzenie losowania. UWAGA: kolumna „luki" w raporcie bramki 0 to
`gap_share` (`src/validation/gate0.py:244`) — udział transakcji domkniętych
**luką cenową** przez SL/TP, a NIE udział transakcji bez wyniku.

**2. 3 godziny bez danych — ADR-045, zaimplementowane.**
Pomiar otoczenia pokazał, że nie są jednym zjawiskiem: **2016-09-02 18:00**
(piątek) to prawdziwa dziura wewnątrz dnia handlowego (~1–2 h, 17:00 też
zapadnięte), a **2017-12-24 22:00** i **2019-05-26 22:00** to opóźnione
otwarcie tygodnia — cały blok 18:00–22:00 pusty, dane wracają o 23:00.
Wszystkie 18 plików (3 × 6 par) ma 0 bajtów, w manifeście `status: "empty"`,
więc odczyt musi pochodzić z otoczenia, nie z pliku.

ADR-045: jawna lista `data.quality.accepted_outages` (godzina + powód +
dowód + data), `passes_gate_0()` nie blokuje na pozycjach z listy, raport
je nadal drukuje ze śladem akceptacji. Detektor NIE jest osłabiany — żadnej
ogólnej reguły „pusto przy weekendzie jest OK", bo ukryłaby awarię
w poniedziałkowy poranek.

Kod w `src/data/quality.py` (`AcceptedOutage`, `accepted_outages_from()`,
`partition_outages()`), podpięty w `scripts/gate0.py` i `scripts/build_bars.py`.
`build_bars.py --report-only` przelicza raport jakości bez przebudowy barów.
8 nowych testów, wszystkie na syntetyku; sprawdzone czterema mutacjami kodu,
że faktycznie upadają (m.in. „lista akceptuje wszystko" i „akceptacja usuwa
godzinę z detekcji"). Pozycja listy niedopasowana do żadnej wykrytej godziny
nie blokuje, ale jest drukowana jako ostrzeżenie — literówka w dacie nie
może zniknąć po cichu.

---

## Co dalej — kolejność

**1. Powtórzenie pomiaru niedzielnych kikutów** na 2015–2021
(`reports/atr_sunday_stub.md` jest z 2015-01…2016-04). Weryfikacja ADR-041
na pełnym zakresie, bez wpisu do `trials.jsonl`.

**2. `scripts/run_v1a.py` BEZ `--dry-run`** — bramka 0 jest zamknięta, więc
to jest odblokowane. **Ale to PRAWDZIWA próba**: dokłada 7 do N w DSR
i do limitu 50 prób, nieodwracalnie. Uruchamiać raz i tylko za wyraźną zgodą
użytkownika. Wcześniej zmierzyć czas dry runem na pełnym roku z prawdziwymi
kontrolami
(`--control-reps 200 --pool-per-group 3000`): dry run na 4 miesiącach
z obciętymi kontrolami trwał ~25 s, ale kontrole rosną z liczbą transakcji
RAZY liczba powtórzeń, więc ekstrapolacja z niego jest bezwartościowa.
Potem bramka 1.

**3. Zostaje kontrola §10.2 nr 10** (rozkład zerowy per kohorta — w dużej
części czeka na kohortę B), **#9 dla kohorty B** i skrypty bramek 1–5.
Z tego bez nowych danych da się zrobić `scripts/gate1.py`: kryterium bramki 1
brzmi „kontrola losowa daje dodatnie expectancy = STOP", a sama kontrola już
istnieje (`src/validation/controls.py`, `gate0.run_random_control`). Wzorzec:
`scripts/gate0.py` — `preflight()` i `require_fresh_bars()` PRZED `start_run`,
`kind="control"`, raport `runs/<id>/gate1.md`.

Czego NIE robić: kohorty B (bramka 2 może zakończyć projekt), optymalizacji
`run_v1a` (nie wiadomo jeszcze, czy jest za wolny), uruchamiania V1a bez
zgody użytkownika (patrz punkt 2), dotykania hold-outu 2024–2025.

---

## Uwaga do `trials.jsonl`

Pierwszy wpis (`20260919T134506Z-c4710e`) powstał przed ADR-029 i nie ma pola
`kind`, więc `n_trials()` liczy go jako próbę strategii (N = 1), choć był
kontrolą. Zachowawczo — zawyża N, nie zaniża. `scripts/gate0.py` deklaruje
już `kind="control"`.
