# Bramka 0 — test negatywny (losowe wejścia)

> Run: `20260919T134506Z-c4710e` · 2015-01-01 → 2016-04-28 · EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, EURJPY
> 20 powtórzeń × 100 wejść na (para, kierunek); 23719 transakcji, 21170 unikalnych, 324 dni roboczych
> Werdykt: **PRZECHODZI**

## Kryteria

| Kryterium | Wynik | Szczegóły |
|---|---|---|
| losowe wejścia: brutto ≈ 0 (E[R] ≈ −koszt) | ✅ | brutto +0.0096 R, CI95 [-0.0267, +0.0445]; netto -0.0010 R vs −koszt -0.0106 R |
| podłoga min_roundturn_cost_pips stosowana | ✅ | 0 z 23719 transakcji poniżej podłogi |
| spread z ticków bid/ask (nie średni, nie mid) | ✅ | wszystkie pary: spread nieujemny i zmienny, ask ≥ bid |
| luki w danych H1 (raport jakości) | ✅ | bez zastrzeżeń |

## Expectancy

Bootstrap blokowy po 20 dni roboczych, 10000 powtórzeń.

| | E[R] | CI95 | SE |
|---|---|---|---|
| netto (R) | -0.0010 | [-0.0369, +0.0336] | 0.0179 |
| brutto (R + koszt) | +0.0096 | [-0.0267, +0.0445] | 0.0181 |
| koszt | 0.0106 | | |

**Rozdzielczość:** połowa CI brutto = 3.4× średni koszt. Test NIE odróżnia kosztu policzonego od pominiętego — to rozstrzyga test martyngałowy na syntetyku i sprawdzenie podłogi per transakcja.

## Per para i kierunek

| Para | Kierunek | n | E[R] | koszt | brutto | trafienia TP | luki |
|---|---|---|---|---|---|---|---|
| AUDUSD | long | 1977 | -0.0593 | 0.0112 | -0.0481 | 0.046 | 0.007 |
| AUDUSD | short | 1974 | -0.0045 | 0.0110 | +0.0065 | 0.088 | 0.002 |
| EURJPY | long | 1981 | -0.0714 | 0.0130 | -0.0584 | 0.120 | 0.038 |
| EURJPY | short | 1973 | +0.1586 | 0.0128 | +0.1714 | 0.144 | 0.004 |
| EURUSD | long | 1969 | +0.0506 | 0.0093 | +0.0600 | 0.152 | 0.014 |
| EURUSD | short | 1980 | -0.0021 | 0.0085 | +0.0064 | 0.087 | 0.004 |
| GBPUSD | long | 1977 | -0.1122 | 0.0091 | -0.1031 | 0.071 | 0.005 |
| GBPUSD | short | 1974 | +0.0401 | 0.0101 | +0.0502 | 0.143 | 0.006 |
| USDCAD | long | 1973 | +0.0753 | 0.0084 | +0.0837 | 0.126 | 0.005 |
| USDCAD | short | 1977 | -0.0658 | 0.0099 | -0.0559 | 0.074 | 0.005 |
| USDJPY | long | 1982 | -0.0639 | 0.0108 | -0.0531 | 0.079 | 0.001 |
| USDJPY | short | 1982 | +0.0434 | 0.0131 | +0.0565 | 0.138 | 0.001 |

Pojedyncze wiersze są silnie autokorelowane (nakładanie się okien) — informacyjnie, bez testów istotności.

## Spread M1 (pipsy)

| Para | min | mediana | p99 | różnych wartości | udział 0 | ujemnych |
|---|---|---|---|---|---|---|
| EURUSD | 0.10 | 0.30 | 1.70 | 182 | 0.0000 | 0 |
| GBPUSD | 0.10 | 1.00 | 4.90 | 436 | 0.0000 | 0 |
| USDJPY | 0.10 | 0.40 | 2.20 | 225 | 0.0000 | 0 |
| AUDUSD | 0.10 | 1.10 | 3.50 | 296 | 0.0000 | 0 |
| USDCAD | 0.10 | 1.20 | 5.10 | 340 | 0.0000 | 0 |
| EURJPY | 0.10 | 0.80 | 3.90 | 450 | 0.0000 | 0 |
