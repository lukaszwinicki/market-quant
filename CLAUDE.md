# market-quant

Aparatura pomiarowa do rozstrzygnięcia jednej hipotezy — **nie jest botem
tradingowym ani platformą**.

> **H₁:** Istnieje prosta, deterministyczna strategia swingowa na 6 głównych
> parach FX, o expectancy istotnie większym od zera po realistycznych kosztach
> i po korekcie na liczbę przeprowadzonych prób.
>
> **H₀ (domyślna): takiej strategii nie ma.** Ciężar dowodu po stronie H₁,
> prior niski.

Sukcesem jest **liczba z przedziałem ufności**, nie działający system. Wynik
„H₁ odrzucone" jest pełnoprawnym sukcesem.

---

## Gdzie jest prawda

| Plik | Rola |
|---|---|
| `docs/PROJECT_SPEC.md` | Obowiązująca specyfikacja. W razie sprzeczności — wygrywa |
| `docs/DECISIONS.md` | Log decyzji (ADR). **Wpisy są niezmienne**; zmiana = nowy ADR |
| `config/v1_baseline.yaml` | Prerejestrowane parametry |
| `docs/AUDIT_REPORT.md` | Uzasadnienia; dlaczego rzeczy zostały usunięte |
| `docs/research/` | Materiał historyczny, **nieobowiązujący** |

Historia rozmów nie jest źródłem prawdy. Jeśli coś ma przetrwać — trafia do
`DECISIONS.md` jako ADR.

---

## Reguły, których nie wolno złamać

**Konfiguracja jest zamrożona.** Zmiana czegokolwiek z `frozen: true`
unieważnia wszystkie dotychczasowe wyniki i wymaga nowego ADR. Po zobaczeniu
pierwszego wyniku backtestu plik jest skażony — każda późniejsza zmiana jest
decyzją podjętą pod wpływem wyniku.

**Żadne wejście do backtestu nie pochodzi od LLM.** Model, którego dane
treningowe obejmują okres testu, zna wynik. Tego nie da się naprawić promptem
ani zmierzyć. Dotyczy scoringu tekstu, klasyfikacji zdarzeń, generowania cech.

**Każda próba jest logowana.** `trials.jsonl`, zapis automatyczny przez harness.
Każda iteracja wspomagana LLM jest próbą. Bez prawdziwego licznika Deflated
Sharpe Ratio nic nie znaczy.

**Hold-out 2024-2025 jest zapieczętowany** do bramki 4. Jedno uruchomienie,
potem projekt się kończy — go albo no-go.

**Bid i ask osobno, nigdzie mid.** Kolejność barier rozstrzygana tickowo albo
pesymistycznie, nigdy optymistycznie.

**Etykieta bara = początek przedziału.** Bar 09:00 (H1) zamyka się o 10:00.
Decyzja o 10:00 może użyć wyłącznie bara 09:00. Używać `last_closed_bar()`,
nigdy ręcznej arytmetyki na znacznikach czasu.

Pełna checklista leakage'u: `PROJECT_SPEC.md` §10.4.

---

## Bramki

| | Tydzień | Kryterium |
|---|---|---|
| 0 | 4 | Strategia losowa daje expectancy ≈ −koszt |
| 1 | 5 | Rozkład zerowy z kontroli losowej |
| **2** | **8** | **Główna.** Expectancy ≥ +0,10 R, t ≥ 2, DSR ≥ 0, PBO ≤ 0,30 |
| 3 | 10 | Każdy komponent ≥ +0,03 R albo usunięty |
| 4 | 11 | Zapieczętowany hold-out, jedno uruchomienie |
| 5 | 15 | Replikacja na kohorcie B |

**Porażka bramki 2 oznacza koniec.** Nie dodajemy macro, ML ani reżimów.
Nie stroimy parametrów.

---

## Praca z kodem

```bash
.venv/bin/python -m pytest tests/ -q          # testy
.venv/bin/python scripts/download_ticks.py    # pobieranie (wznawialne)
```

Środowisko: `.venv`, Python 3.12, polars + numpy + scikit-learn + pyarrow.
Dane w `data/` — ignorowane przez gita, odtwarzalne z downloadera.

**Testy symulatora egzekucji i cech pisz na danych syntetycznych.** Na
prawdziwych tickach nie znasz poprawnej odpowiedzi, więc nie wiesz, czy kod
działa — widzisz tylko, że coś zwraca.

