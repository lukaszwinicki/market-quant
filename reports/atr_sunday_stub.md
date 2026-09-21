# Niedzielne kikuty w szeregu D1

> Cel: rozstrzygnąć, czy deflacja `atr_d1_14` przez niedzielne kikuty jest
> zmianą skali (kosmetyka) czy zmianą składu próby (wymaga naprawy).
> **To pomiar, nie naprawa.** Skrypty jednorazowe, poza repozytorium.
>
> W pliku są **dwa pomiary tego samego zjawiska**:
>
> | | kiedy | okno | rola |
> |---|---|---|---|
> | **§1–8** | 2026-09-20 | 2015-01-01 → 2016-04-28 (tyle barów było wtedy zbudowane; EURUSD ma dane do 2016-09-30, obcięte dla porównywalności) | pomiar pierwotny, podstawa ADR-041 |
> | **§9** | 2026-09-21 | 2015-01-01 → 2021-12-31, pełny segment RESEARCH | powtórzenie po przebudowie barów |
>
> Sekcje 1–8 zostają bez zmian — dokumentują stan wiedzy w chwili podejmowania
> decyzji. Liczby obowiązujące dziś są w §9.

Sprawa zgłoszona w `CLAUDE.md` 2026-09-20 na podstawie dwóch par (EURUSD,
USDJPY). Ten raport rozszerza pomiar na wszystkie sześć par kohorty A i dokłada
pomiar, którego wcześniej nie było: wpływ na rozkład etykiet.

---

## 1. Mechanizm

Rynek FX chodzi ciągle od niedzieli 21:00 UTC do piątku. `daily_bars()` grupuje
bary H1 po dobie kalendarzowej (`group_by_dynamic(every="1d")`, granica 00:00
UTC z `data.d1_boundary`), więc **niedziela dostaje własny bar dzienny zbudowany
z 3 godzin** i wchodzi do `atr(d1, 14)` jako pełnoprawny dzień.

Deflacja dotyczy każdego dnia tygodnia, nie tylko poniedziałku: okno ATR14 to
14 kolejnych barów dziennych, a co szósty jest kikutem — w każdym oknie siedzi
~2,3 kikuta o zakresie ~20% normalnego dnia, czyli `2,3/14 × 0,8 ≈ 13%`.

Drugi, niezależny skutek: `_attach_daily_volatility()` mapuje wartości dnia D
na D+1 przez join po dacie. Sobota nie ma bara dziennego, więc **bary niedzielne
mają `atr_d1_14 = None`**, a bary poniedziałkowe dostają ATR policzony z kikuta.

---

## 2. Bary H1 na dobę

Mediana, identyczna na wszystkich sześciu parach:

| pon | wt | śr | czw | pt | sob | ndz |
|---|---|---|---|---|---|---|
| 24 | 24 | 24 | 24 | 21 | — | **3** |

Przepaść między niedzielą (3) a najkrótszym typowym dniem (piątek, 21) jest
duża, ale **nie pusta** — patrz sekcja 3b, gdzie próg jest wybierany na
podstawie pomiaru, a nie tej tabeli.

## 3. Kikuty i deflacja ATR14

Próg zastosowany w tym skanie: dzień z ≤ 6 barami H1. Wybór progu docelowego
— sekcja 3b.

| para | dni | ndz | ndz = kikut | kikutów pon–pt | zakres ndz / dzień rob. | ATR z kikutami | ATR bez | Δ mediana | Δ parowane |
|---|---|---|---|---|---|---|---|---|---|
| EURUSD | 414 | 69 | **69/69** | 1 | 19,9% | 0,010055 | 0,011549 | −12,9% | **−11,2%** |
| GBPUSD | 414 | 69 | **69/69** | 1 | 20,8% | 0,010892 | 0,012344 | −11,8% | **−11,8%** |
| USDJPY | 414 | 69 | **69/69** | 1 | 25,8% | 0,842286 | 0,940143 | −10,4% | **−11,2%** |
| AUDUSD | 414 | 69 | **69/69** | 1 | 23,1% | 0,008216 | 0,009411 | −12,7% | **−11,1%** |
| USDCAD | 414 | 69 | **69/69** | 1 | 19,6% | 0,010394 | 0,011886 | −12,6% | **−11,5%** |
| EURJPY | 414 | 69 | **69/69** | 1 | 23,5% | 1,140286 | 1,307214 | −12,8% | **−10,7%** |

