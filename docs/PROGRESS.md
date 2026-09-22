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

## BRAMKA 2 NIE PRZECHODZI — PROJEKT ZAKOŃCZONY (2026-09-22)

Run **`20260922T200750Z-b57ab5`**, `scripts/run_v1a.py` bez flag, 2016-01-01 →
2021-12-31, sześć par, 889 transakcji baseline (172 efektywne, nakładanie 96%).
Raport `runs/20260922T200750Z-b57ab5/v1a.md`. **Drzewo czyste, `git_commit` =
`4004211`**, `frozen_sha256` = `79ca85df…`, `kind="strategy"`, `n_variants=7`
— **N w DSR: 1 → 8**, zużyte 8 z 50 prób. Czas 718 s.

**Wszystkie 12 kryteriów na czerwono.** Expectancy netto **−0,0560 R**
CI95 **[−0,1225; +0,0119]** wobec wymaganych **≥ +0,10 R** — próg leży poza
przedziałem. t = −1,62 · DSR = 0,174 (N = 8) · PBO = 0,612 · 1 z 6 par
dodatnia · 0 z 3 podokresów dodatnich · ujemne przy koszcie 1×, 2× i 3×
· koszyk §12 i carry-only niepobite.

**Kontrola #1 rozstrzyga sprawę:** p = **0,8010** przy progu 0,05 (ADR-048).
Mediana losowych wejść **−0,0288** wobec strategii **−0,0560** — losowy wybór
momentu tracił **dwa razy mniej**. 80% z 200 losowych przebiegów wypadło tak
samo dobrze albo lepiej. Kontrola #2 to potwierdza: p = 0,8109.

Ujemne są **wszystkie siedem wariantów** siatki (−0,0303 … −0,0560), więc nie
ma czego stroić, i **wszystkie trzy podokresy**, więc nie chodzi o epokę.

