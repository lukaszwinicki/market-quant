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
w tle, wznawialne; 2026-09-20 14:48 UTC front na **2020-03-23** (~47%
zakresu do 2025-12-31). Zmierzone tempo ~60–90 dni kalendarza na godzinę,
niższe w latach o dużym obrocie. ETA: koniec 2021 (granica segmentu
RESEARCH) ~10 h, koniec 2023 ~22 h, dziś ~38 h. **77** godzin `failed`
do dociągnięcia na końcu (liczba rośnie w trakcie — sprawdzać
w `data/raw/manifest.jsonl`, nie ufać tej notatce):
`download_ticks.py --retry-failed`.

Gotowe (431 testów):
- `src/data/` — downloader, resampling `tick → M1 → H1`, raport jakości
  (święta 25.12/1.01 rozpoznawane, nie liczone jako awarie)
- `scripts/build_bars.py` — Parquet `data/bars/{m1,h1}/symbol=/year=`,
  raport `reports/data_quality.md` (2015–16: bramka 0 przechodzi)
- `src/execution/simulator.py` — fill bid/ask, luki, pesymistyczna
  kolejność barier, podłoga kosztu (ADR-024). Naprawione: spread był
  liczony dwa razy (w cenach fillów i w `cost`); teraz od `gross`
  odejmowana jest tylko dopłata do podłogi, `cost` = max(spread, podłoga)
- `decision_time_for_bar()` w `resample.py` — odwrotność `last_closed_bar()`
- `src/features/technical.py` — 6 cech, test kauzalności;
  `compute_features(h1, donchian=55)` → kolumna `donch_pos_{n}` (siatka)
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
  = N wg ADR-029: suma `n_variants` po przebiegach `kind="strategy"`
  (wpisy bez `kind` = strategy); `n_runs()` = wszystkie starty.
  `kind` ∈ {strategy, control, infra} obowiązkowe. Hash commita, sha256 configu i osobno
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