`Δ mediana` — mediana całego szeregu z kikutami vs mediana szeregu po
odfiltrowaniu. `Δ parowane` — mediana per-dzień `(ATR_z − ATR_bez)/ATR_bez`
na wspólnych datach (n = 331 na parę), czyli bez mieszania różnicy szeregów
z różnicą składu próby.

**Zjawisko jest jednakowe na wszystkich sześciu parach** (−10,7% … −11,8%
parowane). To kalendarz, nie cecha instrumentu.

Jedyny kikut poza niedzielą to **2015-01-01** (2 bary) na każdej parze — Nowy
Rok, dzień rozpoznawany przez raport jakości jako zamknięcie, nie awaria. Próg
łapie go poprawnie. GBPUSD ma dodatkowo 2016-04-29 z 3 barami, ale to artefakt
granicy budowy barów, nie rynek.

## 3b. Gdzie postawić próg niepełnego dnia

Pomiar z sekcji 2 sugerował przepaść 3 → 21 i próg obojętny w całym tym
przedziale. **To był artefakt progu ≤ 6 użytego w skanie.** Przegląd dób
z 7–20 barami znalazł jeden dzień, który przy progu 6 przechodzi, a nie
powinien:

| dzień | barów H1 | co to jest |
|---|---|---|
| 2015-12-25 (pt) | 8 (wszystkie pary) | Boże Narodzenie, resztkowa sesja |
| 2016-09-02 (pt) | 20 (EURUSD) | normalny piątek |
| 2016-04-29, 2016-09-30 | 3–16 | ostatnia doba zbudowanej partycji, artefakt budowy |

Zakres tych dni względem doby pełnej (mediana dni z > 20 barami):

| para | 25.12.2015 (8 barów) | niedziela (3 bary) |
|---|---|---|
| EURUSD | 31,8% | 19,6% |
| GBPUSD | 40,8% | 20,7% |
| USDJPY | 36,0% | 25,1% |
| AUDUSD | 48,8% | 23,1% |
| USDCAD | **13,1%** | 19,5% |
| EURJPY | 37,9% | 23,5% |

Boże Narodzenie ma ten sam defekt co niedziela, tylko łagodniejszy — mediana
~36% zakresu pełnej doby. Musi wypaść z szeregu z tego samego powodu.

Piątek natomiast, mimo 21 barów zamiast 24, jest **dniem pełnym** — brakujące
3 godziny to martwy wieczór po zamknięciu Nowego Jorku:

| para | mediana zakresu pt | pon–czw | udział |
|---|---|---|---|
| EURUSD | 0,010670 | 0,009240 | 115,5% |
| GBPUSD | 0,012540 | 0,011640 | 107,7% |
| USDJPY | 0,989000 | 0,856000 | 115,5% |
| AUDUSD | 0,008550 | 0,008660 | 98,7% |
| USDCAD | 0,012260 | 0,011590 | 105,8% |
| EURJPY | 1,194000 | 1,190000 | 100,3% |

**Prawdziwa przepaść leży więc między 8 a 21 barami**, nie między 3 a 21.
Próg **12 barów** („pół doby handlowej”) siedzi w jej środku. Wartości 9–20
dają na tej próbie identyczny wynik; wartości ≤ 8 przepuszczają 25.12.

Skutek uboczny, świadomy: próg wycina też ostatnią, uciętą dobę zbudowanej
partycji (2016-04-29, 2016-09-30). Doba niepełna jest niepełna niezależnie
od przyczyny, więc to zachowanie pożądane — a po przebudowie barów na pełnym
zakresie te doby i tak będą kompletne.

## 4. Wpływ na rozkład etykiet

Pomiar, którego brakowało w zgłoszeniu. Te same wejścia, ta sama ścieżka cen,
**jedyna różnica to szerokość barier**:

- ramię „z kikutami” — `atr_d1_14` dokładnie jak liczy dziś `_attach_daily_volatility()`
- ramię „bez kikutów” — ATR z dni pełnych, przypisany przez asof (ostatni pełny
  dzień zamknięty przed dobą bara)

Próba ograniczona do barów mających ATR w OBU wariantach, żeby porównanie szło
po tym samym zbiorze wejść. 400 barów × 2 kierunki × 6 par, wejścia
2015-02-01 → 2016-04-10, seed 20260920, **4738 transakcji w każdym ramieniu**.