**Kontrola #3 zapaliła się nietypowo:** cechy starsze o bar dały −0,0268 R,
czyli LEPIEJ niż baseline („ROŚNIE — sprawdź off-by-one"). Nie zmienia to
wniosku. Różnica 0,029 R mieści się w szumie (połowa CI = 0,067 R), a wyciek
z przyszłości czyni wynik LEPSZYM niż rzeczywistość — nie istnieje scenariusz,
w którym ta anomalia ukrywa przewagę. Czytanie właściwe: cechy nie niosą
informacji, więc nie ma znaczenia, z którego bara pochodzi szum.

**Wniosek: H₁ ODRZUCONE, H₀ zostaje w mocy.** Zgodnie z §15 i `CLAUDE.md`:
NIE dodajemy macro, ML ani reżimów, NIE stroimy parametrów. Hold-out
2024–2025 zostaje zapieczętowany na stałe. Kohorta B nie jest uruchamiana.

Wynikowi można wierzyć, bo bramka 0 wykazała, że aparatura mierzy uczciwie,
a bramka 1 — że losowe wejścia tracą tyle, ile kosztują. Gdyby przewaga
istniała, ten sam przyrząd by ją pokazał.

---

## Stan (2026-09-22) — bramki 0 i 1 ZAMKNIĘTE, obie PRZECHODZĄ

**PIECZĘĆ ZMIENIONA: `frozen_sha256` = `79ca85df…`** (ADR-048, unieważniła
`b77d0b69…`). Bramki 0 i 1 przemierzone pod nową pieczęcią — patrz niżej.
Przebieg z niezgodnym hashem jest nieważny.

**Kod:** 556 testów, wszystkie przechodzą. Inwentarz w archiwum. Nigdy nie
powstały: kontrola §10.2 nr 10, kohorta B i skrypty bramek 3–5 — bramka 2
zakończyła projekt, zanim stały się potrzebne.

**Werdykt bramki 2 liczy sam `run_v1a.py`** przez `assess()` w
`strategy/runner.py`: osiem progów §10.3 plus płaskowyż i kontrole #1, #4,
#5 jako `Check`i — dwanaście łącznie. Osobny skrypt bramki 2 nie był
potrzebny. Pole w rejestrze nazywa się `passed_computed_criteria`, nie
`passed_gate_2`, bo kontrola §10.2 nr 10 wymaga kohorty B i nie została
policzona. Przy dwunastu kryteriach na czerwono nie zmienia to wniosku.

**Kontrola #1 została wpięta do werdyktu PRZED przebiegiem** (ADR-048).
Próg istniał wcześniej w `gates.gate_2.also_requires` prozą („p < 0.05"),
pod pieczęcią od prerejestracji — ADR-048 dołożył tylko jego postać
maszynową. Wartość się nie zmieniła.

**Dane.** Bary H1 i M1 dla **2015–2021**, sześć par kohorty A, segment
RESEARCH kompletny w 100%. Pobieranie ticków zakończone 2026-09-22.
Partycje 2022+ świadomie nie zbudowane; hold-outu pilnuje `load_h1`/`load_m1`
(`SealedHoldoutError`), nie brak plików. Raport jakości
(`reports/data_quality.md`): **PRZECHODZI**, luki 0,01% na parę.
Trzy godziny bez ticków u wszystkich par naraz — wykryte i zaakceptowane
jawnie wg ADR-045. Szczegóły: `docs/PROGRESS_ARCHIVE.md`.

---

## Bramka 0 — ZAMKNIĘTA, PRZECHODZI (2026-09-21)

Werdykt obowiązujący: run **`20260922T192347Z-2125e5`**, `gate0.py --end
2021-12-31`, 2015-01-01 → 2021-12-31, bez `--allow-stale-bars`, ziarno 0,
20 × 100 wejść na (para, kierunek). Raport
`runs/20260922T192347Z-2125e5/gate0.md`. **Drzewo czyste, `git_commit` =
`797bd07`**, `frozen_sha256` = `79ca85df…`. Wpis w `trials.jsonl` jako
`kind="control"` — N w DSR nadal 1.

Przemierzone po ADR-048, bo zmiana pieczęci unieważniła poprzedni przebieg
`20260921T161726Z-1e142d` (hash `b77d0b69…`, commit `4df53af`). Werdykt się
nie zmienił. Liczby drgnęły w czwartym miejscu (netto było −0,0110 R) —
poprzedni przebieg szedł na barach USDCAD sprzed przebudowy z 2026-09-22,
nie na innym kodzie. ADR-048 nie dotyka niczego, co liczy bramka 0.

Wszystkie kryteria ADR-025 przeszły. Expectancy netto **−0,0106 R**
[−0,0289; +0,0081], przed kosztem **+0,0010 R** [−0,0174; +0,0195], średni
koszt **0,0116 R**, ujemne przy koszcie 1×, 2× i 3×. Treść bramki 0:
aparatura mierzy uczciwie, symulator nie pokazuje wycieku z przyszłości.

Szczegóły kryteriów, wcześniejsze przebiegi, rozbicie kosztu po latach
i dwie kwestie rozstrzygnięte przy zamykaniu bramki (237 transakcji „bez
wyniku" → warunek `9_friday`; 3 godziny bez danych → ADR-045):
`docs/PROGRESS_ARCHIVE.md`.

---

## Bramka 1 — ZAMKNIĘTA, PRZECHODZI (2026-09-22)

Werdykt obowiązujący: run **`20260922T193136Z-1d27da`**, `scripts/gate1.py
--reps 200 --n-per-side 100`, 2015-01-01 → 2021-12-31, sześć par, ziarno 0.
Raport `runs/20260922T193136Z-1d27da/gate1.md`. **Drzewo czyste,
`git_commit` = `797bd07`**, `frozen_sha256` = `79ca85df…`, `kind="control"` —
**N w DSR nadal 1**.

Przemierzone po ADR-048 (pieczęć unieważniła run `20260922T182800Z-8f81f4`
na hashu `b77d0b69…`). Liczby wyszły **identyczne co do czwartego miejsca** —
to samo ziarno, te same dane, a ADR-048 nie zmienia żadnej wartości, którą
bramka 1 liczy.

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

## Co dalej — nic

**Nic.** Bramka 2 nie przeszła, więc projekt jest zakończony — to była
bramka główna i jej porażka jest odpowiedzią na pytanie, które projekt
zadawał. Bramki 3, 4 i 5 nie mają się do czego odnosić.

Czego NIE robić, gdyby ktoś wracał do tego repozytorium:

- **NIE stroić parametrów V1a.** Wszystkie 7 wariantów ujemne — nie ma
  ustawienia, przy którym reguła zarabia.
- **NIE dodawać macro, ML ani reżimów.** §15 zabrania tego wprost i to
  zobowiązanie zostało podpisane przed pierwszym backtestem.
- **NIE uruchamiać kohorty B** ani §15 „warunku awaryjnego" bez świadomej
  decyzji człowieka zapisanej jako ADR.
- **NIE odpieczętowywać hold-outu 2024–2025.** Służył bramce 4, do której
  projekt nie dotarł. Zostaje nietknięty.

Nowa hipoteza ekonomiczna to nowy projekt, nowa prerejestracja i nowy
licznik prób — nie kontynuacja tego.

---

## Uwaga do `trials.jsonl`

**Końcowe N = 8** z limitu 50: jeden wpis sprzed ADR-029 plus siedem
wariantów przebiegu bramki 2. Wszystkie przebiegi bramek 0 i 1 to
`kind="control"` i do N się nie liczą (ADR-029 pkt 4).

Pierwszy wpis (`20260919T134506Z-c4710e`) powstał przed ADR-029 i nie ma pola
`kind`, więc `n_trials()` liczy go jako próbę strategii, choć był kontrolą.
Zachowawczo — zawyża N, nie zaniża. Miało to znaczenie dla DSR bramki 2:
gdyby liczyć uczciwie, N wynosiłoby 7, a poprzeczka SR*₀ byłaby minimalnie
niższa. Przy DSR = 0,174 wobec progu 0,95 nie zmienia to niczego.
