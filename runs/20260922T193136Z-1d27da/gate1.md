# Bramka 1 — rozkład zerowy z kontroli losowej

> Run: `20260922T193136Z-1d27da` · 2015-01-01 → 2021-12-31 · EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, EURJPY
> 200 powtórzeń × 100 wejść na (para, kierunek); 237654 transakcji, 191767 unikalnych (1821 bez wyniku), 1802 dni roboczych
> Werdykt: **PRZECHODZI**

## Kryterium (§15, ADR-046)

| Warunek | Wynik | Szczegóły |
|---|---|---|
| kontrola losowa nie zarabia: E[R] netto < 0 | ✅ | netto -0.0261 R, koszt 0.0116 R, finansowanie +0.0107 R (dodatnie = koszt) |
| dodatni wynik nie jest istotny: dolny koniec CI95 ≤ 0 | ✅ | CI95 [-0.0402, -0.0122], SE 0.0072, 237654 transakcji w 1802 dniach |
| rozkład zerowy nadaje się na benchmark: ≥ 30 powtórzeń, niezerowy rozrzut | ✅ | 200 powtórzeń, SD 0.0273 R, 1188 transakcji na powtórzenie |

Werdykt `NIEROZSTRZYGNIĘTE` (średnia ≥ 0, ale CI95 zawiera 0) nie jest przejściem ani STOP-em: przy koszcie rzędu 0,01 R sama losowość wyrzuca średnią nad zero na tyle często, że automatyczna decyzja byłaby decyzją szumu. Rozstrzyga człowiek — po dołożeniu danych albo powtórzeń.

## Expectancy netto (po koszcie i po finansowaniu)

Bootstrap blokowy po 20 dni roboczych, 10000 powtórzeń.

| | E[R] | CI95 | SE |
|---|---|---|---|
| netto (R) | -0.0261 | [-0.0402, -0.0122] | 0.0072 |

Średni koszt 0.0116 R, średni koszt finansowania +0.0107 R (dodatnie = koszt; marża 0.5% rocznie, stopy `overnight`). Bez finansowania wynik netto to -0.0154 R — ta liczba jest porównywalna z raportem bramki 0.

## Rozkład zerowy

| powtórzeń | transakcji na powtórzenie | średnia | SD | 2,5% | mediana | 97,5% | udział dodatnich |
|---|---|---|---|---|---|---|---|
| 200 | 1188 | -0.0261 | 0.0273 | -0.0770 | -0.0272 | +0.0264 | 0.170 |

Pełny rozkład: `null.parquet` (jedna średnia na powtórzenie).

**To nie jest rozkład zerowy bramki 2.** SD skaluje się jak 1/√(liczba transakcji w powtórzeniu), a bramka 2 porównuje strategię z kontrolą o tej samej liczebności co strategia (§10.2 #1) — tę liczy sam przebieg V1a. Tutaj liczebność jest deklarowana z góry i zrównoważona kierunkowo, żeby dryf par nie udawał wyniku.

Wejścia losowe nie respektują blackoutu makro (§7.2) ani limitu jednej pozycji na parę — tak samo jak kontrola #1 w przebiegu V1a, z którą ten rozkład ma być porównywalny.

## Per para i kierunek

| Para | Kierunek | n | E[R] | koszt | finansowanie | trafienia TP |
|---|---|---|---|---|---|---|
| AUDUSD | long | 19810 | -0.0405 | 0.0132 | +0.0048 | 0.042 |
| AUDUSD | short | 19796 | -0.0061 | 0.0132 | +0.0128 | 0.065 |
| EURJPY | long | 19822 | -0.0550 | 0.0146 | +0.0186 | 0.065 |
| EURJPY | short | 19783 | -0.0054 | 0.0150 | +0.0027 | 0.066 |
| EURUSD | long | 19816 | -0.0447 | 0.0107 | +0.0438 | 0.069 |
| EURUSD | short | 19820 | -0.0072 | 0.0105 | -0.0206 | 0.050 |
| GBPUSD | long | 19783 | -0.0290 | 0.0090 | +0.0191 | 0.065 |
| GBPUSD | short | 19792 | -0.0246 | 0.0089 | -0.0000 | 0.059 |
| USDCAD | long | 19833 | +0.0208 | 0.0102 | +0.0097 | 0.059 |
| USDCAD | short | 19795 | -0.0484 | 0.0101 | +0.0134 | 0.044 |
| USDJPY | long | 19802 | -0.0359 | 0.0117 | -0.0102 | 0.048 |
| USDJPY | short | 19802 | -0.0373 | 0.0120 | +0.0348 | 0.083 |

Wiersze są silnie autokorelowane (okna się nakładają) — informacyjnie, bez testów istotności.