| wynik | z kikutami | bez kikutów | Δ pp |
|---|---|---|---|
| **bariera czasowa** | 52,1% | **62,6%** | **+10,5** |
| SL | 36,9% | 30,2% | −6,8 |
| TP | 10,2% | **6,5%** | −3,7 |
| gap_sl | 0,7% | 0,7% | +0,0 |
| gap_tp | 0,1% | 0,1% | +0,0 |

Per para, spójnie we wszystkich sześciu:

| para | TP z | TP bez | SL z | SL bez | czas z | czas bez |
|---|---|---|---|---|---|---|
| EURUSD | 11,3% | 8,2% | 34,4% | 28,2% | 53,4% | 62,9% |
| GBPUSD | 8,3% | 4,4% | 44,4% | 34,6% | 46,9% | 60,8% |
| USDJPY | 9,5% | 6,9% | 33,8% | 28,7% | 56,5% | 64,2% |
| AUDUSD | 7,4% | 3,5% | 36,4% | 30,0% | 55,9% | 66,0% |
| USDCAD | 10,7% | 6,2% | 38,5% | 30,3% | 50,6% | 63,1% |
| EURJPY | 14,1% | 9,7% | 34,2% | 29,1% | 49,0% | 58,7% |

**Wniosek: to nie jest kosmetyka.** Udział TP spada o 36% względnie. Gdyby
deflacja była czystym błędem skali, znak expectancy by się nie zmienił i sprawa
byłaby obojętna dla werdyktu. Ale bariery są zaciśnięte przy NIEZMIENIONYM
horyzoncie czasowym, więc zmienia się geometria triple barrier, czyli skład
próby — a nie tylko jednostka, w której jest wyrażona.

## 5. Koszt w R

Jednostka `1 R = sl_multiple × atr_d1_14`, więc zaniżony ATR **zawyża** koszt
wyrażony w R:

| | z kikutami | bez kikutów | Δ |
|---|---|---|---|
| średni `cost_r` | 0,01049 | 0,00898 | **+16,8%** |

Bramka 0 zmierzyła koszt **0,0106 R** (`20260919T134506Z-c4710e`). Zgodność
z ramieniem „z kikutami” jest niemal dokładna, co niezależnie potwierdza, że
ta liczba jest zawyżona o ~17%.

Dla kompletności, na tej samej próbie: średnie R wyniosło −0,0063 z kikutami
i +0,0004 bez. Kierunek błędu **nie jest jednostajnie optymistyczny** — to
zniekształcenie, nie przesunięcie.

## 6. Bary zyskujące ATR po naprawie

Asof („ostatni pełny dzień zamknięty przed dobą bara”) daje bar niedzielnym
ATR z piątku. Dziś nie mają żadnego:

| para | barów H1 | dziś bez ATR, po naprawie z ATR | udział |
|---|---|---|---|
| EURUSD | 8239 | 172 | 2,1% |
| GBPUSD | 8241 | 173 | 2,1% |
| USDJPY | 8244 | 173 | 2,1% |
| AUDUSD | 8242 | 173 | 2,1% |
| USDCAD | 8243 | 173 | 2,1% |
| EURJPY | 8244 | 173 | 2,1% |

To bary sesji niedzielnej 21:00–23:00 UTC. Dziś są blokowane przez `warmup`
(null ATR), czyli **przypadkiem, nie regułą**. Z 1073 barów niedzielnych w tym
oknie **302 (28,1%) niesie sygnał V1a** przy parametrach baseline
(`mom_480 > 0`, `donch_pos_55 > 0,8`) — patrz ADR-042.

Ta sama zmiana naprawia kotwicę poniedziałkową benchmarku §12, która w dry runie
pominęła 16/16 tygodni, bo decyzja o 00:00 UTC czyta bar z niedzieli 23:00.

## 7. Dlaczego to blokuje test odporności z bramki 2

`data.d1_boundary.robustness_test` porównuje „00:00 UTC” z „17:00 NY” i
„22:00 UTC”. **Obie alternatywy kasują kikut całkowicie** — przy granicy
przesuniętej przed 21:00 UTC sesja niedzielna wpada do poniedziałku i żaden
dzień nie jest 3-godzinny.

