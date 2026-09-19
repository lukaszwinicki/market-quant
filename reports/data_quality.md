# Raport jakości danych

> Wygenerowano: 2026-09-19 13:01 UTC
> Bramka 0: **PRZECHODZI**

## Pokrycie

| Symbol | Bary H1 | Oczekiwane | Brakujące | Luki % | Od | Do |
|---|---|---|---|---|---|---|
| AUDUSD | 8,263 | 8,266 | 3 | 0.04 | 2015-01-01 | 2016-04-29 |
| EURJPY | 8,265 | 8,266 | 1 | 0.01 | 2015-01-01 | 2016-04-29 |
| EURUSD | 8,229 | 8,265 | 36 | 0.44 | 2015-01-01 | 2016-04-28 |
| GBPUSD | 8,244 | 8,266 | 22 | 0.27 | 2015-01-01 | 2016-04-29 |
| USDCAD | 8,264 | 8,266 | 2 | 0.02 | 2015-01-01 | 2016-04-29 |
| USDJPY | 8,260 | 8,266 | 6 | 0.07 | 2015-01-01 | 2016-04-29 |

## Spread (w pipsach)

| Symbol | close mediana | close p95 | max mediana | max p95 | max zaobserwowany | ticki/bar |
|---|---|---|---|---|---|---|
| AUDUSD | 1.10 | 2.40 | 1.60 | 6.30 | 35.00 | 2,933 |
| EURJPY | 0.80 | 2.90 | 1.40 | 8.20 | 35.00 | 5,502 |
| EURUSD | 0.30 | 1.20 | 0.80 | 3.90 | 34.30 | 3,724 |
| GBPUSD | 1.00 | 3.20 | 1.60 | 8.10 | 39.70 | 3,404 |
| USDCAD | 1.20 | 3.00 | 1.90 | 7.40 | 34.70 | 2,940 |
| USDJPY | 0.40 | 1.50 | 0.80 | 4.60 | 32.50 | 3,169 |

## Podejrzenie awarii feedu

Brak — żadna godzina handlowa nie jest pusta u wszystkich par naraz.

## Zamknięcia świąteczne

Godziny puste u wszystkich par w blokach dotykających 25.12 albo 1.01 (≤ 36 h). Nie liczone jako luki ani awarie.

| Data | Godzin |
|---|---|
| 2015-12-25 | 13 |
| 2015-12-31 | 2 |
| 2016-01-01 | 21 |

## Komórki niejednoznaczne

Pokrycie między 20% a 80% — ani stabilnie handlowe, ani zamknięte. Typowo granica DST (otwarcie niedzielne przesuwa się między 21:00 a 22:00 UTC), ale systematyczna awaria wygląda tak samo.

| Symbol | Dzień tyg. | Godz. UTC | Pokrycie |
|---|---|---|---|
| AUDUSD | 5 | 21 | 39% |
| AUDUSD | 7 | 21 | 59% |
| EURJPY | 5 | 21 | 39% |
| EURJPY | 7 | 21 | 59% |
| EURUSD | 5 | 21 | 39% |
| EURUSD | 7 | 21 | 58% |
| GBPUSD | 5 | 21 | 39% |
| GBPUSD | 7 | 21 | 59% |
| USDCAD | 5 | 21 | 39% |
| USDCAD | 7 | 21 | 59% |
| USDJPY | 5 | 21 | 39% |
| USDJPY | 7 | 21 | 59% |
