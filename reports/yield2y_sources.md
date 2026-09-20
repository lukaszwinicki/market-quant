# Rentowności 2-letnie — zwiad źródeł (blokada ADR-036)

> Wygenerowano: 2026-09-20 · zakres sprawdzany 2015-01-01 → 2025-12-31
> Cel: rozstrzygnąć, czy `yield_2y` dla EUR, GBP, JPY, AUD, CAD, NZD, CHF
> da się pozyskać na tyle jednorodnie, żeby odblokować benchmark §12.
> **To zwiad, nie implementacja.** Benchmark nie został zbudowany ani policzony.

Kryteria przyjęte przed sondowaniem:

1. częstotliwość dzienna albo miesięczna,
2. 2015–2025 bez luk,
3. stabilny adres nadający się do automatycznego parsowania,
4. **ta sama definicja dla wszystkich walut.**

---

## 1. Co znaleziono

| Waluta | Źródło | Adres | Częstotl. | Zakres w próbie | n | Definicja | Kryteria |
|---|---|---|---|---|---|---|---|
| USD | FRED `DGS2` | `fred.stlouisfed.org` | dzienna | 2015-01-02 → 2025-12-31 | 2750 | Constant-maturity **par yield** (CMT) | 1,2,3 ✔ |
| EUR | ECB Data Portal `YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y` | `data-api.ecb.europa.eu` | dzienna | 2015-01-02 → 2025-12-31 | 2806 | **Zero-kuponowy spot**, Svensson, kapitalizacja ciągła, emitenci AAA | 1,2,3 ✔ |
| EUR (alt.) | Bundesbank `BBSIS.D.I.ZST.ZI.EUR.S1311.B.A604.R02XX.R.A.A._Z._Z.A` | `api.statistiken.bundesbank.de` | dzienna | sprawdzone 200/CSV | — | Zero-kuponowy spot, Svensson, Bundy | 1,3 ✔ |
| GBP | BoE *GLC Nominal daily data* (`glcnominalddata.zip`, ark. „4. spot curve”, kol. 2.0) | `bankofengland.co.uk` | dzienna | 2015-01-01 → 2026-08-28 | 261 + 2273 + 261 | **Zero-kuponowy spot**, spline (VRP) | 1,2,3 ✔ |
| JPY | MoF `historical/jgbcme_all.csv`, kolumna `2Y` | `mof.go.jp` | dzienna | 2015-01-05 → 2025-12-30 | 2688 | Stopa procentowa JGB (**bliska par**, na krzywej benchmarków) | 1,2,3 ✔ |
| CAD | Bank of Canada Valet `BD.CDN.2YR.DQ.YLD` | `bankofcanada.ca/valet` | dzienna | 2015-01-02 → 2025-12-31 | 2744 | Rentowność **konkretnej obligacji benchmarkowej** 2-letniej | 1,2,3 ✔ |
| AUD | RBA F2 `FCMYGBAG2D` (dzienna) | `rba.gov.au` (403 → Wayback) | dzienna | **kończy się 2023-06-07** | — | Interpolowana 2 lata, Yieldbroker | 2 ✘ |
| AUD | RBA F2.1 `FCMYGBAG2` (miesięczna) | `rba.gov.au` (403 → Wayback) | **miesięczna** | 2015-01 → 2025-07 w zrzucie z VIII 2025 | 143 | Interpolowana 2 lata, RBA | 1,3 ✔ (dzienna ✘) |
| NZD | RBNZ B2 „Secondary market government bond closing yields – 2 year” `INM.DG102.NZZCF`, dwa pliki: `hb2-daily-close-1985-2017.xlsx` + `hb2-daily-close.xlsx` | `rbnz.govt.nz` (403 → Wayback) | dzienna | 2015 → 2025-08-22 | 2015: 251, 2016: 251, 2017: 250, 2018: 230, 2019: 220, **2020: 28**, 2021: 241, 2022: 248, 2023: 249, 2024: 251 | Rentowność zamknięcia rynku wtórnego | 2 ✘ |
| CHF | SNB `rendoblid`, wymiar `2J` | `data.snb.ch/api/cube/rendoblid` | dzienna | 2015-01-05 → **2025-07-31** | 2660 | Zero-kuponowy spot, obligacje Konfederacji | 2 ✘ |

### OECD nie ma 2Y — sprawdzone, nie założone

ADR-036 stwierdził brak 2Y na FRED. Zweryfikowano, że to nie jest artefakt FRED-a.
Pobrano strukturę przepływu OECD `OECD.SDD.STES/DSD_STES@DF_FINMARK` (SDMX,
`sdmx.oecd.org/public/rest/dataflow/...?references=all&format=structure`) i wypisano
całą listę kodów `CL_MEASURE`. Miary stóp procentowych są dokładnie trzy:

| Kod | Nazwa |
|---|---|
| `IRLT` | Long-term interest rates (≈10 lat) |
| `IR3TIB` | Short-term interest rates (3M interbank) |
| `IRSTCI` | Immediate interest rates, call money, interbank rate |