- `src/data/calendar.py` — schemat kalendarza (bez wartości), lista
  zamknięta serii HIGH per waluta, `coverage_gaps()` (każda seria w każdym
  roku), `blackout()` (ADR-032: 30 min przed … 120 min po zdarzeniu).
  `scripts/fetch_calendar.py` — cache surowych stron w
  `data/raw/calendar/`, wynik `data/calendar/<źródło>.parquet`, raport
  pokrycia. Źródło `fomc`: 2016–2025, 79 planowanych posiedzeń, godzina
  z komunikatu („For release at 2:00 p.m. EST”), nadzwyczajne pominięte.
  Źródło `fred` (`calendar_fred.py`): daty = pierwsza publikacja okresu
  z ALFRED (`output_type=4`) — 12/rok, GDP 4/rok (advance); serie
  CPIAUCSL, PAYEMS, PCEPI, RSAFS, GDPC1 sprawdzane vs id publikacji.
  Godziny z `config/calendar_times.yaml` — bez `verified: true` seria
  nie daje zdarzeń. Klucz: `FRED_API_KEY` w `.env` (gitignore).
  Źródło `bea` (`calendar_bea.py`): PCE i GDP advance z archiwum bea.gov,
  godzina z nagłówka embarga KAŻDEJ publikacji, daty zgodne z ALFRED co do
  dnia (inaczej błąd). 117 PCE + 40 GDP. PCE: 10 publikacji o 10:00/9:30
  ET zamiast 8:30 — stała godzina byłaby błędna.
  Źródło `bls` (`calendar_bls.py`): CPI i NFP z rocznych kalendarzy
  `bls.gov/schedule/<rok>_sched.htm`, zapisanych RĘCZNIE przez użytkownika
  do `data/raw/calendar/bls/` (bls.gov: 403 dla skryptów). 119 + 119,
  wszystkie 8:30 ET, daty zgodne z ALFRED.
  Źródło `census` (`calendar_census.py`): sprzedaż detaliczna — 2016–2019
  z archiwalnych PDF (`pypdf`, dwa układy nagłówka), 2020+ z rocznych
  kalendarzy wskaźników. 119, wszystkie 8:30 ET, daty zgodne z ALFRED.
  Źródło `ecb` (`calendar_ecb.py`): 8 posiedzeń/rok z konferencją.
  Konferencja — godzina z każdego komunikatu; decyzja — z ecb.pr220627
  (13:45 → 14:15 od 21.07.2022, spójność z konferencją sprawdzana).
  „CET” u EBC = czas lokalny Frankfurtu, potwierdzone na tickach EURUSD 2016.
  Źródło `boc` (`calendar_boc.py`): 80 decyzji. Daty z komunikatów
  `fad-press-release-RRRR-MM-DD`, godzina z rocznego komunikatu
  „…schedule…” („at 09:45 (ET)”; wcześniej 10:00). Godzina dla daty
  z NAJPÓŹNIEJSZEGO harmonogramu, który ją wymienia — 2024 dzieli się
  5 × 10:00 i 3 × 09:45. Każda data harmonogramu musi mieć komunikat.
  Źródło `statcan` (`calendar_statcan.py`): CA_CPI, 120 publikacji.
  Daty z `dai-quo/ssi/homepage/schedule-key_indicators-eng.json`, godzina
  z nagłówka PDF każdej publikacji („Released at 8:30 a.m. Eastern time”),
  data w nagłówku sprawdzana z JSON-em.
  Źródło `boe` (`calendar_boe.py`): 83 posiedzenia MPC 2016–2025. Lista
  przez `POST /_api/Search/RefreshContentPageSearchList`; slug `<miesiąc>-<rok>`
  = planowe (13march-2020 i „special … 19 march 2020” odpadają), data
  z „Published on …”, wymagany czwartek. Godzina 12:00 tylko z konwencji
  → `calendar_times.yaml` (BOE_RATE, `verified: false` — zdarzeń brak).
  Źródło `ons` (`calendar_ons.py`): UK_CPI 119 + UK_LABOUR 119. Kalendarz
  `releasecalendar?keywords=…` ma godzinę KAŻDEJ publikacji (`data-gtm-release-*`);
  9:30 do 2020, potem 7:00. Kalendarz zaczyna się w lutym 2016 — styczeń
  2016 (CPI 19.01, praca 20.01) z biuletynów, godzina z `calendar_times.yaml`
  (ONS_BULLETIN, `verified: false`), stąd 11 zamiast 12 publikacji w 2016.
  Źródło `rba` (`calendar_rba.py`): 104 decyzje (11/rok do 2023, 8 od 2024).
  rba.gov.au daje skryptom 403, więc strony czytane z kopii Wayback —
  harmonogram zapisany PRZED rokiem dowodzi zarazem planowości. Dwa układy:
  tekstowy („media release issued at 2.30 pm” + dni) i od 2024 lista
  z godziną i strefą per posiedzenie. 2018 nie ma zapisu harmonogramu:
  planowość z treści komunikatu („At its meeting today”). Nieplanowe
  19.03.2020 pominięte.
  Źródło `abs` (`calendar_abs.py`): AU_CPI, 41 publikacji (kwartalne, od
  X 2025 miesięczne). Godzina z każdej strony wydania: nowy układ
  („Release date and time … 11:30am AEDT”, skrót sprawdzany ze strefą),
  ausstats do 06.2020 („Released at 11:30 AM (CANBERRA TIME)”).
  Źródło `jp` (`calendar_jp.py`): JP_CPI, 120 publikacji. Harmonogram
  `data/kouhyou/e-stat_cpi.xml` (UTF-16) ma datę i godzinę (8:30 JST);
  lata 2016–2021 z kopii Wayback rocznych plików. Klucz = rok i miesiąc
  odniesienia (zmiana ery 平成→令和 zmienia nazwę), termin z najnowszej
  kopii (plik z 2017 zapowiadał styczeń 2018 na 2.03, wyszło 23.02).
  Źródło `boj` (`calendar_boj.py`): 79 decyzji. BoJ podaje godzinę
  ogłoszenia tylko do 2015 („Announced at 12:17 p.m.”), metadane PDF nie są
  publikacją (29.01.2016: ModDate 13:59, rynek 12:38). Znacznik = koniec
  posiedzenia z nagłówka protokołu (`minu_<rok>/g*.pdf`, od 2018 `.htm`);
  publikacja ~7 min później (zmierzone na M1 USDJPY 2016), więc mieści się
  w oknie −30/+120. Nadzwyczajne (16.03 i 22.05.2020) rozpoznane po
  zwrotach „Unscheduled Monetary Policy Meeting” / „brought forward” —
  w latach 2016–2025 żaden inny protokół ich nie ma; 2020 ma 7 planowych.
  Źródło `eurostat` (`calendar_eurostat.py`): EA_HICP_FLASH, 121 publikacji
  (12 na każdy rok 2016–2025 + grudzień 2025 wydany w 2026, poza zakresem).
  Kalendarz Eurostatu sięga 2025, portlet listy daje 403, więc sondowane są
  trwałe adresy `products-euro-indicators/w/2-DDMMYYYY-<sufiks>` (dni robocze
  24. → 7. następnego miesiąca, sufiksy ap/bp/cp — wyszło 106/14/1); brak
  komunikatu = `<title>EU Login`. Flash rozpoznaje tytuł („Euro area annual
  inflation …”, odczyt finalny brzmi inaczej i wypada w połowie miesiąca).
  Sondowanie kończy się na pierwszym trafieniu w miesiącu, brak trafienia
  w całym oknie = błąd. ~550 adresów w cache, więc powtórny przebieg jest bez
  sieci. Kontrola metody: dla 2025 (jedyny rok z kalendarzem Eurostatu)
  sondowanie dało te same 12 dat co kalendarz. Godzina: 11:00 czasu
  Europe/Luxembourg Z DST, nie stały CET — wyszło 71 zdarzeń o 09:00 UTC
  (lato) i 49 o 10:00 UTC (zima). Rozstrzygnięte dwoma dowodami: kalendarz
  2025 podaje „11:00Z” i zimą, i latem (więc to czas lokalny, nie UTC),
  a na M1 EURUSD zakres minuty / mediana dnia daje 7,3× o 10:00 UTC w 6 dniach
  zimowych i 3,7× o 09:00 UTC w 8 letnich (pozostałe minuty ≤ 2,2×).
  ec.europa.eu odpowiada 429 i zrywa połączenia — pauza 2,5 s i ponawianie