Zakazane w V1: xgboost, lightgbm, HMM, PostgreSQL, Redis, FastAPI, React,
Docker, MCP, Discord, TA-Lib. Pełna lista w `config/v1_baseline.yaml`.

---

## Commity

Po angielsku, sam temat, bez body — chyba że „dlaczego" nie widać z diffa
(np. zmiana wartości `frozen: true`: wtedy nazwij ADR i unieważniony hash).

Prefiksy: `docs:` `config:` `feat:` `fix:` `test:` `chore:`

Przed commitem: `git add -A --dry-run`. Wpis `data/` w `.gitignore` bez
ukośnika ignorował kiedyś `src/data/` — czyli kod.

---

## Stan

Bramka 0 w toku. Pobieranie ticków Dukascopy (kohorta A, 2015 → dziś) leci
w tle, wznawialne; 2026-09-19 było na 2016-04 (~11%). 18 godzin `failed`
do dociągnięcia na końcu: `download_ticks.py --retry-failed`.

Gotowe (194 testy):
- `src/data/` — downloader, resampling `tick → M1 → H1`, raport jakości
  (święta 25.12/1.01 rozpoznawane, nie liczone jako awarie)
- `scripts/build_bars.py` — Parquet `data/bars/{m1,h1}/symbol=/year=`,
  raport `reports/data_quality.md` (2015–16: bramka 0 przechodzi)
- `src/execution/simulator.py` — fill bid/ask, luki, pesymistyczna
  kolejność barier, podłoga kosztu (ADR-024). Naprawione: spread był
  liczony dwa razy (w cenach fillów i w `cost`); teraz od `gross`
  odejmowana jest tylko dopłata do podłogi, `cost` = max(spread, podłoga)
- `decision_time_for_bar()` w `resample.py` — odwrotność `last_closed_bar()`
- `src/features/technical.py` — 6 cech, test kauzalności
- `src/labels/triple_barrier.py` — etykiety z `t1`, `overlap_fraction`,
  `effective_sample_size`
- `src/validation/` — `cpcv.py` (grupy = całe dni, purge po `t1` +
  podłoga 10 dni rob., embargo 5 dni od ostatniego `t1` testu),
  `dsr.py` (PSR/DSR, `n_obs` = efektywne n), `pbo.py` (CSCV, N ≥ 2),
  `controls.py` (losowe wejścia dopasowane per (para, kierunek), rozkład
  zerowy, p-value), `bootstrap.py` (bloki 20 dni roboczych, weekend →
  poniedziałek). Test martyngałowy: losowe wejścia dają E[R] = −koszt
- `src/harness/registry.py` — `start_run(purpose, params)`: katalog
  `runs/<ts>-<hex>/` (kopia configu, `run.json`, `metrics.json`,
  `diff.patch` gdy drzewo brudne), wpis `start` do `trials.jsonl` PRZED
  kodem badawczym, `end` w `finally` (ok/error/interrupted). `n_trials()`
  = liczba startów, bez filtrów. Hash commita, sha256 configu i osobno
  sekcji `frozen: true`, commit zamrożenia. `trials.jsonl` nie liczy się
  jako brudne drzewo
- `src/harness/market.py` — `load_m1(symbol, start, end, cfg)` czyta tylko
  potrzebne lata; zakres dotykający hold-outu → `SealedHoldoutError`
  (wyjście: `unseal=True`, bramka 4). `cost_model_for()` z configu
  (EURJPY = cross, podłoga 2,5). `load_h1()` — ta sama pieczęć
- `slice_window()` w `resample.py` (search_sorted); `label_events` podaje
  symulatorowi tylko okno [decyzja, bariera czasowa]
- `src/validation/gate0.py` + `scripts/gate0.py` — bramka 0 na harnessie:
  losowe wejścia zrównoważone long/short per para, memo transakcji
  (deterministyczne w (symbol, ts, kierunek)). Kryteria wg ADR-025:
  a) rachunek kosztu per transakcja (`cost_r = max(spread_r, podłoga)`,
  `r = gross_r − dopłata`; etykiety niosą `gross_r`, `spread_r`),
  b) test martyngałowy uruchamiany przez skrypt, c) CI95 przed kosztem
  ∋ 0 i połowa CI ≤ 0,05 R (szerszy = NIEROZSTRZYGNIĘTE). Plus spread
  z ticków i raport luk H1. Wynik w `runs/<id>/gate0.md` + `labels.parquet`
