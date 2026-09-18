# AUDIT_REPORT.md — niezależny audyt koncepcji „Forex Signal Bot"

> **Autor audytu:** niezależny reviewer (Claude Opus 5)
> **Data:** 2026-09-18
> **Materiał wejściowy:** `docs/research/INITIAL_CONVERSATION.md`, `docs/research/OPUS_AUDIT_PROMPT.md`, `docs/research/README_FOREX_BOT_AUDIT.md`
> **Status materiału wejściowego:** hipoteza, nie specyfikacja
> **Zakres:** audyt koncepcyjny, metodologiczny i architektoniczny. Bez implementacji.

---

## 0. Nota o statusie twierdzeń w tym dokumencie

Stosuję konsekwentne etykiety:

- **[FAKT]** — weryfikowalne stwierdzenie o dokumentacji, API, literaturze lub matematyce.
- **[WYLICZENIE]** — wynik rachunku, który sam przeprowadziłem; założenia podane jawnie.
- **[HIPOTEZA]** — twierdzenie o rynku wymagające testu empirycznego.
- **[OPINIA]** — moja ocena inżynierska/metodologiczna.
- **[BRAK DOWODÓW]** — nie da się rozstrzygnąć na obecnym etapie.

Nie mam dostępu do żadnych Waszych danych ani wyników. Wszystko poniżej, co dotyczy rentowności, jest z definicji hipotezą.

---

# 1. Ocena całej koncepcji

## 1.1 Odpowiedź na pytanie nadrzędne

Pytanie z `OPUS_AUDIT_PROMPT.md` §2 brzmi: czy metodologia daje rozsądną szansę na uczciwe zbadanie istnienia przewagi?

**Odpowiedź: NIE w obecnej formie. TAK po radykalnym uproszczeniu.**

Powód jest jeden i jest ilościowy, nie estetyczny. Wyjaśniam go w §1.3, bo to jest najważniejszy akapit całego audytu.

## 1.2 Co jest mocne (i należy to zachować)

1. **Orientacja na swing, nie scalping.** To nie jest preferencja stylistyczna, to jest decyzja o przeżywalności ekonomicznej. **[WYLICZENIE]** Przy stopie 60 pipsów na EURUSD i realistycznym łącznym koszcie round-turn ~1.0 pipsa (spread ECN 0.1–0.3 + prowizja ~0.7 pipsa ekwiwalentu) koszt to ~0,017 R. Przy stopie 8 pipsów ten sam koszt to 0,125 R. Scalping wymaga edge'u ~10× większego. Wasz wybór jest poprawny i nie ma w tym dokumencie nic, co by go podważało.
2. **Jawne odrzucenie LLM jako generatora sygnału w V1.** To jest poprawna i nietrywialna decyzja — patrz §3.9, gdzie pokazuję, że alternatywa jest metodologicznie nienaprawialna.
3. **Odrzucenie social sentymentu.** Poprawne. Nie wymaga uzasadnienia poza tym, że nikt nie pokazał incremental value po kosztach.
4. **`P(TP before SL)` zamiast „cena wzrośnie".** To jest właściwy kierunek — target związany z tradowalnym rezultatem. Ma jednak pułapki, których dokumenty nie widzą (§3.6).
5. **„NO TRADE jest prawidłowym wynikiem"** i brak dziennego limitu transakcji. Poprawne.
6. **Filozofia z §12 `INITIAL_CONVERSATION.md`.** Wszystkie 13 punktów jest słusznych. Problem w tym, że reszta dokumentu ich nie przestrzega (§3.1).

## 1.3 Co jest słabe — problem centralny

**Przestrzeń hipotez proponowanego systemu jest o kilka rzędów wielkości większa niż dostępna próba. To nie jest problem do „uważnego obejścia". To jest problem, który sam z siebie gwarantuje overfitting.**

**[WYLICZENIE]** Policzmy dostępną próbę. Realistycznie:

- 8 par walutowych,
- 10 lat danych (2015–2025) — dłużej sięgać nie ma sensu, bo reżim mikrostruktury FX po 2008/2015 jest inny,
- selektywny system swingowy: ~2 transakcje na parę na miesiąc.

Daje to ~1 900 transakcji brutto. Ale transakcje **nie są niezależne**: pary FX to w praktyce system ~3 czynników (blok USD, blok EUR, blok JPY/risk). Jednoczesne pozycje na EURUSD, GBPUSD, AUDUSD to w dużej mierze jeden zakład na USD. Efektywna liczba niezależnych obserwacji to realnie **600–900**.

Teraz ile potrzeba, żeby cokolwiek wykryć. Statystyka t dla oczekiwanej wartości w R:

```
t = (μ / σ) × √N
```

gdzie σ dla systemu z barierami ~1 R (rozkład wyników ma odchylenie standardowe rzędu 1,0–1,3 R).

| Prawdziwy edge μ | N potrzebne dla t = 2 | N potrzebne dla t = 3,3 (po korekcie na 100 testów) |
|---|---|---|
| 0,20 R | 100 | 272 |
| 0,10 R | 400 | 1 089 |
| 0,05 R | 1 600 | 4 356 |
| 0,02 R | 10 000 | 27 225 |

**[WYLICZENIE]** Wniosek: przy ~700 efektywnych obserwacjach jesteście w stanie wykryć edge **nie mniejszy niż ~0,10–0,15 R na transakcję**, i to tylko jeśli liczba przetestowanych wariantów jest mała (kilkadziesiąt, nie kilka tysięcy).

A teraz przestrzeń, którą proponują dokumenty:

| Wymiar | Liczba wariantów (ostrożnie) |
|---|---|
| 4 timeframe'y × reguła zgodności (hard/soft/partial) | ~10 |
| ~10 wskaźników × 3 progi każdy | ~3⁵ = 243 realistycznych podzbiorów |
| definicja reżimu (4 metody × parametry) | ~20 |
| model (reguły / logit / GBM × hiperparametry) | ~30 |
| geometria SL/TP (mnożnik ATR × RR × time barrier) | ~100 |
| trailing / exit warianty | ~10 |
| dobór instrumentów | ~50 |

Iloczyn: **~10⁹**. Nawet jeśli faktycznie przetestujecie ręcznie tylko 200 kombinacji, to przy 700 obserwacjach maksimum z 200 losowych strategii bez żadnego edge'u da Sharpe'a rzędu 0,8–1,2 i „ładną" krzywą equity. **[FAKT]** To jest dokładnie zjawisko, które kwantyfikują Bailey i López de Prado w Deflated Sharpe Ratio i w Probability of Backtest Overfitting (CSCV).

**To jest jedyny naprawdę ważny wniosek tego audytu.** Wszystkie moje rekomendacje „usuń to" wynikają z niego, a nie z tego, że dany komponent jest „zły". Każdy dodatkowy stopień swobody kradnie Wam moc statystyczną, której nie macie.

## 1.4 Czego dokumenty w ogóle nie zawierają, a co jest niezbędne

**Nigdzie w `INITIAL_CONVERSATION.md` nie ma sformułowanej hipotezy ekonomicznej: DLACZEGO miałaby istnieć przewaga.**

Jest opis maszynerii (multi-timeframe, regime detection, ML, macro), ale nie ma odpowiedzi na pytanie: kto jest po drugiej stronie tej transakcji i dlaczego systematycznie traci?

To nie jest pytanie filozoficzne. FX majors to najgłębszy i najbardziej konkurencyjny rynek świata (~7,5 bln USD dziennie). Propozycja brzmi: uczestnik detaliczny, na darmowych danych, z publicznymi wskaźnikami, znajdzie przewagę, której nie zarbitrażowały podmioty z lepszymi danymi, lepszą egzekucją i tańszym finansowaniem.

**[FAKT]** Anomalie FX, które przetrwały recenzję akademicką i replikację poza próbą, to w praktyce trzy: **carry** (Lustig/Roussanov/Verdelhan 2011; Menkhoff/Sarno/Schmeling/Schrimpf 2012), **momentum przekrojowe i trend-following na koszyku walut** (Menkhoff i in., JFE 2012) oraz **value/PPP** na bardzo długich horyzontach. Wszystkie trzy są: przekrojowe (koszyk, nie pojedyncza para), wolnoobrotowe (tygodnie–miesiące), i mają artykułowane uzasadnienie jako premia za ryzyko.

**„Wysokiej jakości setup swingowy na GBPJPY z konfluencji D1/H4/H1/M15" nie należy do tej listy i nie ma publicznej evidence base.** **[OPINIA]** To nie znaczy, że jest niemożliwe. To znaczy, że prior powinien być niski, a poprzeczka dowodowa wysoka — i że architektura powinna być projektowana pod falsyfikację, a nie pod bogactwo funkcji.

## 1.5 Co jest spekulacyjne

Wszystko, co w dokumentach jest opisane czasownikiem „powinno": macro powinno pomagać, regime detection powinien poprawiać wynik, konfluencja powinna zwiększać jakość sygnału, pyramiding powinien zwiększać zysk w trendzie. **Żadne z tych twierdzeń nie ma w dokumentach ani jednego odwołania do dowodu.** To są hipotezy i tak są traktowane w §2.

## 1.6 Czego nie da się jeszcze ocenić

- Czy jakikolwiek edge istnieje. **[BRAK DOWODÓW — WYMAGANY TEST.]**
- Czy jakość darmowych danych wystarcza do wiarygodnej symulacji egzekucji. To da się rozstrzygnąć w ~2 tygodnie (§13.2) i **powinno to być pierwszą rzeczą, którą zrobicie**.
- Czy różnica między feedem Dukascopy a Waszym docelowym brokerem niszczy wyniki. Wymaga porównania równoległego.

---

# 2. Audyt założeń

Ocena: **KEEP** / **TEST** / **MODIFY** / **REMOVE** / **INSUFFICIENT EVIDENCE (IE)**

## 2.1 Styl i struktura

| Założenie | Ocena | Uzasadnienie | Wymagany test | Rekomendacja |
|---|---|---|---|---|
| Swing zamiast scalpingu | **KEEP** | Koszt w R maleje ~7× względem scalpingu (§1.2) | Brak — to argument kosztowy, nie predykcyjny | Zachować jako twardy constraint |
| Mała liczba transakcji, wysoka selektywność | **MODIFY** | Sprzeczne z potrzebą mocy statystycznej (§1.3). Selektywność obniża N, a N jest Waszym wąskim gardłem | Krzywa: expectancy vs liczba transakcji przy różnych progach | Selektywność jako **wynik** optymalizacji EV, nie jako cel projektowy |
| 0–3 transakcje dziennie akceptowalne | **KEEP** | Poprawne | — | — |
| Brak dziennego limitu transakcji | **KEEP** | Poprawne | — | — |
| „NO TRADE" jako pełnoprawny wynik | **KEEP** | Poprawne i niedoceniane | — | Musi być domyślnym stanem |
| M5/M1 poza V1 | **MODIFY** | Poza **sygnałem** — tak. Ale M1/tick są **obowiązkowe w symulatorze egzekucji** (§3.8) | — | M1/tick TYLKO w fill engine |

## 2.2 Hierarchia timeframe'ów

| Założenie | Ocena | Uzasadnienie | Wymagany test | Rekomendacja |
|---|---|---|---|---|
| D1 = kontekst, H4 = trend, H1 = setup, M15 = entry | **REMOVE** | Cztery TF na tej samej serii cenowej to nie są niezależne informacje (§5.1). Korelacja miary trendu H4 vs H1 to typowo 0,7–0,9 | Macierz korelacji cech między TF; test, czy dodanie TF zwiększa AUC poza próbą | Zastąpić **jedną bazą H1 + wielolookbackowymi cechami** |
| D1 jako hard filter | **REMOVE** | Hard filter to dyskretny parametr o wysokiej wariancji; wycina próbę bez zysku informacyjnego | — | Cecha ciągła, nie filtr |
| Wymagana pełna zgodność wszystkich TF | **REMOVE** | Koniunkcja 4 silnie skorelowanych warunków redukuje N o rząd wielkości, dodając ~0 informacji | Porównanie N i expectancy: full alignment vs continuous score | Ciągły score |
| M15 jako timing wejścia | **TEST** | Hipoteza „lepszy timing na M15 poprawia R" nie jest przetestowana. Przy stopie 60 pipsów poprawa wejścia o 3 pipsy to 0,05 R — niebanalne, ale i niepewne | Ten sam sygnał, wejście po H1 close vs wejście z triggerem M15 | Nie wchodzi do V1; test w V2 |
| Różne reguły dla różnych instrumentów | **REMOVE** | Mnoży parametry i dzieli próbę | — | Pooling po instrumentach z normalizacją przez ATR (§5.4) |

## 2.3 Analiza techniczna

| Założenie | Ocena | Uzasadnienie | Wymagany test | Rekomendacja |
|---|---|---|---|---|
| RSI | **REMOVE** | RSI(n) to monotoniczna transformacja znormalizowanego momentum; redundantny wobec zwrotu/σ | Korelacja RSI vs return/ATR (spodziewam się >0,85) | Usunąć |
| MACD | **REMOVE** | MACD = różnica dwóch EMA = ten sam sygnał co spread EMA, który już macie | — | Usunąć |
| ADX | **REMOVE** | ADX miesza siłę trendu i zmienność; ta sama informacja co \|return\|/ATR, ale w nieprzejrzystej formie | Korelacja ADX vs \|zwrot_n\|/ATR | Usunąć |
| EMA/SMA jako sygnał | **MODIFY** | Sama średnia to nie cecha; cechą jest `(cena − EMA)/ATR` | — | Zachować w formie znormalizowanej |
| ATR | **KEEP** | Jedyny niezbędny wskaźnik: normalizuje wszystko inne i definiuje sizing | — | Rdzeń systemu |
| Momentum / zwroty wielolookbackowe | **KEEP** | Najlepiej udokumentowana cecha w FX | — | Rdzeń |
| Breakout (Donchian N-bar) | **TEST** | Deterministyczny, testowalny, jest odpowiednikiem „BOS" | Donchian N ∈ {20, 55, 100} — max 3 warianty, prerejestrowane | Jedna reguła breakout |
| Pullback | **TEST** | Wymaga definicji; po sformalizowaniu = `(cena − max_n)/ATR` | — | Jako cecha ciągła |
| Support/resistance | **REMOVE** | Brak jednoznacznej definicji; każda implementacja to ukryty parametr | — | Zastąpione przez Donchian |
| Konfluencja wielointerwałowa | **REMOVE** | Patrz §5.1 | — | Zastąpione term structure momentum |
| BOS / CHoCH / FVG / liquidity | **REMOVE** | Pojawiają się w Waszym promptcie, ale **nie w dokumentach źródłowych** — to scope creep. Po sformalizowaniu BOS/CHoCH ≡ Donchian breakout z wolnym parametrem swing lookback. FVG jest deterministyczny, ale to po prostu detektor luk (§6.5) | FVG: test opcjonalny w V2 | Usunąć z V1 |