- `src/strategy/v1a.py` — reguła V1a + NO TRADE wg ADR-033:
  `decision_frame()` (warunki per bar), `run_v1a()` (sekwencyjnie: limity
  bloków walutowych, portfela, jedna pozycja na parę do `t1`), log decyzji
  z powodem dla KAŻDEGO bara. `rules_from(cfg)`, `grid_from(cfg)`.
  Testy tylko na syntetyku; na prawdziwych danych jeszcze nie uruchamiane

Prerejestracja przed V1a (ADR-027..031, config `frozen_sha256`
`2eab678f…`): DSR ≥ 0,95; siatka 7 wariantów jeden-parametr-naraz
w `signal_v1a.sensitivity_grid`, płaskowyż = każdy sąsiad ≥ 50% E[R]
baseline, ten sam znak; N = warianty w przebiegach `strategy` (kontrola
oceniająca sygnał V1a to też `strategy`); wejście tylko gdy cały horyzont
mieści się w splicie (każda granica); CPCV 6/2 = 15 podziałów, 5 ścieżek.
ADR-032: blackout 30 min przed … 120 min po, tylko zdarzenia planowane,
terminy wyłącznie parsowane ze źródeł. ADR-033: interpretacja V1a/NO TRADE.
ADR-034 (doprecyzowuje 032): kopie Wayback jako nośnik strony oficjalnej,
znacznik BoJ = koniec posiedzenia z protokołu, kryteria planowości per źródło,
godzina jako czas lokalny + strefa (nigdy stały offset).

Kalendarz (2026-09-20): KOMPLETNY dla kohorty A, 1740 zdarzeń, 16 serii,
`coverage_gaps()` puste dla 2016–2025 (sprawdzane też przez `require_coverage()`).
Per seria: FOMC 79, US_CPI 119, US_NFP 119, US_PCE 117, US_RETAIL_SALES 119,
US_GDP_ADVANCE 40; ECB_RATE 80, ECB_PRESS_CONF 80, EA_HICP_FLASH 120;
BOE_RATE 83, UK_CPI 120, UK_LABOUR 120; BOJ_RATE 79, JP_CPI 120;
RBA_RATE 104, AU_CPI 41; BOC_RATE 80, CA_CPI 120.