Test zapisany w tej postaci porównuje więc „zepsuty ATR” z „dobrym ATR”, a nie
trzy konwencje granicy doby. Kryterium porażki (ADR-024: expectancy zmienia znak
albo spada o >30%) jest przy zmierzonych wielkościach — koszt w R +16,8%, udział
TP −36% względnie — realnie osiągalne **jako artefakt**.

Kierunek tego błędu jest pesymistyczny dla H₁, więc nie łamie ADR-024. Ale
fałszywe „no-go” na bramce 2 kończy projekt tak samo skutecznie jak prawdziwe,
a aparatura ma dawać liczbę z przedziałem ufności, nie werdykt przechylony
w bezpieczną stronę.

## 8. Zakres i ograniczenia pomiaru

- Okno 2015-01-01 → 2016-04-28, 331 sparowanych dni na parę. Tyle barów jest
  zbudowane; front pobierania ticków stoi na 2021-02-12.
- Mechanizm jest strukturalny (co szósta doba to 3-godzinny kikut), więc dłuższy
  szereg nie powinien zmienić obrazu. Warto jednak powtórzyć pomiar po
  przebudowie barów na pełnym zakresie.
- Ramię „bez kikutów” odtwarza proponowaną naprawę, ale nie jest jej
  implementacją — to osobny kod pomiarowy.

**Powtórzenie wykonane 2026-09-21 — §9.** Obraz się nie zmienił; dwie rzeczy
doprecyzowane (sezonowość długości kikuta, zawężenie marginesu progu).

---

## 9. Powtórzenie na 2015–2021

> Wygenerowano: 2026-09-21 · okno 2015-01-01 → 2021-12-31 (pełny segment
> RESEARCH) · sześć par kohorty A · commit `7aaecf0`, drzewo czyste.
> **Pomiar, nie próba:** skrypty w katalogu tymczasowym sesji, bez
> `start_run`, bez wpisu do `trials.jsonl`. N w DSR bez zmian.

Pomiar z §1–8 obejmował 16 miesięcy i to jedyny powód, dla którego warto go
powtórzyć. Mechanizm jest strukturalny, więc to **weryfikacja, nie otwarte
pytanie** — i tak też wyszło.

### 9.1 Ramiona porównania i ich wierność

| ramię | szereg dzienny | dostępność wartości dziennych |
|---|---|---|
| **z kikutami** (przed ADR-041) | `daily_bars(h1, min_bars=1)` | złączenie po DOKŁADNEJ dacie, D → D+1 |
| **bez kikutów** (stan obecny) | `daily_bars(h1)`, `min_bars=12` | złączenie **asof** (ADR-041 pkt 2) |

Ramię „z kikutami” nie jest rekonstrukcją z opisu — to funkcja wyjęta wprost
z repozytorium (`git show e5e9f0e~1:src/features/technical.py`). Sprawdzone, że
kod pomiarowy daje **identyczne** wartości `atr_d1_14` co tamta funkcja: na
syntetycznym tygodniu FX z sesją niedzielną (1491 barów) i na EURUSD 2017–2018
(12 430 barów).

**Kontrola negatywna aparatury:** przy obu ramionach ustawionych na tę samą
funkcję wszystkie różnice wychodzą dokładnie zero (EURUSD i USDJPY, 300 barów
× 2 kierunki). Różnice w sekcjach 9.6–9.7 pochodzą więc z ATR, a nie
z losowania, parowania czy kolejności kolumn.

### 9.2 Struktura szeregu dziennego

| para | dób (bez progu) | dób pełnych | niedziel | niedziela = kikut | kikutów pon–pt | mediana barów ndz | zakres ndz / doba pełna |
|---|---|---|---|---|---|---|---|
| EURUSD | 2189 | 1816 | 364 | **364/364** | 9 | 3 | 19,8% |
| GBPUSD | 2188 | 1816 | 363 | **363/363** | 9 | 3 | 23,2% |
| USDJPY | 2189 | 1816 | 364 | **364/364** | 9 | 3 | 30,5% |
| AUDUSD | 2188 | 1816 | 363 | **363/363** | 9 | 3 | 25,9% |
| USDCAD | 2188 | 1816 | 363 | **363/363** | 9 | 3 | 22,0% |
| EURJPY | 2189 | 1816 | 364 | **364/364** | 9 | 3 | 30,3% |

