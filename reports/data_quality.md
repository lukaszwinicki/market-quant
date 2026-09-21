# Raport jakości danych

> Wygenerowano: 2026-09-21 16:16 UTC
> Bramka 0: **PRZECHODZI**

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

Wykryto 3, wszystkie zaakceptowane ręcznie — patrz sekcja niżej. Brak godzin nierozstrzygniętych.

## Zaakceptowane ręcznie (ADR-045)

**3 godzin** wykrytych przez detektor i zaakceptowanych jawnie w `data.quality.accepted_outages`. Detektor NIE został osłabiony — każda z tych godzin nadal jest wykrywana.

| Godzina UTC | Powód | Dowód | Zaakceptowano |
|---|---|---|---|
| 2016-09-02 18:00 | awaria feedu Dukascopy wewnatrz dnia handlowego, ~1-2 h | 17:00 = 4,5-8,9 kB (zapadniete ~10x), 18:00 = 0 na 6 parach, 19:00 = 20-40 kB; 1 bar H1 z 43 634 na pare, 0 transakcji bez etykiety (reports/gate0_dropped.md) | 2026-09-21 |
| 2017-12-24 22:00 | opoznione otwarcie tygodnia (Wigilia) — rynek stal, nie awaria | caly blok 18:00-22:00 = 0 na 6 parach, dane wracaja o 23:00 (0,5-1,7 kB); brak barow w kazdym zrodle, wiec nie ma czego odzyskac | 2026-09-21 |
| 2019-05-26 22:00 | opoznione otwarcie tygodnia — poniedzialek 27.05.2019 to Memorial Day i UK spring bank holiday | blok 18:00-22:00 = 0 na 6 parach, 23:00 = 0-53 B, 00:00 = 6-34 kB | 2026-09-21 |

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
