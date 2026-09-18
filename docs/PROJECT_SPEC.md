# PROJECT_SPEC.md — market-quant

> **Status:** obowiązująca specyfikacja V1
> **Wersja:** 1.0
> **Data:** 2026-09-18
> **Zastępuje:** `docs/research/INITIAL_CONVERSATION.md` (materiał historyczny, nieobowiązujący)
> **Podstawa:** `docs/AUDIT_REPORT.md`
>
> W razie sprzeczności między tym dokumentem a czymkolwiek innym w repozytorium — **obowiązuje ten dokument**.

---

## 1. Czym ten projekt JEST

Aparaturą pomiarową do odrzucenia jednej hipotezy:

> **H₁:** Istnieje prosta, deterministyczna strategia swingowa na 6 głównych parach FX, oparta na momentum wielohoryzontowym i pozycji w zakresie cenowym, o expectancy istotnie większym od zera po realistycznych kosztach transakcyjnych i po korekcie na liczbę przeprowadzonych prób.

**H₀ (hipoteza zerowa, domyślna): takiej strategii nie ma.**

Ciężar dowodu spoczywa na H₁. Prior dla H₁ jest niski.

## 2. Czym ten projekt NIE JEST

- Nie jest botem tradingowym.
- Nie jest platformą.
- Nie jest produktem.
- Nie jest systemem z interfejsem, bazą danych, kontenerami ani powiadomieniami.
- Nie jest systemem, w którym LLM generuje sygnał.

Wszystkie powyższe mogą powstać **po** rozstrzygnięciu H₁ — i tylko jeśli zostanie ono rozstrzygnięte na korzyść H₁.

## 3. Definicja sukcesu

Sukcesem jest **liczba z przedziałem ufności**, uzyskana w ~11 tygodni.

Wynik „expectancy = −0,01 R, CI [−0,06; +0,04], H₁ odrzucone" jest **pełnoprawnym sukcesem projektu**. Oznacza, że w 11 tygodni dowiedzieliście się czegoś prawdziwego, zamiast spędzić rok na budowaniu systemu, który powie Wam to samo, tylko drożej i mniej wiarygodnie.

---

# 4. Zakres V1

## 4.1 Instrumenty — ZAMROŻONE

Zbiór jest zamrożony w całości **przed pierwszym backtestem** i dzieli się na dwie rozłączne kohorty o różnych rolach.

### Kohorta A — FX, zbiór odkrywczy (V1)

```
EURUSD  GBPUSD  USDJPY  AUDUSD  USDCAD  EURJPY
```

Na tym zbiorze przebiegają bramki 0–4. To jedyny zbiór, na którym wolno cokolwiek dobierać.

### Kohorta B — surowce i indeksy, zbiór replikacyjny (po bramce 2)

```
XAUUSD (złoto)   WTI (ropa)   S&P 500   DAX
```

**Kohorta B nie jest zbiorem treningowym.** Służy do replikacji reguły z parametrami zamrożonymi hashem gita po bramce 2. Zero dostrajania, zero ponownego dopasowania, zero zmiany parametrów po zobaczeniu jej wyników.

Wybór **S&P 500, nie Nasdaq** — rozstrzygnięty przed pierwszym backtestem. Uzasadnienie: czystszy benchmark bety, węższy spread względem ATR, dłuższa i lepsza historia CFD. Obserwacja „Nasdaq ładniej trenduje" jest wiedzą in-sample i nie może wpływać na ten wybór.

### Wykluczone świadomie