Zgodnie z §3: **każda niedziela jest kikutem, na każdej parze.** Kikuty to
372–373 z 2188–2189 dób, czyli 17,0% szeregu — co szósta doba, jak w pomiarze
pierwotnym. Mediana barów w dobie: pon–czw 24, piątek 21, niedziela 3,
identycznie na sześciu parach.

Udział zakresu niedzieli wzrósł na parach jenowych (USDJPY 25,8% → 30,5%,
EURJPY 23,5% → 30,3%) — to różnica okna, nie zmiana mechanizmu. Wciąż
trzykrotnie poniżej doby pełnej.

### 9.3 Niedziela ma 3 bary latem, 2 zimą

Czego nie było widać na 16 miesiącach, bo mediana to przykrywa:

| barów H1 w niedzielę | niedziel | co to jest |
|---|---|---|
| 3 (21:00, 22:00, 23:00 UTC) | **237** | czas letni w Nowym Jorku, otwarcie 21:00 UTC |
| 2 (22:00, 23:00 UTC) | **125** | czas zimowy, otwarcie 22:00 UTC |
| 1 (23:00 UTC) | 1–2 | 2017-12-24 i 2019-05-26 — godziny z listy ADR-045 |
| brak doby | 1–2 | 2017-12-31 (sylwester), 2019-05-26 na GBPUSD/AUDUSD/USDCAD |

Kikut jest więc **jeszcze krótszy, niż zakładał pomiar pierwotny** — przez
jedną trzecią roku ma 2 godziny, nie 3. Kierunek błędu bez zmian, tylko
głębszy. Przy okazji: trzy godziny zaakceptowane w ADR-045 wychodzą tu
niezależnie, jako niedziele z jednym barem albo bez doby.

### 9.4 Próg 12 — margines węższy, niż sądziliśmy

Wszystkie doby o mniej niż 21 barach H1 w całym segmencie RESEARCH, poza
niedzielami:

| dzień | barów H1 | zakres / doba pełna | co to jest |
|---|---|---|---|
| 01.01. 2015, 2018, 2019, 2020 | 2 | 14–42% | Nowy Rok |
| 25.12.2015, 25.12.2020 | 7–8 | 18–67% | Boże Narodzenie |
| 25.12. 2017, 2018, 2019 | **10** | 19–75% | Boże Narodzenie |
| 2016-09-02 | **20** | 98–223% | normalny piątek bez jednej godziny ticków (ADR-045) |

1.01.2016 i 1.01.2021 (piątki) nie mają ANI JEDNEGO bara — nie wchodzą do
szeregu w ogóle. **Żadna doba nie ma 11–19 barów**, więc przepaść z §3b istnieje
też na pełnym zakresie.

Ale jej krawędzie się przesunęły. Na 16 miesiącach najdłuższe Boże Narodzenie
miało 8 barów i próg 9–20 dawał identyczny wynik. Na 7 latach są trzy
Boże Narodzenia po **10 barów**, a 2016-09-02 ma 20 i jest dniem pełnym
(98–223% zakresu). Identyczny wynik dają więc dopiero wartości **11–20**:

- próg ≤ 10 przepuszcza trzy Boże Narodzenia o 19–75% zakresu doby,
- próg ≥ 21 wycina 2016-09-02, czyli normalny piątek.

**`min_h1_bars = 12` nadal siedzi w środku przepaści** i nadal jest poprawne —
ale margines wynosi 11–20, a nie 9–20. ADR-041 podał 9–20 z zastrzeżeniem
„na tej próbie”, więc nie jest to sprzeczność, tylko zawężenie na dłuższym
szeregu. Odnotowane, bo gdyby ktoś kiedyś chciał zejść z progiem poniżej 11,
powołując się na zapisany tam zakres — na pełnym segmencie RESEARCH nie ma do
tego podstawy. Sam próg 12 zostaje bez zmian, więc **pieczęć `frozen_sha256`
się nie zmienia i nowy ADR nie jest potrzebny.**

Piątek pozostaje dniem PEŁNYM: mediana zakresu piątku (21 barów) to 99–107%
mediany pon–czw, na każdej parze.

### 9.5 Deflacja ATR14