Trzy godziny, których źródła nie podają przy publikacji, są prerejestrowane
w `config/calendar_times.yaml` i zweryfikowane przez użytkownika 2026-09-20
(`verified: true`): BOE_RATE 12:00 Londyn, ONS_BULLETIN 9:30 Londyn (tylko
styczeń 2016, przed startem kalendarza ONS), EA_HICP_FLASH 11:00
Europe/Luxembourg. Każdy wpis niesie cytat, dowód i wynik testu na tickach.
Wniosek metodologiczny: godzina jest trzymana jako czas lokalny + strefa,
nigdy jako stały offset — dla HICP flash stały CET dawałby latem błąd godziny.

Rok 2015 nie jest potrzebny (rozgrzewka; FOMC 2015 nie podaje godziny).
Runner V1a ma wołać `require_coverage(events, symbole, start, end)` przed
liczeniem czegokolwiek — brak serii wygląda w `blackout()` tak samo jak brak
zdarzenia (ADR-032 pkt 4).
Kopie z Wayback (`web.archive.org/web/<znacznik>id_/<adres>`) są używane
tam, gdzie serwis blokuje skrypty (RBA) albo usunął pliki (roczne
harmonogramy stat.go.jp) — treść jest wierną kopią strony oficjalnej,
a znacznik zapisu bywa dowodem, że termin był znany z wyprzedzeniem.

Ustalenia z danych:
- Rozgrzewka: `vol_pct_252` wymaga 252 dni → pierwszy handlowalny bar
  ~rok po starcie danych (2016-01). Rok 2015 to tylko historia dla cech.
- Nakładanie etykiet ~99% przy horyzoncie 10 dni: efektywne n jest
  o rząd wielkości mniejsze od nominalnego. Do testów istotności
  używać `effective_sample_size`, nie liczby wierszy.
- Spready 2015 (mediana `spread_close`): EURUSD 0,3, USDJPY 0,4,
  pozostałe 0,8–1,2 pipsa. Podłoga 1,5 / 2,5 pipsa zwykle wiąże.
- `data/raw/dukascopy/EURUSD/2019,2020` — było 130 godzin próbek z testów
  dekodera; NIEAKTUALNE, downloader przeszedł przez 2019 i 2020, wszystkie
  pary mają komplet. Partycje barów zbudowane wtedy z tych próbek (118
  barów H1 za 2019, 6 za 2020) zostały usunięte — to był cichy zaniżacz
  próby, patrz `src/data/provenance.py`.

- Wydajność (2026-09-20): ~1,5 ms na transakcję w najgorszym przypadku
  (pełne okno 10 dni = 14 tys. barów M1, żadna bariera nietrafiona);
  wcześniej ~32 ms. Dwie zmiany: `_first_event()` szuka pierwszego bara
  z barierą wektorowo (numpy, 0,03 ms zamiast 29 ms), a `simulate_trade`
  wycina okno przez `slice_window()` (wyszukiwanie binarne) zamiast
  `filter` (6,4 ms). Stąd wymóg: `m1` posortowane po `ts` — sprawdzane,
  bo cichy zły wycinek byłby gorszy niż błąd. Logika i kolejność barier
  bez zmian; test porównuje `_first_event` z naiwnym skanem na losowych
  ścieżkach (200 przypadków na stronę).

- `src/data/provenance.py` + `require_fresh_bars()` w `harness/market.py` —
  obok każdej partycji `source.json` z liczbą godzin cache, z których
  powstała; runner odrzuca partycję zbudowaną z wycinka (`StaleBarsError`).
  `scripts/gate0.py` woła to przed `start_run`, żeby nieudana próba nie
  szła do `trials.jsonl`. Ucieczka: `--allow-stale-bars`
- `src/validation/controls.py` — komplet kontroli #1, #2, #3, #7 (§10.2):
  `shuffled_label_null()` (tasowanie WEWNĄTRZ grup (symbol, kierunek);
  rozkład zerowy jest wyśrodkowany na średniej puli, nie na zerze),
  `shift_features()` (tylko cechy modelujące, `atr_d1_14` nietknięte),
  `permutation_max_drawdown()` (permutacja kolejności DNI, nie transakcji)
- `src/validation/cost_sensitivity.py` — drabinka 1×/2×/3× (§9).
  Symulator raportuje teraz `slippage` osobno (`slip_r` w etykiecie), więc
  mnożnik skaluje cały modelowany koszt, nie sam spread. Przy 1× wynik
  jest identyczny z `r` symulatora — pilnuje tego test. Podpięte do
  raportu bramki 0
