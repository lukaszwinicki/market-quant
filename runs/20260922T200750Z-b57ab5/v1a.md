# V1a — przebieg na segmencie RESEARCH

> Run: `20260922T200750Z-b57ab5` · 2016-01-01 → 2021-12-31 · EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, EURJPY
> Dane od 2015-01-01 (rok rozgrzewki cech, bez decyzji)
> 7 wariantów siatki (ADR-028), N w DSR = 8 (ADR-029); raportowany jest baseline
> Werdykt liczonych kryteriów: **NIE PRZECHODZI** — niepełny, patrz niżej

**Koszyk §12 jest ZAWĘŻONY względem specyfikacji** (ADR-038): carry mierzy `interbank_3m`, nie `yield_2y` — tej serii nie ma w jednej definicji dla ośmiu walut (`reports/yield2y_sources.md`); uniwersum to pięć walut kohorty A vs USD zamiast ośmiu, bo NZDUSD i USDCHF nie są pobierane, a CHF jest wykluczony w sekcji `instruments` z `frozen: true`. Nogi: long top-1, short bottom-1. Prior z literatury dotyczy koszyków G10 i stosuje się do tego koszyka słabiej.

Nie jest liczona kontrola §10.2 nr 10 (rozkład zerowy per kohorta). Kontrola nr 9 (buy & hold per instrument) jest policzona dla kohorty A jako ramię 4b (ADR-044); dla kohorty B zostaje otwarta.

## Kryteria bramki 2

| Kryterium | Wynik | Szczegóły |
|---|---|---|
| expectancy netto ≥ +0.10 R | ❌ | -0.0560 R, CI95 [-0.1225, +0.0119] |
| t ≥ 2.0 | ❌ | t = -1.62 (bootstrap blokowy, 20 dni) |
| DSR ≥ 0.95 (ADR-027) | ❌ | DSR = 0.174, SR -0.0601 vs SR*₀ +0.0131, N = 8, n_eff = 172 |
| PBO ≤ 0.3 | ❌ | PBO = 0.612 z 7 wariantów |
| dodatnie przy 2× kosztach | ❌ | 1×: -0.0560 · 2×: -0.0730 · 3×: -0.0899 |
| dodatnie na CAŁEJ osi marży (ADR-037) | ❌ | 0.5%: -0.0560 · 1%: -0.0673 · 2%: -0.0899 |
| ≥ 4 par dodatnich | ❌ | 1 z 6 |
| ≥ 2 podokresy dodatnie | ❌ | 2016-01..2017-12: -0.1019 · 2017-12..2020-01: -0.0381 · 2020-01..2021-12: -0.0290 |
| płaskowyż (ADR-028) | ❌ | baseline -0.0560 R ≤ 0 — płaskowyż nie ma czego potwierdzać |
| kontrola #1: p < 0.05 wobec losowych wejść (ADR-048) | ❌ | p = 0.8010 z 200 powtórzeń (najniższe osiągalne 0.0050) |
| kontrola #5: koszyk carry + trend (§12) pobity | ❌ | ΔSharpe +0.0450, CI95 [-0.0758, +0.1684]; strategia -0.0536 przy 4.60 R otwartego ryzyka, koszyk -0.0986 przy 2.00 R |
| kontrola #4: carry-only pobity (ADR-044) | ❌ | ΔSharpe -0.0336, CI95 [-0.2128, +0.1267]; strategia -0.0682 przy 4.60 R otwartego ryzyka, carry-only -0.0346 przy 2.00 R |

## Próba

- transakcji baseline: **889**, efektywnych (nienakładających się): **172**, nakładanie 95.9%
- do testów istotności wchodzi n_eff, nie liczba wierszy

## Log decyzji (każdy zamknięty bar H1, ADR-033)

| Powód | barów (pierwszy) | udział | barów (zadziałał) |
|---|---|---|---|
| `no_signal` | 159202 | 70.939% | 159202 |
| `6_open_position` | 10815 | 4.819% | 53292 |
| `4_ccy_limit` | 39729 | 17.703% | 41449 |
| `5_portfolio` | 8854 | 3.945% | 17286 |
| `8_rollover` | 51 | 0.023% | 9342 |
| `1_blackout` | 2304 | 1.027% | 7699 |
| `9_friday` | 25 | 0.011% | 5592 |
| `2_vol_pct` | 1322 | 0.589% | 5433 |
| `10_sunday_open` | 26 | 0.012% | 3078 |
| `split_boundary` | 326 | 0.145% | 1434 |
| `warmup` | 876 | 0.390% | 876 |
| `no_fill` | 1 | 0.000% | 1 |
| `enter` | 889 | 0.396% | — |