## 2.4 Macro

| Założenie | Ocena | Uzasadnienie | Wymagany test | Rekomendacja |
|---|---|---|---|---|
| `surprise = actual − consensus` jako cecha kierunkowa | **REMOVE z V1** | **[FAKT]** Literatura wskazuje, że reakcja FX na niespodziankę makro zachodzi w sekundach–minutach i **nie ma wyraźnego post-announcement drift** w FX. To, co da się wycenić na H1+, jest już wycenione | Event study: skumulowany zwrot w oknie T+15min … T+72h warunkowany standaryzowaną niespodzianką | Usunąć jako alfę; patrz niżej |
| Punkt-w-czasie consensus z darmowych źródeł | **REMOVE — BLOCKER** | **[FAKT]** Darmowe kalendarze nie archiwizują consensusu w wersji sprzed publikacji, nie dają timestampu co do sekundy i backfillują `previous` wartościami zrewidowanymi. Trading Economics ma prawdziwy point-in-time, ale płatnie | — | Nie da się uczciwie zbacktestować. Nie udawać, że się da |
| Macro jako filtr ryzyka (blackout okna) | **KEEP** | To kontrola kosztu i wariancji, nie alfa. Wymaga tylko **harmonogramu** wydarzeń, nie ich wartości — więc nie ma problemu point-in-time | Test: czy blackout redukuje ogon strat bez utraty expectancy | Jedyny macro-komponent w V1 |
| Yield / rate differential (2Y) | **KEEP / TEST** | **[FAKT]** Wolnozmienne, dostępne za darmo i point-in-time (FRED i odpowiedniki), z udokumentowanym uzasadnieniem ekonomicznym (carry). Jedyna macro-cecha z realnym priorem | Incremental value vs baseline czysto cenowy | Jedyna macro-cecha kierunkowa w V1 |
| Analiza tekstu banków centralnych (LLM/dictionary) | **REMOVE** | 3 powody: (a) ~32 zdarzenia/rok → próba za mała; (b) LLM z cutoffem po okresie testu = **parametric look-ahead** — **[FAKT]** udokumentowane w literaturze; (c) zmiana 2Y yield differential w oknie posiedzenia mierzy dokładnie to samo, za darmo i bez leakage'u | — | Zastąpić rynkową miarą repricingu |
| „hawkish = bullish currency" | **REMOVE** | Dokumenty słusznie to kwestionują. Właściwa miara to **zmiana oczekiwań**, nie poziom retoryki | — | — |

## 2.5 Model i sygnał

| Założenie | Ocena | Uzasadnienie | Wymagany test | Rekomendacja |
|---|---|---|---|---|
| Regime detection poprawia wynik | **TEST (nie w V1)** | Dzieli próbę na 4 części → 175 obs./reżim → gwarantowany overfit. Dodatkowo HMM ma pułapkę leakage'u (§3.5) | Baseline z ciągłą cechą vol-percentyl vs 4-stanowy model | V1: **jedna ciągła zmienna** (percentyl zmienności), zero hard switchy |
| HMM / Markov switching | **REMOVE z V1** | Złożoność bez wykazanej korzyści + realne ryzyko użycia smoothed zamiast filtered prawdopodobieństw | — | V2, warunkowo |
| ML (XGBoost/LightGBM) | **REMOVE z V1** | ~700 obs., silnie skorelowane cechy, SNR bliski zeru, niestacjonarność. GBM dopasuje szum | — | Maks. logit z ≤5 cechami i silną regularyzacją |
| ML w ogóle potrzebny | **IE** | Nie da się rozstrzygnąć przed baseline'em | Incremental AUC/expectancy logit vs reguły | Reguły najpierw |
| `P(TP before SL)` jako target | **KEEP z zastrzeżeniem** | Właściwy target, ale etykiety triple-barrier **nakładają się w czasie** → autokorelacja → konieczne purging+embargo. Oraz: jeśli bariery są w ATR, a ATR jest cechą, etykieta jest splątana z cechą (§3.6) | — | Zachować + obowiązkowy purged CV |
| Meta-labeling | **REMOVE z V1** | Wymaga wcześniej zwalidowanego modelu pierwotnego. Przedwczesne | — | V2 |
| EV jako główne kryterium | **KEEP z twardym zastrzeżeniem** | EV z **nieskalibrowanego** prawdopodobieństwa to selekcja najbardziej przeszacowanych predykcji (§3.7) | Reliability diagram na foldzie kalibracyjnym; Brier | Wymagana jawna kalibracja |

## 2.6 Ryzyko

| Założenie | Ocena | Uzasadnienie | Wymagany test | Rekomendacja |
|---|---|---|---|---|
| 0,25–0,5% ryzyka na transakcję | **MODIFY** | Na etapie badawczym to parametr **nieistotny**: przy sizingu liniowym procent skaluje krzywą, nie zmienia expectancy w R ani Sharpe'a | — | Badać wszystko w R; % dobrać na końcu z rozkładu drawdownu |
| Volatility-adjusted sizing jako osobna warstwa | **REMOVE** | Stop = k×ATR + stałe ryzyko % **już jest** sizingiem odwrotnie proporcjonalnym do zmienności. Druga warstwa to podwójne liczenie | — | Usunąć |
| Fractional Kelly | **REMOVE** | Kelly wymaga znajomości edge'u. Przy edge'u o dużym błędzie estymacji Kelly systematycznie przelewaruje | — | Nie w tym projekcie |
| Limity ekspozycji walutowej | **KEEP** | Krytyczne. 5 „różnych" par to często 1–2 realne zakłady | — | Netto per waluta w jednostkach R |
| Macierz kowariancji do limitów | **REMOVE** | Błąd estymacji dominuje przy tej próbie | — | Proste bloki walutowe, ρ=1 wewnątrz bloku |
| Drawdown-based de-risking | **TEST** | Często obniża wartość końcową i czyni backtest ścieżkowo zależnym | Porównanie z/bez, z Monte Carlo | Nie w V1 |
| Pyramiding | **REMOVE z V1** | §12 | — | Usunąć całkowicie |

## 2.7 Infrastruktura i Claude

| Założenie | Ocena | Uzasadnienie | Wymagany test | Rekomendacja |
|---|---|---|---|---|
| Stack: FastAPI + Postgres + Redis + React/Next + Docker | **REMOVE z V1** | Stack produkcyjny dla pytania badawczego. Sprzeczny z §12 i §19 samych dokumentów | — | Python + Parquet + CLI |
| TimescaleDB | **REMOVE z V1** | Parquet + Polars obsługuje ~10 lat M1 × 8 par bez problemu | — | V2 przy live ingestion |
| Frontend / Lightweight Charts | **REMOVE z V1** | Zero wartości dowodowej | — | Później |
| Discord alerty | **REMOVE z V1** | Ma sens dopiero gdy istnieje zwalidowany sygnał | — | V2 |
| MCP | **REMOVE z V1** | Rozwiązanie szukające problemu na tym etapie | — | V2/V3 |
| Claude nie generuje sygnału | **KEEP** | Poprawne i ważne | — | — |
| Brak Claude API w V1 | **KEEP** | Poprawne | — | — |
| Workflow Discord → copy/paste → Claude | **REMOVE** | Wprowadza człowieka w pętlę decyzyjną, czego **nie da się zbacktestować**. Niszczy rozdzielność między badaniem a uznaniowością | — | Usunąć |

---

# 3. Błędy koncepcyjne

Bez łagodzenia.

## 3.1 Dokument zaprzecza sam sobie

`INITIAL_CONVERSATION.md` §12 deklaruje: „Prostota jest preferowana", „Każdy dodatkowy komponent musi zostać empirycznie zweryfikowany", „Nie zakładamy, że więcej cech = lepiej".

Ten sam dokument §13 i §18 proponuje: PostgreSQL + TimescaleDB + Redis + React + Next.js + TypeScript + Lightweight Charts + Docker Compose + Discord bot + MCP + XGBoost + HMM + 12 wskaźników + 4 timeframe'y + pyramiding.

**To jest wprost sprzeczne.** §18 wymienia 14 punktów MVP, z czego co najmniej 6 (frontend, wykresy, Discord, paper trading, MCP, stan pozycji) nie ma żadnego związku z pytaniem „czy istnieje przewaga". Deklarowana filozofia nie została zastosowana do własnej architektury.

## 3.2 Brak jakiegokolwiek kryterium falsyfikacji

`INITIAL_CONVERSATION.md` §16 wymienia 20 metryk, ale **ani jednego progu**. Nie ma zdania „jeśli X < Y, porzucamy projekt". Bez tego każdy wynik da się zracjonalizować jako „obiecujący, wymaga dostrojenia" — a to jest dokładny mechanizm, przez który projekty tego typu żyją latami bez edge'u. Wasz prompt słusznie to naprawia, czyniąc kill criteria obowiązkowymi. To był największy brak dokumentów źródłowych.

## 3.3 Konfluencja wielointerwałowa jest bliska tautologii

Najczęstsze nieporozumienie w tradingu detalicznym i jedno z głównych założeń dokumentów.

**[FAKT — matematyka]** EMA o okresie *n* na timeframie *T* jest przybliżeniem EMA o okresie *n·k* na timeframie *T/k*. EMA(50) na H4 ≈ EMA(200) na H1 ≈ EMA(~8) na D1. To są te same liczby liczone z tej samej serii cenowej.

Czyli „D1 bullish AND H4 bullish AND H1 bullish" nie jest trzema niezależnymi potwierdzeniami. To jest jedno stwierdzenie — „momentum na wielu horyzontach jest dodatnie" — wyrażone w sposób, który sugeruje trzy dowody tam, gdzie jest jeden. Traktowanie skorelowanych warunków jak niezależnych głosów systematycznie zawyża subiektywną pewność i nie zawyża prawdziwego prawdopodobieństwa.

**Konsekwencja praktyczna:** wymaganie pełnej zgodności redukuje liczbę transakcji o rząd wielkości (zabijając moc statystyczną) w zamian za ~zero dodatkowej informacji.

## 3.4 Definicja świecy D1 i H4 w FX jest arbitralna i nikt tego nie zauważył

**[FAKT]** FX nie ma giełdy ani oficjalnego zamknięcia. „Świeca D1" zależy od konwencji brokera: 17:00 NY, 00:00 UTC, 00:00 GMT+2, 00:00 GMT+3 — wszystkie są w użyciu. Te same dane tickowe dają **różne świece D1** i **różne poziomy „high/low dnia"**.

Dodatkowo: świece H4 mają fazę zależną od punktu zakotwiczenia (00:00 vs 01:00 vs 17:00), a **DST w USA i UE przełącza się w różnych terminach** (rozbieżność ~2–3 tygodnie dwa razy w roku), więc offset sesji względem UTC zmienia się nietrywialnie.

Oznacza to, że cały poziom „D1 context" i „H4 trend" zawiera **ukryty, nieudokumentowany parametr**, który:
- nie jest w dokumentach wymieniony,
- prawie na pewno różni się między Dukascopy a Waszym docelowym brokerem,
- może istotnie zmienić wyniki backtestu.

To jest samodzielny argument za zejściem do **jednej bazy H1** (gdzie faza jest znacznie mniej dotkliwa) i budowaniem kontekstu przez okna kroczące, a nie przez agregaty kalendarzowe.

## 3.5 Pułapka leakage'u w regime detection, której dokumenty nie widzą

**[FAKT]** W `hmmlearn` metoda `.predict()` zwraca dekodowanie Viterbiego **po całej sekwencji**, czyli stan w czasie *t* zależy od obserwacji z *t+1, t+2, …*. Analogicznie w `statsmodels` `MarkovRegression`: `.smoothed_marginal_probabilities` używa przyszłości; kauzalne są tylko `.filtered_marginal_probabilities`.

To jest jeden z najczęstszych cichych look-ahead bugów w projektach z regime detection, i daje spektakularnie dobre, całkowicie fałszywe wyniki. Dokumenty wymieniają „HMM" jako kandydata, nie wspominając o tym w ogóle.

Ten sam problem dotyczy każdej normalizacji: z-score liczony na całej próbie, percentyl zmienności z pełnej historii, `StandardScaler` dopasowany przed splitem, winsoryzacja po globalnych kwantylach. **Wszystkie statystyki normalizujące muszą być liczone w oknie rozszerzającym (expanding), wyłącznie z przeszłości.**

## 3.6 Target `P(TP before SL)` ma dwie niewidoczne wady

**(a) Splątanie etykiety z cechą.** Jeśli TP = 2×ATR, SL = 1×ATR, a ATR jest jednocześnie cechą modelu, to model może nauczyć się geometrii barier zamiast sygnału. Prawdopodobieństwo trafienia bariery zależy od `bariera/σ` — jeśli obie strony równania zawierają ATR, część „predykcji" jest tożsamościowa.

**(b) Nakładanie się etykiet.** Transakcja otwarta o 10:00 z horyzontem 5 dni i transakcja o 11:00 dzielą prawie całe okno wynikowe. Ich etykiety są silnie skorelowane. Standardowy k-fold CV na takich danych daje wyniki zawyżone o rząd wielkości. Wymagane: **purging** (usunięcie z treningu obserwacji, których okno wyniku zachodzi na test) i **embargo** (dodatkowy bufor po teście). Dokumenty wspominają „purging/embargo tam, gdzie potrzebne" — otóż jest potrzebne **zawsze** przy tym targecie, to nie jest opcja.

**(c) Brak darmowego lunchu.** `P(TP before SL)` przy symetrycznych barierach jest niemal równoważne predykcji znaku filtrowanego zwrotu. Przy RR 1:2 base rate pod błądzeniem losowym to ~33%; z kosztami break-even to ~34–35%. Model musi stabilnie bić 35%, a nie „mieć accuracy 60%".

## 3.7 EV na nieskalibrowanym prawdopodobieństwie to selekcja własnych błędów

To jest najgroźniejszy błąd metodologiczny w proponowanym signal engine i nie jest w dokumentach zauważony.

Reguła „handluj, gdy EV > próg" wybiera obserwacje z **prawego ogona przewidywanego p**. Ale prawy ogon predykcji to dokładnie ten obszar, w którym modele są najbardziej przeszacowane — regresja do średniej działa najsilniej na ekstremach. Efekt: im agresywniej filtrujecie po EV, tym bardziej systematycznie wybieracie przypadki, w których model się myli w tę samą stronę.