**Punktu 2-letniego w OECD nie ma w ogóle** — ani na stats.oecd.org, ani w nowym
data-explorerze, bo obie fasady serwują ten sam przepływ. Droga „OECD.Stat”
z ADR-036 pkt 2(a) jest zamknięta u źródła.

### Trzy twarde luki

- **AUD, dzienna:** RBA przestało publikować dzienne rentowności AGS. Ostatni zrzut
  Wayback pliku `f2-data.csv` z treścią pochodzi z 2023-06-08 i kończy się na
  2023-06-07; nowsze żądania Wayback zwracają tę samą kopię. Następca, `f2.1-data.csv`,
  ma `Frequency,Monthly` i `Series ID FCMYGBAG2` (bez `D`). Po połowie 2023 AUD ma
  wyłącznie dane miesięczne.
- **NZD, rok 2020:** seria `INM.DG102.NZZCF` ma w 2020 **28 obserwacji** zamiast ~250
  (2018: 230, 2019: 220 też są niepełne). Dziura wypada dokładnie w okresie, w którym
  różnice stóp się rozjeżdżały.
- **CHF, druga połowa 2025:** kostki SNB z rentownościami (`rendoblid` dzienna,
  `rendoblim` miesięczna) mają `PublishingDate` 2025-09-01 i ostatnią obserwację
  2025-07-31. To nie jest awaria portalu — inne kostki tego samego API są bieżące
  (`devkum` i `zimoma`: 2026-09-01, `snbbipo`: 2026-08-31). Serie rentowności
  wyglądają na wygaszone. Dziura wypada **wewnątrz zapieczętowanego hold-outu**.

### Kryterium 4 (jedna definicja) nie jest spełnione przez żaden zestaw

Osiem walut wymaga ośmiu instytucji, a te liczą „rentowność 2-letnią” na cztery
różne sposoby:

| Konstrukcja | Waluty |
|---|---|
| Zero-kuponowy spot z modelu (Svensson / spline) | EUR, GBP, CHF |
| Par yield constant-maturity | USD |
| Rentowność konkretnej obligacji benchmarkowej | CAD |
| Interpolacja po krzywej benchmarków / rynek wtórny | JPY, AUD, NZD |

Na punkcie 2-letnim różnice są rzędu pojedynczych punktów bazowych, ale są
systematyczne per waluta, a benchmark §12 jest **rankingiem przekrojowym** — czyli
dokładnie tą operacją, w której stały bias per waluta nie znosi się w różnicy.
Żadne z ośmiu źródeł nie da się podmienić na inne tak, żeby definicja była wspólna.

---

## 2. Dwie blokady §12 poza rentownościami

Zwiad ujawnił, że nawet rozwiązanie sprawy rentowności **nie odblokowuje §12**.

1. **Brak danych cenowych dla dwóch walut.** §12 rankuje „8 walut vs USD”, czyli
   potrzebuje m.in. NZDUSD i USDCHF. Kohorta A to sześć par
   (`EURUSD GBPUSD USDJPY AUDUSD USDCAD EURJPY`) pokrywających sześć walut:
   USD, EUR, GBP, JPY, AUD, CAD. NZD i CHF nie są pobierane.
2. **CHF jest wykluczony decyzją zamrożoną.** `config/v1_baseline.yaml`,
   sekcja `instruments` z `frozen: true`, wpis
   `excluded.CHF: "Zerwanie pega EURCHF 2015-01-15 — seria niereprezentatywna"`.
   Dołożenie USDCHF do zbioru instrumentów to zmiana sekcji `frozen: true`,
   czyli unieważnienie wszystkich dotychczasowych wyników i nowy `frozen_sha256`
   — za benchmark porównawczy.

Innymi słowy: §12 w literalnym brzmieniu („8 walut”) jest niewykonalny nie z powodu
rentowności, tylko z powodu zamrożonego zbioru instrumentów.

---

## 3. Pomiar: czy podmiana 2Y → 3M zmienia ranking

ADR-036 pkt 2(b) dopuszcza `interbank_3m` pod warunkiem uzasadnienia, „dlaczego
zmiana punktu krzywej nie zmienia sensu rankingu carry”. Uzasadnienie słowne byłoby
tu wyborem z wygody, przed którym ten sam ADR ostrzega, więc zmierzono.

**Metoda.** Dla każdego miesiąca 2015-01 … 2021-12 (**wyłącznie segment RESEARCH** —
hold-out nietknięty) zbudowano przekrój: rentowność 2Y (średnia miesięczna z serii
dziennych powyżej, dla AUD wartość miesięczna RBA) i `interbank_3m` z
`data/rates/fred.parquet`. Porównano ranking walut po jednej i po drugiej mierze.
Skrypt jednorazowy, nie wchodzi do repozytorium.