„Pierwszy” to powód o najwyższym priorytecie ADR-033; „zadziałał” — ile barów warunek obejmował niezależnie od priorytetu. Warunek o niskim priorytecie może mieć zero w pierwszej kolumnie i tysiące w drugiej.

## Koszt 1×, 2×, 3× (§9)

| Koszt | E[R] | modelowany koszt (R) | dodatnie |
|---|---|---|---|
| 1× | -0.0560 | 0.0281 | NIE |
| 2× | -0.0730 | 0.0451 | NIE |
| 3× | -0.0899 | 0.0620 | NIE |

Finansowanie jest w każdym scenariuszu ODEJMOWANE, ale nie skalowane mnożnikiem — swap rośnie z dni trzymania i różnicy stóp, a nie z warunków brokera na spreadzie (ADR-035, ADR-037).

## Oś marży swapu (ADR-037, OBOWIĄZKOWA)

| Marża brokera | E[R] | średni swap (R) | dodatnie |
|---|---|---|---|
| 0.5% | -0.0560 | +0.0112 | NIE |
| 1% | -0.0673 | +0.0225 | NIE |
| 2% | -0.0899 | +0.0450 | NIE |

Marża jest jedyną liczbą w modelu kosztów bez sparsowanego źródła. Werdykt zależny wyłącznie od wartości punktowej jest nieważny.

## Warianty siatki (ADR-028)

| Wariant | Donchian | SL | TP | n | E[R] |
|---|---|---|---|---|---|
| baseline | 55 | 2 | 4 | 889 | -0.0560 |
| D- | 40 | 2 | 4 | 918 | -0.0498 |
| D+ | 70 | 2 | 4 | 875 | -0.0477 |
| S- | 55 | 1.5 | 4 | 987 | -0.0444 |
| S+ | 55 | 2.5 | 4 | 850 | -0.0303 |
| T- | 55 | 2 | 3 | 938 | -0.0528 |
| T+ | 55 | 2 | 5 | 882 | -0.0529 |

## CPCV (ADR-031)

6 grup, 2 testowe → 15 podziałów. Purge zjada średnio 1.5% próby, embargo 0.4%.

**Pięć ścieżek backtestu jest tu zdegenerowane.** V1a niczego nie dopasowuje, więc transakcje danej grupy są identyczne w każdym podziale, w którym jest ona grupą testową — każda ścieżka odtwarza pełną próbę. Poniżej rozrzut po PODZIAŁACH, który mierzy zależność wyniku od okresu, a nie przeuczenie.

- E[R] w częściach testowych: mediana -0.0381, min -0.1356, max -0.0020, dodatnich 0/15

## Podokresy (§10.3)

| Okres | n | E[R] |
|---|---|---|
| 2016-01..2017-12 | 291 | -0.1019 |
| 2017-12..2020-01 | 310 | -0.0381 |
| 2020-01..2021-12 | 288 | -0.0290 |

## Per para i kierunek (kontrola #8)

| Para | Kierunek | n | E[R] | koszt | przed kosztem | trafienia TP | luki |
|---|---|---|---|---|---|---|---|
| AUDUSD | long | 71 | +0.0299 | 0.0121 | +0.0420 | 0.056 | 0.000 |
| AUDUSD | short | 71 | +0.0339 | 0.0143 | +0.0483 | 0.070 | 0.014 |
| EURJPY | long | 94 | -0.1137 | 0.0151 | -0.0986 | 0.053 | 0.000 |
| EURJPY | short | 84 | -0.0959 | 0.0159 | -0.0800 | 0.119 | 0.024 |
| EURUSD | long | 72 | -0.0075 | 0.0106 | +0.0031 | 0.069 | 0.000 |
| EURUSD | short | 67 | -0.0112 | 0.0117 | +0.0005 | 0.045 | 0.015 |
| GBPUSD | long | 75 | -0.1902 | 0.0078 | -0.1824 | 0.053 | 0.000 |
| GBPUSD | short | 66 | +0.0176 | 0.0094 | +0.0270 | 0.091 | 0.015 |
| USDCAD | long | 76 | -0.0512 | 0.0109 | -0.0403 | 0.079 | 0.013 |
| USDCAD | short | 69 | -0.1094 | 0.0101 | -0.0992 | 0.029 | 0.014 |
| USDJPY | long | 70 | -0.0420 | 0.0118 | -0.0302 | 0.043 | 0.014 |
| USDJPY | short | 74 | -0.0923 | 0.0127 | -0.0797 | 0.108 | 0.027 |

## Kontrole §10.2