- `src/data/rates.py` + `scripts/fetch_rates.py` — stopy z FRED,
  `data/rates/fred.parquet`, raport `reports/rates_coverage.md`.
  Overnight (OECD `IRSTCI01<ISO>M156N`) komplet 132/132 miesiące
  2015–2025 dla całej kohorty A. `rate_on()` bierze miesiąc POPRZEDNI —
  średnia stycznia nie jest znana w styczniu
- `src/execution/financing.py` — swap FX (ADR-035, ADR-037): `rollover_days()`
  ze środą liczoną potrójnie (tydzień = 1+1+3+1+1 = 7),
  `financing_r()` kierunkowe, `apply_financing()` dokłada `financing_r`
  i pomniejsza `r` (wynik sprzed korekty = `r + financing_r`).
  Marża `cohort_a_markup_annual_pct: 0.5` to JEDYNA liczba w modelu
  kosztów bez sparsowanego źródła, więc NIE wolno jej raportować
  punktowo: każdy wynik idzie z osią `cohort_a_markup_sensitivity`
  [0,5; 1,0; 2,0] przez `markup_ladder()` (ADR-037). `refinanced()`
  przelicza marżę z `fin_unit_r` bez ponownego czytania stóp

ADR-037: marża swapu 0,5% + OBOWIĄZKOWA oś wrażliwości [0,5; 1,0; 2,0].
Koryguje ADR-035 pkt 4, który deklarował zabezpieczenie przez drabinkę
1×/2×/3× — nieistniejące, bo finansowanie świadomie nie jest nią skalowane.
Powod: przy stopie 1,1% ceny marża 1,0% kosztuje 0,035 R, czyli 3,3× cały
zmierzony spread i 35% progu bramki 2; dla USDCAD i EURJPY przewyższa
medianę faktycznego carry 3–5×.
ADR-035: finansowanie kohorty A modelowane jawnie (pominięcie warte
~0,13 R przy różnicy stóp 2,8 pp i stopie 1,1% ceny — więcej niż CAŁY
próg bramki 2, i kierunkowe, więc podszywa się pod sygnał).
ADR-036: FRED nie ma rentowności 2-letnich poza USD, więc benchmark
carry + trend (§12, ADR-019) jest NIEWYKONALNY zgodnie ze spec.
Zamiennik musi być prerejestrowany przed bramką 2 — nie teraz, żeby nie
wybierać wejścia do benchmarku po zobaczeniu wyniku strategii.
`frozen_sha256` bez zmian (`2eab678f…`) — `costs` nie jest zamrożone.

Czego NADAL nie ma (spec wymaga): kontrole §10.2 nr 4, 5, 9, 10;
benchmark carry + trend (§12, blokada z ADR-036); runner V1a i skrypty
bramek 1–5; cała kohorta B.

Następne (gdy pobieranie dojdzie do końca 2021): `download_ticks.py
--retry-failed`, `build_bars.py`, potem `scripts/gate0.py` — przebieg
zamykający bramkę 0 (nowy symulator, kryteria ADR-025; kolejna próba
w `trials.jsonl`). Sprawdzić w raporcie: liczbę „bez wyniku" (po ADR-026
powinna spaść z ~1,2% prawie do zera) i połowę CI ≤ 0,05 R. Symulator jest
już zwektoryzowany (~1,5 ms na transakcję), więc 7 lat nie wymaga dalszej
optymalizacji przed bramką 0.

Uwaga do `trials.jsonl`: jedyny wpis (`20260919T134506Z-c4710e`) powstał
przed ADR-029 i nie ma pola `kind`, więc `n_trials()` liczy go jako próbę
strategii (N = 1), choć był kontrolą. Zachowawczo — zawyża N, nie zaniża.
`scripts/gate0.py` deklaruje już `kind="control"`.

Równolegle (nie czeka na dane): kalendarz jest skończony, więc następny
krok bez danych to runner V1a na harnessie (`kind="strategy"`, `n_variants=7`) —
uruchamiać dopiero po zamknięciu bramki 0 i przy pełnym pokryciu
kalendarza. Potem bramka 1.