Skutek praktyczny: backtest pokazuje, że „wysoki EV = wysokie R", live pokazuje, że nie.

**Wymagane bezwzględnie:** kalibracja (Platt/isotonic) dopasowana na **osobnym foldzie**, reliability diagram, Brier score **w koszyku wyselekcjonowanym**, nie na całej próbie, oraz ocena realizowanego expectancy w decylu najwyższego EV.

## 3.8 Backtest na świecach H1 systematycznie zawyża wyniki — problem kolejności wewnątrz świecy

**[FAKT]** Jeśli w danej świecy `high` przekroczył TP, a `low` przekroczył SL, z OHLC **nie da się ustalić, co nastąpiło pierwsze**. Typowa (często domyślna) implementacja zakłada korzystną kolejność, co daje cichy, systematyczny bias optymistyczny — tym większy, im szersze świece i im ciaśniejsze bariery.

To nie jest detal. Przy stopie 1×ATR i TP 2×ATR na H1 znaczący odsetek świec dotyka obu barier.

**Rozwiązania (w kolejności jakości):**
1. Symulacja fillów na danych tickowych (Dukascopy bid+ask) — jedyne poprawne.
2. Symulacja na M1 — dobre przybliżenie.
3. Założenie pesymistyczne (SL zawsze pierwszy) — dopuszczalne jako dolne ograniczenie.

Dokumenty tego nie wymieniają. Powinno to być punktem 1 listy „ukryte problemy".

## 3.9 LLM jako oceniający historyczny tekst = look-ahead wbudowany w wagi modelu

**[FAKT]** Zweryfikowane w literaturze (m.in. „Profit Mirage: Revisiting Information Leakage in LLM-based Financial Agents", arXiv:2510.07920; oraz prace o „parametric look-ahead"): model językowy, którego dane treningowe obejmują okres backtestu, **zna wynik**. Prosząc go o ocenę komunikatu FOMC z marca 2021, nie otrzymujecie predykcji — otrzymujecie przypomnienie.

