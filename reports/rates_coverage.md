# Pokrycie stóp procentowych

> Wygenerowano: 2026-09-20 14:42 UTC · źródło FRED · 2015-01-01 → 2025-12-31 (132 miesięcy)

## Serie

| Rodzaj | Waluta | Seria | Obserwacji | Od | Do |
|---|---|---|---|---|---|
| overnight | USD | `IRSTCI01USM156N` | 132 | 2015-01-01 | 2025-12-01 |
| overnight | EUR | `IRSTCI01EZM156N` | 132 | 2015-01-01 | 2025-12-01 |
| overnight | GBP | `IRSTCI01GBM156N` | 132 | 2015-01-01 | 2025-12-01 |
| overnight | JPY | `IRSTCI01JPM156N` | 132 | 2015-01-01 | 2025-12-01 |
| overnight | AUD | `IRSTCI01AUM156N` | 132 | 2015-01-01 | 2025-12-01 |
| overnight | CAD | `IRSTCI01CAM156N` | 132 | 2015-01-01 | 2025-12-01 |
| overnight | NZD | `IRSTCI01NZM156N` | 120 | 2015-01-01 | 2024-12-01 |
| overnight | CHF | `IRSTCI01CHM156N` | 111 | 2015-01-01 | 2024-03-01 |
| interbank_3m | USD | `IR3TIB01USM156N` | 131 | 2015-01-01 | 2025-12-01 |
| interbank_3m | EUR | `IR3TIB01EZM156N` | 132 | 2015-01-01 | 2025-12-01 |
| interbank_3m | GBP | `IR3TIB01GBM156N` | 132 | 2015-01-01 | 2025-12-01 |
| interbank_3m | JPY | `IR3TIB01JPM156N` | 132 | 2015-01-01 | 2025-12-01 |
| interbank_3m | AUD | `IR3TIB01AUM156N` | 132 | 2015-01-01 | 2025-12-01 |
| interbank_3m | CAD | `IR3TIB01CAM156N` | 132 | 2015-01-01 | 2025-12-01 |
| interbank_3m | NZD | `IR3TIB01NZM156N` | 132 | 2015-01-01 | 2025-12-01 |
| interbank_3m | CHF | `IR3TIB01CHM156N` | 132 | 2015-01-01 | 2025-12-01 |
| yield_2y | USD | `DGS2` | 2750 | 2015-01-02 | 2025-12-31 |
| yield_2y | EUR | — | **brak** | | |
| yield_2y | GBP | — | **brak** | | |
| yield_2y | JPY | — | **brak** | | |
| yield_2y | AUD | — | **brak** | | |
| yield_2y | CAD | — | **brak** | | |
| yield_2y | NZD | — | **brak** | | |
| yield_2y | CHF | — | **brak** | | |

## Luki w kohorcie A (USD, EUR, GBP, JPY, AUD, CAD)

- `overnight`: **komplet** — 132/132 miesięcy dla każdej waluty
- `interbank_3m`: USD brakuje 1 mies.

## Benchmark carry + trend (SPEC §12) — NIE DA SIĘ POLICZYĆ ZGODNIE ZE SPEC

Benchmark rankuje waluty po `yield_2y`. FRED nie ma tej serii dla: **EUR**, **GBP**, **JPY**, **AUD**, **CAD**, **NZD**, **CHF**.

Wyszukiwanie po nazwie („2-Year Government Benchmark Bond Yield”, „2-year government bond yield”) zwraca wyłącznie Turcję i Meksyk („6-month to 2-year”) oraz serie niezwiązane. To nie jest kwestia identyfikatora — tych danych na FRED nie ma.

Jedyna jednorodna seria terminowa dla wszystkich ośmiu walut to `interbank_3m` (OECD, miesięczna). Podmiana `yield_2y` → `interbank_3m` zmienia benchmark obowiązkowy, więc wymaga ADR-u, a nie decyzji w skrypcie. Alternatywa: inne źródło (OECD.Stat, Investing.com, dane banków centralnych) — osobny odcinek pracy, porównywalny z kalendarzem.
