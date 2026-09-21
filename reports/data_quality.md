# Raport jakości danych

> Wygenerowano: 2026-09-21 15:09 UTC
> Bramka 0: **NIE PRZECHODZI**

## Powody odrzucenia

- 3 godzin podejrzanych o awarię feedu — wymagają ręcznego sprawdzenia przed akceptacją danych

## Pokrycie

| Symbol | Bary H1 | Oczekiwane | Brakujące | Luki % | Od | Do |
|---|---|---|---|---|---|---|
| AUDUSD | 43,629 | 43,634 | 5 | 0.01 | 2015-01-01 | 2021-12-31 |
| EURJPY | 43,630 | 43,634 | 4 | 0.01 | 2015-01-01 | 2021-12-31 |
| EURUSD | 43,631 | 43,634 | 3 | 0.01 | 2015-01-01 | 2021-12-31 |
| GBPUSD | 43,628 | 43,634 | 6 | 0.01 | 2015-01-01 | 2021-12-31 |
| USDCAD | 43,628 | 43,634 | 6 | 0.01 | 2015-01-01 | 2021-12-31 |
| USDJPY | 43,629 | 43,634 | 5 | 0.01 | 2015-01-01 | 2021-12-31 |

## Spread (w pipsach)

| Symbol | close mediana | close p95 | max mediana | max p95 | max zaobserwowany | ticki/bar |
|---|---|---|---|---|---|---|
| AUDUSD | 1.00 | 2.20 | 1.40 | 5.50 | 35.00 | 2,631 |
| EURJPY | 0.60 | 2.50 | 1.10 | 7.10 | 37.50 | 5,590 |
| EURUSD | 0.30 | 1.10 | 0.60 | 3.40 | 34.40 | 3,582 |
| GBPUSD | 0.90 | 3.40 | 1.50 | 8.10 | 40.00 | 3,668 |
| USDCAD | 1.10 | 2.90 | 1.60 | 6.80 | 35.00 | 2,984 |
| USDJPY | 0.30 | 1.30 | 0.70 | 4.20 | 35.00 | 2,927 |

## Podejrzenie awarii feedu

**3 godzin** bez danych u wszystkich par jednocześnie, mimo że wg wyprowadzonego kalendarza są handlowe.

To podpis awarii feedu, nie zamknięcia rynku. Wymaga ręcznego sprawdzenia przed akceptacją danych — inaczej luka pozostanie niewidoczna dla backtestu.

| Godzina UTC |
|---|
| 2016-09-02 18:00 |
| 2017-12-24 22:00 |
| 2019-05-26 22:00 |

## Zamknięcia świąteczne

Godziny puste u wszystkich par w blokach dotykających 25.12 albo 1.01 (≤ 36 h). Nie liczone jako luki ani awarie.

| Data | Godzin |
|---|---|
| 2015-12-25 | 13 |
| 2015-12-31 | 2 |
| 2016-01-01 | 21 |
| 2017-12-25 | 14 |
| 2017-12-31 | 2 |
| 2018-01-01 | 22 |
| 2018-12-25 | 14 |
| 2018-12-31 | 1 |
| 2019-01-01 | 22 |
| 2019-12-25 | 14 |
| 2019-12-31 | 2 |
| 2020-01-01 | 22 |
| 2020-12-25 | 13 |
| 2020-12-31 | 2 |
| 2021-01-01 | 21 |

## Komórki niejednoznaczne

Pokrycie między 20% a 80% — ani stabilnie handlowe, ani zamknięte. Typowo granica DST (otwarcie niedzielne przesuwa się między 21:00 a 22:00 UTC), ale systematyczna awaria wygląda tak samo.

| Symbol | Dzień tyg. | Godz. UTC | Pokrycie |
|---|---|---|---|
| AUDUSD | 5 | 21 | 34% |
| AUDUSD | 7 | 21 | 65% |
| EURJPY | 5 | 21 | 34% |
| EURJPY | 7 | 21 | 65% |
| EURUSD | 5 | 21 | 34% |
| EURUSD | 7 | 21 | 65% |
| GBPUSD | 5 | 21 | 34% |
| GBPUSD | 7 | 21 | 65% |
| USDCAD | 5 | 21 | 34% |
| USDCAD | 7 | 21 | 65% |
| USDJPY | 5 | 21 | 34% |
| USDJPY | 7 | 21 | 65% |