| Instrument | Powód |
|---|---|
| CHF | Zerwanie pega EURCHF 2015-01-15 czyni serię niereprezentatywną |
| GBPJPY | Kandydat na selection bias („bo ładnie trenduje") |
| Egzotyki (TRY, ZAR, MXN) | Szeroki spread, ryzyko polityczne, słabe dane |
| Dow Jones | Korelacja z S&P ~0,95, ważony ceną — zero wartości informacyjnej |
| Nasdaq | Korelacja z S&P ~0,90–0,95; wybrany jeden indeks US |
| Srebro | Korelacja ze złotem ~0,8, wyższa zmienność, szerszy spread względny → V2 |
| Nikkei 225 | Skorelowany z S&P **i** z USDJPY, który jest już w kohorcie A → V2 |

### Efektywna liczba czynników

| Zbiór | Czynniki niezależne | Wykrywalny edge (t = 2) |
|---|---|---|
| Kohorta A | ~3 (USD, EUR, JPY) | ~0,09 R |
| Kohorta A + B w jednej puli | ~6 | ~0,06 R |

Pooling nie jest stosowany w V1 — patrz `DECISIONS.md` ADR-021. Replikacja na nietkniętej klasie aktywów jest dowodem mocniejszym niż redukcja progu wykrywalności o 0,03 R.

## 4.2 Okres

| Segment | Zakres | Reguła dostępu |
|---|---|---|
| RESEARCH | 2015-01-01 → 2021-12-31 | CPCV, swobodny dostęp |
| VALIDATION | 2022-01-01 → 2023-12-31 | Ograniczone uruchomienia, każde logowane |
| **SEALED HOLD-OUT** | 2024-01-01 → 2025-12-31 | **Zero dostępu do Gate 4. Jedno uruchomienie.** |

## 4.3 Timeframe

**Jedna baza: H1.**

M1/tick wyłącznie wewnątrz symulatora egzekucji. D1, H4, M15 **nie występują** w warstwie sygnału.

Częstotliwość decyzyjna: zamknięcie świecy H1.

---

# 5. Dane

## 5.1 Ceny

| Element | Specyfikacja |
|---|---|
| Źródło | Dukascopy historical tick (bid + ask) |
| Zakres | 2015-01-01 → dziś |
| Pipeline | tick → M1 → H1, resampling własny |
| Format | Parquet, partycjonowany po `(para, rok)` |
| Strefa czasowa | **UTC wszędzie**, bez wyjątków |
| Weryfikacja krzyżowa | HistData.com — porównanie barów, próg zgodności 99% |

**Zasady twarde:**
- Bid i ask przechowywane **osobno**. Cena mid nie występuje nigdzie w systemie.
- Luki > 60 s w godzinach handlowych — zliczone i udokumentowane w raporcie jakości.
- Sesje wyprowadzane z UTC z jawnym uwzględnieniem **różnych dat przełączenia DST w USA i UE**.

**Kohorta B — dodatkowe wymagania (tygodnie 12–14, nie wcześniej):**

| Wymaganie | Uwaga |
|---|---|
| Osobny kalendarz sesji per instrument | Indeksy nie chodzą 24/5; luki otwarcia są codzienne, nie tygodniowe |
| Osobny raport jakości danych per instrument | Historia poza majorsami FX jest krótsza; to **CFD brokera, nie dane giełdowe** |
| Jawna obsługa dywidend | CFD na indeks cenowy rozlicza dywidendy — nieciągłość w serii |
| Model finansowania wg wzoru z §9 | Zwalidowany wobec realnych stawek brokera |
| Decyzja o WTI 2020-04-20 (cena ujemna, −37 USD) | Podjęta **przed** zobaczeniem wyników, analogicznie do CHF. Rekomendacja: wykluczyć dzień z próby, zachować jako test stresowy egzekucji |
| Decyzja o zatrzymaniach notowań (circuit breakers) | Odwzorowane w CFD jako luka; reguła traktowania ustalona ex ante |

## 5.2 Makro

| Element | Specyfikacja |
|---|---|
| Yieldy | FRED/ALFRED (`DGS2`) + ECB Data Portal / BoE / BoJ / ONS dla pozostałych walut |
| Dostęp | **Wyłącznie przez ALFRED z `realtime_start` = data decyzji** |
| Margines bezpieczeństwa | +1 dzień roboczy opóźnienia publikacji |
| Harmonogram wydarzeń | Oficjalne źródła: BLS, BEA, Eurostat, ONS, kalendarze posiedzeń Fed/ECB/BoE/BoJ/RBA/BoC/RBNZ |
| Zawartość harmonogramu | **Tylko `(timestamp_utc, waluta, nazwa, ranga)`. BEZ wartości actual/consensus/previous** |

**Zakazane:** scraping ForexFactory/Investing.com; jakiekolwiek użycie wartości `consensus` lub `surprise` w V1 (brak darmowego archiwum point-in-time — patrz `AUDIT_REPORT.md` §7.4).

---

# 6. Cechy — dokładnie sześć

Wszystkie na H1, wszystkie kauzalne, wszystkie normalizacje w **oknie rozszerzającym** (tylko przeszłość).

Obowiązują **dwie różne skale zmienności** i nie wolno ich mylić:

- `atr_h1_14` — ATR(14) liczony na barach H1. Służy wyłącznie do **normalizacji cech**.
- `atr_d1_14` — ATR(14) liczony na barach D1. Służy wyłącznie do **skalowania barier i sizingu**.

| # | Nazwa | Definicja |
|---|---|---|
| 1 | `atr_h1_14` | ATR(14) na H1, w jednostkach ceny (normalizator cech, nie cecha predykcyjna) |
| 2 | `mom_24` | `(close − close[−24]) / (atr_h1_14 × √24)` |
| 3 | `mom_120` | `(close − close[−120]) / (atr_h1_14 × √120)` |
| 4 | `mom_480` | `(close − close[−480]) / (atr_h1_14 × √480)` |
| 5 | `donch_pos_55` | `(close − min_55) / (max_55 − min_55)` ∈ [0,1] |
| 6 | `vol_pct_252` | Percentyl `atr_d1_14` w oknie rozszerzającym ≥252 dni |

Czynnik `√n` skaluje każde momentum zmiennością jego własnego horyzontu. Bez niego trzy cechy momentum różnią się skalą o czynnik ~√20, mają nieporównywalne rozkłady i psują regularyzację L2 w modelu logitowym.

**Cechy makro (V1b, SHOULD HAVE):**

| # | Nazwa | Definicja |
|---|---|---|
| 7 | `carry_2y` | `yield_2y(waluta bazowa) − yield_2y(waluta kwotowana)` |
| 8 | `d_carry_20d` | `carry_2y(t) − carry_2y(t − 20 dni roboczych)` |

**Zakazane w V1:** RSI, MACD, ADX, Stochastic, CCI, Williams %R, Bollinger, support/resistance, wolumen, BOS, CHoCH, FVG, order blocks, liquidity, jakiekolwiek cechy wielointerwałowe.

**Pooling:** model uczony na połączonej próbie wszystkich 6 par. Testy istotności przez **bootstrap blokowy po dacie** (cały dzień = jeden blok), nigdy po obserwacji.

---

# 7. Sygnał

## 7.1 V1a — reguła deterministyczna (MUST HAVE)

```
LONG (SHORT symetrycznie):
  mom_480       > 0
  donch_pos_55  > 0.80
  NOT blackout(t)
  vol_pct_252   < 0.95

WEJŚCIE: rynkowe na zamknięciu świecy H1, po cenie ASK
SL:      entry − 2.0 × atr_d1_14
TP:      entry + 4.0 × atr_d1_14
TIME:    wyjście rynkowe po 10 dniach roboczych
```

**Parametry swobodne: `{55, 2.0, 4.0}` — i tylko te trzy.** Progi 0,80 i 0,95 są ustalone i nietykalne.

**Skala barier musi odpowiadać horyzontowi.** Bariery na poziomie `2 × atr_h1_14` (≈20 pipsów na EURUSD) przy horyzoncie 10 dni zostałyby trafione w ciągu godzin, bariera czasowa nigdy by nie zadziałała, a etykiety zdegenerowałyby się do szumu mikrostruktury. Warunkiem poprawności triple barrier jest `bariera ≈ σ√T`; dla T = 10 dni daje to `2 × atr_d1_14` (≈1,1% ceny na EURUSD, ≈120 pipsów). Cechy pozostają liczone na H1 — zmienia się wyłącznie skala barier i sizingu.

## 7.2 Blackout makro

```
blackout(t) = TRUE  ⟺  w [t − 30 min, t + 120 min] wypada wydarzenie rangi HIGH
                        dla którejkolwiek z dwóch walut pary
```

Ranga HIGH — lista zamknięta: decyzje stóp (FOMC, ECB, BoE, BoJ, RBA, BoC, RBNZ); US CPI, NFP, PCE, retail sales, GDP advance; EA HICP flash + konferencja ECB; UK CPI + labour market; krajowe CPI dla walut z koszyka.

Skutek: **zakaz otwierania nowej pozycji**. Istniejące pozycje nie są zamykane (to osobna hipoteza, V2).

## 7.3 V1b — model probabilistyczny (SHOULD HAVE, tylko po Gate 2)

| Element | Specyfikacja |
|---|---|
| Input | 8 cech (§6) |
| Próba | Tylko zamknięcia H1 spełniające warunki blackout i `vol_pct` |
| Label | Triple barrier o **identycznej geometrii co V1a** (2/4 ATR, 10 dni) |
| Target | `y ∈ {1,0}` = TP przed SL; time barrier → `y = 0` |
| Model | Regresja logistyczna, L2; `C` dobierane **wyłącznie na foldzie wewnętrznym** |
| Kalibracja | Isotonic/Platt na **osobnym foldzie kalibracyjnym** |
| EV | `EV = p̂ × 2.0 − (1 − p̂) × 1.0 − koszt_R` |
| Próg wejścia | `EV > 0.10 R` — prerejestrowany, nie strojony |

**Wymagane w raporcie z każdego uruchomienia V1b:** reliability diagram, Brier score **w top-decylu EV**, oraz tabela przewidywane EV vs realizowane średnie R per decyl EV.

## 7.4 NO TRADE — lista zamknięta

System nie handluje, gdy:

1. `blackout(t) = TRUE`
2. `vol_pct_252 > 0.95`
3. `EV ≤ 0.10 R` (tylko V1b)
4. Przekroczony limit ekspozycji na którąkolwiek z walut pary
5. Przekroczony limit ryzyka portfela
6. Istnieje otwarta pozycja na tej parze
7. **Dane niekompletne** — luka > 2 barów H1 w ostatnich 480, lub brak odczytu yieldów < 5 dni roboczych
8. Okno rollover 16:45–17:15 NY
9. Piątek po 15:00 NY

**Każde NO TRADE jest logowane z powodem.** NO TRADE jest stanem domyślnym.

---

# 8. Risk Engine

| Poziom | Reguła |
|---|---|
| Ryzyko transakcji | Stałe `r%` equity; `SL = 2 × atr_d1_14`. **Bez dodatkowej warstwy vol-scalingu** (stop w ATR już nią jest) |
| Ekspozycja walutowa | Max **2 R netto** na walutę |
| Ryzyko portfela | Max **6 R**, przy założeniu `ρ = 1` wewnątrz bloku walutowego |
| Bloki walutowe | `{USD}` · `{EUR, CHF}` · `{GBP}` · `{JPY}` · `{AUD, NZD, CAD}` |
| Pozycje na parę | Max 1 |
| Pyramiding | **ZAKAZANY w V1** |
| Drawdown de-risking | **BRAK w V1** |
| Fractional Kelly | **ZAKAZANY** |

**Zasada badawcza:** wszystko mierzone w **R**. `r%` nie jest parametrem badawczym — przy sizingu liniowym skaluje krzywą, nie zmienia expectancy w R ani Sharpe'a. Dobierany na końcu z rozkładu drawdownu.

---

# 9. Model kosztów — obowiązkowy

| Składnik | Model |
|---|---|
| Spread | **Rzeczywisty historyczny bid/ask z ticków** w momencie fillu. Nigdy średni, nigdy mid |
| Prowizja | Wliczona w podłogę kosztu — nie modelowana osobno |
| **Podłoga kosztu** | `max(spread_tickowy + prowizja, podłoga)`; 1,5 pipsa majors, 2,5 pipsa crosses |
| Poślizg — wejście | ≥ 0,5 × mediana spreadu w danej godzinie, niekorzystnie |
| Poślizg — SL | **≥ 1,0 × spread, niekorzystnie** (asymetria: stop realizuje się, gdy rynek się porusza) |
| Poślizg — TP | 0, ale fill **tylko przy pełnym przekroczeniu poziomu** |
| Swap (kohorta A) | Punkty swapowe brokera; potrójny swap w środę |
| **Finansowanie (kohorta B)** | Pełna stawka: benchmark + marża brokera. Patrz niżej — to dominujący składnik kosztu |
| Weekend gap | Fill po pierwszej dostępnej cenie; **stopy nie chronią przez lukę** |
| Luka sesyjna (kohorta B) | Codzienna przerwa w notowaniach indeksów; stopy nie chronią przez lukę otwarcia |
| Dywidendy (kohorta B) | Rozliczenie dywidend na CFD indeksu cenowego — jawna nieciągłość w serii |
| **Kolejność barier** | **Rozstrzygana na tickach.** Wariant awaryjny: SL zawsze pierwszy (pesymistycznie). **Nigdy optymistycznie** |

**Raportowanie obowiązkowe: wynik przy 1×, 2× i 3× kosztach.**

### Finansowanie pozycji — wzór obowiązujący

W FX płacisz **różnicę** stóp. W CFD na indeks lub surowiec płacisz **pełną** stawkę (benchmark SOFR/€STR plus marża brokera, typowo 1,5–3% rocznie). Procent ryzyka skraca się we wzorze:

```
Koszt_R = (stawka_roczna × dni_trzymania) / (365 × stop_jako_ułamek_ceny)
```

Wartości orientacyjne dla 10-dniowego trzymania, do weryfikacji na danych własnych:

| Instrument | Stop (2 × ATR D1) | Spread w R | Finansowanie w R |
|---|---|---|---|
| EURUSD | ~1,1% | ~0,008 | ~0,025 (differential) |
| XAUUSD | ~2,4% | ~0,008 | ~0,08 |
| S&P 500 CFD (long) | ~1,8% | ~0,006 | **~0,107** |
| DAX CFD (long) | ~2,0% | ~0,008 | ~0,096 |

**Wnioski wiążące dla projektu:**

1. Spread **nie jest** binding constraint przy horyzoncie swingowym na żadnym z tych instrumentów. Założenie „tylko instrumenty o wąskim spreadzie" jest słuszne, ale niewystarczające.
2. Finansowanie długiej pozycji w indeksie jest **rzędu całego poszukiwanego edge'u** i kilkanaście razy większe od spreadu.
3. Finansowanie jest **asymetryczne kierunkowo**: long płaci benchmark + marżę, short otrzymuje benchmark − marżę. Różnica rzędu 0,14 R między kierunkami nie ma związku z sygnałem i musi być modelowana jawnie.
4. Koszt skaluje się liniowo z liczbą dni — skrócenie horyzontu na kohorcie B do 5 dni halvuje go. Test tego wariantu jest prerejestrowany w V2, nie w V1.

---

# 10. Walidacja

## 10.1 CPCV

| Parametr | Wartość |
|---|---|
| Grupy | 6 |
| Grup testowych na kombinację | 2 (→ 15 ścieżek) |
| **Purge** | 10 dni roboczych (= max holding period) |
| **Embargo** | 5 dni roboczych |
| Jednostka bloku | Cały dzień, wszystkie pary łącznie |

Walk-forward (3 lata / 6 mies.) jako kontrola zgodności. **Rozbieżność CPCV vs WF = leakage lub niestacjonarność → STOP.**

## 10.2 Kontrole obowiązkowe

| # | Kontrola | Kryterium |
|---|---|---|
| 1 | **Random entry, identyczne wyjście i sizing, ta sama liczba transakcji** | Rozkład zerowy — **benchmark nr 1** |
| 2 | Shuffled labels | Wynik ≈ 0 |
| 3 | Shifted features (+1 bar w przyszłość) | Wynik **nie może rosnąć** |
| 4 | Buy & hold / carry-only | Musi zostać pobity |
| 5 | **Koszyk carry + trend** (§12) | Musi zostać pobity |
| 6 | Block bootstrap (20 dni), 10 000 replikacji | CI |
| 7 | Monte Carlo permutacji | Rozkład max DD |
| 8 | **Expectancy osobno dla longów i shortów**, per instrument | Wykrywa dryf kierunkowy udający edge |
| 9 | **Buy & hold per instrument** (obowiązkowe na kohorcie B) | Oddziela betę od sygnału |
| 10 | Kontrola losowa uruchomiona **osobno dla każdej kohorty** | Rozkład zerowy różni się między klasami aktywów |

Kontrole 8–10 są krytyczne dla kohorty B. Indeksy akcyjne mają silny dodatni dryf, którego pary FX nie mają: strategia z przewagą longów pokaże dodatnie expectancy wynikające wyłącznie z premii za ryzyko akcyjne. DAX jest tu szczególnie zdradliwy, bo jest indeksem **dochodowym** (z reinwestowanymi dywidendami), więc jego dryf jest jeszcze silniejszy niż S&P, który jest indeksem cenowym.

## 10.3 Progi

| Metryka | Próg |
|---|---|
| Expectancy netto | ≥ +0,10 R |
| t-stat (block bootstrap) | ≥ 2,0 |
| **Deflated Sharpe Ratio** | ≥ 0 przy liczbie prób z `trials.jsonl` |
| **PBO (CSCV)** | ≤ 0,30 |
| Odporność kosztowa | Expectancy > 0 przy 2× kosztach |
| Stabilność instrumentów | Dodatnia na ≥ 4 z 6 par |
| Stabilność czasowa | Dodatnia w ≥ 2 z 3 podokresów |
| Wrażliwość parametryczna | Płaskowyż, nie szpikulec |

## 10.4 Checklista leakage'u — do przejścia przed KAŻDYM raportowanym wynikiem

- [ ] Wszystkie normalizacje w oknie rozszerzającym, tylko przeszłość
- [ ] Żaden `fit()` nie widział danych testowych (w tym skaler, imputer, kalibrator)
- [ ] Makro przez ALFRED z `realtime_start` = data decyzji
- [ ] Bar H1 zamknięty przed momentem decyzji (kontrola off-by-one)
- [ ] Symulator fillów nie widzi cen po momencie decyzji
- [ ] Kolejność barier: tickowo lub pesymistycznie
- [ ] Bid/ask osobno, **nigdzie mid**
- [ ] Brak modeli stanu ze smoothingiem (`predict()` Viterbi, `smoothed_marginal_probabilities`)
- [ ] Zbiór instrumentów zamrożony
- [ ] Parametry zapisane w YAML z hashem git **przed** uruchomieniem
- [ ] `trials.jsonl` zaktualizowany automatycznie
- [ ] **Żadne wejście do backtestu nie pochodzi od LLM**
- [ ] Kontrole 2 i 3 z §10.2 przeszły

---

# 11. Stack techniczny

```
Python 3.12 + polars + numpy + scikit-learn + scipy + pyarrow + matplotlib + pytest

Przechowywanie:  Parquet na dysku
Interfejs:       CLI; notebooki tylko do eksploracji
Konfiguracja:    YAML wersjonowany, z hashem git
Wyniki:          runs/<timestamp>/ + append do trials.jsonl
```

**Zakazane w V1:** PostgreSQL, TimescaleDB, Redis, FastAPI, React, Next.js, Lightweight Charts, Docker, MCP, Discord, XGBoost/LightGBM, HMM, PyTorch, TA-Lib, OpenBB.

## Struktura repozytorium

```
market-quant/
├── CLAUDE.md
├── docs/{PROJECT_SPEC,DECISIONS,AUDIT_REPORT}.md + research/
├── config/v1_baseline.yaml
├── src/
│   ├── data/        downloadery, resampling, raport jakości
│   ├── execution/   ★ symulator fillów — najważniejszy moduł
│   ├── features/    6 cech
│   ├── labels/      triple barrier
│   ├── signal/      reguła + logit
│   ├── risk/        sizing i limity
│   └── validation/  CPCV, DSR, PBO, kontrole, bootstrap
├── tests/           ★ najgęściej dla execution/
├── trials.jsonl     append-only, zapis automatyczny
└── runs/            niewersjonowane
```

---

# 12. Benchmark obowiązkowy — koszyk carry + trend

```
Raz w tygodniu, 8 walut vs USD:
  ranking po (yield_2y + zwrot 3-miesięczny)
  long top 2, short bottom 2
  równe ryzyko, sizing przez ATR
  brak stopów, rebalans tygodniowy
```

Strategia z udokumentowanym w literaturze priorem, znikomym obrotem i praktycznie zerową liczbą stopni swobody.

**Jeśli system z §7 nie bije tego koszyka poza próbą — cała złożoność jest nieuzasadniona i przechodzimy na koszyk.**

---

# 13. Rola Claude

## Dozwolone

Implementacja kodu · adwersaryjny audyt leakage'u · implementacja testów statystycznych · projektowanie i **prerejestracja** eksperymentów · analiza zamkniętych eksperymentów · code review · wyjaśnianie metodologii.

## Zakazane — twardo

| Zakaz | Powód |
|---|---|
| **Generowanie jakichkolwiek wejść do backtestu** | Parametric look-ahead — nienaprawialne |
| Runtime signal generation | Brak kalibracji i odtwarzalności |
| **Wybór, który wariant backtestu zachować** | To jest próba; delegowanie czyni licznik niepoliczalnym |
| Interpretowanie krzywej equity jako dowodu | — |
| Decyzje o wielkości pozycji | — |

## Zasada

> **Każda iteracja wspomagana LLM jest próbą i musi trafić do `trials.jsonl`.**

Zapis jest automatyczny, wykonywany przez harness backtestu, bez możliwości ręcznego pominięcia.

---

# 14. Harmonogram i bramki

| Tydzień | Zakres | Bramka |
|---|---|---|
| 1–2 | Dane + raport jakości | — |
| 3–4 | Symulator egzekucji + testy | **Gate 0** |
| 5 | Kontrola losowa | **Gate 1** |
| 6 | Cechy + etykiety | — |
| 7 | V1a + CPCV | — |
| 8 | DSR, PBO, wrażliwość | **Gate 2 ← najważniejsza** |
| 9–10 | carry + blackout + logit | **Gate 3** |
| 11 | Zapieczętowany hold-out, jedno uruchomienie | **Gate 4** |
| 12–14 | Kohorta B: dane, kalendarze sesji, model finansowania | **Gate 0B** |
| 15 | Replikacja z zamrożonymi parametrami, jedno uruchomienie | **Gate 5** |

Kohorta B nie opóźnia bramek 0–4. Gdyby weszła do V1, przesunęłaby bramkę 0 o te same 2–3 tygodnie, czyli opóźniła moment, w którym w ogóle zaczynasz mierzyć.

---

# 15. KILL CRITERIA

**Prerejestrowane. Podpisane przed pierwszym backtestem. Nienegocjowalne po fakcie.**

## Gate 0 — infrastruktura (tydzień 4)

STOP, jeśli:
- Strategia losowa **nie** daje expectancy ≈ −koszt (→ model kosztów zepsuty), **lub**
- Luki > 5% barów H1 w godzinach handlowych na ≥2 parach, **lub**
- Spread nie jest odtwarzany z rzeczywistych ticków bid/ask, **lub**
- Model kosztów nie stosuje podłogi `min_roundturn_cost_pips`.

## Gate 1 — rozkład zerowy (tydzień 5)

STOP, jeśli kontrola losowa daje dodatnie expectancy.

## Gate 2 — baseline (tydzień 8) — **BRAMKA GŁÓWNA**

STOP, jeśli V1a **nie spełnia jednocześnie wszystkich** progów z §10.3 oraz nie bije istotnie kontroli losowej.

> **Jeśli Gate 2 nie przechodzi: warstwa techniczna nie ma edge'u na tych danych w tym stylu. Nie dodajemy macro. Nie dodajemy ML. Nie dodajemy reżimów. Nie strojymy parametrów. Kończymy projekt albo wracamy do zupełnie innej hipotezy ekonomicznej.**

## Gate 3 — incremental value (tydzień 10)

- Komponent bez ≥ +0,03 R poza próbą → **usuwamy komponent** (nie strojymy go).
- System nie bije koszyka carry + trend → przechodzimy na koszyk.

## Gate 4 — hold-out (tydzień 11) — jedno uruchomienie

STOP, jeśli:
- Expectancy < 50% wartości z walidacji, **lub**
- Expectancy < +0,05 R, **lub**
- Max DD > 2× max DD z walidacji.

## Gate 0B — infrastruktura kohorty B (tydzień 14)

STOP replikacji (nie całego projektu), jeśli: model finansowania nie da się zwalidować wobec realnych stawek brokera, **lub** kalendarz sesji nie odtwarza luk otwarcia, **lub** historia CFD krótsza niż 6 lat na którymkolwiek instrumencie.

## Gate 5 — replikacja na kohorcie B (tydzień 15) — jedno uruchomienie

Parametry zamrożone hashem gita po bramce 2. **Zero dostrajania.**

Replikacja **potwierdza** edge, jeśli expectancy netto > 0 na ≥3 z 4 instrumentów kohorty B, przy uwzględnieniu pełnego modelu finansowania.

Replikacja **nie potwierdza**, jeśli którykolwiek warunek zawiedzie. Wynik negatywny nie unieważnia bramki 4, ale obniża wiarygodność edge'u i musi być raportowany razem z nim — nigdy przemilczany.

## Warunek awaryjny — jedna próba na kohorcie B po porażce bramki 2

**Zapisany teraz, przed pierwszym backtestem, żeby nie był decyzją post hoc.**

Jeżeli kohorta A nie przejdzie bramki 2, przysługuje **dokładnie jedna** prerejestrowana próba na kohorcie B, z identyczną regułą i identycznymi parametrami. Zero dostrajania. Liczona jako próba w `trials.jsonl`.

Uzasadnienie: FX majors są prawdopodobnie najtrudniejszą klasą aktywów dla metod momentum — brak naturalnych hedgerów o niskiej wrażliwości cenowej i brak kierunkowej premii za ryzyko. Porażka na kohorcie A niesie realne ryzyko fałszywie negatywnego wyniku dla samej metody.

**Jeżeli i ta próba zawiedzie — projekt się kończy.** Bez tego zapisu w tygodniu 8 sam sobie wynegocjujesz „jeszcze jedno podejście", a to już będzie data snooping.

## Kill globalny

| Warunek | Skutek |
|---|---|
| > 50 zalogowanych prób bez przejścia Gate 2 | **STOP** |
| > 4 miesiące pracy bez przejścia Gate 2 | **STOP** |
| Konieczność złamania punktu z checklisty §10.4, by uzyskać dodatni wynik | **STOP natychmiast** — wynik pochodzi z leakage'u |

## Warunki przejścia na prawdziwe pieniądze

Wszystkie jednocześnie:
1. Gate 4 zdany.
2. ≥ 6 miesięcy forward paper tradingu z expectancy w granicach CI z backtestu.
3. Poślizg i spread w paper tradingu ≤ modelowane.
4. Zero ręcznych interwencji w całym okresie paper tradingu.

---

# 16. V2 — po Gate 2 i Gate 3

Każda pozycja to osobny, prerejestrowany eksperyment z własnym progiem.

| # | Komponent | Próg incremental value |
|---|---|---|
| 1 | Trailing chandelier 3×ATR | +0,03 R |
| 2 | Time barrier 5 vs 10 dni | +0,02 R |
| 3 | M15 entry timing | +0,03 R |
| 4 | Dwustanowy reżim zmiennościowy | +0,03 R |
| 5 | Paper trading live | 6 mies. zgodności |
| 6 | Discord | — |
| 7 | Gradient boosting vs logit | +0,05 R |
| 8 | Trading Economics + event surprise | +0,05 R |
| 9 | Drawdown de-risking | Poprawa Calmar bez utraty CAGR |
| 10 | Pyramiding jako nakładka sizingowa | Poprawa Sharpe'a |
| 11 | MCP / dashboard | — |
| 12 | Horyzont 5 dni na kohorcie B | Halvuje koszt finansowania; +0,03 R |
| 13 | Srebro, Nikkei 225 jako rozszerzenie kohorty B | +0,03 R, po potwierdzeniu bramki 5 |
| 14 | Pooling kohort A + B w jednym modelu | Musi pobić oba modele osobne |

**Reguła bez wyjątków: komponent poniżej progu jest usuwany, a nie strojony aż zadziała.**

---

# 17. Elementy usunięte z pierwotnej koncepcji

Pyramiding · ML drzewiaste · HMM/Markov switching · analiza tekstu banków centralnych · event surprise jako alfa · scraping kalendarzy · SMC (BOS/CHoCH/FVG/liquidity/order blocks) · RSI · MACD · ADX · Stochastic · Bollinger · support/resistance · M15 w warstwie sygnału · hierarchia czterech timeframe'ów · hard filter D1 · wymóg pełnej zgodności TF · osobne reguły per instrument · fractional Kelly · osobna warstwa vol-scalingu · drawdown de-risking w V1 · PostgreSQL · TimescaleDB · Redis · FastAPI · React/Next.js · Lightweight Charts · Docker · MCP · Discord · workflow Discord→Claude · OpenBB · social sentiment · CHF

Uzasadnienie każdego usunięcia: `docs/AUDIT_REPORT.md`.

---

# 18. Zasada nadrzędna

> Największym zagrożeniem dla tego projektu nie jest brak przewagi na rynku.
> Największym zagrożeniem jest zbudowanie systemu, który **nie potrafi powiedzieć, że przewagi nie ma**.
>
> Każda decyzja projektowa jest oceniana według jednego kryterium: czy zwiększa, czy zmniejsza zdolność systemu do udzielenia uczciwej odpowiedzi „nie".