Nie da się tego naprawić promptem („udawaj, że nie wiesz"). Nie da się tego zmierzyć. Nie da się tego odjąć.

**Wniosek: żadne historyczne dane wejściowe do backtestu nie mogą być generowane przez LLM.** Wasza decyzja o niestosowaniu Claude jako generatora sygnału jest więc nie tylko oszczędnością — jest metodologiczną koniecznością. Zapiszcie to jako twardą regułę, nie jako preferencję budżetową.

## 3.10 Ukryty inflator liczby testów: iteracja z pomocą LLM

Subtelne i praktycznie ważne. Deflated Sharpe wymaga **liczby przeprowadzonych prób**. Każde „Claude, dlaczego to nie zadziałało, co spróbować dalej?" po którym coś próbujecie, jest próbą i musi być zalogowane.

Przy pracy z asystentem tempo generowania wariantów rośnie 10–50×, więc **licznik prób rośnie w tempie, którego intuicja nie nadąża śledzić**. Bez jawnego, maszynowego rejestru prób liczba w DSR będzie zaniżona, a DSR przestanie cokolwiek znaczyć.

**Rekomendacja:** rejestr prób (`trials.jsonl`) zapisywany automatycznie przez harness backtestu, bez możliwości ręcznego pominięcia wpisu.

## 3.11 Selection bias w doborze instrumentów

„GBPJPY, bo ładnie trenduje" to selekcja na podstawie przeszłego zachowania — czyli in-sample. Zbiór instrumentów musi być **prerejestrowany przed pierwszym backtestem** i niezmieniany.

Dodatkowo: **[FAKT]** 15.01.2015 SNB zniósł peg EURCHF; para poruszyła się w minutach o ~30%, z fillami daleko poza podanymi stopami. Każdy backtest obejmujący ten dzień jest przez niego zdominowany. Decyzja co do traktowania tego zdarzenia musi zapaść **przed** zobaczeniem wyników (rekomendacja: wykluczyć CHF z V1, a zdarzenie zachować jako test stresowy egzekucji).

## 3.12 „Alert do Discorda → copy/paste do Claude" nie jest systemem, który da się zbadać

`INITIAL_CONVERSATION.md` §8 proponuje workflow, w którym człowiek kopiuje alert do Claude po pogłębioną analizę. To brzmi oszczędnie, ale:

- Wprowadza **nieudokumentowaną, nieodtwarzalną decyzję uznaniową** w krytycznym punkcie.
- Wyników takiego systemu **nie da się zbacktestować**, bo nie da się odtworzyć, co człowiek zrobiłby historycznie.
- Faktyczny system staje się „człowiek z podpowiedziami", a nie system — i cała maszyneria walidacyjna przestaje mierzyć to, co jest wykonywane.

**REMOVE.** Jeśli chcecie warstwy uznaniowej, musi być poza pętlą badawczą i jawnie oznaczona jako taka.

## 3.13 Ryzyko licencyjne scrapingu kalendarzy

**[FAKT]** ForexFactory, Investing.com i Trading Economics mają ToS ograniczające automatyczne pobieranie i redystrybucję. Dane z darmowych scraperów bywają backfillowane i edytowane po fakcie, więc nie stanowią archiwum point-in-time. To podwójny problem: prawny i metodologiczny.

**Rekomendacja:** w V1 używać **wyłącznie harmonogramu wydarzeń** (który da się zbudować z oficjalnych źródeł: BLS, BEA, Eurostat, ONS, kalendarze posiedzeń Fed/ECB/BoE/BoJ), a wartości makro brać z **FRED/ALFRED** (prawdziwe vintages, darmowe, licencyjnie czyste).

---

# 4. Poprawiona architektura

## 4.1 Zasada porządkująca

> Architektura V1 nie jest systemem tradingowym. Jest **aparaturą pomiarową** służącą do odrzucenia hipotezy o istnieniu przewagi przy minimalnej liczbie stopni swobody.

Konsekwencje:
- Każdy komponent, który nie zmienia wyniku pomiaru, jest usuwany.
- Każdy komponent, który dodaje stopień swobody, musi „zapłacić" wzrostem expectancy poza próbą.
- Kolejność budowy: **symulator egzekucji → kontrola losowa → baseline → dopiero potem cechy**.

## 4.2 Warstwy

```
┌──────────────────────────────────────────────────────────┐
│ L0  DANE (offline, Parquet)                              │
│     Dukascopy tick bid/ask → M1 → H1                     │
│     FRED/ALFRED (vintages) → 2Y yields                   │
│     harmonogram wydarzeń (oficjalne źródła)              │
├──────────────────────────────────────────────────────────┤
│ L1  SYMULATOR EGZEKUCJI  ← buduje się to NAJPIERW        │
│     fill na tickach/M1, bid/ask osobno,                  │
│     rozstrzyganie kolejności barier, model poślizgu,     │
│     swap, rollover, weekend gap                          │
├──────────────────────────────────────────────────────────┤
│ L2  CECHY (H1, kauzalne, expanding-window normalizacja)  │
│     ~6 cech. Nie więcej.                                 │
├──────────────────────────────────────────────────────────┤
│ L3  SYGNAŁ                                               │
│     V1a: reguła deterministyczna                         │
│     V1b: logit ≤5 cech + kalibracja                      │
├──────────────────────────────────────────────────────────┤
│ L4  RISK / SIZING                                        │
│     stałe ryzyko w R, limity per waluta, limit portfela  │
├──────────────────────────────────────────────────────────┤
│ L5  WALIDACJA                                            │
│     CPCV + purge/embargo, DSR, PBO, kontrole losowe,     │
│     sensitivity kosztowa, zapieczętowany hold-out        │
└──────────────────────────────────────────────────────────┘
```

**Czego tu nie ma i nie powinno być w V1:** bazy danych, API, frontendu, Dockera, Redisa, MCP, Discorda, kolejek, mikroserwisów, live'u.

## 4.3 Kolejność prac (to jest ważniejsze niż diagram)

| Krok | Cel | Warunek przejścia dalej |
|---|---|---|
| 0 | Dane + symulator egzekucji + model kosztów | Symulator odtwarza znane fille; koszt liczony z rzeczywistych ticków z podłogą detaliczną |
| 1 | **Kontrola losowa**: losowe wejścia, identyczne wyjścia i sizing, ta sama liczba transakcji | Znany rozkład zerowy expectancy i Sharpe'a |
| 2 | Baseline deterministyczny (≤3 parametry) | Bije kontrolę losową z DSR-skorygowanym t > 2 |
| 3 | Dodanie warunkowania zmiennością | +≥0,03 R poza próbą, inaczej usunąć |
| 4 | Dodanie carry (2Y differential) | +≥0,03 R poza próbą, inaczej usunąć |
| 5 | Dodanie blackoutu makro | Redukcja ogona strat bez utraty expectancy |
| 6 | Logit + kalibracja | Bije reguły poza próbą |
| 7 | Zapieczętowany hold-out — **jedno uruchomienie** | Decyzja go/no-go |

**Krok 1 jest najważniejszy i najczęściej pomijany.** Bez znajomości rozkładu zerowego nie wiecie, czy Sharpe 0,9 to sukces czy typowy wynik losowania.

---

# 5. Model wielointerwałowy

## 5.1 Diagnoza

Odpowiadam wprost na Wasze pytania:

| Pytanie | Odpowiedź |
|---|---|
| Czy D1 powinien być hard filterem czy kontekstem? | **Ani jednym, ani drugim jako osobna warstwa.** Informacja „kontekstu D1" to po prostu zwrot na długim lookbacku — wyrażcie go jako cechę ciągłą na bazie H1 |
| Czy H4 powinien definiować reżim? | **Nie.** Reżim to zmienność, a zmienność mierzy się lepiej oknem kroczącym niż agregatem świecowym o arbitralnej fazie (§3.4) |
| Czy H1 powinien wykrywać setup? | **Tak — H1 jest jedyną bazą, której potrzebujecie** |
| Czy M15 wyłącznie do timingu? | **Poza V1.** M15 nie wnosi do sygnału; M1/tick wnoszą do symulatora fillów |
| Czy wymagana pełna zgodność TF? | **Nie.** Koniunkcja skorelowanych warunków zabija N bez zysku informacyjnego (§3.3) |
| Czy partial alignment jest lepszy? | **Tak, w formie ciągłego score'u** — czyli po prostu suma znormalizowanych zwrotów na kilku lookbackach |
| Czy różne instrumenty potrzebują innych reguł? | **Nie w V1.** Osobne reguły per para = ×8 parametrów przy ÷8 próbie na regułę |

## 5.2 Proponowana zamiana

**Zamiast czterech timeframe'ów — jedna baza H1 i term structure momentum.**

| Stara warstwa | Nowa reprezentacja (wszystko na H1) |
|---|---|
| D1 context | `r_480` = zwrot za 480 barów H1 (≈ 20 dni handlowych), znormalizowany przez ATR |
| H4 trend | `r_120` = zwrot za 120 barów H1 (≈ 5 dni) |
| H1 setup | `r_24` = zwrot za 24 bary H1 (≈ 1 dzień) + pozycja w kanale Donchiana |
| M15 entry | — (usunięte z sygnału) |

Te cztery liczby zawierają **wszystko**, co zawierała hierarchia TF, plus:
- brak arbitralnej fazy świec,
- brak problemu DST,
- brak feed-dependent definicji D1,
- jednolita częstotliwość decyzyjna,
- ~4 parametry zamiast ~40.

## 5.3 Częstotliwość decyzyjna

**Rekomendacja: ocena raz na zamknięcie świecy H1**, a w wariancie jeszcze prostszym — **raz dziennie o stałej godzinie UTC**.

Uzasadnienie: mniej punktów decyzyjnych = mniej okazji do dopasowania się do szumu, mniej kosztów, mniejsza wrażliwość na mikrostrukturę. Dla systemu swingowego z horyzontem 3–10 dni granularność H1 jest już z zapasem wystarczająca. **[OPINIA]** Jeśli sygnał wymaga precyzji lepszej niż jedna godzina, żeby działać, to prawdopodobnie nie jest sygnałem.

## 5.4 Pooling po instrumentach

**Wszystkie cechy normalizowane przez ATR danego instrumentu, model uczony na połączonej próbie wszystkich par.**

Korzyść: ~8× większa próba treningowa i wymuszenie ogólności zamiast dopasowania do jednej pary.

Koszt: przekrojowa korelacja obserwacji. **Musi być uwzględniona w testach istotności** — bootstrap blokowy po dacie (całe dni jako bloki), nie po obserwacjach.

---

# 6. Technical Engine

## 6.1 Pełna lista cech V1 — sześć pozycji

| # | Cecha | Definicja | Rola |
|---|---|---|---|
| 1 | `atr_h1_14` | ATR(14) na H1, w jednostkach ceny | Normalizator cech. Nie jest cechą predykcyjną |
| 2 | `mom_24` | `(close − close[−24]) / (atr_h1_14 × √24)` | Momentum krótkie |
| 3 | `mom_120` | `(close − close[−120]) / (atr_h1_14 × √120)` | Momentum średnie |
| 4 | `mom_480` | `(close − close[−480]) / (atr_h1_14 × √480)` | Momentum długie (dawne „D1 context") |
| 5 | `donch_pos_55` | `(close − min_55) / (max_55 − min_55)` ∈ [0,1] | Pozycja w zakresie; zastępuje S/R, breakout i „market structure" |
| 6 | `vol_pct_252` | percentyl `atr_d1_14` względem **rozszerzającego się** okna ≥252 dni | Warunkowanie reżimem (ciągłe) |

To wszystko. Sześć liczb.

**Dwie rozłączne skale zmienności.** `atr_h1_14` służy wyłącznie normalizacji cech, `atr_d1_14` (ATR(14) na barach D1) wyłącznie skalowaniu barier i sizingu. Mieszanie ich jest błędem — patrz §11.2. Czynnik `√n` skaluje każde momentum zmiennością jego własnego horyzontu; bez niego trzy cechy momentum różnią się skalą o czynnik ~√20 i psują regularyzację L2.

## 6.2 Co zostało usunięte i dlaczego

| Usunięte | Powód |
|---|---|
| RSI | `RSI(n)` to monotoniczna funkcja stosunku sum przyrostów dodatnich do całkowitych — bliski duplikat `mom_n` po normalizacji |
| MACD | Różnica dwóch EMA ≡ liniowa kombinacja momentum na dwóch lookbackach |
| ADX | Miesza siłę trendu i zmienność; rozdzielenie na `mom` i `vol_pct` jest czystsze i interpretowalne |
| Stochastic, CCI, Williams %R | Wszystkie to warianty „gdzie cena jest w zakresie" ≡ `donch_pos` |
| Bollinger Bands | `(cena − SMA)/σ` ≡ `mom` znormalizowane zmiennością |
| Osobne EMA/SMA | Bez normalizacji nie są cechą; po normalizacji to `mom` |
| Support/Resistance | Brak jednoznacznej definicji |
| Wolumen | **[FAKT]** W spot FX nie istnieje prawdziwy wolumen — brokerzy raportują tick count własnego feedu. Nieporównywalne między źródłami |

**[OPINIA]** Podejrzewam, że macierz korelacji standardowego zestawu 12 wskaźników ma efektywny rank 3–4. Sprawdźcie to — to jest tani test (PCA na cechach), zajmuje godzinę i jest bardzo pouczający.

## 6.3 Cechy warunkowo dopuszczalne w V2 (po przejściu Gate 2)

- `skew_120`, `kurt_120` — asymetria rozkładu zwrotów
- `range_efficiency` = `|r_n| / Σ|r_1|` (miara „czystości" trendu, Kaufman Efficiency Ratio)
- Godzina sesji / dzień tygodnia (sezonowość intradzienna) — **ostrożnie, silny kandydat na data mining**

## 6.4 Formalizacja „market structure" — konkretnie

Prosiliście o zamianę subiektywnych pojęć na deterministyczne reguły. Oto jak to wygląda po sformalizowaniu:

| Pojęcie SMC | Deterministyczna wersja | Ocena |
|---|---|---|
| Swing high/low | Fraktal: `high[i]` jest max w oknie `[i−k, i+k]` | **Wymaga potwierdzenia k barów po fakcie → sygnał dostępny dopiero w `i+k`. Notoryczne źródło look-ahead** |
| HH/HL, LH/LL | Sekwencja swingów wg powyższego | Zależy od `k`; dla `k` z zakresu 3–10 wyniki się istotnie różnią → ukryty parametr |
| BOS (break of structure) | `close > ostatni swing high` | ≡ `close > max_n` = **Donchian breakout**. Nic nowego |
| CHoCH | Pierwszy BOS w przeciwnym kierunku po serii | ≡ zmiana znaku `donch_pos` przez skrajność. Nic nowego |
| Liquidity / liquidity grab | „Wybicie poziomu i powrót" | Wymaga progu czasu i progu powrotu = 2 dodatkowe parametry. **Czysta konstrukcja post-hoc** |
| Order block | Ostatnia świeca przeciwna przed impulsem | Wymaga definicji „impulsu" = kolejny parametr |

**Wniosek: po uczciwej formalizacji cała rodzina SMC redukuje się do Donchian + ATR, które już macie, plus 2–4 wolne parametry, których nie stać Was na estymację.**

**REMOVE.**

## 6.5 Wyjątek: FVG jest faktycznie deterministyczny

Uczciwie: Fair Value Gap ma jednoznaczną definicję trzyświecową — luka bycza gdy `low[i] > high[i−2]`. Zero wolnych parametrów. Jest testowalny.

**[BRAK DOWODÓW — WYMAGANY TEST.]** Nie znam evidence base dla wartości predykcyjnej FVG w FX. Jeśli chcecie, to jest jedyny element SMC, który da się uczciwie sprawdzić — jako **jeden prerejestrowany test w V2**, nie jako komponent V1.

---

# 7. Macro Engine

## 7.1 Rozstrzygnięcie zasadnicze

Dokumenty traktują macro jako źródło kierunkowej alfy. **To jest prawdopodobnie błąd na Waszym horyzoncie.**

**[FAKT]** Literatura wysokiej częstotliwości (Andersen/Bollerslev/Diebold/Vega 2003 i późniejsze prace o price discovery w FX) pokazuje, że reakcja kursu na niespodziankę makro jest **niemal natychmiastowa**, a materiał z wyszukiwania wskazuje na **brak wyraźnego post-announcement drift w FX** — zdarza się natomiast odwrócenie po małych niespodziankach.

To znaczy: informacja jest wyceniona, zanim zdążycie ją użyć na H1. Do tego spread w momencie publikacji rozszerza się wielokrotnie, a poślizg jest największy — więc nawet część, którą teoretycznie dałoby się złapać, konsumuje koszt.

## 7.2 Podział, o który prosiliście (A–E z prompta audytowego)

| Komponent | Ocena V1 | Uzasadnienie |
|---|---|---|
| **A. Event surprise** (actual vs consensus) | **REMOVE** | Brak driftu + niemożliwy do odtworzenia point-in-time consensus z darmowych źródeł (§7.4) |
| **B. Monetary policy repricing** | **KEEP w formie rynkowej** | Zmiana 2Y yield differential, nie tekst |
| **C. Yield / rate differential** | **KEEP** | Jedyna macro-cecha z realnym priorem (carry). Darmowa, wolnozmienna, point-in-time |
| **D. Central bank text** | **REMOVE** | §3.9 + próba ~32/rok |
| **E. Scheduled-event risk** | **KEEP** | Kontrola ryzyka, nie alfa. Wymaga tylko harmonogramu |

## 7.3 Konkretna specyfikacja macro V1 — dwie rzeczy

### 7.3.1 Carry / rate differential

```
carry_2y(para XXXYYY, t) = yield_2y(XXX, t) − yield_2y(YYY, t)
d_carry_20d(t)           = carry_2y(t) − carry_2y(t − 20 dni roboczych)
```

- Źródło: FRED (`DGS2` dla US) + odpowiedniki krajowe; gdzie brak — obligacje 2Y z oficjalnych źródeł banków centralnych.
- **Krytyczne:** wszystkie odczyty przez ALFRED z `realtime_start` = data decyzji, plus **jeden dzień opóźnienia publikacji** jako margines bezpieczeństwa.
- `d_carry_20d` jest proxy dla „repricingu oczekiwań" — mierzy to, co miała mierzyć analiza tekstu banków centralnych, tylko rynkowo i bez leakage'u.

**[FAKT]** Historyczne prawdopodobieństwa z CME FedWatch **nie są darmowo dostępne** — pełna historia wymaga płatnego API FedWatch lub CME DataMine; darmowy feed settlementów przechowuje ~5 dni roboczych. Rentowność 2Y jest darmowym substytutem przechwytującym większość tej informacji.

### 7.3.2 Blackout wydarzeń

```
blackout(t) = TRUE jeśli w [t − 30min, t + 120min] wypada wydarzenie
              o randze HIGH dla którejkolwiek z dwóch walut pary
```

Ranga HIGH — lista zamknięta, prerejestrowana:
- Decyzje stóp: FOMC, ECB, BoE, BoJ, RBA, BoC, RBNZ, SNB
- US: CPI, NFP/Employment Situation, PCE, retail sales, GDP (advance)
- EA: HICP flash, ECB press conference
- UK: CPI, labour market
- Inne: krajowe CPI dla walut w koszyku

Zastosowanie: **zakaz otwierania nowej pozycji w oknie blackoutu**. Nie zamykanie istniejących (to osobna hipoteza do testu).

**Dlaczego to jest legalne metodologicznie:** wymaga wyłącznie **daty i godziny** wydarzenia, które są znane z wyprzedzeniem. Zero problemu point-in-time, zero problemu rewizji, zero ryzyka licencyjnego (harmonogramy publikują BLS, BEA, Eurostat, ONS, banki centralne).

## 7.4 Dlaczego point-in-time consensus jest blokerem — szczegółowo

Żeby uczciwie zbacktestować `surprise = actual − consensus`, potrzebujecie na każde zdarzenie:

| Wymagana informacja | Dostępność za darmo |
|---|---|
| Consensus **w wersji z T−1 min** (consensus jest rewidowany do ostatniej chwili) | ❌ Brak archiwum |
| Timestamp publikacji z dokładnością do sekundy | ❌ Kalendarze podają minutę, czasem strefę niejednoznacznie |
| `actual` jako **pierwszy druk**, nie wartość zrewidowana | ⚠️ FRED/ALFRED: ✅. Kalendarze: ❌ (backfillowane) |
| `previous` w wersji obowiązującej przed publikacją | ❌ Kalendarze pokazują wartość po rewizji |
| Rozproszenie prognoz (do standaryzacji niespodzianki) | ❌ Wyłącznie płatne (Bloomberg/Refinitiv) |

**[FAKT]** Trading Economics oferuje prawdziwy endpoint point-in-time — ale w planie płatnym.

**Wniosek: przy budżecie V1 feature „surprise" nie jest możliwy do uczciwego zbacktestowania.** Wersja z backfillowanym consensusem będzie wyglądać lepiej niż rzeczywistość, bo backfill zawiera informację, której wtedy nie było.

**To jest przykład sytuacji, w której właściwą odpowiedzią jest „nie robimy tego", a nie „robimy przybliżenie".** Przybliżenie tutaj nie jest gorszym pomiarem — jest pomiarem systematycznie przesuniętym w korzystną stronę.

**V2/V3:** jeśli projekt przejdzie Gate 2, subskrypcja Trading Economics (lub porównywalna) jest uzasadnionym wydatkiem — ale dopiero wtedy.

---

# 8. Regime Engine

## 8.1 Odpowiedź: w V1 nie budujcie regime engine

**[WYLICZENIE]** Przy ~700 efektywnych obserwacjach podział na 4 reżimy daje ~175 obserwacji na reżim. Odchylenie standardowe estymatora expectancy przy σ = 1 R i N = 175 to `1/√175` ≈ 0,076 R. Czyli przedział ufności na oszacowanie edge'u w reżimie ma szerokość ~±0,15 R — szerszą niż cały edge, którego szukacie.

**Estymacja per-reżim jest przy tej próbie statystycznie bezwartościowa.**

## 8.2 Co zamiast tego

**Jedna ciągła zmienna warunkująca:** `vol_pct_252` (percentyl ATR w oknie rozszerzającym).

Zalety wobec dyskretnych reżimów:
- Nie dzieli próby — każda obserwacja wnosi informację.
- Brak progów (czyli brak parametrów do dopasowania).
- Brak problemu klasyfikacji stanu i jego niepewności.
- Trywialnie kauzalna.
- Odpowiada na to samo pytanie: „czy rynek jest teraz spokojny czy wzburzony".

**[OPINIA]** Percentyl zmienności przechwytuje moim zdaniem większość praktycznej wartości regime detection w FX, przy zerowym koszcie złożoności. „Trend vs range" jest w dużej mierze funkcją tej samej zmiennej plus `|mom|`, którą już macie.

## 8.3 Ranking metod (gdyby jednak wracać do tematu w V2)

| Metoda | Ocena | Komentarz |
|---|---|---|
| Percentyl zmienności (ciągły) | **✅ V1** | Baseline, którego trzeba najpierw pobić |
| Dwustanowy próg na zmienności | ⚠️ V2 | +1 parametr; musi udowodnić przewagę nad ciągłym |
| Trend/range przez efficiency ratio | ⚠️ V2 | Kolejne +1–2 parametry |
| GMM / k-means clustering | ❌ | Klastry w cechach ≠ reżimy w zwrotach; brak ograniczenia czasowego |
| HMM / Markov switching | ❌ V1, ⚠️ V3 | Realna wartość teoretyczna, ale: pułapka filtered/smoothed (§3.5), niestabilność estymacji stanów, wrażliwość na inicjalizację, trudna walidacja OOS |

**Twarda reguła jeśli kiedykolwiek sięgniecie po HMM:** wyłącznie `filtered_marginal_probabilities`, parametry modelu re-estymowane w każdym oknie walk-forward wyłącznie na danych przeszłych, i obowiązkowy test: czy stan w czasie *t* zmienia się, gdy dołożycie dane po *t*? Jeśli tak — macie leakage.

---

# 9. Signal Engine

## 9.1 V1a — baseline deterministyczny

Prerejestrowany, ≤3 parametry, żadnej optymalizacji po zobaczeniu wyników.

```
WEJŚCIE LONG (analogicznie SHORT):
  1.  mom_480 > 0                     — kierunek długoterminowy
  2.  donch_pos_55 > 0.8              — wybicie górnej części zakresu
  3.  NOT blackout(t)                 — brak wydarzenia makro
  4.  vol_pct_252 < 0.95              — nie w skrajnej panice zmiennościowej

  WEJŚCIE: rynkowe po zamknięciu świecy H1, po cenie ask
  SL:      entry − 2.0 × atr_d1_14
  TP:      entry + 4.0 × atr_d1_14     (RR 1:2)
  TIME:    zamknięcie po 10 dniach roboczych
```

Parametry swobodne: `{55, 2.0, 4.0}` — i **tylko te trzy**. Progi 0,8 i 0,95 są ustalone z góry i nietykane.

## 9.2 V1b — model probabilistyczny

Dopiero jeśli V1a przejdzie Gate 2.

| Element | Specyfikacja |
|---|---|
| **Input** | 6 cech z §6.1 + `carry_2y` + `d_carry_20d` = 8 cech |
| **Selekcja próby** | Wyłącznie zamknięcia H1 spełniające warunki 3 i 4 z V1a (blackout, skrajna zmienność) — reszta obserwacji nie jest kandydatem |
| **Label** | Triple barrier z **tą samą geometrią co V1a** (2/4 ATR, 10 dni). Bariery ustalone ex ante i **nigdy nie optymalizowane razem z modelem** |
| **Target** | `y ∈ {1, 0}` = TP trafione przed SL. Time barrier → `y = 0` (konserwatywnie) |
| **Model** | Regresja logistyczna, L2, `C` dobierane **wyłącznie na foldzie wewnętrznym** |
| **Kalibracja** | Isotonic lub Platt, na **osobnym foldzie kalibracyjnym**, nigdy na treningowym |
| **Probability** | `p̂` skalibrowane |
| **EV** | `EV = p̂ × TP_R − (1 − p̂) × 1.0 − koszt_R` (TP_R = 2,0) |
| **Próg** | `EV > 0.10 R` — prerejestrowany, nie strojony |

## 9.3 Warunki NO TRADE — lista zamknięta

System **nie handluje**, gdy:

1. `blackout(t) = TRUE`
2. `vol_pct_252 > 0.95` (skrajna zmienność — poślizg nieprzewidywalny)
3. `EV ≤ 0.10 R`
4. Osiągnięty limit ekspozycji na którąkolwiek z dwóch walut pary
5. Osiągnięty limit ryzyka portfela
6. Istnieje otwarta pozycja na tej samej parze
7. **Dane są niekompletne** — luka w barach H1 > 2 bary w ostatnich 480, lub brak aktualnego odczytu yieldów (< 5 dni roboczych)
8. Okno rollover: 16:45–17:15 NY (spread szeroki, wolumen minimalny)
9. Piątek po 15:00 NY (ryzyko luki weekendowej bez możliwości zarządzania)

**Punkt 7 jest nietypowy i ważny:** systemy traktują braki danych jako niewidoczne, a to jest częsty mechanizm cichego błędu. Brak danych musi być jawnym powodem NO TRADE, logowanym jak każdy inny.

## 9.4 Uwaga o EV — powtórzona, bo jest krytyczna

EV liczone z `p̂` jest tak dobre, jak kalibracja `p̂`. Obowiązkowo w raporcie z każdego backtestu:

- reliability diagram na foldach testowych,
- Brier score **w decylu najwyższego EV** (nie na całej próbie),
- **porównanie: przewidywane EV vs realizowane średnie R w każdym decylu EV**.

Jeśli w najwyższym decylu EV realizowane R jest istotnie niższe niż przewidywane — model jest przeszacowany dokładnie tam, gdzie go używacie, i EV jako kryterium nie działa (§3.7).

---

# 10. Risk Engine

## 10.1 Zasada nadrzędna dla fazy badawczej

**Wszystko mierzcie w R. Procent ryzyka dobierzcie na samym końcu.**

**[FAKT — matematyka]** Przy sizingu `wielkość = (equity × r%) / dystans_SL` i braku compoundingu wewnątrz okresu, zmiana `r%` skaluje krzywą equity liniowo. Expectancy w R, Sharpe, profit factor i max DD **w R** są niezmiennicze. Dopiero compounding i ograniczenia drawdownowe wprowadzają nieliniowość.

Wniosek: **`r%` nie jest parametrem badawczym w sensie predykcyjnym.** Nie marnujcie na niego prób. Po ustaleniu, że edge istnieje, `r%` wynika z rozkładu drawdownu i Waszej tolerancji, a nie z optymalizacji.

## 10.2 Specyfikacja V1

| Poziom | Reguła | Uzasadnienie |
|---|---|---|
| **Ryzyko transakcji** | Stałe `r%` equity; `SL = 2 × atr_d1_14` | Stop w ATR ⇒ sizing już jest odwrotnie proporcjonalny do zmienności. **Nie dodawać drugiej warstwy vol-scalingu — to podwójne liczenie** |
| **Ekspozycja walutowa** | Max **2 R netto** na pojedynczą walutę | Kluczowe: long EURUSD + long GBPUSD + short USDJPY to 3 R short USD, nie 3 niezależne zakłady |
| **Ryzyko portfela** | Max **6 R** sumy otwartych ryzyk, liczone przy założeniu `ρ = 1` wewnątrz bloku walutowego | Przy ~700 obserwacjach estymacja kowariancji jest szumem. Konserwatywne bloki są odporniejsze |
| **Bloki walutowe** | `{USD}`, `{EUR, CHF}`, `{GBP}`, `{JPY}`, `{AUD, NZD, CAD}` (commodity/risk-on) | Przybliżenie jakościowe, ale stabilne w czasie |
| **Jedna pozycja na parę** | Twarde | Eliminuje ukryty pyramiding |
| **Drawdown de-risking** | **BRAK w V1** | Czyni wyniki ścieżkowo zależnymi i komplikuje Monte Carlo. TEST w V2 |

## 10.3 Model kosztów — obowiązkowy, jawny, konserwatywny

Bez tego cały backtest jest bezwartościowy.

| Składnik | Model V1 |
|---|---|
| **Spread** | Rzeczywisty historyczny bid/ask z ticków Dukascopy w momencie fillu. **Nie średni spread.** Nie mid |
| **Prowizja** | Wliczona w podłogę kosztu — nie modelowana osobno (ADR-024) |
| **Poślizg — wejście** | ≥ 0,5 × mediana spreadu w danej godzinie, w niekorzystną stronę |
| **Poślizg — SL** | **≥ 1,0 × spread** w niekorzystną stronę. Stop-loss ma **asymetryczny poślizg** — realizuje się dokładnie wtedy, gdy rynek się porusza |
| **Poślizg — TP** | 0 (limit); ale **fill tylko przy pełnym przekroczeniu poziomu** |
| **Swap / financing** | Punkty swapowe brokera; **[WYLICZENIE]** przy notional ≈ 0,9× equity i 5-dniowym trzymaniu drag rzędu 1% rocznie daje ~0,025 R — porównywalne ze spreadem, więc nie do pominięcia. Potrójny swap w środę |
| **Weekend gap** | Otwarcie niedzielne po cenie rzeczywistej; stopy **nie chronią przez lukę** — fill po pierwszej dostępnej cenie |
| **Rozszerzenie spreadu** | Automatycznie zawarte, jeśli używacie rzeczywistych ticków bid/ask |

**Test wrażliwości obowiązkowy: raportujcie wynik przy 1×, 2× i 3× modelowanych kosztach. Jeśli edge znika przy 2×, nie jest prawdziwy.**

---

# 11. Exit Engine

## 11.1 Największe niedostrzeżone źródło overfittingu

Reguły wyjścia mają zwykle **więcej** stopni swobody niż reguły wejścia (mnożnik SL, mnożnik TP, aktywacja trailingu, krok trailingu, break-even trigger, time barrier, exit na reżimie...). Optymalizacja wejścia i wyjścia razem mnoży przestrzeń hipotez.

**Reguła: wyjście jest ustalone ex ante jako część definicji etykiety i nie jest strojone razem z modelem.**

## 11.2 V1 — wyjście minimalne

```
SL:   2.0 × atr_d1_14 od wejścia, statyczny
TP:   4.0 × atr_d1_14 od wejścia, statyczny
TIME: wyjście rynkowe po 10 dniach roboczych
```

Trzy liczby. Zero trailingu. Zero break-even. Zero exitów na reżimie.

**Skala barier musi odpowiadać horyzontowi.** Warunkiem poprawności triple barrier jest `bariera ≈ σ√T`. Dla T = 10 dni i σ_dzienna ≈ 0,55% na EURUSD właściwy rząd wielkości to ~1,1% ceny, czyli `2 × atr_d1_14` (≈120 pipsów). Bariera `2 × atr_h1_14` (≈20 pipsów) zostałaby trafiona w ciągu godzin, bariera czasowa nigdy by nie zadziałała, a etykiety zdegenerowałyby się do szumu mikrostruktury. To jest pułapka niezależna od doboru cech i łatwa do przeoczenia, bo obie wielkości nazywają się „ATR(14)".

**Dlaczego statyczne:** trailing czyni wynik zależnym od ścieżki wewnątrz świecy, przez co nie da się go wyrazić jako triple barrier i **wymaga symulacji tickowej**, żeby nie kłamał. Do tego dodaje 2–3 parametry do i tak przeciążonej przestrzeni.

## 11.3 Warianty do testu po Gate 2 — maksymalnie trzy, prerejestrowane

1. **Trailing chandelier:** `SL = max(SL, highest_close_since_entry − 3 × ATR)`
2. **Break-even po 1R:** przesunięcie SL na wejście + koszt po osiągnięciu +1 R
3. **Krótszy time barrier:** 5 dni zamiast 10

Każdy testowany **osobno**, przeciwko identycznym wejściom, z zalogowaniem próby. Żadnych kombinacji, żadnego przeszukiwania siatki.

## 11.4 Jak ograniczyć overfitting wyjść — konkretnie

- **Kontrola losowa dla wyjścia:** to samo wyjście przy losowych wejściach. Jeśli wyjście X poprawia wynik również przy losowych wejściach, to nie jest interakcja sygnał–wyjście, tylko ogólny efekt geometrii (najczęściej: zmiana efektywnej ekspozycji). Bardzo pouczający test, prawie nigdy nierobiony.
- **Wykres wrażliwości:** expectancy jako funkcja mnożnika SL na siatce {1,5; 2,0; 2,5; 3,0}. Chcecie **płaskowyżu**, nie szpikulca. Szpikulec = dopasowanie do szumu.
- **Stabilność między parami:** jeśli optymalny mnożnik to 2,0 na EURUSD i 4,5 na GBPJPY, to nie znaleźliście struktury, tylko szum.

---

# 12. Pyramiding

## 12.1 Decyzja: REMOVE z V1. Bezwarunkowo.

Trzy niezależne powody, z których każdy wystarcza:

**1. Mnoży przestrzeń parametrów na bazie niezwalidowanego sygnału.** Kiedy dokładać, ile, jak przesunąć SL, jaki cap — to ≥4 nowe parametry dołożone do systemu, którego edge bazowy nie został jeszcze wykazany. To jest optymalizacja nadbudowy nad czymś, co może być zerem.

**2. Aktywnie utrudnia pomiar — to jest argument, który przesądza.** Pyramiding zwiększa skośność i wariancję rozkładu wyników pojedynczego trade idea. Z §1.3: `N ∝ (σ/μ)²`. Zwiększenie σ przy stałym μ **zwiększa liczbę transakcji potrzebną do wykrycia edge'u**. Innymi słowy: pyramiding sprawia, że trudniej stwierdzić, czy system w ogóle działa. Na etapie badawczym to jest dyskwalifikujące.

**3. Jest matematycznie nadmiarowy jako osobny koncept.** Pyramiding to po prostu **wypukła funkcja sizingu warunkowana zrealizowanym ruchem**. Jako taki należy do warstwy sizingu i powinien być testowany jako nakładka na zwalidowany sygnał — a nie jako element strategii wejścia.

## 12.2 Uwaga o „niezrealizowanym zysku jako darmowym kapitale"

Dokumenty słusznie odrzucają tę intuicję. Dopowiem, dlaczego jest ona szczególnie zdradliwa: pyramiding sprawia, że **największą ekspozycję macie w momencie największego dotychczasowego ruchu**, czyli typowo najbliżej wyczerpania trendu i przy najwyższej zmienności. Rozkład wyników zyskuje gruby lewy ogon dokładnie w tych stanach, w których korelacja między parami rośnie do ~1.

## 12.3 Jeśli mimo to wróci w V2

Twarde ograniczenia, prerejestrowane:

| Parametr | Wartość |
|---|---|
| Max dodań | 2 |
| **Total risk cap całej piramidy** | ≤ 1,0 × początkowego ryzyka R — **piramida nigdy nie zwiększa ryzyka scenariusza** |
| Warunek konieczny | SL wszystkich jednostek na poziomie ≥ break-even łącznej pozycji **przed** dodaniem |
| Zakaz | blackout makro, `vol_pct > 0,8`, dodanie bliżej niż 1 ATR od poprzedniego |
| Księgowanie | **Jedna ekspozycja, jedno ryzyko scenariusza** — liczone przeciw limitom portfela jak jedna pozycja |

---

# 13. Backtesting Framework

To jest najważniejsza część projektu. Więcej wartości powstanie tutaj niż w signal engine.

## 13.1 Zasada

> Backtest nie służy do znalezienia strategii, która działa. Służy do **odrzucenia** strategii, które nie działają. Jeśli Wasz framework nie potrafi rutynowo powiedzieć „nie", jest zepsuty.

## 13.2 Krok 0 — walidacja samego symulatora (2 tygodnie, przed wszystkim innym)

Zanim cokolwiek zbadacie, musicie wiedzieć, że aparatura mierzy.

| Test | Kryterium przejścia |
|---|---|
| Rekonstrukcja barów | H1 zbudowane z ticków Dukascopy zgadzają się z barami z niezależnego źródła (HistData/OANDA) w granicach spreadu, na ≥99% barów |
| Integralność ticków | Raport braków: luki > 60 s w godzinach handlowych, zliczone i udokumentowane |
| Sanity fillów | Ręcznie zweryfikowane 20 transakcji, tick po ticku |
| Kolejność barier | Udokumentowany odsetek barów H1 dotykających obu barier; porównanie wyniku „tick-accurate" vs „pesymistycznie" vs „optymistycznie". **Różnica między wariantem optymistycznym a tickowym to miara błędu, który popełniłby naiwny backtest** |
| Realizm kosztów | Efektywny koszt = `max(spread_tickowy + prowizja, podłoga)`; podłoga 1,5 pipsa majors, 2,5 crosses. **Broker-agnostyczne** — patrz ADR-024 |
| Test negatywny | Strategia losowa daje expectancy ≈ **−koszt**, nie 0 i nie +. Jeśli daje 0 lub więcej, **model kosztów jest zepsuty** |

**Ostatni wiersz jest najtańszym i najostrzejszym testem poprawności całego stosu. Zróbcie go pierwszy.**

## 13.3 Podział danych

```
2015-01-01 ─────────── 2021-12-31 │ 2022-01-01 ── 2023-12-31 │ 2024-01-01 ── 2025-12-31
        RESEARCH (CPCV)           │      VALIDATION           │    SEALED HOLD-OUT
                                  │   (ograniczona liczba     │  (JEDNO uruchomienie,
                                  │    uruchomień, logowane)  │   na samym końcu)
```

Zasady niepodlegające negocjacji:
- Hold-out **nie jest oglądany, wczytywany ani wspominany** do momentu decyzji finalnej.
- Każde uruchomienie na VALIDATION jest logowane do `trials.jsonl`.
- Po uruchomieniu na hold-oucie **projekt się kończy** — wynikiem jest go albo no-go. Nie „dostroimy i sprawdzimy jeszcze raz".

## 13.4 Walidacja krzyżowa

**CPCV (Combinatorial Purged Cross-Validation)** na części RESEARCH:

| Parametr | Wartość | Uzasadnienie |
|---|---|---|
| Liczba grup | 6 | |
| Grup testowych na kombinację | 2 | Daje 15 ścieżek zamiast 1 → rozkład wyników, nie punkt |
| **Purge** | = max holding period = **10 dni roboczych** | Usuwa z treningu obserwacje, których okno wyniku zachodzi na test |
| **Embargo** | 5 dni roboczych | Bufor na autokorelację zmienności |
| Jednostka bloku | **cały dzień**, wszystkie pary | Bo obserwacje w tym samym dniu na różnych parach są skorelowane (§5.4) |

Walk-forward (okno kroczące 3 lata trening / 6 mies. test) jako **kontrola zgodności** z CPCV. Jeśli CPCV i WF dają istotnie różne wyniki — macie leakage albo niestacjonarność; w obu wypadkach nie wolno iść dalej.

## 13.5 Kontrole — obowiązkowe, w tej kolejności

| # | Kontrola | Co mierzy |
|---|---|---|
| 1 | **Random entry, identyczne wyjście i sizing, ta sama liczba transakcji** | Rozkład zerowy. **Najważniejszy benchmark w całym projekcie.** Większość „edge'ów" detalicznych ginie właśnie tutaj |
| 2 | **Shuffled labels** | Czy pipeline nie ma leakage'u. Wynik musi być ≈ 0 |
| 3 | **Shifted features** (cechy przesunięte o +1 bar w przyszłość) | Jeśli wynik **rośnie** — macie look-ahead |
| 4 | **Buy & hold / carry-only** | Czy bijecie trywialną alternatywę |
| 5 | **Koszyk carry + trend** (§17.4) | Czy bijecie najlepszą znaną darmową alternatywę |
| 6 | Block bootstrap (bloki 20-dniowe), 10 000 replikacji | CI dla expectancy i Sharpe'a |
| 7 | Monte Carlo permutacji kolejności transakcji | Rozkład max DD |

## 13.6 Metryki i progi

| Metryka | Próg akceptacji |
|---|---|
| Expectancy netto | ≥ **+0,10 R**/transakcja |
| t-stat expectancy (block bootstrap) | ≥ **2,0** |
| **Deflated Sharpe Ratio** | ≥ **0** przy prawdziwej liczbie prób z `trials.jsonl` |
| **PBO (CSCV)** | ≤ **0,30** |
| Wrażliwość kosztowa | Expectancy > 0 przy **2× kosztach** |
| Stabilność instrumentów | Dodatnia na ≥ **4 z 6** par |
| Stabilność czasowa | Dodatnia w ≥ **2 z 3** podokresów |
| Stabilność parametrów | **Płaskowyż**, nie szpikulec, w analizie wrażliwości |
| Kalibracja (tylko V1b) | Brier w top-decylu EV nie gorszy niż base rate; monotoniczny reliability diagram |

## 13.7 Obowiązkowa checklista leakage'u

Do przejścia przed **każdym** raportowanym wynikiem:

- [ ] Wszystkie normalizacje (z-score, percentyl, skaler, winsoryzacja) liczone w oknie **rozszerzającym**, tylko z przeszłości
- [ ] Żaden `fit()` nie widział danych testowych — w tym `StandardScaler`, imputer, kalibrator
- [ ] Wszystkie dane makro pobrane przez ALFRED z `realtime_start` = data decyzji
- [ ] Bar H1 zamknięty **przed** momentem decyzji (klasyczny błąd off-by-one: użycie `close` bieżącego bara)
- [ ] Symulator fillów nie widzi cen po momencie decyzji
- [ ] Kolejność barier rozstrzygana na tickach lub pesymistycznie
- [ ] Ceny bid i ask osobno; **nigdzie mid**
- [ ] Brak modeli stanu ze smoothingiem (`predict()` Viterbi, `smoothed_marginal_probabilities`)
- [ ] Zbiór instrumentów zamrożony przed pierwszym backtestem
- [ ] Wszystkie progi i parametry zapisane w pliku konfiguracyjnym z hashem git **przed** uruchomieniem
- [ ] `trials.jsonl` zaktualizowany automatycznie
- [ ] Żadne wejście do backtestu nie pochodzi od LLM
- [ ] Testy 2 i 3 z §13.5 przeszły

---

# 14. Data Architecture

## 14.1 Klasyfikacja źródeł

| Źródło | Co dostarcza | Ograniczenia | Klasyfikacja |
|---|---|---|---|
| **Dukascopy historical tick** | Tick bid/ask, 15+ lat, 60+ instrumentów, bez klucza API | **[FAKT]** Format: tysiące plików LZMA, wymaga downloadera i resamplingu. Feed jednego brokera — nie jest „rynkiem". Konwencja czasu do zweryfikowania | **USE** — podstawowy feed badawczy |
| **FRED / ALFRED** | Serie makro + **prawdziwe vintages** przez `realtime_start`/`realtime_end`; yieldy US | **[FAKT]** Głównie US; pokrycie zagraniczne uboższe. Klucz API darmowy | **USE** — podstawa macro |
| **HistData.com** | M1 i tick, darmowe, bez konta | **[FAKT]** Bary M1 **wyłącznie z bid**; ask tylko w plikach tickowych. Timestamp w EST **bez DST**. Brak gwarancji jakości | **USE WITH LIMITATIONS** — wyłącznie do **krzyżowej weryfikacji** barów Dukascopy |
| **OANDA v20 (demo)** | REST + streaming, bid/ask/mid | **[FAKT]** `count` max **5000** świec na żądanie → historia przez paginację. Wymaga rachunku v20. Feed brokerski | **USE** — do live/paper, **nie** jako główny feed historyczny |
| **ECB Data Portal / BoE / BoJ / ONS / Eurostat / BLS / BEA** | Oficjalne serie + **harmonogramy publikacji** | Różne API, różne formaty, wymaga adapterów | **USE** — harmonogram wydarzeń i yieldy nie-US |
| **Trading Economics API** | Kalendarz z **prawdziwym point-in-time** | **[FAKT]** Funkcja point-in-time w planie płatnym | **RESEARCH ONLY / V2** — jedyny czysty sposób na feature „surprise" |
| **ForexFactory / Investing.com (scraping)** | Kalendarz z consensusem | **[FAKT]** ToS ograniczają scraping i redystrybucję. Dane backfillowane/edytowane → **brak archiwum point-in-time** | **REMOVE** — ryzyko prawne i metodologiczne |
| **CME FedWatch** | Implikowane prawdopodobieństwa stóp | **[FAKT]** Historia przez płatne API FedWatch lub DataMine; darmowy feed settlementów ~5 dni | **REMOVE z V1** — substytut: 2Y yield differential |
| **Yahoo Finance / yfinance** | Kursy FX | Dane dzienne, jakość niepewna, brak bid/ask, ToS niejasne | **REMOVE** |
| **Alpha Vantage / Twelve Data (free)** | FX intraday | Ostre limity requestów, krótka historia intraday na darmowym planie | **REMOVE z V1** |
| **OpenBB** | Agregacja danych | Warstwa nad innymi źródłami — nie rozwiązuje żadnego z powyższych problemów, dodaje zależność | **REMOVE z V1** |
| **Social sentiment (X, Reddit)** | — | Wyłączony decyzją projektową; brak dowodów incremental value | **REMOVE** |

## 14.2 Rekomendowany stack danych V1

```
CENY      Dukascopy tick bid/ask, 2015-01-01 → dziś, 6 par
          → M1 (fill engine) → H1 (cechy) → Parquet partycjonowany po parze i roku

YIELDY    FRED/ALFRED (DGS2) + ECB/BoE/BoJ/ONS dla pozostałych walut
          → seria dzienna z realtime_start, Parquet

KALENDARZ Harmonogram wydarzeń HIGH z oficjalnych źródeł
          → tylko (timestamp_utc, waluta, nazwa, ranga). BEZ wartości
```

## 14.3 Zbiór instrumentów — zamrożony przed pierwszym backtestem

Dwie rozłączne kohorty o różnych rolach — pełne uzasadnienie w **Aneksie B**.

**Kohorta A — zbiór odkrywczy (V1, bramki 0–4):**

```
EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, EURJPY
```

Majors + jeden cross; szerokie pokrycie bloków walutowych; najwęższe spready; najlepsza jakość danych.

**Kohorta B — zbiór replikacyjny (po bramce 2):**

```
XAUUSD, WTI, S&P 500, DAX
```

**Wykluczone świadomie:**
- **CHF** — **[FAKT]** dyskontynuacja pega 15.01.2015 czyni serię niereprezentacyjną; zdarzenie zachowane jako test stresowy egzekucji
- **Egzotyki** (TRY, ZAR, MXN) — szeroki spread, ryzyko polityczne, słabe dane
- **GBPJPY** — mimo popularności: klasyczny kandydat na selection bias („bo ładnie trenduje")
- **Dow Jones** — korelacja z S&P ~0,95, ważony ceną; zero wartości informacyjnej
- **Nasdaq** — korelacja z S&P ~0,90–0,95; wybrany jeden indeks US
- **Srebro, Nikkei 225** — odroczone do V2 (§18)

## 14.4 Problem feed mismatch — jak go traktować

**[FAKT]** FX jest OTC: nie ma jednej ceny. Dukascopy ≠ OANDA ≠ Wasz docelowy broker. Różnice dotyczą poziomu, spreadu, granic świec i traktowania weekendu.

Obowiązkowo w V1:
1. Cały research na **jednym** feedzie (Dukascopy) — spójność ważniejsza niż „prawda".
2. **Test wrażliwości na feed:** powtórzcie finalny backtest na barach z HistData. Jeśli wynik istotnie się zmienia — strategia zależy od artefaktów feedu, nie od rynku. To jest tani i bardzo ostry test.
3. Wszystkie timestampy w **UTC**, sesje wyprowadzane z UTC z jawnym uwzględnieniem różnych dat DST w USA i UE.
4. Weekend: jawna reguła, że pozycja jest trzymana przez lukę i stopy nie chronią.

---

# 15. Technology Architecture

## 15.1 Stack V1 — minimalny

```
Python 3.12
├── polars            — przetwarzanie danych (znacznie szybsze od pandas na tickach)
├── numpy
├── scikit-learn      — logit + kalibracja, nic więcej
├── scipy             — testy statystyczne
├── pyarrow           — Parquet
├── matplotlib        — wykresy do raportów
└── pytest            — testy, przede wszystkim symulatora egzekucji

Przechowywanie:  pliki Parquet na dysku
Interfejs:       CLI + skrypty; notebooki wyłącznie do eksploracji
Konfiguracja:    YAML z hashem git, wersjonowany
Wyniki:          katalog run/<timestamp>/ + append do trials.jsonl
Kontrola wersji: git (repo nie jest jeszcze zainicjalizowane — zróbcie to)
```

## 15.2 Czego świadomie nie ma i dlaczego

| Technologia z dokumentów | Dlaczego nie w V1 |
|---|---|
| PostgreSQL / TimescaleDB | 10 lat × 6 par × H1 to ~500 tys. wierszy; ticki to ~10–50 GB na dysku. Parquet + Polars radzi sobie bez serwera. Baza to koszt bez korzyści badawczej |
| Redis | Nie ma stanu współdzielonego. Nie ma live'u |
| FastAPI | Nie ma klienta |
| React / Next.js / Lightweight Charts | Zero wartości dowodowej. Największy pochłaniacz czasu w projektach tego typu |
| Docker | Jeden użytkownik, jedna maszyna. `venv` + `requirements.txt` wystarczy. Docker gdy będzie deployment |
| Discord | Kanał dostawy dla sygnału, którego jeszcze nie ma |
| MCP | Warstwa integracji dla systemu, który jeszcze nie istnieje |
| XGBoost / LightGBM | §2.5 |
| TA-Lib | 6 cech liczy się w 30 liniach numpy. Unikacie zależności C i niejasności definicji wskaźników |
| PyTorch | Nie |

**[OPINIA]** Budowanie infrastruktury przed walidacją edge'u to najczęstszy sposób, w jaki projekty tego typu umierają — nie dlatego, że infrastruktura jest zła, ale dlatego, że po trzech miesiącach budowania dashboardu nikt nie chce już usłyszeć, że sygnał nie działa. Koszt utopiony psuje ocenę. To jest ryzyko projektowe, nie tylko techniczne.

## 15.3 Struktura repozytorium

```
market-quant/
├── CLAUDE.md
├── docs/
│   ├── PROJECT_SPEC.md          ← specyfikacja obowiązująca
│   ├── DECISIONS.md             ← log decyzji (ADR)
│   ├── AUDIT_REPORT.md          ← ten dokument
│   └── research/                ← materiał źródłowy (historyczny)
├── config/
│   └── v1_baseline.yaml         ← wszystkie parametry, wersjonowane
├── src/
│   ├── data/                    ← downloadery, resampling, walidacja jakości
│   ├── execution/               ← ★ symulator fillów — najważniejszy moduł
│   ├── features/                ← 6 cech
│   ├── labels/                  ← triple barrier
│   ├── signal/                  ← reguła + logit
│   ├── risk/                    ← sizing i limity
│   └── validation/              ← CPCV, DSR, PBO, kontrole, bootstrap
├── tests/                       ← ★ najgęściej dla execution/
├── trials.jsonl                 ← rejestr WSZYSTKICH prób (append-only)
└── runs/                        ← wyniki, niewersjonowane
```

Gwiazdkami oznaczyłem to, na czym powinniście spędzić najwięcej czasu. **Symulator egzekucji zasługuje na więcej uwagi niż signal engine** — bo błąd w signal engine daje zły sygnał, a błąd w symulatorze daje **fałszywą pewność**, że zły sygnał jest dobry.

---

# 16. Rola Claude

## 16.1 Co Claude POWINIEN robić

| Rola | Uzasadnienie |
|---|---|
| Implementacja kodu | Oczywiste i bezpieczne |
| **Adwersaryjny audyt leakage'u** | Największa wartość. Konkretne zadanie: „znajdź w tym module każdy sposób, w jaki informacja z przyszłości mogłaby trafić do cechy" |
| Implementacja testów statystycznych | DSR, PBO, CPCV, block bootstrap — łatwe do pomylenia, warto mieć drugą parę oczu |
| Projektowanie eksperymentów | Pomoc w **prerejestracji** hipotez przed uruchomieniem |
| Analiza post-hoc **zamkniętego** eksperymentu | Za zgodą, że wynik analizy nie wraca do V1 bez zalogowania próby |
| Wyjaśnianie metodologii | — |
| Code review | — |

## 16.2 Czego Claude NIE POWINIEN robić — twarde zakazy

| Zakaz | Powód |
|---|---|
| **Generowanie jakichkolwiek danych wejściowych do backtestu** | Parametric look-ahead (§3.9). Dotyczy scoringu tekstu CB, klasyfikacji newsów, „oceny sentymentu" historycznych zdarzeń. **Nienaprawialne** |
| **Runtime signal generation** | Brak kalibracji, brak odtwarzalności, brak możliwości backtestu |
| **Wybór, który wariant backtestu zachować** | To jest selekcja modelu — czyli próba, która musi trafić do `trials.jsonl`. Delegowanie jej do LLM czyni licznik prób niepoliczalnym |
| **Interpretowanie krzywej equity jako dowodu** | LLM chętnie znajdzie narrację do każdego wykresu |
| **Decyzje o wielkości pozycji w live'ie** | — |

## 16.3 Zasada, która nie jest oczywista

> **Każda iteracja wspomagana LLM jest próbą i musi zostać zalogowana.**

Praca z asystentem zwiększa tempo generowania wariantów o rząd wielkości. Jeśli licznik prób w DSR tego nie odzwierciedla, DSR przestaje mieć jakiekolwiek znaczenie — a to jest jedyne zabezpieczenie przed §1.3.

Praktycznie: harness backtestu zapisuje wpis do `trials.jsonl` **automatycznie, przy każdym uruchomieniu**, bez możliwości ręcznego pominięcia. Nie polegajcie na dyscyplinie.

## 16.4 MCP i Discord

**Oba: nie w V1.** MCP ma sens dopiero gdy istnieje stabilny system z danymi wartymi odpytywania. Discord — gdy istnieje zwalidowany sygnał wart wysłania. Workflow „Discord → copy/paste → Claude" należy usunąć całkowicie (§3.12), bo wprowadza nieodtwarzalną decyzję uznaniową w środek pętli.

---

# 17. V1 — najmniejszy system dający wartościowe wyniki

## 17.1 Zakres

| Priorytet | Komponent |
|---|---|
| **MUST HAVE** | Downloader Dukascopy tick → M1 → H1, Parquet |
| | Raport jakości danych (luki, duplikaty, anomalie) |
| | **Symulator egzekucji tick-accurate** z pełnym modelem kosztów |
| | **Kontrola losowa** (random entry, identyczne wyjście) |
| | 6 cech technicznych (§6.1) |
| | Etykiety triple barrier |
| | Reguła deterministyczna V1a (§9.1) |
| | Risk engine: sizing + limity walutowe/portfelowe |
| | CPCV + purge/embargo + block bootstrap |
| | DSR + PBO |
| | Analiza wrażliwości: koszty, parametry, instrumenty, podokresy |
| | `trials.jsonl` z automatycznym zapisem |
| **SHOULD HAVE** | Loader FRED/ALFRED + `carry_2y` |
| | Harmonogram wydarzeń + blackout |
| | Logit + kalibracja (V1b) |
| | Benchmark: koszyk carry + trend (§17.4) |
| **LATER (V2)** | Warianty wyjść, regime engine, live paper trading, Discord, dashboard |
| **REMOVE** | Pyramiding, ML drzewiaste, HMM, analiza tekstu CB, event surprise, SMC/BOS/CHoCH/liquidity, RSI/MACD/ADX, M15 w sygnale, Postgres/Redis/FastAPI/React/Docker, MCP, social sentiment, Discord→Claude workflow |

## 17.2 Harmonogram

| Tydzień | Zakres | Wynik |
|---|---|---|
| 1–2 | Dane + raport jakości | Parquet, udokumentowane luki |
| 3–4 | **Symulator egzekucji + testy** | Test negatywny: strategia losowa daje −koszt |
| 5 | Kontrola losowa | **Rozkład zerowy expectancy i Sharpe'a** |
| 6 | Cechy + etykiety | — |
| 7 | V1a + CPCV | Pierwszy uczciwy wynik |
| 8 | DSR, PBO, wrażliwość | **Gate 2: decyzja** |
| 9–10 | (warunkowo) carry + blackout + logit | Incremental value każdego komponentu |
| 11 | (warunkowo) zapieczętowany hold-out — **jedno uruchomienie** | **Decyzja go/no-go** |

**~11 tygodni pracy niepełnowymiarowej do uczciwej odpowiedzi.** Dla porównania: sama implementacja architektury z `INITIAL_CONVERSATION.md` §13 to prawdopodobnie 6+ miesięcy przed pierwszym wiarygodnym wynikiem.

## 17.3 Co V1 ma dostarczyć

Nie „działającego bota". **Liczbę z przedziałem ufności** — odpowiedź na pytanie: czy prosta, kosztowo realistyczna strategia swingowa na 6 parach ma expectancy istotnie większe od zera po korekcie na liczbę prób?

To jest jedyny wynik, który cokolwiek znaczy.

## 17.4 Benchmark, którego dokumenty nie przewidują, a który jest niezbędny

**Koszyk carry + trend:**

```
Raz w tygodniu, na 8 walutach względem USD:
  ranking po (yield_2y + zwrot 3-miesięczny)
  long top 2, short bottom 2
  równe ryzyko, sizing przez ATR
  brak stopów, rebalans tygodniowy
```

**Dlaczego to musi być w V1:** to jest strategia z **udokumentowanym w literacie priorem**, implementowalna z tych samych darmowych danych, o znikomym obrocie (koszty pomijalne) i praktycznie zerowej liczbie stopni swobody.

**Jeśli Wasz system multi-timeframe nie bije tego koszyka poza próbą, cała złożoność jest nieuzasadniona** — a Wy macie działającą alternatywę, na którą nie trzeba było budować signal engine'u.

**[OPINIA]** Uważam ten benchmark za najbardziej wartościową pojedynczą rzecz, jaką mogę dodać do Waszego planu. Ustawia poprzeczkę na właściwym poziomie i chroni przed 6 miesiącami pracy nad czymś, co przegrywa z 50 liniami kodu.

---

# 18. V2 — tylko to, co ma potencjał mierzalnej wartości

Wyłącznie po przejściu Gate 2 **i** Gate 3. Każda pozycja to **osobny, prerejestrowany eksperyment z własnym progiem incremental value**.

| Priorytet | Komponent | Hipoteza do testu | Próg |
|---|---|---|---|
| 1 | Trailing chandelier (3×ATR) | Poprawia expectancy netto | +0,03 R |
| 2 | Time barrier 5 vs 10 dni | Krótszy horyzont = mniej ryzyka bez utraty edge'u | +0,02 R |
| 3 | M15 entry timing | Lepsze wejście daje mierzalną poprawę R | +0,03 R |
| 4 | Dwustanowy reżim zmiennościowy | Bije wersję ciągłą | +0,03 R |
| 5 | Paper trading live | Zgodność z backtestem w granicach CI | 6 mies. |
| 6 | Discord | — (dostawa) | — |
| 7 | Logit → gradient boosting | Bije logit poza próbą | +0,05 R |
| 8 | Trading Economics + event surprise | Uzasadniony wydatek dopiero tutaj | +0,05 R |
| 9 | Drawdown de-risking | Poprawia Calmar bez utraty CAGR | — |
| 10 | Pyramiding jako nakładka sizingowa | Poprawia Sharpe, nie tylko zwrot | — |
| 11 | MCP / dashboard | — (wygoda) | — |

**Reguła bez wyjątków: komponent, który nie osiągnie progu, jest usuwany, a nie „dostrajany aż zadziała". Dostrajanie aż zadziała to definicja overfittingu.**

---

# 19. Kill Criteria

Prerejestrowane. Do zapisania w `PROJECT_SPEC.md` **przed** pierwszym backtestem.

## Gate 0 — infrastruktura (koniec tygodnia 4)

**PORZUCAMY, jeśli:**
- Symulator egzekucji nie przechodzi testu negatywnego (strategia losowa nie daje expectancy ≈ −koszt), **lub**
- Luki w danych > 5% barów H1 w godzinach handlowych na ≥2 parach, **lub**
- Spread nie jest odtwarzany z rzeczywistych ticków bid/ask lub model nie stosuje podłogi kosztu.

*Uzasadnienie: bez działającej aparatury pomiarowej każdy dalszy wynik jest bezwartościowy.*

## Gate 1 — rozkład zerowy (koniec tygodnia 5)

**PORZUCAMY, jeśli:**
- Kontrola losowa daje dodatnie expectancy → model kosztów jest nierealistyczny i wymaga naprawy przed czymkolwiek innym.

## Gate 2 — baseline (koniec tygodnia 8) — **najważniejsza bramka**

**PORZUCAMY, jeśli baseline deterministyczny NIE spełnia jednocześnie:**

| Kryterium | Próg |
|---|---|
| Expectancy netto | ≥ +0,10 R |
| t-stat (block bootstrap po dniach) | ≥ 2,0 |
| **DSR przy prawdziwej liczbie prób** | ≥ 0 |
| **PBO (CSCV)** | ≤ 0,30 |
| Przewaga nad kontrolą losową | Istotna na poziomie 5% |
| Odporność kosztowa | Expectancy > 0 przy **2× kosztach** |
| Stabilność instrumentów | Dodatnia na ≥ 4 z 6 par |
| Stabilność czasowa | Dodatnia w ≥ 2 z 3 podokresów |
| Wrażliwość parametryczna | Płaskowyż, nie szpikulec |

**Jeśli Gate 2 nie przechodzi: warstwa techniczna nie ma edge'u na tych danych i w tym stylu. Nie dodajemy macro, nie dodajemy ML, nie dodajemy reżimów. Kończymy albo wracamy do zupełnie innej hipotezy ekonomicznej.**

To jest zdanie, które najłatwiej będzie zignorować. Zapiszcie je i podpiszcie się pod nim przed uruchomieniem pierwszego backtestu.

## Gate 3 — incremental value (tydzień 10)

**Każdy komponent osobno:**
- Nie daje ≥ +0,03 R poza próbą → **usuwamy komponent** (nie strojymy go).
- Jeśli po dodaniu wszystkich komponentów system nie bije **koszyka carry + trend** → złożoność nieuzasadniona, przechodzimy na koszyk.

## Gate 4 — hold-out (tydzień 11)

**Jedno uruchomienie. PORZUCAMY, jeśli:**
- Expectancy na hold-oucie < 50% expectancy z walidacji, **lub**
- Expectancy na hold-oucie < +0,05 R, **lub**
- Max DD na hold-oucie > 2× max DD z walidacji.

## Kill globalny

| Warunek | Skutek |
|---|---|
| **> 50 zalogowanych prób bez przejścia Gate 2** | STOP. Przy tej liczbie prób DSR i tak zniweluje każdy wynik |
| **> 4 miesiące pracy bez przejścia Gate 2** | STOP |
| Konieczność złamania którejkolwiek zasady z §13.7, żeby uzyskać dodatni wynik | STOP **natychmiast** — to jest sygnał, że wynik pochodzi z leakage'u |

## Warunek przejścia na prawdziwe pieniądze

**Wszystkie muszą być spełnione:**
1. Gate 4 zdany.
2. **≥ 6 miesięcy forward paper tradingu** z expectancy w granicach CI z backtestu.
3. Poślizg i spread w paper tradingu ≤ modelowane w backteście.
4. Zero ręcznych interwencji w okresie paper tradingu.

**[OPINIA]** Punkt 4 jest trudniejszy, niż brzmi, i jest tym, na czym najczęściej kończą się takie projekty.

---

# 20. Podsumowanie audytu

## 20.1 Odpowiedź na pytanie z §1

**Czy ten system ma realną szansę znaleźć statystycznie uzasadnioną przewagę po kosztach?**

Odpowiedź uczciwa: **prior jest niski, ale pytanie jest odpowiadalne — pod warunkiem radykalnego uproszczenia.**

- Wersja z dokumentów: **nie**. Przestrzeń hipotez przekracza dostępną próbę o rzędy wielkości (§1.3), więc dostaniecie dodatni wynik niezależnie od tego, czy edge istnieje. To jest gwarantowane, nie prawdopodobne.
- Wersja po audycie: **tak, można uczciwie odpowiedzieć** — z tym, że najbardziej prawdopodobną odpowiedzią jest „nie ma edge'u", i to też jest wartościowy wynik uzyskany w 11 tygodni zamiast w rok.

## 20.2 Co usunąć (lista zbiorcza)

Pyramiding · ML drzewiaste · HMM/Markov switching · analiza tekstu banków centralnych · event surprise jako alfa · scraping kalendarzy · SMC (BOS/CHoCH/liquidity/order blocks) · RSI · MACD · ADX · Stochastic · Bollinger · support/resistance · M15 w warstwie sygnału · hierarchia czterech timeframe'ów · hard filter D1 · wymóg pełnej zgodności TF · osobne reguły per instrument · fractional Kelly · osobna warstwa vol-scalingu · drawdown de-risking w V1 · PostgreSQL · TimescaleDB · Redis · FastAPI · React/Next.js · Lightweight Charts · Docker · MCP · Discord · workflow Discord→Claude · OpenBB · social sentiment · CHF z koszyka instrumentów

## 20.3 Co dodać (czego w dokumentach nie ma)

1. **Symulator egzekucji tick-accurate z rozstrzyganiem kolejności barier** (§3.8) — bez tego wszystko kłamie w tę samą stronę.
2. **Kontrola losowa jako pierwszy benchmark** (§13.5) — bez rozkładu zerowego nie wiecie, co znaczy Wasz wynik.
3. **Benchmark koszyka carry + trend** (§17.4) — jedyna alternatywa z realnym priorem.
4. **`trials.jsonl` z automatycznym zapisem** (§3.10) — bo DSR bez prawdziwego licznika prób jest teatrem.
5. **Prerejestrowane kill criteria z liczbami** (§19) — największy brak dokumentów źródłowych.
6. **Checklista leakage'u** (§13.7).
7. **Test negatywny modelu kosztów** (§13.2) — najtańszy i najostrzejszy test poprawności całego stosu.
8. **Test wrażliwości na feed** (§14.4).

## 20.4 Jedno zdanie

> Największym zagrożeniem dla tego projektu nie jest brak przewagi na rynku — to jest normalne i do przeżycia. Największym zagrożeniem jest **zbudowanie systemu, który nie potrafi powiedzieć, że przewagi nie ma**. Architektura z dokumentów źródłowych jest dokładnie takim systemem. Architektura po audycie ma szansę nim nie być.

---

# Aneks A — analiza istniejących projektów open-source

Klasyfikacja: **ADOPT** / **ADAPT** / **REJECT** / **UNKNOWN**

## A.1 Wzorzec powtarzający się we wszystkich

Sprawdziłem, co da się zweryfikować publicznie. Wniosek jest jednolity i wart zapamiętania:

> **Żaden z tych projektów nie publikuje: (a) prawdziwej liczby przetestowanych wariantów, (b) korekty na multiple testing, (c) wyniku na zapieczętowanym hold-oucie, (d) modelu kosztów zwalidowanego wobec realnych fillów.**

Bez tych czterech rzeczy deklarowane wyniki nie są dowodem przewagi — są opisem tego, co autor znalazł w danych, które przeszukiwał. To nie jest zarzut wobec konkretnych autorów; to opis standardu w całej kategorii.

Drugi powtarzający się wzorzec: **stosunek kodu infrastrukturalnego do kodu walidacyjnego wynosi zwykle ~50:1**. To odwrotność właściwych proporcji dla pytania badawczego.

## A.2 Projekty

| Projekt | Co zweryfikowałem | Co jest warte wzięcia | Ocena |
|---|---|---|---|
| **ForexFlow** ([repo](https://github.com/bmarshall511/forexflow)) | **[FAKT]** Self-hosted platforma FX: integracja OANDA, alerty TradingView, analiza trade'ów przez Claude w runtime, detekcja stref podaży/popytu, dashboard ryzyka. Next.js 15 + TypeScript + WebSockets, ~58 tys. linii, monorepo | Wzorzec adapterów brokerskich; szyfrowanie credentiali (AES-256-GCM); struktura ryzyka w UI | **REJECT jako strategia** — Claude w runtime to dokładnie ten wzorzec, który odrzuciliście, i słusznie (§3.9). **ADAPT (V2+)** warstwę integracji OANDA |
| **Claude Trader** | Nie udało mi się jednoznacznie zidentyfikować kanonicznego repozytorium. Opis z dokumentów: D1/H4/H1+M15, multi-agent Claude, monitoring pozycji | Hierarchia TF — którą zresztą odrzucam (§5) | **UNKNOWN / REJECT.** Deklarowane wyniki agentów LLM na danych historycznych są obciążone parametric look-ahead i nie stanowią dowodu |
| **ForexAI Bot** | Nie zweryfikowałem publicznie. Z dokumentów: próba LightGBM, **późniejsze odejście od ML**, setupy strukturalne, regime detection, kontrole DD/korelacji | **Sama lekcja: ML nie poprawił strategii.** To jest spójne z §2.5 i z ogólną charakterystyką problemu (mała próba, niski SNR) | **ADOPT lekcję. UNKNOWN wyniki** |
| **AlphaFX** | Nie zweryfikowałem publicznie. Z dokumentów: regime detection, sizing, correlated exposure, backtesting | Podejście do correlated exposure | **UNKNOWN.** Krótkie próby nie potwierdzają przewagi — Wasza własna konkluzja jest poprawna |
| **TradingAgents** ([arXiv:2412.20138](https://arxiv.org/pdf/2412.20138)) | **[FAKT]** Multi-agent LLM (analitycy fundamentalni/sentymentu/techniczni, researcherzy bull/bear, risk team), LangGraph, wielu dostawców LLM. Deklaruje poprawę zwrotów, Sharpe'a i max DD wobec baseline'ów. Autorzy przyznają: **dwa uruchomienia na tym samym tickerze i dacie mogą dać różne wyniki** | Dekompozycja ról jako **wzorzec architektoniczny dla organizacji pracy**, nie dla generowania sygnału | **REJECT jako strategia.** Dwa niezależne problemy: (1) parametric look-ahead — literatura pokazuje, że agenty LLM tracą przewagę na danych po cutoffie ([arXiv:2510.07920](https://arxiv.org/pdf/2510.07920)); (2) niedeterminizm uniemożliwia rzetelny backtest. **ADAPT** ideę adwersaryjnego reviewera — ale jako narzędzie dla Was, nie dla systemu |
| **Jesse** | Framework backtestowy z Monte Carlo i testami istotności | **Metodologia:** Monte Carlo na permutacjach, testy istotności, struktura raportu | **ADAPT metodologię.** **REJECT jako zależność** — framework narzuci Wam swoją abstrakcję barów, a Wy potrzebujecie kontroli nad symulacją fillów na poziomie ticka (§3.8). To jest dokładnie ta część, której nie wolno oddać bibliotece |
| **OpenBB** | Warstwa agregacji danych + integracje AI | Katalog źródeł jako punkt wyjścia do researchu | **REJECT z V1.** Nie rozwiązuje żadnego z Waszych realnych problemów (point-in-time, ticki, bid/ask), a dodaje dużą zależność |

## A.3 Wniosek dla Was

Jedyne, co warto stąd wziąć, to **metodologia walidacyjna Jesse** (i to jako inspiracja, nie zależność) oraz **lekcja z ForexAI Bot** (ML nie pomógł).

Wszystko pozostałe to warstwa integracyjna i UI — czyli dokładnie ta część, którą audyt zaleca odłożyć do V2.

**[OPINIA]** Fakt, że tak wiele projektów w tej kategorii ma bogatą infrastrukturę i ubogą walidację, nie jest przypadkiem. Infrastruktura daje widoczny postęp i jest przyjemna do budowania. Walidacja daje najczęściej odpowiedź „nie" i jest nieprzyjemna. To jest mechanizm selekcji, który działa również na Was — i jest powodem, dla którego §17.2 stawia symulator egzekucji i kontrolę losową przed jakimkolwiek signal engine.

---

# Aneks B — rozszerzenie o surowce i indeksy

Odpowiedź na pytanie, czy testować też złoto, ropę, srebro, DAX, Nasdaq, S&P 500, Dow Jones i Nikkei 225 — i kiedy.

## B.1 Rekomendacja

**Zamroź pełny zestaw 10 instrumentów teraz. Testuj FX najpierw. Kohortę uruchom po bramce 2 jako replikację, nie jako drugie podejście.**

## B.2 Dlaczego zamrozić teraz, a nie testować teraz

Koszt prerejestracji jest asymetryczny w czasie. Zbiór zapisany **przed** jakimkolwiek backtestem nie jest dodatkową próbą — to większa próbka dla tej samej hipotezy. Zbiór dopisany **po** zobaczeniu wyników jest jednocześnie dodatkową próbą i decyzją podjętą pod wpływem wyniku.

„FX nie zadziałał, spróbujmy surowców" to podręcznikowy data snooping. Zamrożenie listy kosztuje dziesięć minut i jeden commit; niezamrożenie kosztuje bezpowrotnie integralność testu.

## B.3 Dlaczego replikacja jest warta więcej niż pooling

| Wariant | N efektywne | Wykrywalny edge (t = 2) |
|---|---|---|
| Sam FX | ~700 | ~0,09 R |
| Pooling A + B | ~1400 | ~0,06 R |

Pooling obniża próg wykrywalności o ~0,03 R. Edge rzędu 0,06–0,09 R po kosztach jest i tak na granicy tradowalności, więc zysk jest skromny.

Replikacja daje coś jakościowo innego. Wynik +0,12 R na FX potwierdzony **niezależnie** przez +0,10 R na kohorcie B jest dowodem nieporównanie mocniejszym niż pojedyncze +0,11 R na połączonej puli, bo pula nie odróżnia „efekt jest prawdziwy" od „jedna klasa aktywów wyciągnęła średnią".

**[OPINIA]** DSR i PBO to protezy: korygują za liczbę prób, ale nie uratują przed subtelnym przeszukiwaniem. Replikacja na nietkniętej klasie aktywów omija ten problem w całości i jest najmocniejszym dowodem dostępnym detalicznemu badaczowi — mocniejszym niż zapieczętowany hold-out czasowy, bo to inny rynek, inna mikrostruktura i inni uczestnicy, a nie ten sam rynek w innym okresie.

## B.4 Dlaczego FX jest właściwym poligonem na start

| Problem | FX majors | Indeksy / surowce |
|---|---|---|
| Handel ciągły | 24/5, luka raz w tygodniu | Luki codziennie, circuit breakery |
| Finansowanie | Różnica stóp, ~0,025 R | **Pełna stawka, ~0,11 R, asymetryczna** |
| Dryf kierunkowy | Brak | Silna beta akcyjna |
| Dywidendy | Nie dotyczy | Nieciągłości w serii |
| Kalendarz sesji | Jeden | Osobny per klasa |

Zaczynając od FX budujesz i debugujesz symulator egzekucji na przypadku najprostszym, a złożoność dokładasz do narzędzia już zwalidowanego. Pułapka bety jest w FX nieobecna, więc pierwszy wynik nie będzie zanieczyszczony premią za ryzyko.

## B.5 Finansowanie — pułapka, której spread nie oddaje

W FX płaci się **różnicę** stóp. W CFD na indeks lub surowiec płaci się **pełną** stawkę: benchmark (SOFR/€STR) plus marża brokera, **[FAKT]** typowo 1,5–3% rocznie, łącznie ~7% przy dzisiejszych stopach.

Procent ryzyka skraca się we wzorze:

```
Koszt_R = (stawka_roczna × dni_trzymania) / (365 × stop_jako_ułamek_ceny)
```

**[WYLICZENIE]** Dla 10-dniowego trzymania, przy stopie `2 × atr_d1_14`:

| Instrument | Stop | Spread w R | Finansowanie w R |
|---|---|---|---|
| EURUSD | ~1,1% | ~0,008 | ~0,025 (differential) |
| XAUUSD | ~2,4% | ~0,008 | ~0,08 |
| S&P 500 CFD (long) | ~1,8% | ~0,006 | **~0,107** |
| DAX CFD (long) | ~2,0% | ~0,008 | ~0,096 |

Wnioski:

1. Spread **nie jest** binding constraint przy horyzoncie swingowym na żadnym z tych instrumentów. Kryterium „tylko wąski spread" jest słuszne, ale niewystarczające.
2. Finansowanie długiej pozycji w indeksie jest **rzędu całego poszukiwanego edge'u** i kilkanaście razy większe od spreadu.
3. Jest **asymetryczne kierunkowo**: long płaci benchmark + marżę, short otrzymuje benchmark − marżę. Różnica ~0,14 R między kierunkami nie ma związku z sygnałem.
4. Skaluje się liniowo z liczbą dni — skrócenie horyzontu do 5 dni halvuje je (V2).

## B.6 Beta zanieczyszcza pomiar

Indeksy akcyjne mają silny dodatni dryf, którego pary FX nie mają. Model uczony na wspólnej puli nauczy się „bądź long indeksy" — i zmierzy premię za ryzyko akcyjne, nie przewagę.

DAX jest tu szczególnie zdradliwy: to indeks **dochodowy** (z reinwestowanymi dywidendami), więc ma jeszcze mocniejszy dryf niż S&P, który jest indeksem cenowym.

Wymagane kontrole (8–10 w `PROJECT_SPEC.md` §10.2): expectancy osobno dla longów i shortów per instrument, buy & hold per instrument, kontrola losowa osobno dla każdej kohorty.

## B.7 Trimming listy

| Instrument | Decyzja | Powód |
|---|---|---|
| Złoto | Dodaj | Dobra historia, wąski spread, częściowo nowy czynnik |
| Ropa WTI | Dodaj | Najbardziej niezależny czynnik w zestawie |
| S&P 500 | Dodaj | Czystszy benchmark bety i lepsza historia CFD niż Nasdaq |
| DAX | Dodaj | Korelacja z S&P ~0,7 — wnosi ~0,3 czynnika |
| Dow Jones | **Usuń** | Korelacja z S&P ~0,95, ważony ceną |
| Nasdaq | **Usuń** | Korelacja z S&P ~0,90–0,95 |
| Srebro | V2 | Korelacja ze złotem ~0,8, wyższa zmienność |
| Nikkei 225 | V2 | Skorelowany z S&P **i** z USDJPY, już obecnym w kohorcie A |

**[OPINIA]** Argument „Nasdaq ładniej trenduje" jest wiedzą in-sample i nie może wpływać na wybór — to ta sama pułapka co „GBPJPY, bo ładnie trenduje" (§3.11).

## B.8 Uczciwe zastrzeżenie

**[FAKT]** Literatura o time-series momentum obejmuje kilkadziesiąt kontraktów futures i znajduje efekt szeroko w klasach aktywów, ale FX majors nie są miejscem, gdzie jest on najsilniejszy. Surowce i indeksy mają naturalnych hedgerów o niskiej wrażliwości cenowej i premie za ryzyko do zbierania; majors FX nie mają ani jednego, ani drugiego.

Startujecie więc od przypadku najtrudniejszego. To właściwa decyzja dla postawionej hipotezy (projekt jest o FX), ale niesie realne ryzyko fałszywie negatywnego wyniku dla samej metody. Dlatego `PROJECT_SPEC.md` §15 zawiera **prerejestrowany warunek awaryjny**: jedna próba na kohorcie B w razie porażki bramki 2, zapisana teraz, żeby nie była decyzją post hoc.

## B.9 Wpływ na harmonogram

Żaden na bramki 0–4. Kohorta dokłada 2–3 tygodnie, ale w tygodniu 12+, czyli **po** pierwszej uczciwej odpowiedzi. Gdyby weszła do V1, przesunęłaby bramkę 0 o te same 2–3 tygodnie — czyli opóźniła moment, w którym w ogóle zaczynacie mierzyć.

**[FAKT]** Dukascopy udostępnia 1600+ instrumentów, w tym indeksy i surowce, ale historia poza majorsami FX jest krótsza, a dane to **CFD brokera, nie notowania giełdowe**. Każda klasa aktywów wymaga własnego kalendarza sesji, własnego raportu jakości i własnego modelu kosztów — stąd osobna bramka 0B.

---

## Źródła zewnętrzne zweryfikowane podczas audytu

- [Dukascopy Historical Data Export](https://www.dukascopy.com/swiss/english/marketwatch/historical/)
- [HistData — Data Files: Detailed Specification](https://www.histdata.com/f-a-q/data-files-detailed-specification/)
- [FRED API — Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html) · [ALFRED](https://fred.stlouisfed.org/docs/api/fred/alfred.html)
- [Trading Economics — Economic Calendar Point-in-Time](https://docs.tradingeconomics.com/economic_calendar/point-in-time/)
- [CME FedWatch API](https://www.cmegroup.com/market-data/market-data-api/fedwatch-api.html)
- [OANDA v20 — Instrument Endpoints](https://developer.oanda.com/rest-live-v20/instrument-ep)
- [Price discovery and liquidity recovery: Forex market reactions to macro announcements (JIMF)](https://www.sciencedirect.com/science/article/pii/S0261560621001534)
- [The High-Frequency Effects of U.S. Macroeconomic Data Releases on FX (Federal Reserve IFDP 823)](https://www.federalreserve.gov/pubs/ifdp/2004/823/ifdp823.htm)
- [Profit Mirage: Revisiting Information Leakage in LLM-based Financial Agents (arXiv:2510.07920)](https://arxiv.org/pdf/2510.07920)
- [Summoning the Oracle to Slay It: Mitigating Look-Ahead Bias in Financial Backtesting with LLMs (arXiv:2605.24564)](https://arxiv.org/html/2605.24564v2)
- [TradingAgents: Multi-Agents LLM Financial Trading Framework (arXiv:2412.20138)](https://arxiv.org/pdf/2412.20138)
- [ForexFlow (GitHub)](https://github.com/bmarshall511/forexflow)
