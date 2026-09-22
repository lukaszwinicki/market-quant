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

## Stan (2026-09-22) — bramki 0 i 1 ZAMKNIĘTE, obie PRZECHODZĄ

**Kod:** 551 testów. Inwentarz w archiwum. Brakuje: kontrola §10.2 nr 10,
skrypty bramek **3–5**, kohorta B, `#9` dla kohorty B.

**Bramka 2 NIE potrzebuje osobnego skryptu** — jej werdykt liczy sam
`run_v1a.py` przez `assess()` w `strategy/runner.py`: wszystkie osiem progów
z §10.3 plus kontrole #4 i #5 jako `Check`i, raport `v1a.md`, kod wyjścia
0/1. Wcześniejsza notatka „brakuje skryptów bramek 2–5" myliła.

**Ale werdykt jest NIEPEŁNY wobec §15** i pole w rejestrze nazywa się
uczciwie `passed_computed_criteria`, nie `passed_gate_2`. §15 wymaga, żeby
V1a „biło istotnie kontrolę losową"; kontrole §10.2 (w tym #1) trafiają do
raportu jako p-wartości, ale **żadna z nich nie jest `Check`iem** i nie
wchodzi do `passed`. Progu dla p kontroli #1 nie ma ani w konfiguracji,
ani w żadnym ADR. Do rozstrzygnięcia PRZED przebiegiem V1a — po zobaczeniu
p byłaby to decyzja podjęta pod wpływem wyniku.

**Dane.** Bary H1 i M1 zbudowane dla **2015–2021**, sześć par kohorty A
(EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, EURJPY). Partycje 2022+ świadomie
NIE zbudowane — nie są do niczego potrzebne przed bramką 4, a hold-outu
pilnuje `load_h1`/`load_m1` (`SealedHoldoutError`), nie brak plików.

**Pobieranie ticków ZAKOŃCZONE** (2026-09-22 14:52, 100%, dane do
2026-09-21). Downloader już nie działa — notatka „leci w tle" jest nieaktualna.
Front sprawdzać komendą, nie z notatek:

```bash
for p in EURUSD GBPUSD USDJPY AUDUSD USDCAD EURJPY; do \
  printf "%-7s " $p; find data/raw/dukascopy/$p -type f | sed "s|.*$p/||" | sort | tail -1; done
```

Godzin `failed`: **13** po deduplikacji (manifest jest append-only, liczy się
ostatni status pary godzina+symbol). **Żadna nie leży w RESEARCH ani
w `validation`** — 3 w hold-oucie, 10 po nim. Segment badawczy jest kompletny
w 100%. `download_ticks.py --retry-failed` dotyczyłby więc wyłącznie
zapieczętowanego hold-outu; przed bramką 4 nie ma po co go uruchamiać.

Ostatnia brakująca godzina segmentu badawczego (USDCAD 2021-10-05 02:00)
dociągnęła się 2026-09-22 rano, więc bary USDCAD 2021 zostały przebudowane
(6240/6240 godzin cache) — luka tej pary spadła z 6 do 5 barów z 43 634.
Złapała to blokada `require_fresh_bars()` przy pierwszej próbie bramki 1:
działa i warto jej ufać.

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

Wszystkie kryteria ADR-025 przeszły. Expectancy netto **−0,0110 R**
[−0,0294; +0,0076], średni koszt **0,01156 R**, ujemne przy koszcie 1×, 2×
i 3×. Treść bramki 0: aparatura mierzy uczciwie, symulator nie pokazuje
wycieku z przyszłości.