| Zestaw | Miesięcy z kompletem | Spearman (mediana / średnia / min) | Zgodna noga long | Zgodna noga short |
|---|---|---|---|---|
| §12 dosłownie: 8 walut, top-2 / bottom-2 | 73/84 | 0,976 / 0,954 / 0,786 | 51/73 = **70%** | 73/73 = **100%** |
| Kohorta A: 5 walut vs USD, top-1 / bottom-1 | 84/84 | 1,000 / 0,955 / 0,700 | 70/84 = **83%** | 84/84 = **100%** |
| Kohorta A: 5 walut vs USD, top-2 / bottom-2 | 84/84 | 1,000 / 0,955 / 0,700 | 62/84 = 74% | 84/84 = 100% |

Odczyt:

- **Porządek poziomów jest praktycznie ten sam** (mediana ρ ≈ 0,98–1,00). Punkt 3M
  i punkt 2Y krótkiego końca krzywej niosą tę samą informację o tym, która waluta
  płaci więcej.
- **Noga short jest identyczna w 100% miesięcy.** Waluta o najniższym carry
  (JPY, potem CHF/EUR) jest najniższa przy obu miarach zawsze.
- **Noga long rozjeżdża się w ok. 20–30% miesięcy** — waluty na górze rankingu są
  ciasno skupione i 2Y, który wycenia oczekiwania na 2 lata, zamienia je miejscami
  względem 3M. To realny koszt podmiany i trzeba go zapisać, a nie wygładzić.

---

## 4. Wnioski — ocena trzech wariantów z ADR-036

**(a) Własne źródło rentowności 2-letnich — ODPADA.**
Nie z powodu nakładu pracy (osiem parserów to odcinek porównywalny z kalendarzem
i byłby wykonalny), tylko dlatego, że wynik i tak nie spełniłby kryteriów:
kryterium 4 jest niespełnialne z definicji (cztery różne konstrukcje), a kryterium 2
łamią trzy niezależne luki, z których dwie (NZD 2020, CHF 2025H2) są po stronie
wydawcy i nie da się ich obejść parserem. Dodatkowo nie rozwiązuje to żadnej
z dwóch blokad z §2 tego raportu.

**(b) `interbank_3m` — WYKONALNE, z zapisanym kosztem.**
Jedna instytucja, jedna definicja, jeden format, komplet 132/132 miesięcy dla
wszystkich ośmiu walut, dane już pobrane i zbuforowane. Pomiar z §3 pokazuje, że
ranking poziomów się nie zmienia, a noga short jest identyczna; koszt to ~20–30%
miesięcy z inną nogą long.

**(c) Wykreślenie §12 — niepotrzebne.**
Byłoby zasadne, gdyby carry nie dawało się zmierzyć wcale. Daje się — tylko na
innym punkcie krzywej.

**Rekomendacja:** wariant (b) plus zawężenie koszyka do walut, które projekt
faktycznie posiada (5 vs USD zamiast 8), bo alternatywą jest ruszenie sekcji
`frozen: true`. Rozstrzygnięcie zapisane jako **ADR-038**, prerejestrowane
przed bramką 2 i przed jakimkolwiek wynikiem V1a, zgodnie z ADR-036 pkt 2.

---

## 5. Adresy użyte w zwiadzie (odtwarzalne)

```
https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y?startPeriod=2015-01-01&endPeriod=2025-12-31&format=csvdata
https://api.statistiken.bundesbank.de/rest/data/BBSIS/D.I.ZST.ZI.EUR.S1311.B.A604.R02XX.R.A.A._Z._Z.A?startPeriod=2015-01-01&endPeriod=2025-12-31&format=csv
https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/glcnominalddata.zip
https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv
https://www.bankofcanada.ca/valet/observations/BD.CDN.2YR.DQ.YLD/csv?start_date=2015-01-01&end_date=2025-12-31
https://web.archive.org/web/<znacznik>id_/https://www.rba.gov.au/statistics/tables/csv/f2-data.csv      (403 bez Wayback)
https://web.archive.org/web/<znacznik>id_/https://www.rba.gov.au/statistics/tables/csv/f2.1-data.csv    (403 bez Wayback)
https://web.archive.org/web/<znacznik>id_/https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily-close-1985-2017.xlsx
https://web.archive.org/web/<znacznik>id_/https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily-close.xlsx
https://data.snb.ch/api/cube/rendoblid/data/csv/en
https://sdmx.oecd.org/public/rest/dataflow/OECD.SDD.STES/DSD_STES@DF_FINMARK/?references=all&format=structure
```

Uwaga techniczna na przyszłość: pliki BoE i RBNZ to `.xlsx`, a RBA historyczne to
`.xls`. W `.venv` nie ma ani `openpyxl`, ani `xlrd` — na potrzeby zwiadu arkusze
czytano rozpakowując ZIP i parsując `sheet*.xml`. Budowa produkcyjnego parsera
wymagałaby dołożenia zależności; dla wariantu (b) nie jest potrzebna, bo
`interbank_3m` przychodzi z FRED jako CSV.