- Symulator, ADR-026: bariera czasowa w czasie zamkniętego rynku →
  `TIME_BARRIER` po ostatnim barze (`market_closed_between`). Zamknięcie:
  weekend, 25.12, 1.01; ogon dnia przed nim tylko od 20:00 UTC w piątek
  i od 17:00 w wigilię/sylwestra — wcześniejsze urwanie danych to awaria
  (`NO_DATA`). Progi godzinowe to doprecyzowanie implementacyjne ADR-026

Bramka 0 — pierwszy przebieg, NIEAKTUALNY po ADR-026 (`20260919T134506Z-c4710e`, pierwszy wpis
w `trials.jsonl`, drzewo brudne → `diff.patch`): 2015-01 → 2016-04-28,
6 par, 20 × 100 wejść na (para, kierunek), 23 719 transakcji, 11 min.
PRZECHODZI: netto −0,0010 R [−0,037; +0,034], brutto +0,0096 R
[−0,027; +0,045], koszt 0,0106 R, 0 naruszeń podłogi.
Moc: połowa CI = 3,4× koszt — na prawdziwych danych test NIE odróżnia
kosztu policzonego od pominiętego; to robi test martyngałowy + podłoga
per transakcja. Wykrywa tylko duży bias brutto (look-ahead, kolejność barier).

Do rozstrzygnięcia przez użytkownika (ADR przed bramką 2):
- Próg `deflated_sharpe_min: 0.0` jest pusty — DSR to prawdopodobieństwo
  ∈ [0,1]. Do wyboru: DSR ≥ 0,5 (≡ SR̂ ≥ SR*₀) albo 0,95 (konwencja
  z literatury). Pole jest `frozen: true`.
- Spec §10.1: 6/2 daje 15 **podziałów**, ale 5 **ścieżek**, nie 15.
- PBO wymaga ≥ 2 wariantów — siatka wrażliwości wokół {55, 2.0, 4.0}
  musi zostać prerejestrowana przed pierwszym uruchomieniem.

Ustalenia z danych:
- Rozgrzewka: `vol_pct_252` wymaga 252 dni → pierwszy handlowalny bar
  ~rok po starcie danych (2016-01). Rok 2015 to tylko historia dla cech.
- Nakładanie etykiet ~99% przy horyzoncie 10 dni: efektywne n jest
  o rząd wielkości mniejsze od nominalnego. Do testów istotności
  używać `effective_sample_size`, nie liczby wierszy.
- Spready 2015 (mediana `spread_close`): EURUSD 0,3, USDJPY 0,4,
  pozostałe 0,8–1,2 pipsa. Podłoga 1,5 / 2,5 pipsa zwykle wiąże.
- `data/raw/dukascopy/EURUSD/2019,2020` — 130 godzin próbek z testów
  dekodera; poprawne, downloader je pominie.

- Wydajność: po wycięciu okien ~30 ms/transakcję (EURUSD 2016). Teraz
  wąskim gardłem jest pętla Pythona po ~14k barach M1 w `_find_exit`.
  1000 transakcji × 200 powtórzeń ≈ 100 min — jeśli za wolno,
  wektoryzować wyszukiwanie pierwszego dotknięcia bariery (numpy).
- Transakcje z końca 2023 z horyzontem w 2024 rozstrzygają się na cenach
  hold-outu — `load_m1` je zablokuje. Do rozstrzygnięcia przy walidacji.
- Do decyzji (ADR): czy przebiegi kontroli/infrastruktury liczą się
  do N w DSR. Rejestr zapisuje `purpose`, `n_trials()` liczy wszystko.

Następne (gdy pobieranie dojdzie do końca 2021): `download_ticks.py
--retry-failed`, `build_bars.py`, potem `scripts/gate0.py` — przebieg
zamykający bramkę 0 (nowy symulator, kryteria ADR-025; kolejna próba
w `trials.jsonl`). Sprawdzić w raporcie: liczbę „bez wyniku" (po ADR-026
powinna spaść z ~1,2% prawie do zera) i połowę CI ≤ 0,05 R. Ok. 32 ms na
unikalną transakcję — przy 7 latach rozważyć wektoryzację `_find_exit`.
Potem bramka 1: rozkład zerowy dla sygnału V1a.