Szczegóły kryteriów, wcześniejsze przebiegi, rozbicie kosztu po latach
i dwie kwestie rozstrzygnięte przy zamykaniu bramki (237 transakcji „bez
wyniku" → warunek `9_friday`; 3 godziny bez danych → ADR-045):
`docs/PROGRESS_ARCHIVE.md`.

---

## Niedzielne kikuty — jedno ustalenie, które nadal obowiązuje

Margines progu `min_h1_bars` to **11–20**, nie 9–20 jak podaje ADR-041
(„na tej próbie") — na 7 latach są trzy Boże Narodzenia po 10 barów. Próg 12
zostaje w środku przepaści, ale **nie wolno zejść poniżej 11**, powołując się
na ADR-041. Cały pomiar: `docs/PROGRESS_ARCHIVE.md`.

---

## Bramka 1 — ZAMKNIĘTA, PRZECHODZI (2026-09-22)

Werdykt: run **`20260922T182800Z-8f81f4`**, `scripts/gate1.py --reps 200
--n-per-side 100`, 2015-01-01 → 2021-12-31, sześć par, ziarno 0.
Raport `runs/20260922T182800Z-8f81f4/gate1.md`. **Drzewo czyste,
`git_commit` = `1609183`**, `frozen_sha256` = `b77d0b69…`, `kind="control"` —
**N w DSR nadal 1**.

Wszystkie trzy warunki ADR-046 przeszły, i to nie na styk: expectancy netto
**−0,0261 R**, CI95 **[−0,0402; −0,0122]** — **całe CI leży pod zerem**, więc
nie ma mowy o stanie `NIEROZSTRZYGNIĘTE`. Średni koszt 0,0116 R, finansowanie
+0,0107 R. Bez finansowania −0,0154 R (to liczba porównywalna z bramką 0,
która finansowania w ogóle nie liczy — tam było −0,0110 R).

Produkt bramki: `null.parquet`, 200 powtórzeń × ~1188 transakcji,
SD 0,0273 R, 17% powtórzeń dodatnich. **To nie jest rozkład zerowy bramki 2** —
tam kontrola musi mieć liczebność strategii i liczy ją sam `run_v1a`.

Treść wyniku: losowe wejścia tracą mniej więcej tyle, ile kosztują, a strata
jest istotna. Nie ma śladu przewagi tam, gdzie żadnej być nie może.

---

## Ile potrwa przebieg V1a — ZMIERZONE (2026-09-21)

**Ok. 15 minut na pełnym segmencie RESEARCH, z zapasem 10–25**, RAM 3–4 GB.
Zmierzone dry runem na roku 2016 (3 min 17 s) — kontrola #2 nie rośnie
z zakresem, bo `--pool-per-group 3000` tnie ją do 12 × 3000. Pełne rozbicie
na fazy: `docs/PROGRESS_ARCHIVE.md`.

**Wniosek: `run_v1a.py` NIE wymaga optymalizacji.** To minuty, nie godziny —
nie robić kolejnych dry runów „dla pewności".

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

## Stopy procentowe — dziura znaleziona i zamknięta (ADR-047, 2026-09-22)

Pierwszy przebieg bramki 1 padł po 200 powtórzeniach: `brak stopy overnight
dla USD na 2015-01-22`. Szereg z FRED zaczynał się dokładnie tam, gdzie split,
a `rate_on()` czyta miesiąc wcześniejszy. Pełna diagnoza: **ADR-047**.

Naprawione: dociągnięty 2014 (teraz domyślny zakres `fetch_rates.py`) i nowe
`require_coverage_for_decisions()` w `gate1.py` oraz w `preflight()` runnera.
**Żadna wartość 2015–2025 się nie zmieniła** — porównane wiersz po wierszu
wobec kopii sprzed pobrania: 442 dołożone, zero zmienionych, zero usuniętych.

`run_v1a.py` tej dziury **nie dotykał** (pierwsza decyzja 2016-01-01). Gdyby
dotykał, byłoby drogo: przebieg `kind="strategy"` liczy się do N także wtedy,
gdy kończy się błędem (ADR-029).

W `trials.jsonl` został wpis przerwanego przebiegu `20260922T180657Z-3acbf1`
(`kind="control"`, `status="error"`). Rejestr jest append-only, N to nie rusza.

---

## Co dalej — kolejność

**1. `scripts/run_v1a.py` BEZ `--dry-run`** — odblokowane, bramki 0 i 1
zamknięte. **To PRAWDZIWA próba**: dokłada 7 do N w DSR i do limitu 50 prób,
nieodwracalnie. Uruchamiać raz i tylko za wyraźną zgodą użytkownika.
Czas przebiegu jest już zmierzony (~15 min, niżej), więc nie ma po co robić
kolejnego dry runu.

**2. Zostaje** kontrola §10.2 nr 10 (rozkład zerowy per kohorta — w dużej
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
