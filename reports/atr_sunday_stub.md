# Niedzielne kikuty w szeregu D1 — pomiar przed ADR-041

> Wygenerowano: 2026-09-20 · okno wspólne 2015-01-01 → 2016-04-28 (tyle barów
> jest zbudowane; EURUSD ma dane do 2016-09-30, obcięte dla porównywalności)
> Cel: rozstrzygnąć, czy deflacja `atr_d1_14` przez niedzielne kikuty jest
> zmianą skali (kosmetyka) czy zmianą składu próby (wymaga naprawy).
> **To pomiar, nie naprawa.** Skrypty jednorazowe, poza repozytorium.

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

Przepaść między niedzielą (3) a najkrótszym prawdziwym dniem (piątek, 21) jest
na tyle duża, że **próg niepełnego dnia nie jest parametrem do strojenia** —
każda wartość z przedziału 4–20 daje w tej próbie identyczny wynik.

## 3. Kikuty i deflacja ATR14

Próg zastosowany w pomiarze: dzień z ≤ 6 barami H1.

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