| para | ATR z kikutami | ATR bez | Δ mediana | **Δ parowane** | n par |
|---|---|---|---|---|---|
| EURUSD | 0,006705 | 0,007708 | −13,0% | **−11,9%** | 1803 |
| GBPUSD | 0,009367 | 0,010807 | −13,3% | **−11,2%** | 1803 |
| USDJPY | 0,637393 | 0,723929 | −12,0% | **−10,7%** | 1803 |
| AUDUSD | 0,005768 | 0,006574 | −12,3% | **−11,0%** | 1803 |
| USDCAD | 0,007775 | 0,008884 | −12,5% | **−11,4%** | 1803 |
| EURJPY | 0,838321 | 0,950143 | −11,8% | **−10,3%** | 1803 |

`Δ parowane` — mediana per-dzień `(ATR_z − ATR_bez)/ATR_bez` na wspólnych
datach, czyli bez mieszania różnicy szeregów z różnicą składu próby. Rozrzut
wewnątrz pary: decyl 10% to −18…−20%, decyl 90% to −4…−6%.

**Pomiar pierwotny dawał −10,7…−11,8%; teraz −10,3…−11,9% przy 5,4-krotnie
dłuższym szeregu.** Jednakowo na sześciu parach. To kalendarz, nie cecha
instrumentu — potwierdzone.

### 9.6 Wpływ na rozkład etykiet

Te same wejścia, ta sama ścieżka cen, jedyna różnica to szerokość barier.
Próba ograniczona do barów mających ATR w OBU ramionach (252 508 kandydatów).
2000 barów × 2 kierunki × 6 par, ziarno 20260921, wejścia
**2015-01-23 → 2021-12-17**, **23 786 transakcji w każdym ramieniu** (z 24 000;
214 bez wyniku — NO_DATA albo brak danych w chwili decyzji, identycznie w obu
ramionach).

| wynik | z kikutami | bez kikutów | Δ pp | Δ względne |
|---|---|---|---|---|
| **bariera czasowa** | 52,5% | **62,0%** | **+9,5** | +18,1% |
| SL | 37,6% | 31,4% | −6,1 | −16,3% |
| **TP** | 9,0% | **5,9%** | **−3,2** | **−35,1%** |
| gap_sl | 0,7% | 0,6% | −0,1 | −19,1% |
| gap_tp | 0,2% | 0,1% | −0,1 | −45,2% |

Per para, spójnie we wszystkich sześciu:

| para | TP z | TP bez | SL z | SL bez | czas z | czas bez |
|---|---|---|---|---|---|---|
| EURUSD | 9,0% | 5,8% | 37,5% | 31,4% | 52,7% | 62,2% |
| GBPUSD | 9,5% | 6,5% | 38,5% | 32,2% | 51,4% | 60,8% |
| USDJPY | 9,4% | 6,8% | 37,6% | 31,5% | 51,8% | 61,0% |
| AUDUSD | 8,6% | 5,0% | 37,8% | 31,4% | 53,0% | 63,1% |
| USDCAD | 8,3% | 4,7% | 37,3% | 30,9% | 53,8% | 63,8% |
| EURJPY | 9,5% | 6,3% | 36,6% | 31,1% | 52,5% | 61,3% |

**Spadek udziału TP o 35,1% względnie** wobec 36% w pomiarze pierwotnym.
Wniosek z §4 zostaje w mocy co do joty: to nie jest kosmetyka, bo bariery są
zaciśnięte przy NIEZMIENIONYM horyzoncie czasowym, więc zmienia się geometria
triple barrier — czyli skład próby, a nie tylko jednostka.

### 9.7 Koszt w R

| | z kikutami | bez kikutów | Δ |
|---|---|---|---|
| średni `cost_r` | 0,01326 | 0,01143 | **+16,0%** |

Per para zawyżenie wynosi 13,3% (EURJPY) do 17,3% (EURUSD) — pomiar pierwotny
dał +16,8% na wspólnej próbie.

Wartości bezwzględne są wyższe niż w §5 (0,01049 → 0,00898), bo okno obejmuje
teraz lata 2016–2021, w których spread jest większy w stosunku do zmienności.
To ta sama obserwacja co na etykietach bramki 0 (`labels.parquet` tamtego
przebiegu, średni `cost_r` per rok): 2015 **0,00909**, 2016 0,00984,
2017 0,01112, 2018 0,01139, 2019 **0,01503**, 2020 0,01134, 2021 0,01311.

**Niezależna zgodność z bramką 0:** ramię „bez kikutów” daje 0,01143 R, a
zamknięta bramka 0 (`20260921T161726Z-1e142d`, ten sam zakres, obecny kod,
zbalansowane losowanie, 20 powtórzeń) zmierzyła **0,01156 R**. Dwie różne
drogi losowania, różnica 1,1%.

