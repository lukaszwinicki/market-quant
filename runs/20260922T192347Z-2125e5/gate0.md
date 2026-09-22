# Bramka 0 — test negatywny (losowe wejścia)

> Run: `20260922T192347Z-2125e5` · 2015-01-01 → 2021-12-31 · EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, EURJPY
> 20 powtórzeń × 100 wejść na (para, kierunek); 23770 transakcji, 23492 unikalnych (226 bez wyniku: NO_DATA lub brak danych w chwili decyzji), 1801 dni roboczych
> Werdykt: **PRZECHODZI**

## Kryteria (ADR-025)

| Kryterium | Wynik | Szczegóły |
|---|---|---|
| a. rachunek kosztu per transakcja (podłoga, spread raz) | ✅ | 0 z 23770 transakcji łamie cost = max(spread, podłoga) lub r = gross − dopłata |
| b. martyngał (syntetyk): E[R] = −koszt przy koszcie 0,5 R | ✅ | `test_random_entries_on_random_walk_lose_exactly_the_cost`: 1 passed in 2.49s |
| c. losowe wejścia: CI95 przed kosztem ∋ 0, połowa CI ≤ 0.05 R | ✅ | przed kosztem +0.0010 R, CI95 [-0.0174, +0.0195], połowa 0.0185 R; netto -0.0106 R vs −koszt -0.0116 R |
| spread z ticków bid/ask (nie średni, nie mid) | ✅ | wszystkie pary: spread nieujemny i zmienny, ask ≥ bid |
| luki w danych H1 (raport jakości) | ✅ | bez zastrzeżeń |

## Expectancy

Bootstrap blokowy po 20 dni roboczych, 10000 powtórzeń.

| | E[R] | CI95 | SE |
|---|---|---|---|
| netto (R) | -0.0106 | [-0.0289, +0.0081] | 0.0094 |
| przed kosztem (R + koszt) | +0.0010 | [-0.0174, +0.0195] | 0.0094 |
| koszt | 0.0116 | | |

**Rozdzielczość:** połowa CI przed kosztem = 1.6× średni koszt. Część c NIE odróżnia kosztu policzonego od pominiętego — to rozstrzygają części a i b.

## Koszt 1×, 2×, 3× (§9)

Na losowych wejściach to nie jest kryterium — expectancy ma tu być ujemne. Tabela jest w raporcie, żeby ten sam rachunek był widoczny wszędzie, gdzie raportujemy expectancy.

| Koszt | E[R] | modelowany koszt (R) | dodatnie |
|---|---|---|---|
| 1× | -0.0106 | 0.0171 | NIE |
| 2× | -0.0277 | 0.0343 | NIE |
| 3× | -0.0448 | 0.0514 | NIE |

## Per para i kierunek

| Para | Kierunek | n | E[R] | koszt | przed kosztem | trafienia TP | luki |
|---|---|---|---|---|---|---|---|
| AUDUSD | long | 1978 | -0.0604 | 0.0132 | -0.0471 | 0.039 | 0.003 |
| AUDUSD | short | 1978 | +0.0554 | 0.0132 | +0.0685 | 0.064 | 0.006 |
| EURJPY | long | 1980 | -0.0468 | 0.0146 | -0.0323 | 0.064 | 0.011 |
| EURJPY | short | 1977 | -0.0156 | 0.0149 | -0.0007 | 0.067 | 0.009 |
| EURUSD | long | 1984 | -0.0095 | 0.0108 | +0.0013 | 0.069 | 0.010 |
| EURUSD | short | 1984 | -0.0435 | 0.0105 | -0.0330 | 0.048 | 0.009 |
| GBPUSD | long | 1977 | +0.0100 | 0.0091 | +0.0191 | 0.068 | 0.005 |
| GBPUSD | short | 1985 | -0.0366 | 0.0088 | -0.0277 | 0.059 | 0.005 |
| USDCAD | long | 1984 | +0.0397 | 0.0102 | +0.0499 | 0.062 | 0.007 |
| USDCAD | short | 1981 | +0.0332 | 0.0099 | +0.0431 | 0.049 | 0.004 |
| USDJPY | long | 1976 | -0.0566 | 0.0117 | -0.0449 | 0.044 | 0.010 |
| USDJPY | short | 1986 | +0.0036 | 0.0118 | +0.0154 | 0.088 | 0.011 |

Pojedyncze wiersze są silnie autokorelowane (nakładanie się okien) — informacyjnie, bez testów istotności.

## Spread M1 (pipsy)

| Para | min | mediana | p99 | różnych wartości | udział 0 | ujemnych |
|---|---|---|---|---|---|---|
| EURUSD | 0.10 | 0.30 | 2.00 | 338 | 0.0000 | 0 |
| GBPUSD | 0.10 | 0.90 | 6.00 | 688 | 0.0000 | 0 |
| USDJPY | 0.10 | 0.30 | 2.50 | 386 | 0.0000 | 0 |
| AUDUSD | 0.10 | 1.00 | 3.50 | 477 | 0.0000 | 0 |
| USDCAD | 0.10 | 1.10 | 5.30 | 572 | 0.0000 | 0 |
| EURJPY | 0.10 | 0.60 | 4.40 | 878 | 0.0000 | 0 |
