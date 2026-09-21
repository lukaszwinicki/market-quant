# Bramka 0 — 237 transakcji bez wyniku: rozkład i przyczyna

> Pomiar 2026-09-21, przebieg `20260921T151443Z-187ab1` (2015-01-01 → 2021-12-31,
> 6 par kohorty A, 20 × 100 wejść na (para, kierunek), ziarno 0).
> Diagnostyka tylko do odczytu, BEZ wpisu do `trials.jsonl`.

## Metoda

`make_evaluator` trzyma `evaluate.memo` z kluczem `(para, moment, kierunek)`
(`src/validation/gate0.py:114`). Transakcja, dla której `label_events` nie
zwróciło żadnego wiersza, siedzi tam jako wartość `None`
(`src/validation/gate0.py:129`). Pełna lista jest więc dostępna bez
odtwarzania strumienia losowego — wystarczy powtórzyć pipeline z tymi samymi
parametrami i przeczytać `memo`.

Odtworzone dokładnie: 23 488 unikalnych transakcji, **237 bez wyniku** (1,01%),
23 251 z etykietą — zgodnie z `metrics.json`.

## Wynik: 91% to ostatni bar tygodnia

| Grupa | n | udział |
|---|---|---|
| piątek 21:00 i 22:00 (ostatni bar tygodnia) | **215** | 90,7% |
| zamknięcia świąteczne (24.12, 25.12, 31.12) | 9 | 3,8% |
| pojedyncze godziny cienkiej płynności | 13 | 5,5% |
| **z 3 godzin podejrzanych o awarię feedu** | **0** | 0% |

### Piątkowy bar: rozkład idealnie zgodny z czasem letnim

Odpada dokładnie ten bar, którego **moment decyzji** (etykieta bara + 1 h)
wypada po zamknięciu rynku w piątek o 17:00 czasu Nowego Jorku.

| Miesiąc | 21:00 odpada | 21:00 zostaje | 22:00 odpada | 22:00 zostaje |
|---|---|---|---|---|
| I | 0 | 16 | 16 | 0 |
| II | 0 | 14 | 25 | 0 |
| III | 8 | 9 | 5 | 0 |
| IV–X | 123 | **0** | 0 | 0 |
| XI | 5 | 15 | 13 | 0 |
| XII | 0 | 18 | 20 | 0 |

Czas letni (IV–X): zamknięcie o 21:00 UTC, więc bar 21:00 odpada w 100%
przypadków (0 zostaje), a bar 22:00 w ogóle nie istnieje.
Czas zimowy (XI–III): zamknięcie o 22:00 UTC, bar 21:00 przechodzi w 100%,
odpada bar 22:00. Marzec i listopad dzielą się zgodnie z datą zmiany czasu.

Dla porównania tło: każda inna komórka (dzień tygodnia × godzina) ma
160–230 transakcji z etykietą i zero albo jedną bez wyniku.

### Pozostałe 22

Święta — moment decyzji w zamkniętym rynku: 2015-12-25 08:00 (×2),
2015-12-31 22:00 (×2), 2018-12-24 22:00, 2018-12-31 23:00, 2019-12-25 08:00,
2020-12-25 07:00, 2020-12-25 08:00.

Pojedyncze godziny, w większości 21:00 UTC w dzień powszedni (najcieńsza
godzina doby — brak ticku w minucie decyzji): 2018-05-30, 2018-09-04,
2019-07-25, 2019-10-16, 2020-04-13, 2020-07-28, 2021-06-22 (×2), 2021-07-21,
2021-08-11. Plus trzy nietypowe: 2015-04-22 13:00, 2015-05-06 13:00,
2016-12-19 03:00.

### Trzy godziny podejrzane o awarię feedu nie dają ANI JEDNEJ

2016-09-02 18:00, 2017-12-24 22:00 i 2019-05-26 22:00 nie mają barów H1
w ogóle, więc nigdy nie weszły do puli kandydatów. Ich wkład w 237 wynosi
zero — sprawdzone wprost.

## Werdykt: gubienie nie jest wybiórcze w sposób, który przekrzywia wynik

Odpadnięcie zależy **wyłącznie od znacznika czasu wejścia** (kalendarz
i godzina zamknięcia rynku), a nie od tego, co cena zrobiła później. Nie ma
tu look-aheadu ani biasu optymistycznego: nie odpadają transakcje przegrywające
ani wygrywające, odpadają piątkowe wieczory. Ostrzeżenie z ADR-026 przed cichym,
selektywnym gubieniem transakcji nie realizuje się.

## To NIE jest luka w regułach — warunek 9 już to obejmuje

Pierwsza interpretacja tego pomiaru brzmiała „brakuje warunku NO TRADE dla
piątkowego zamknięcia, odbicie ADR-042". Jest błędna. Warunek istnieje:
`{id: 9, rule: "piątek po 15:00 NY"}` (`config/v1_baseline.yaml:357`),
zaimplementowany w `src/strategy/v1a.py:161` jako moment decyzji przeliczony
na `America/New_York`, piątek, godzina ≥ 15:00.

Odpadające decyzje wypadają o **17:00–18:00 czasu NY** (22:00/23:00 UTC),
więc `9_friday` obejmuje je wszystkie, w obu reżimach czasu i bez problemu
z DST — bo warunek jest zapisany jako czas lokalny NY, nie jako offset UTC.
Nowy ADR byłby duplikatem istniejącej reguły.

Dlaczego te bary widać w bramce 0: kontrola losowa **świadomie nie stosuje
warunków NO TRADE**. Jej zadaniem jest test negatywny symulatora, nie
strategii, więc losuje z całej puli kandydatów — także z barów, których V1a
nigdy by nie zagrał (piątkowy wieczór, sesja niedzielna). Dla samej bramki 0
skutek jest zachowawczy: symulator jest sprawdzany na szerszym i cieńszym
zbiorze barów niż ten, na którym pracuje strategia.