Średnie R na tej próbie: −0,0177 z kikutami, −0,0172 bez. Jak w §5, kierunek
błędu **nie jest jednostajnie optymistyczny** — to zniekształcenie, nie
przesunięcie.

### 9.8 Bary zyskujące ATR po naprawie

| | barów H1 | zyskuje ATR | udział |
|---|---|---|---|
| sześć par razem | 261 775 | **5823** | **2,2%** |

Na parę: 959 (EURUSD, USDJPY, EURJPY) i 982 (GBPUSD, AUDUSD, USDCAD). To
w przeważającej części bary sesji niedzielnej — 957 na pierwszych trzech
parach, 956 na pozostałych — które przed
ADR-041 były blokowane przez null ATR — czyli przypadkiem, a nie regułą. Udział
zgadza się z §6 (2,1%). Ich wykluczenie z handlu jest dziś jawną regułą —
warunek `10_sunday_open`, ADR-042.

Reszta — 2 bary na EURUSD, USDJPY i EURJPY, 26 na GBPUSD, AUDUSD i USDCAD — to
**poniedziałki, które w starym kodzie traciły ATR całkowicie**. Pokazują drugi
defekt z §1 na żywym przykładzie:

| dzień | pary | barów | dlaczego |
|---|---|---|---|
| 2018-01-01 (pon) | wszystkie sześć | 2 | poprzedzająca niedziela 2017-12-31 (sylwester) nie ma ani jednego bara |
| 2019-05-27 (pon) | GBPUSD, AUDUSD, USDCAD | 24 | niedziela 2019-05-26 bez barów na tych trzech parach (ADR-045) |

Złączenie po dokładnej dacie szuka dla poniedziałku wpisu o kluczu „niedziela
+ 1 dzień”. Gdy niedzieli nie ma w szeregu w ogóle, poniedziałek nie dostaje
nic — cała doba wypada z handlu przez brak cechy. Asof daje mu ATR z piątku.
Stąd 982 zamiast 959 właśnie na tych trzech parach: **mniej niedziel w danych
znaczyło w starym kodzie więcej straconych poniedziałków.**

### 9.9 Zestawienie: pomiar pierwotny vs powtórzenie

| wielkość | 2015-01…2016-04 | 2015–2021 | |
|---|---|---|---|
| niedziel będących kikutem | 69/69 na parę | **363–364/363–364 na parę** | bez zmian |
| deflacja ATR14 (parowana) | −10,7…−11,8% | **−10,3…−11,9%** | bez zmian |
| udział TP | 10,2% → 6,5% (−36%) | **9,0% → 5,9% (−35,1%)** | bez zmian |
| udział bariery czasowej | 52,1% → 62,6% | **52,5% → 62,0%** | bez zmian |
| zawyżenie `cost_r` | +16,8% | **+16,0%** | bez zmian |
| bary zyskujące ATR | 2,1% | **2,2%** | bez zmian |
| długość kikuta | 3 bary | **3 latem, 2 zimą** | doprecyzowane |
| margines progu `min_h1_bars` | 9–20 | **11–20** | doprecyzowane |

**Werdykt: ADR-041 potwierdzone na pełnym segmencie RESEARCH.** Żadna liczba
nie zmienia się na tyle, żeby ruszyć decyzję, próg ani pieczęć. Dwa
doprecyzowania (9.3, 9.4) idą w tę samą stronę co decyzja i nie wymagają
nowego ADR — `min_h1_bars = 12` pozostaje wewnątrz przepaści.

### 9.10 Ograniczenia

- Ramię „z kikutami” to kod historyczny uruchomiony na dzisiejszych barach,
  a nie wynik sprzed naprawy — bary zostały od tamtej pory przebudowane.
  Do pytania „czy kikuty deflują ATR” to jest właściwe porównanie, bo obie
  strony widzą te same ceny.
- Próba etykiet to losowe wejścia, nie sygnały V1a. Mierzymy geometrię barier,
  nie przewagę; do werdyktu o strategii ten pomiar się nie nadaje i nie ma
  takiego zamiaru.
- 2022–2025 nieruszane: partycje barów nie są zbudowane, a hold-out 2024–2025
  jest zapieczętowany do bramki 4.