| # | Kontrola | Wynik |
|---|---|---|
| 1 | losowe wejścia, ta sama liczba na (para, kierunek) | E[R] strategii -0.0560 vs mediana losowych -0.0288, p = 0.8010 |
| 2 | przetasowane wyniki (pula 35638 zdarzeń) | mediana rozkładu zerowego -0.0288, p = 0.8109 |
| 3 | cechy starsze o bar — wynik NIE MOŻE rosnąć | -0.0268 R na 893 transakcjach (ROŚNIE — sprawdź off-by-one) |
| 7 | permutacja kolejności DNI | max DD 52.13 R, p = 0.9403 (duże p = obsunięcie typowe) |

Rozkład zerowy kontroli #2 jest wyśrodkowany na średniej PULI, nie na zerze — pytanie brzmi „czy wybór jest lepszy niż losowy”, a nie „czy wynik jest dodatni”.

## Kontrola #5 — koszyk carry + trend (§12)

Werdykt: **NIE POBITY** — ΔSharpe +0.0450, CI95 [-0.0758, +0.1684] (1053 dni, 10000 replikacji; te same bloki dla obu serii).

| | Sharpe | średnie dzienne R | średnie otwarte ryzyko |
|---|---|---|---|
| V1a | -0.0536 | -0.0473 | 4.60 R |
| koszyk §12 | -0.0986 | -0.0211 | 2.00 R |

Kryterium jest bezskalowe (Sharpe), bo obie serie chodzą na różnych budżetach ryzyka — kolumna „otwarte ryzyko” pokazuje, jak bardzo. Porównanie średnich dziennych R faworyzowałoby stronę o większej ekspozycji bez żadnej przewagi (ADR-040).

### Per kotwica rebalansu (ADR-039, ADR-040 pkt 5)

| Kotwica | E[R] na transakcję | rebalansów | pominiętych tygodni | transakcji |
|---|---|---|---|---|
| poniedziałek | -0.2107 | 313 | 0 | 158 |
| wtorek | -0.1141 | 313 | 0 | 171 |
| środa | -0.0556 | 313 | 0 | 162 |
| czwartek | -0.0736 | 313 | 0 | 157 |
| piątek | -0.2337 | 314 | 0 | 162 |

Rozrzut między kotwicami to JEDYNA kontrola wrażliwości, jaką ten koszyk ma — V1a ma siatkę z ADR-028, koszyk nie ma nic. Wynik koszyka jest średnią z pięciu podportfeli, każdy z piątą częścią kapitału.

## Kontrola #4 — carry-only i buy & hold (§10.2, ADR-044)

### 4a — carry-only (ramię rozstrzygające)

Werdykt: **NIE POBITY** — ΔSharpe -0.0336, CI95 [-0.2128, +0.1267] (651 dni, 9960 replikacji; te same bloki dla obu serii).

| | Sharpe | średnie dzienne R | średnie otwarte ryzyko |
|---|---|---|---|
| V1a | -0.0682 | -0.0765 | 4.60 R |
| carry-only | -0.0346 | -0.0058 | 2.00 R |

Ablacja koszyka §12: ta sama konstrukcja, ranking bez członu momentum (ADR-044). Ranking §12 jest zdominowany przez momentum — 4,2× większy rozrzut przekrojowy (ADR-039) — więc dopiero to ramię mierzy, czy strategia bije sam carry. Zero parametrów swobodnych.

| Kotwica | E[R] na transakcję | pominiętych tygodni |
|---|---|---|
| poniedziałek | -0.6262 | 0 |
| wtorek | -0.4124 | 0 |
| środa | -0.8511 | 0 |
| czwartek | -0.2928 | 0 |
| piątek | -0.9520 | 0 |

### 4b — buy & hold (diagnostyka, NIE próg)

| Para | suma R (long, całe okno) |
|---|---|
| AUDUSD | +4.449 |
| EURJPY | -2.090 |
| EURUSD | -0.272 |
| GBPUSD | -7.142 |
| USDCAD | -9.185 |
| USDJPY | -3.811 |
| **razem** | **-18.052** |
| *V1a, dla porównania* | *-49.812* |

**Bez werdyktu i bez Sharpe'a, celowo.** FX nie ma broniącego się kierunku pasywnego — long jest tak samo arbitralny jak short, więc poprzeczka zależałaby od tego, w którą stronę poszedł dolar w tej próbie. Dodatkowo jedna noga na parę wrzuca całe R w dzień wejścia, więc jej Sharpe byłby artefaktem przypisania (ADR-044). To ramię mierzy, ile z wyniku dałby sam statyczny dryf kierunkowy — tę samą kwestię, co kontrola #8, widzianą od zewnątrz.

Realizuje §10.2 #9 („buy & hold per instrument”) dla kohorty A. Dla kohorty B #9 zostaje otwarte jako próg.

