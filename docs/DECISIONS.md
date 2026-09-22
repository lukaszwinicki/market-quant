# DECISIONS.md — log decyzji architektonicznych

Format: ADR (Architecture Decision Record). Każdy wpis jest niezmienny. Zmiana decyzji = nowy wpis, który jawnie wskazuje zastępowany (`Zastępuje: ADR-xxx`).

**Status:** `ACCEPTED` · `SUPERSEDED` · `PROPOSED`

Wszystkie decyzje z 2026-09-18 wynikają z `docs/AUDIT_REPORT.md`.

---

## ADR-001 — Projekt jest eksperymentem, nie produktem

**Status:** ACCEPTED · 2026-09-18

**Kontekst:** `INITIAL_CONVERSATION.md` §18 definiuje MVP jako 14-punktowy system z frontendem, bazą, Dockerem, Discordem i MCP. Ten sam dokument §12 deklaruje prymat prostoty i empirycznej weryfikacji.

**Decyzja:** V1 jest aparaturą pomiarową do rozstrzygnięcia jednej hipotezy. Żaden komponent niesłużący pomiarowi nie wchodzi do V1.

**Konsekwencje:** Usunięte: frontend, API, baza danych, Docker, Discord, MCP, paper trading. Czas do pierwszego wiarygodnego wyniku spada z ~6 miesięcy do ~11 tygodni.

**Ryzyko:** Brak widocznego postępu w pierwszych tygodniach. Akceptowane świadomie — widoczny postęp infrastrukturalny jest w tym projekcie pułapką kosztu utopionego.

---

## ADR-002 — Jedna baza czasowa (H1) zamiast hierarchii D1/H4/H1/M15

**Status:** ACCEPTED · 2026-09-18

**Kontekst:** Pierwotna koncepcja opiera się na konfluencji czterech timeframe'ów.

**Decyzja:** Jedna baza H1. Kontekst wielohoryzontowy wyrażony jako `mom_24`, `mom_120`, `mom_480`. M1/tick wyłącznie w symulatorze egzekucji.

**Uzasadnienie:**
1. Wskaźniki na różnych TF liczone z tej samej serii są silnie skorelowane (EMA(50)@H4 ≈ EMA(200)@H1). Konfluencja nie jest niezależnym potwierdzeniem.
2. **[FAKT]** FX nie ma oficjalnego zamknięcia — granica świecy D1 jest konwencją brokera (17:00 NY / 00:00 UTC / …). Cała warstwa „D1 context" zawiera ukryty, feed-zależny parametr.
3. Różne daty przełączenia DST w USA i UE zmieniają fazę świec H4/D1 dwa razy w roku.
4. Redukcja liczby parametrów z ~40 do ~4.

**Konsekwencje:** Usunięte: hierarchia TF, hard filter D1, wymóg pełnej zgodności, M15 w sygnale. M15 entry timing → V2 jako testowalna hipoteza.

---

## ADR-003 — Sześć cech technicznych, koniec

**Status:** ACCEPTED · 2026-09-18

**Decyzja:** `atr_14`, `mom_24`, `mom_120`, `mom_480`, `donch_pos_55`, `vol_pct_252`.

> **Skorygowane przez ADR-023:** `atr_14` rozdzielone na `atr_h1_14` (normalizacja cech) i `atr_d1_14` (bariery i sizing); momentum normalizowane przez `atr_h1_14 × √n`.

**Uzasadnienie:** RSI ≈ znormalizowane momentum. MACD ≡ kombinacja momentum na dwóch lookbackach. ADX miesza siłę trendu i zmienność, które są już rozdzielone. Stochastic/CCI/Williams/Bollinger ≡ pozycja w zakresie ≡ `donch_pos`. Wolumen w spot FX nie istnieje (tick count brokera).

**Konsekwencje:** Drastyczna redukcja przestrzeni hipotez. Ryzyko: możliwe pominięcie realnej cechy. Akceptowane — cechy można dodać po Gate 2 jako prerejestrowane eksperymenty.

---

## ADR-004 — Smart Money Concepts usunięte

**Status:** ACCEPTED · 2026-09-18

**Kontekst:** BOS/CHoCH/FVG/liquidity pojawiają się w prompcie audytowym, ale nie w dokumentach źródłowych.

**Decyzja:** Usunięte z V1 w całości.

**Uzasadnienie:** Po deterministycznej formalizacji: BOS ≡ Donchian breakout; CHoCH ≡ zmiana znaku `donch_pos`; swing high/low wymaga potwierdzenia k barów po fakcie (**notoryczne źródło look-ahead**); liquidity grab i order block wymagają 2–4 dodatkowych wolnych parametrów. Cała rodzina redukuje się do Donchian + ATR plus parametry, na których estymację nie ma próby.

**Wyjątek odnotowany:** FVG ma jednoznaczną definicję trzyświecową (`low[i] > high[i−2]`) i zero wolnych parametrów. Dopuszczony jako **jeden prerejestrowany test w V2**. **[BRAK DOWODÓW — WYMAGANY TEST.]**

---

## ADR-005 — Macro: tylko carry i blackout

**Status:** ACCEPTED · 2026-09-18

**Decyzja:**
- ZACHOWANE: `carry_2y`, `d_carry_20d` (FRED/ALFRED, point-in-time), blackout wydarzeń (tylko harmonogram).
- USUNIĘTE: `surprise = actual − consensus`, analiza tekstu banków centralnych, CME FedWatch, scraping kalendarzy.

**Uzasadnienie:**
1. **[FAKT]** Literatura wskazuje na brak wyraźnego post-announcement drift w FX — reakcja na niespodziankę zachodzi w sekundach/minutach. Na H1 informacja jest już wyceniona.
2. **[FAKT]** Darmowe kalendarze nie archiwizują consensusu sprzed publikacji, backfillują `previous` wartościami zrewidowanymi i nie dają rozproszenia prognoz. **Feature „surprise" nie jest możliwy do uczciwego zbacktestowania przy budżecie V1.**
3. **[FAKT]** Historia CME FedWatch wymaga płatnego API/DataMine. Substytut: 2Y yield differential.
4. Analiza tekstu CB: ~32 zdarzenia/rok (próba za mała) + parametric look-ahead przy użyciu LLM. Zmiana 2Y differential w oknie posiedzenia mierzy to samo, za darmo i bez leakage'u.
5. Blackout wymaga wyłącznie daty i godziny, znanych z wyprzedzeniem → zero problemu point-in-time, zero ryzyka licencyjnego.

**Konsekwencje:** Trading Economics (point-in-time, płatne) staje się uzasadnionym wydatkiem dopiero po Gate 2 → V2.

---

## ADR-006 — Bez regime detection w V1

**Status:** ACCEPTED · 2026-09-18

**Decyzja:** Jedna ciągła zmienna `vol_pct_252`. Zero dyskretnych reżimów, zero HMM, zero clusteringu.

**Uzasadnienie:**
1. **[WYLICZENIE]** ~700 efektywnych obserwacji ÷ 4 reżimy = ~175/reżim. SE estymatora expectancy ≈ 0,076 R → CI szersze niż poszukiwany edge. Estymacja per-reżim jest statystycznie bezwartościowa.
2. **[FAKT]** Pułapka leakage'u: `hmmlearn.predict()` zwraca dekodowanie Viterbiego po całej sekwencji (stan w `t` zależy od `t+1…`); w `statsmodels` kauzalne są wyłącznie `filtered_marginal_probabilities`, nie `smoothed_`. To jeden z najczęstszych cichych look-ahead bugów.
3. Zmienna ciągła nie dzieli próby, nie wprowadza progów i jest trywialnie kauzalna.

**Warunek powrotu (V3):** wyłącznie `filtered`, re-estymacja w każdym oknie WF, plus test: czy stan w `t` zmienia się po dołożeniu danych po `t`?

---

## ADR-007 — Bez ML drzewiastego w V1

**Status:** ACCEPTED · 2026-09-18

**Decyzja:** V1a reguła deterministyczna; V1b maksymalnie regresja logistyczna L2 z ≤8 cechami i jawną kalibracją.

**Uzasadnienie:** ~700 efektywnych obserwacji, silnie skorelowane cechy, SNR bliski zeru, niestacjonarność. GBM dopasuje szum. Spójne z lekcją z ForexAI Bot (odejście od LightGBM).

**Konsekwencje:** Gradient boosting → V2, z progiem +0,05 R incremental value poza próbą.

---

## ADR-008 — Target: P(TP before SL), z obowiązkowym purge/embargo

**Status:** ACCEPTED · 2026-09-18

**Decyzja:** Triple barrier (2 ATR SL / 4 ATR TP / 10 dni). Purge = 10 dni roboczych, embargo = 5 dni roboczych, bloki dzienne.

> **Skorygowane przez ADR-023:** ATR w definicji barier liczony na **D1**, nie na H1. Skala barier musi odpowiadać horyzontowi (`bariera ≈ σ√T`).

**Uzasadnienie i zastrzeżenia:**
1. Target bezpośrednio związany z tradowalnym rezultatem — poprawny wybór.
2. **Etykiety nakładają się w czasie** → silna autokorelacja → purging i embargo są **obowiązkowe, nie opcjonalne**.
3. **Ryzyko splątania:** bariery w ATR + ATR jako cecha ⇒ część „predykcji" jest tożsamościowa. `atr_14` traktowany jako normalizator, nie jako cecha predykcyjna.
4. Base rate przy RR 1:2 pod błądzeniem losowym ≈ 33%; break-even z kosztami ≈ 34–35%. Model musi stabilnie bić 35%, a nie „mieć accuracy 60%".

---

## ADR-009 — EV jako kryterium wymaga jawnej kalibracji

**Status:** ACCEPTED · 2026-09-18

**Kontekst:** `INITIAL_CONVERSATION.md` przyjmuje EV jako kryterium bez omówienia kalibracji.

**Decyzja:** EV pozostaje kryterium, ale `p̂` musi być skalibrowane na **osobnym foldzie**, a raport z każdego uruchomienia musi zawierać reliability diagram, Brier score **w top-decylu EV** oraz tabelę przewidywane EV vs realizowane R per decyl.

**Uzasadnienie:** Próg „EV > x" selekcjonuje prawy ogon przewidywanego `p̂` — czyli dokładnie obszar maksymalnego przeszacowania. Bez kalibracji reguła EV systematycznie wybiera przypadki, w których model myli się w tę samą stronę. Backtest pokazuje wtedy „wysoki EV = wysokie R", a live nie.

---

## ADR-010 — Pyramiding usunięty z V1

**Status:** ACCEPTED · 2026-09-18

**Decyzja:** Zakazany w V1. Powrót możliwy w V2 wyłącznie jako **nakładka sizingowa** na zwalidowany sygnał.

**Uzasadnienie:**
1. ≥4 nowe parametry nadbudowane nad niezwalidowanym sygnałem.
2. **Decydujące:** zwiększa σ rozkładu wyników przy stałym μ. Ponieważ `N ∝ (σ/μ)²`, pyramiding **zwiększa liczbę transakcji potrzebną do wykrycia edge'u** — czyli aktywnie utrudnia pomiar. Na etapie badawczym to dyskwalifikuje.
3. Matematycznie to wypukła funkcja sizingu warunkowana zrealizowanym ruchem — należy do warstwy sizingu, nie do strategii wejścia.
4. Największa ekspozycja powstaje przy największym dotychczasowym ruchu, typowo blisko wyczerpania trendu i przy najwyższej zmienności — gdy korelacje między parami dążą do 1.

**Warunek powrotu:** total risk cap ≤ 1,0 × początkowego R (piramida nigdy nie zwiększa ryzyka scenariusza); księgowanie jako jedna ekspozycja.

---

## ADR-011 — Ryzyko w R; procent equity nie jest parametrem badawczym

**Status:** ACCEPTED · 2026-09-18

**Decyzja:** Cały research w jednostkach R. `r%` dobierany po rozstrzygnięciu H₁, z rozkładu drawdownu.

**Uzasadnienie:** **[FAKT]** Przy `wielkość = (equity × r%) / dystans_SL` zmiana `r%` skaluje krzywą liniowo; expectancy w R, Sharpe i profit factor są niezmiennicze. Testowanie 0,25% vs 0,5% vs 1% to marnowanie prób na parametr bez wpływu na rozstrzygnięcie hipotezy.

**Dodatkowo:** stop w ATR + stałe `r%` **już jest** sizingiem odwrotnie proporcjonalnym do zmienności. Druga warstwa vol-scalingu to podwójne liczenie — usunięta. Fractional Kelly usunięty (wymaga znajomości edge'u; przy dużym błędzie estymacji systematycznie przelewaruje).

---

## ADR-012 — Symulator egzekucji tick-accurate jest komponentem nr 1

**Status:** ACCEPTED · 2026-09-18

**Decyzja:** Symulator fillów na tickach bid/ask budowany **przed** jakimkolwiek signal engine. Kolejność barier rozstrzygana tickowo; wariant awaryjny — pesymistyczny (SL pierwszy). **Nigdy optymistyczny.**

**Uzasadnienie:** **[FAKT]** Gdy w jednej świecy `high` przekracza TP, a `low` przekracza SL, z OHLC nie da się ustalić kolejności. Domyślne założenie korzystnej kolejności daje cichy, systematyczny bias optymistyczny, rosnący wraz z szerokością świec i ciasnością barier.

**Konsekwencja projektowa:** błąd w signal engine daje zły sygnał; błąd w symulatorze daje **fałszywą pewność**, że zły sygnał jest dobry. Dlatego `src/execution/` i jego testy mają najwyższy priorytet jakościowy w repozytorium.

---

## ADR-013 — Kontrola losowa jako pierwszy benchmark

**Status:** ACCEPTED · 2026-09-18

**Decyzja:** Przed pierwszym backtestem strategii uruchamiamy: losowe wejścia, identyczne wyjścia, identyczny sizing, identyczna liczba transakcji. Wynik definiuje rozkład zerowy.

**Uzasadnienie:** Bez rozkładu zerowego Sharpe 0,9 jest liczbą bez interpretacji. Dodatkowo test negatywny: strategia losowa musi dawać expectancy ≈ **−koszt**. Jeśli daje 0 lub więcej, model kosztów jest zepsuty — i jest to najtańszy oraz najostrzejszy test poprawności całego stosu.

---

## ADR-014 — `trials.jsonl` z zapisem automatycznym

**Status:** ACCEPTED · 2026-09-18

**Decyzja:** Harness backtestu zapisuje wpis przy **każdym** uruchomieniu, bez możliwości ręcznego pominięcia. Plik append-only, wersjonowany.

**Uzasadnienie:** Deflated Sharpe Ratio wymaga prawdziwej liczby prób. Praca wspomagana LLM zwiększa tempo generowania wariantów o rząd wielkości, więc licznik rośnie szybciej, niż intuicja nadąża śledzić. Bez maszynowego rejestru DSR jest teatrem, a §1.3 audytu gwarantuje fałszywie dodatni wynik.

**Konsekwencja:** każde „Claude, co spróbować dalej?" po którym coś próbujecie, jest próbą.

---

## ADR-015 — Claude nie generuje żadnych wejść do backtestu

**Status:** ACCEPTED · 2026-09-18

**Decyzja:** Twardy zakaz. Dotyczy scoringu komunikatów banków centralnych, klasyfikacji newsów, oceny sentymentu, generowania cech i wyboru wariantu do zachowania.

**Uzasadnienie:** **[FAKT]** Parametric look-ahead — model, którego dane treningowe obejmują okres backtestu, zna wynik ([arXiv:2510.07920](https://arxiv.org/pdf/2510.07920)). Nie da się tego naprawić promptem, zmierzyć ani odjąć.

**Konsekwencja:** decyzja „Claude nie jest generatorem sygnału" przestaje być oszczędnością budżetową, a staje się **koniecznością metodologiczną**. Zapisana jako niezmienna reguła projektu.

---

## ADR-016 — Workflow Discord → copy/paste → Claude usunięty

**Status:** ACCEPTED · 2026-09-18 · **Zastępuje:** `INITIAL_CONVERSATION.md` §8

**Decyzja:** Usunięty w całości.

**Uzasadnienie:** Wprowadza nieodtwarzalną decyzję uznaniową w środek pętli decyzyjnej. Wyników takiego układu nie da się zbacktestować, bo nie da się odtworzyć, co człowiek zrobiłby historycznie. Faktycznym systemem staje się „człowiek z podpowiedziami", a cała maszyneria walidacyjna przestaje mierzyć to, co jest wykonywane.

**Jeśli warstwa uznaniowa ma istnieć — musi być poza pętlą badawczą i jawnie oznaczona jako taka.**

---

## ADR-017 — Zbiór instrumentów zamrożony; CHF wykluczony

**Status:** ACCEPTED · 2026-09-18

**Decyzja:** `EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, EURJPY`. Niezmienny po pierwszym backteście.

**Uzasadnienie:** Dobór instrumentu po jego przeszłym zachowaniu („GBPJPY ładnie trenduje") to selekcja in-sample. **[FAKT]** CHF wykluczony ze względu na zerwanie pega EURCHF 2015-01-15 (ruch ~30% w minutach, fille daleko poza stopami) — zdarzenie dominowałoby każdy backtest. Zachowane jako osobny test stresowy egzekucji.

---

## ADR-018 — Stack: Python + Parquet + CLI

**Status:** ACCEPTED · 2026-09-18 · **Zastępuje:** `INITIAL_CONVERSATION.md` §13

**Decyzja:** Python 3.12, polars, numpy, scikit-learn, scipy, pyarrow, matplotlib, pytest. Parquet na dysku. CLI.

**Uzasadnienie:** 10 lat × 6 par × H1 ≈ 500 tys. wierszy; ticki 10–50 GB — Parquet + Polars radzi sobie bez serwera. Brak klienta ⇒ brak potrzeby API. Brak stanu współdzielonego ⇒ brak potrzeby Redisa. Jeden użytkownik, jedna maszyna ⇒ `venv` zamiast Dockera.

**Ryzyko odnotowane:** budowanie infrastruktury przed walidacją edge'u to najczęstszy sposób, w jaki takie projekty umierają — po miesiącach pracy nad dashboardem koszt utopiony psuje ocenę wyniku.

---

## ADR-019 — Koszyk carry + trend jako benchmark obowiązkowy

**Status:** ACCEPTED · 2026-09-18

**Decyzja:** Prosty koszyk (8 walut, ranking po `yield_2y + zwrot 3M`, long top 2 / short bottom 2, rebalans tygodniowy, bez stopów) implementowany w V1 jako obowiązkowy benchmark.

**Uzasadnienie:** **[FAKT]** Carry i momentum przekrojowe w FX mają udokumentowany w literaturze prior (Lustig/Roussanov/Verdelhan 2011; Menkhoff/Sarno/Schmeling/Schrimpf 2012). Koszyk jest implementowalny z tych samych darmowych danych, ma znikomy obrót i praktycznie zero stopni swobody.

**Konsekwencja:** jeśli system z ADR-002…009 nie bije koszyka poza próbą, cała złożoność jest nieuzasadniona i przechodzimy na koszyk. Chroni przed miesiącami pracy nad czymś, co przegrywa z 50 liniami kodu.

---

## ADR-020 — Kill criteria prerejestrowane

**Status:** ACCEPTED · 2026-09-18

**Decyzja:** Gate 0–4 plus kill globalny, z konkretnymi liczbami, zapisane w `PROJECT_SPEC.md` §15 **przed** pierwszym backtestem.

**Uzasadnienie:** `INITIAL_CONVERSATION.md` §16 wymienia 20 metryk i **ani jednego progu**. Bez prerejestrowanych progów każdy wynik da się zracjonalizować jako „obiecujący, wymaga dostrojenia" — a to jest dokładny mechanizm, przez który projekty tego typu żyją latami bez edge'u.

**Kluczowy zapis:** > 50 zalogowanych prób bez przejścia Gate 2 = STOP, ponieważ przy tej liczbie prób DSR i tak zniweluje każdy wynik.

---

## ADR-021 — Kohorta B (surowce, indeksy) jako zbiór replikacyjny, nie treningowy

**Status:** ACCEPTED · 2026-09-18

**Kontekst:** Pytanie, czy rozszerzyć zbiór o instrumenty o wąskim spreadzie: złoto, ropę, srebro, DAX, Nasdaq, S&P 500, Dow Jones, Nikkei 225.

**Decyzja:**
1. Pełny zbiór 10 instrumentów **zamrożony teraz**, przed pierwszym backtestem.
2. Kohorta A (6 par FX) = zbiór odkrywczy; bramki 0–4.
3. Kohorta B (XAUUSD, WTI, S&P 500, DAX) = **zbiór replikacyjny**, uruchamiany po bramce 2, z parametrami zamrożonymi hashem gita. Zero dostrajania.
4. Brak poolingu kohort w V1.
5. Jedna prerejestrowana próba na kohorcie B w razie porażki bramki 2, liczona jako próba.

**Uzasadnienie — dlaczego zamrozić teraz:**

Koszt prerejestracji jest asymetryczny w czasie. Zbiór zapisany **przed** jakimkolwiek backtestem nie jest dodatkową próbą — jest większą próbką dla tej samej hipotezy. Zbiór dopisany **po** zobaczeniu wyników jest jednocześnie dodatkową próbą i decyzją podjętą pod wpływem wyniku. „FX nie zadziałał, spróbujmy surowców" to podręcznikowy data snooping.

**Uzasadnienie — dlaczego replikacja, a nie pooling:**

| Wariant | N efektywne | Wykrywalny edge (t = 2) |
|---|---|---|
| Sam FX | ~700 | ~0,09 R |
| Pooling A + B | ~1400 | ~0,06 R |

Pooling obniża próg wykrywalności o ~0,03 R. Edge rzędu 0,06–0,09 R po kosztach jest i tak na granicy tradowalności, więc zysk jest skromny.

Replikacja daje coś jakościowo innego: wynik +0,12 R na FX potwierdzony **niezależnie** przez +0,10 R na kohorcie B jest dowodem nieporównanie mocniejszym niż pojedyncze +0,11 R na połączonej puli, bo pula nie odróżnia „efekt jest prawdziwy" od „jedna klasa aktywów wyciągnęła średnią". DSR i PBO korygują za liczbę prób, ale nie ratują przed subtelnym przeszukiwaniem; niezależna replikacja omija ten problem w całości.

**Uzasadnienie — dlaczego FX pierwszy:**

FX majors są jednorodne w sposób, w jaki kohorta B nie jest: handel ciągły 24/5, finansowanie jako różnica stóp, brak dryfu kierunkowego, brak dywidend, jeden kalendarz sesji. Symulator egzekucji buduje się i debuguje na przypadku najprostszym, a złożoność dokłada do narzędzia już zwalidowanego.

**Trimming listy użytkownika:** Dow Jones usunięty (korelacja z S&P ~0,95, ważony ceną). Nasdaq usunięty na rzecz S&P (korelacja ~0,90–0,95 — drugi indeks US nic nie wnosi; S&P wybrany za czystszy benchmark bety i lepszą historię CFD). Srebro odroczone (korelacja ze złotem ~0,8). Nikkei odroczony (skorelowany z S&P **i** z USDJPY, już obecnym w kohorcie A).

**Ryzyko odnotowane:** FX majors są prawdopodobnie najtrudniejszą klasą aktywów dla metod momentum — brak naturalnych hedgerów o niskiej wrażliwości cenowej i brak kierunkowej premii za ryzyko. Stąd warunek awaryjny w punkcie 5.

---

## ADR-022 — Finansowanie kohorty B modelowane pełną stawką, nie różnicą

**Status:** ACCEPTED · 2026-09-18

**Decyzja:** Koszt finansowania liczony wzorem `Koszt_R = (stawka_roczna × dni) / (365 × stop_jako_%_ceny)`, przy stawce = benchmark + marża brokera (1,5–3% rocznie), asymetrycznie dla longów i shortów.

**Uzasadnienie:** W FX płaci się **różnicę** stóp między walutami. W CFD na indeks lub surowiec płaci się **pełną** stawkę. Przy 10-dniowym trzymaniu i stopie 1,8% ceny daje to ~0,107 R na długiej pozycji w S&P — wartość **rzędu całego poszukiwanego edge'u** i kilkanaście razy większą od spreadu.

**Konsekwencje:**
1. Założenie „wybieramy instrumenty o wąskim spreadzie" jest słuszne, ale niewystarczające — spread nie jest tu binding constraint.
2. Finansowanie jest asymetryczne kierunkowo (~0,14 R różnicy między long a short) i musi być modelowane jawnie, inaczej wygeneruje pozorną przewagę shortów.
3. Koszt skaluje się liniowo z liczbą dni — skrócenie horyzontu na kohorcie B do 5 dni trafia do V2 jako prerejestrowany test.

**Dodatkowo:** obowiązkowe kontrole 8–10 (expectancy long/short osobno, buy & hold per instrument, kontrola losowa per kohorta), bo indeksy akcyjne mają silny dodatni dryf, którego FX nie ma. DAX jest indeksem **dochodowym**, więc jego dryf jest jeszcze silniejszy niż S&P.

---

## ADR-023 — Korekta skali barier: ATR na D1, nie na H1

**Status:** ACCEPTED · 2026-09-18 · **Koryguje:** ADR-008

**Kontekst:** Pierwotna specyfikacja podawała `SL = 2.0 × ATR(14)` przy ATR liczonym na H1 i horyzoncie 10 dni roboczych.

**Błąd:** To jest wewnętrznie sprzeczne. `2 × ATR(14)` z H1 to ≈20 pipsów na EURUSD — przy horyzoncie 10 dni bariera zostałaby trafiona w ciągu godzin, bariera czasowa nigdy by nie zadziałała, a etykiety zdegenerowałyby się do szumu mikrostruktury.

**Decyzja:** Wprowadzone **dwie rozłączne skale zmienności**:

| Skala | Zastosowanie |
|---|---|
| `atr_h1_14` | Wyłącznie normalizacja cech |
| `atr_d1_14` | Wyłącznie skalowanie barier i sizingu |

`SL = 2.0 × atr_d1_14`, `TP = 4.0 × atr_d1_14`. Cechy nadal liczone na H1.

**Uzasadnienie:** Warunkiem poprawności triple barrier jest `bariera ≈ σ√T`. Dla T = 10 dni i σ_dzienna ≈ 0,55% na EURUSD daje to ≈1,7%; `2 × atr_d1_14` ≈ 1,1% jest właściwym rzędem wielkości, `2 × atr_h1_14` ≈ 0,1% nie jest.

**Konsekwencja drugorzędna:** momentum normalizowane teraz przez `atr_h1_14 × √n` zamiast samego `atr_h1_14`. Bez czynnika `√n` trzy cechy momentum różnią się skalą o czynnik ~√20, mają nieporównywalne rozkłady i psują regularyzację L2.

**Wpływ na koszty:** przy poprawnej skali stopu koszt spreadu spada z ~0,05 R do ~0,008 R na EURUSD, a dominującym składnikiem staje się finansowanie (ADR-022).

---

## ADR-024 — Model kosztów broker-agnostyczny; bez badania konkretnego brokera

**Status:** ACCEPTED · 2026-09-19

**Kontekst:** Użytkownik prawdopodobnie będzie handlował przez CMC Markets. Rozważano dopisanie do konfiguracji sekcji `execution_venue` z parametrami tego brokera i kalibrację modelu kosztów przez logowanie spreadów na rachunku demo.

**Decyzja:** Odrzucone. Model kosztów jest broker-agnostyczny. Żaden broker nie jest wymieniony w konfiguracji.

**Uzasadnienie:**

1. **Edge zależny od brokera nie jest edge'em.** Strategia, która przeżywa tylko przy najwęższym dostępnym spreadzie, jest artefaktem zaokrąglenia, nie przewagą. Wymóg niezależności od miejsca egzekucji jest mocniejszym kryterium niż dokładna kalibracja.
2. **Dane z demo są niewiarygodne.** Spready na rachunkach demo bywają istotnie węższe niż live — to ogólna przypadłość platform, nie zarzut wobec konkretnego brokera. Kalibracja na demo dawałaby fałszywe poczucie precyzji.
3. **Prawdziwy pomiar kosztu jest możliwy dopiero na rachunku live o małej wielkości**, czyli po bramce 4. Badanie tego wcześniej jest przedwczesną optymalizacją nadbudowaną nad niezwalidowaną strategią.

**Mechanizm zastępczy — zapas kosztowy zamiast kalibracji:**

| Element | Wartość |
|---|---|
| Podłoga kosztu round-turn, majors | 1,5 pipsa |
| Podłoga kosztu round-turn, crosses | 2,5 pipsa |
| Efektywny koszt | `max(spread_tickowy + prowizja, podłoga)` |
| Wymóg przeżycia | expectancy > 0 przy **3×** kosztów |

Surowy spread Dukascopy (~0,2–0,4 pipsa round-turn na majorsach) jest węższy niż u typowego brokera detalicznego, więc modelowanie go wprost byłoby optymistyczne. Podłoga odpowiada przeciętnym warunkom detalicznym; mnożnik 3× pokrywa z zapasem rozrzut między brokerami i rozszerzenia spreadu.

**Konsekwencja dla granicy świecy D1:** zamiast dopasowywać `atr_d1_14` do konwencji konkretnej platformy, granica dnia staje się **testem odporności** uruchamianym na bramce 2 (warianty 00:00 UTC, 17:00 NY, 22:00 UTC). Kryterium porażki: expectancy zmienia znak lub spada o >30% między wariantami. Jeśli wynik zależy od granicy dnia, problem jest w strategii, nie w brokerze.

**Odrzucone wraz z tą decyzją:** logowanie spreadów przez skrypt MQL4 na MT4, sekcja `execution_venue` w konfiguracji, wymóg walidacji kosztów wobec spreadów brokera w bramce 0.

---

## ADR-025 — Operacjonalizacja kryterium bramki 0 „strategia losowa daje expectancy ≈ −koszt”

**Status:** ACCEPTED · 2026-09-19 · **Doprecyzowuje:** `gates.gate_0` (bez zmiany wartości `frozen: true`)

**Kontekst:** Tekst kryterium nie mówi, co znaczy „≈”. Pierwszy przebieg `scripts/gate0.py` (`20260919T134506Z-c4710e`, 2015-01 → 2016-04-28, 23 719 transakcji) zmierzył koszt 0,0106 R przy połowie CI95 średniej 0,036 R. Szum jest 3,4× większy od mierzonej wielkości. Na prawdziwych danych równość `E[R] = −koszt` jest nierozróżnialna od `E[R] = 0`, czyli koszt policzony i pominięty dają ten sam werdykt. Żadna tolerancja tego nie naprawi: przy barierach w `atr_d1_14` (ADR-023) koszt jest o rząd wielkości mniejszy od szumu dostępnego w kilku latach danych.

**Decyzja:** Kryterium jest spełnione, gdy przechodzą wszystkie trzy części. Każda testuje to, co da się zmierzyć:

| Część | Dane | Kryterium | Wykrywa |
|---|---|---|---|
| a. Rachunek kosztu | każda transakcja, prawdziwe | `cost = max(spread_implikowany, podłoga)` i `net = gross − (cost − spread_implikowany)`; zero naruszeń | koszt pominięty, podwójny, brak podłogi |
| b. Martyngał | syntetyczne (`tests/test_controls.py`) | brutto (R + koszt_R) w ±3 SE od 0 przy znanym koszcie 0,5 R | koszt źle odjęty w symulatorze |
| c. Losowe wejścia | prawdziwe (`scripts/gate0.py`) | CI95 brutto zawiera 0 **oraz** połowa CI95 ≤ 0,05 R | look-ahead, optymistyczna kolejność barier |

Wynik części c z połową CI > 0,05 R to **„nierozstrzygnięte”**, nie „przechodzi”. Wymaga więcej danych.

**Uzasadnienie progu 0,05 R:** połowa progu bramki 2 (0,10 R). Bias symulatora poniżej 0,05 R sam nie wyprodukuje fałszywego przejścia bramki 2, a większy zostaje wykryty. Bez progu szerokości mało danych daje szeroki CI, który zawsze zawiera 0, i test przechodzi za darmo.

**Kolejność zdarzeń (jawnie):** warunek „CI95 brutto ∋ 0” był w kodzie przed pierwszym przebiegiem (dowód: `runs/20260919T134506Z-c4710e/diff.patch`). Próg szerokości 0,05 R dodano **po** zobaczeniu wyniku, w którym połowa CI wyniosła 0,036 R. Próg wyprowadzono z progu bramki 2, nie z tego wyniku. Pierwszy przebieg nie zamyka bramki 0, bo ADR-026 zmienia symulator.

---

## ADR-026 — Bariera czasowa w czasie zamkniętego rynku: wyjście po ostatnim barze przed zamknięciem

**Status:** ACCEPTED · 2026-09-19

**Kontekst:** Bariera czasowa to moment decyzji + 10 dni roboczych. Dla wejścia w niedzielę 21:00–23:00 UTC (otwarcie tygodnia) wypada w piątek o tej samej godzinie, już po zamknięciu rynku (ostatni bar 20:59 lub 21:59 UTC zależnie od DST). Symulator uznawał brak barów przed barierą za `NO_DATA`, a `label_events` usuwał takie transakcje z próby. W pierwszym przebiegu bramki 0 dotyczyło to ~1,2% losowych wejść. Strategia traciłaby w ten sposób **wszystkie** wejścia z otwarcia tygodnia, po cichu i selektywnie.

Przyczyna: symulator nie odróżniał „rynek zamknięty” (wynik znany) od „brak danych” (wynik nieznany).

**Decyzja:** Jeżeli między ostatnim barem okna a barierą czasową rynek był zamknięty, transakcja kończy się `TIME_BARRIER` po cenie zamknięcia ostatniego bara (bid dla long, ask dla short, spread z tego bara). Zamknięcie rynku oznacza:

- weekend: ostatni bar w piątek, bariera w piątek po nim, w sobotę albo w niedzielę przed otwarciem;
- 25.12 i 1.01 (`MARKET_HOLIDAYS`, ta sama lista co w raporcie jakości) oraz dzień przed nimi po ostatnim barze.

Każdy inny brak danych przed barierą pozostaje `NO_DATA`, żeby awarie feedu nadal były widoczne.

**Uzasadnienie:** tak postępuje trader, którego horyzont kończy się w weekend: zamyka pozycję przed zamknięciem rynku. Nie jest to optymistyczne, bo spread przy piątkowym zamknięciu jest szeroki i pochodzi z ticków. Nie wymaga danych spoza okna `[decyzja, bariera]`. `time_barrier_business_days: 10` bez zmian.

**Odrzucone:**
- Wyjście po otwarciu po weekendzie: dokłada lukę weekendową i dwa dni finansowania, których decyzja o wejściu nie zakładała.
- Zakaz wejść w niedzielę wieczorem: nowy warunek na zamkniętej liście `no_trade_conditions`, czyli zmiana prerejestracji.
- Status quo: selektywne, nielogowane usuwanie wejść z otwarcia tygodnia.

**Konsekwencje:** wyniki symulatora sprzed tej zmiany (pierwszy przebieg bramki 0) są nieaktualne. Bramkę 0 zamyka dopiero przebieg na nowym symulatorze. Wejście w piątek po zamknięciu nadal nie jest możliwe (brak danych w momencie decyzji), i słusznie.

---

## ADR-027 — Próg DSR na bramce 2: 0,95

**Status:** ACCEPTED · 2026-09-19 · **Zmienia:** `validation.acceptance_thresholds.deflated_sharpe_min` (`frozen: true`) z 0.0 na 0.95

**Kontekst:** DSR to prawdopodobieństwo z przedziału [0, 1]. Próg „DSR ≥ 0” (spec §10.3, config) jest zawsze spełniony, więc kryterium nic nie odrzucało. Najpewniej miało oznaczać „deflowany Sharpe ≥ 0”, czyli SR̂ ≥ SR*₀, co odpowiada DSR ≥ 0,5.

**Decyzja:** `deflated_sharpe_min: 0.95`. Wynik musi dawać 95% pewności, że prawdziwy Sharpe przekracza oczekiwane maksimum z N prób o zerowym Sharpe'ie.

**Uzasadnienie:** DSR ≥ 0,5 to wynik lepszy od mediany maksimum z N prób szumu, czyli na granicy szumu. Ciężar dowodu leży po stronie H₁, a prior jest niski. 0,95 to konwencja z literatury (Bailey & López de Prado 2014), spójna z progiem t ≥ 2.

**Unieważnienie:** zmienia się `frozen_sha256`. Poprzedni hash: `eac58655ffb32bc9f9dc54eea8cfef6602095d4a5818e2fd3e85c8a9dc2e3250`. Nie ma jeszcze żadnego wyniku strategii. Jedyny przebieg na starym hashu (`20260919T134506Z-c4710e`, bramka 0) nie zależy od progów bramki 2 i jest i tak nieaktualny po ADR-026.

---

## ADR-028 — Siatka wrażliwości: jeden parametr naraz, 7 wariantów; definicja płaskowyżu

**Status:** ACCEPTED · 2026-09-19 · **Doprecyzowuje:** §10.3 „Wrażliwość parametryczna: płaskowyż, nie szpikulec”, wymóg N ≥ 2 w PBO

**Kontekst:** PBO (CSCV) mierzy proces wyboru i wymaga co najmniej 2 wariantów. Test płaskowyżu nie miał zdefiniowanych ani wariantów, ani kryterium. Oba trzeba ustalić przed pierwszym uruchomieniem V1a.

**Decyzja:** siatka jest prerejestrowana w `signal_v1a.sensitivity_grid`: baseline plus po jednym kroku ~±25% na każdym parametrze swobodnym, pozostałe parametry na baseline.

| Wariant | donchian_lookback | sl_multiple | tp_multiple |
|---|---|---|---|
| baseline | 55 | 2.0 | 4.0 |
| D− / D+ | 40 / 70 | 2.0 | 4.0 |
| S− / S+ | 55 | 1.5 / 2.5 | 4.0 |
| T− / T+ | 55 | 2.0 | 3.0 / 5.0 |

**Płaskowyż:** każdy z 6 sąsiadów ma expectancy netto tego samego znaku co baseline i ≥ 50% jego wartości. Jeden sąsiad poniżej oznacza szpikulec, czyli bramka 2 nie przechodzi.

**Rola wariantów:** raportowany wynik to zawsze baseline. Siatka nie służy do wyboru parametrów, tylko do PBO i testu płaskowyżu. Mimo to każdy wariant liczy się do N w DSR (ADR-029): policzony wariant to wariant, który mógł wpłynąć na decyzję.

**Odrzucone:** pełna siatka 3×3×3 = 27. Lepiej widać interakcje, ale N w DSR rośnie do 27 na przebieg, a obliczenia trwają ~4× dłużej.

---

## ADR-029 — Licznik prób: tylko warianty strategii; kategoria przebiegu deklarowana przed wynikiem

**Status:** ACCEPTED · 2026-09-19 · **Doprecyzowuje:** ADR-014, `kill_global.max_trials_before_gate_2`

**Kontekst:** `n_trials()` liczył każdy wpis `start`, łącznie z kontrolami losowymi i przebiegami infrastruktury. Kontrola losowa nie jest kandydatem na strategię. Wliczanie jej zawyża N i SR*₀ w DSR oraz zjada limit 50 prób powtórkami bramki 0. Z drugiej strony filtrowanie po fakcie byłoby ręcznym pominięciem (`manual_skip_allowed: false`).

**Decyzja:**
1. `start_run()` wymaga `kind` ∈ {`strategy`, `control`, `infra`}. Kategoria jest zapisywana we wpisie `start`, czyli **przed** jakimkolwiek wynikiem, i nie da się jej zmienić (rejestr jest append-only).
2. Przebieg `strategy` deklaruje `n_variants` (np. 7 dla siatki z ADR-028). Bez deklaracji liczy się 1.
3. **N** = suma `n_variants` po wszystkich przebiegach `strategy`, także przerwanych i zakończonych błędem. To samo N trafia do DSR i do limitu 50 prób.
4. `control` i `infra` są logowane jak dotąd, ale do N się nie liczą.
5. Wpisy bez `kind` (sprzed tej decyzji) liczą się jako `strategy`: konserwatywnie i bez etykietowania wstecz. Dotyczy to jednego przebiegu (`20260919T134506Z-c4710e`), który dodaje +1 do N.

**Zabezpieczenie:** kontrola, która ocenia sygnał V1a albo którykolwiek jego wariant, jest przebiegiem `strategy`, niezależnie od celu. `control` oznacza wyłącznie wejścia niezależne od sygnału (losowe, buy & hold, koszyk benchmarkowy).

---

## ADR-030 — Horyzont transakcji nie przekracza granicy splitu

**Status:** ACCEPTED · 2026-09-19

**Kontekst:** Wejście z końca grudnia 2021 z horyzontem 10 dni roboczych rozstrzyga się na cenach ze splitu walidacyjnego. Wejście z końca 2023 rozstrzyga się na cenach z zapieczętowanego hold-outu (`load_m1` je zablokuje). W CPCV na splicie research oznaczałoby to zajrzenie w walidację.

**Decyzja:** w danym splicie wejście jest dozwolone tylko wtedy, gdy cały horyzont (decyzja + 10 dni roboczych) mieści się przed końcem splitu. Dotyczy to wszystkich granic: research → validation, validation → hold-out, hold-out → koniec danych. Etykieta się nie zmienia. To ta sama reguła, którą stosuje już `gate0.eligible_candidates`.

**Koszt:** ~2 tygodnie wejść na końcu każdego splitu.

**Odrzucone:** ucinanie horyzontu na granicy. Zachowuje wejścia, ale części transakcji daje krótszy horyzont i inny rozkład R, czyli dwie różne etykiety w jednej próbie.

---

## ADR-031 — Korekta spec §10.1: CPCV 6/2 daje 15 podziałów i 5 ścieżek

**Status:** ACCEPTED · 2026-09-19 · **Koryguje:** PROJECT_SPEC §10.1, komentarz `validation.cpcv.n_test_groups` w configu

**Kontekst:** Spec podaje „2 grupy testowe → 15 ścieżek”. To pomyłka. C(6, 2) = 15 to liczba **podziałów** trening/test. Każda grupa jest testowa w C(5, 1) = 5 podziałach, więc da się złożyć φ = 15 · 2 / 6 = **5 ścieżek** backtestu (López de Prado 2018, rozdz. 12).

**Decyzja:** parametry bez zmian (6 grup, 2 testowe). Obowiązuje interpretacja: 15 podziałów, 5 ścieżek. `src/validation/cpcv.py` już tak liczy (`n_splits`, `n_paths`). Rozkład wyniku ścieżkowego na bramce 2 ma 5 punktów, nie 15. Wnioski o jego rozrzucie trzeba formułować ostrożnie.

---

## ADR-032 — Blackout: kierunek okna, tylko zdarzenia planowane, terminy wyłącznie ze źródeł

**Status:** ACCEPTED · 2026-09-19 · **Koryguje:** PROJECT_SPEC §7.2 (formuła okna) · **Doprecyzowuje:** ADR-005, sekcję `blackout`

**Kontekst:** Spec §7.2 definiuje blackout jako „zdarzenie w [t − 30 min, t + 120 min]”, co blokuje wejścia od 120 min **przed** zdarzeniem do 30 min **po** nim. Config (`window_before_minutes: 30`, `window_after_minutes: 120`) mówi odwrotnie. Spec nie mówi też nic o decyzjach nadzwyczajnych ani o pochodzeniu godzin publikacji.

**Decyzja:**
1. **Kierunek:** wejście w chwili t jest zablokowane, gdy dla którejkolwiek waluty pary istnieje zdarzenie HIGH o czasie e takim, że `e − 30 min ≤ t ≤ e + 120 min`. To odczyt zgodny z nazwami pól configu: 30 min przed publikacją, 2 h po niej. Formuła w spec §7.2 była odwrócona.
2. **Tylko zdarzenia planowane.** Decyzje nadzwyczajne (np. Fed 2020-03-03 i 2020-03-15) nie wchodzą do kalendarza. Blackout przed zdarzeniem, którego nikt nie zapowiedział, to look-ahead.
3. **Data i godzina pochodzą wyłącznie ze źródła oficjalnego**, parsowane automatycznie przez skrypt, z URL-em źródła w każdym wierszu. Nie wolno wpisywać ręcznie ani generować przez LLM terminów, godzin ani „stałych konwencji” (np. „CPI zawsze o 8:30 ET”). Jeśli źródło podaje tylko datę, konwencję godziny trzeba prerejestrować z cytatem ze źródła i zweryfikować ręcznie.
4. **Pokrycie jest warunkiem wejścia do backtestu.** Każda seria HIGH wymagana dla walut kohorty ma mieć zdarzenia w każdym roku badanego okresu. Brak serii nie może po cichu oznaczać „brak blackoutu”. Backtest bez pełnego pokrycia jest odrzucany.

**Zawartość kalendarza:** wyłącznie `(timestamp_utc, currency, name, rank, source)`. Kolumny z wartościami (actual, consensus, forecast, previous, surprise) są odrzucane przy wczytaniu.

---

## ADR-033 — Interpretacja reguły V1a i warunków NO TRADE

**Status:** ACCEPTED · 2026-09-19 · **Doprecyzowuje:** PROJECT_SPEC §7.1, §7.4, §8

**Decyzja (każdy punkt to odczyt miejsca, w którym tekst był niejednoznaczny):**

| Punkt | Odczyt |
|---|---|
| Short „symetrycznie” | `mom_480 < 0` i `donch_pos < 1 − 0,80 = 0,20`. Nierówności ostre, jak w §7.1 |
| `vol_pct_252` na granicy | NO TRADE, gdy `> 0,95` (§7.4, `vol_pct_max`). Wartość równa 0,95 jest dozwolona. Brak wartości (rozgrzewka) = NO TRADE z powodem `warmup` |
| Limit 2 R netto | **Per blok walutowy**, ρ = 1: ekspozycje walut w bloku się sumują (`currency_blocks`). Long base = +1 R base, −1 R quote. Wejście dozwolone, jeśli po nim \|netto bloku\| ≤ 2 R dla obu walut pary |
| Limit portfela 6 R | Suma otwartego ryzyka, 1 R na pozycję. W kohorcie A (6 par × max 1 pozycja) nigdy nie wiąże |
| Otwarta pozycja na parze | Pozycja zajmuje parę od wejścia do `t1` z symulatora. Nowe wejście jest możliwe dopiero przy decyzji po `t1` |
| Rollover | Decyzja w [16:45, 17:15] czasu Nowego Jorku, obie granice włącznie, z DST przez `America/New_York` |
| Piątek | Decyzja w piątek o 15:00 czasu NY lub później = NO TRADE. Granica włącznie, konserwatywnie |
| Luka w danych | Więcej niż 2 brakujące bary H1 między kolejnymi barami, w czasie gdy rynek działa (zamknięcie wg `market_closed_between`, ADR-026), w ostatnich 480 barach |
| Yieldy w pkt 7 | Dotyczą przebiegów, które używają yieldów (V1b). V1a ich nie czyta, więc warunek jest nieaktywny i nie może blokować |
| Granica splitu | ADR-030: horyzont musi mieścić się w splicie |
| Logowanie | Każdy zamknięty bar H1 każdej pary dostaje wiersz decyzji z akcją i powodem. Priorytet powodu: `warmup` → `data_gap` → `no_signal` → numer z listy §7.4 → `split_boundary` |

---

## ADR-034 — Kalendarz: kopie archiwalne jako źródło, znacznik zdarzenia bez publikowanej godziny, kryteria planowości

**Status:** ACCEPTED · 2026-09-20 · **Doprecyzowuje:** ADR-032

**Kontekst:** ADR-032 wymaga, żeby data i godzina pochodziły ze strony oficjalnej, parsowanej automatycznie, i żeby do kalendarza trafiały wyłącznie zdarzenia planowane. Przy dociąganiu 10 brakujących serii (BoE, ONS, BoJ, Statistics Bureau, RBA, ABS, BoC, StatCan, Eurostat) trzy sytuacje okazały się nieprzewidziane: część serwisów nie odpowiada skryptom albo usunęła archiwalne pliki; BoJ w ogóle nie publikuje godziny ogłoszenia decyzji po 2015 r.; a „planowość” trzeba rozstrzygać innym sygnałem w każdym źródle.

**Decyzja:**

1. **Kopia archiwalna jest dopuszczalnym nośnikiem strony oficjalnej.** Gdy serwis odpowiada skryptom 403 (rba.gov.au) albo usunął plik, który kiedyś publikował (roczne harmonogramy `stat.go.jp`), wolno czytać kopię z Wayback Machine (`web.archive.org/web/<znacznik>id_/<adres>`). Treść jest wiernym zapisem strony oficjalnej, a adres kopii zawiera adres źródłowy i moment zapisu, więc zostaje sprawdzalny. Dwa warunki: adres kopii trafia do `source`, a znacznik zapisu jest wybrany świadomie — dla harmonogramów bierzemy zapis sprzed opisywanego roku, bo to on dowodzi, że termin był znany z wyprzedzeniem. Zakaz z ADR-032 dotyczy pochodzenia treści (nie wolno jej wpisywać z pamięci), nie kanału dostępu.

2. **Gdy źródło nie publikuje godziny zdarzenia, wolno użyć innego momentu z tego samego źródła, jeśli jest ściśle sprzężony z publikacją i udokumentowany.** BoJ podawał godzinę ogłoszenia tylko do 2015 r.; od 2016 nie ma jej ani na liście komunikatów, ani w komunikacie, ani po japońsku (metadane PDF to nie publikacja — dla 29.01.2016 `ModDate` wskazuje 13:59 JST, a rynek ruszył o 12:38). Znacznikiem `BOJ_RATE` jest więc godzina zakończenia posiedzenia z nagłówka protokołu. Zmierzone opóźnienie publikacji wynosi +7 min (M1 USDJPY, trzy posiedzenia 2016) i mieści się w oknie −30/+120 min, więc znacznika NIE przesuwamy o tę wartość: przesunięcie byłoby dopasowaniem do danych okresu testu. Protokół wychodzi ok. miesiąc po posiedzeniu, czyli minuta jest znana ex post — dopuszczalne, bo data posiedzenia jest ogłaszana z rocznym wyprzedzeniem, a blackout wyłącznie blokuje wejścia i nie niesie informacji o kierunku.

3. **Planowość rozstrzyga sygnał z tego samego źródła, wskazany w module.** Nie ma jednej reguły dla wszystkich banków; każdy moduł nazywa swoją w docstringu i wypisuje pominięte zdarzenia do logu. Przyjęte: RBA — data musi być w harmonogramie zapisanym przed rokiem (dla 2018, którego archiwum nie ma, zwrot „At its meeting today” w komunikacie); BoJ — protokół bez zwrotów „Unscheduled Monetary Policy Meeting” i „brought forward”; BoE — slug strony `<miesiąc>-<rok>` (posiedzenia nadzwyczajne mają inny) i publikacja w czwartek; BoC — data musi występować w rocznym komunikacie z harmonogramem; Fed — jak dotąd (lista posiedzeń planowanych).

4. **Godzina jest przechowywana jako czas lokalny plus nazwa strefy, nigdy jako stały offset.** Przeliczenie na UTC robi `ZoneInfo` z datą publikacji, więc DST wchodzi automatycznie. Rozstrzygnięte empirycznie dla HICP flash: kalendarz Eurostatu podaje „11:00Z” zarówno dla zdarzeń zimowych, jak i letnich (gdyby pole było w UTC, letnie miałyby 09:00Z), a na M1 EURUSD zakres minuty względem mediany dnia daje 7,3× o 10:00 UTC w dniach zimowych i 3,7× o 09:00 UTC w letnich. Stały CET dawałby latem godzinę pudła. Uwaga odwrotna niż przy EBC (ADR-032, `calendar_ecb`), gdzie „CET” w komunikacie oznacza czas lokalny Frankfurtu — dlatego strefę ustala się per źródło i potwierdza na danych.

**Konsekwencja dla weryfikacji godzin:** wpis w `config/calendar_times.yaml` niesie `local_time`, `timezone`, cytat, dowód i wynik testu na tickach; bez `verified: true` (potwierdzenie użytkownika) źródło nie wypuszcza zdarzeń. Tak potwierdzono 2026-09-20: `BOE_RATE` 12:00 Europe/London, `ONS_BULLETIN` 09:30 Europe/London (tylko styczeń 2016), `EA_HICP_FLASH` 11:00 Europe/Luxembourg.

---

## ADR-035 — Finansowanie kohorty A modelowane jawnie; stopa overnight z FRED, marża prerejestrowana

**Status:** ACCEPTED · 2026-09-20 · **Doprecyzowuje:** ADR-024, SPEC §9

**Kontekst:** `config/v1_baseline.yaml` deklarował `financing.cohort_a_mode: rate_differential`, `directional_asymmetry: true` i `triple_swap_wednesday: true`, ale w kodzie nie było ani jednej linii swapu. Wszystkie dotychczasowe wyniki liczyły wyłącznie spread i poślizg.

Skala pominięcia: bramka 0 zmierzyła koszt spreadu na 0,0106 R. Różnica stóp EUR/USD sięgała w okresie badawczym 2,8 pp; przy stopie 2 × `atr_d1_14` ≈ 1,1% ceny i czternastu dniach kalendarzowych (10 dni roboczych) daje to ok. 0,13 R — **więcej niż cały próg bramki 2** (0,10 R) i ponad dziesięciokrotność spreadu. Liczba jest przypięta testem `test_financing_is_material_against_the_gate_2_threshold`.

Drugi, poważniejszy problem: swap jest kierunkowy. Long dostaje to, co short płaci. Pominięcie go nie obniża wyniku symetrycznie, tylko dokłada stałą przewagę jednej stronie każdej pary — czyli dokładnie ten kształt, który kontrola #8 z §10.2 ma rozpoznawać jako dryf udający edge. Strategia kupująca AUD za JPY w latach 2017–2019 zarabiałaby na carry i wyglądała jak sygnał.

**Decyzja:** Finansowanie jest modelowane jawnie, dla każdej transakcji kohorty A, wzorem z konfiguracji:

```
Koszt_R = (stawka_roczna × dni) / (365 × stop_jako_ułamek_ceny)
stawka_roczna = marża + (kwotowana − bazowa)   long
                marża + (bazowa − kwotowana)   short
```

1. **Źródło stóp:** OECD *Immediate Rates (< 24 Hours): Call Money/Interbank Rate*, `IRSTCI01<ISO>M156N` z FRED. Sprawdzone 2026-09-20: komplet 132/132 miesiące 2015–2025 dla wszystkich sześciu walut kohorty A. Raport: `reports/rates_coverage.md`.

2. **Stopa z miesiąca poprzedzającego decyzję.** Seria miesięczna dla stycznia jest średnią ze stycznia, więc w styczniu nieznana. Użycie jej byłoby zaglądaniem w przyszłość. Stopa overnight jest publicznie obserwowalna na bieżąco, więc średnia miesiąca minionego jest w chwili decyzji faktycznie znana — wybór konserwatywny, nie przybliżenie. Stopa ustalona w chwili decyzji obowiązuje do końca transakcji; wariant „stopa z dnia rozstrzygnięcia” byłby look-aheadem.

3. **Potrójny swap w środę.** Rollover w środę przesuwa datę waluty przez weekend i nalicza trzy dni; sobota i niedziela nie mają własnego rolloveru. Pełny tydzień daje 1+1+3+1+1 = 7 dni, czyli tyle, ile dni kalendarzowych.

4. **Marża brokera:** `costs.financing.cohort_a_markup_annual_pct: 1.0`, płacona przez obie strony. **To jedyna liczba w modelu kosztów bez sparsowanego źródła** — jest założeniem modelowym, nie pomiarem, i jest tak oznaczona w konfiguracji. Nie da się jej wyprowadzić bez wyboru konkretnego brokera, czego zakazuje ADR-024. Zabezpieczenie: jej wpływ musi być widoczny w obowiązkowej drabince 1×/2×/3× (§9), a wartość jest prerejestrowana przed pierwszym przebiegiem V1a.

**Uzasadnienie wyboru „modelować" zamiast „pominąć z uzasadnieniem":** pominięcie byłoby optymistyczne dla jednej strony każdej pary i nieprzewidywalne co do znaku. Nie istnieje pesymistyczny wariant uproszczony: obciążenie obu stron pełną różnicą stóp karałoby stronę, która carry faktycznie dostaje, i zaniżałoby wynik z powodu niezwiązanego z jakością sygnału.

**Odrzucone:**
- *Stopa dzienna zamiast miesięcznej.* FRED ma serie dzienne tylko dla USD (`DFF`), EUR (`ECBDFR`) i GBP (`IUDSOIA`); dla JPY, AUD i CAD nie ma. Mieszanie częstotliwości między walutami tej samej pary dawałoby różnicę stóp o niejednorodnym pochodzeniu.
- *Punkty swapowe konkretnego brokera.* Zakazane przez ADR-024 (model broker-agnostyczny).
- *Zerowa marża.* Carry wychodziłby darmowy, a przy dużych różnicach stóp strona otrzymująca miałaby systematyczną, niezwiązaną z sygnałem przewagę.

**Konsekwencje:** `financing_r` jest osobną kolumną etykiety, a `r` jest o nią pomniejszone; wynik sprzed korekty pozostaje odtwarzalny jako `r + financing_r`. Drabinka kosztowa odejmuje finansowanie w każdym scenariuszu, ale go NIE skaluje mnożnikiem — swap rośnie z liczby dni trzymania i różnicy stóp, a nie z warunków brokera na spreadzie. Sekcja `frozen: true` nie zmienia się (`costs` nie jest zamrożone), więc `frozen_sha256` = `2eab678f…` zostaje bez zmian i prerejestracja z ADR-027..031 jest nienaruszona. Wynik bramki 0 (losowe wejścia) nie wymaga przeliczenia: jest testem negatywnym na symetrycznej próbie long/short, a jego kryterium dotyczy wyniku przed kosztem.

---

## ADR-036 — Benchmark carry + trend: brak rentowności 2-letnich blokuje §12; decyzja odłożona do bramki 2

**Status:** ACCEPTED · 2026-09-20 · **Dotyczy:** SPEC §12, ADR-019

**Kontekst:** ADR-019 czyni koszyk carry + trend benchmarkiem obowiązkowym, a §12 definiuje jego ranking jako `yield_2y + zwrot 3-miesięczny` dla ośmiu walut vs USD. Przy budowie źródła stóp (2026-09-20) okazało się, że FRED ma rentowność 2-letnią **wyłącznie dla USD** (`DGS2`). Dla EUR, GBP, JPY, AUD, CAD, NZD i CHF nie ma jej w żadnej częstotliwości. Wyszukiwanie po nazwie („2-Year Government Benchmark Bond Yield”, „2-year government bond yield”) zwraca Turcję, Meksyk („6-month to 2-year”) i serie niezwiązane. To brak danych, nie zły identyfikator. Udokumentowane w `reports/rates_coverage.md`, odtwarzalne z cache w `data/raw/rates/`.

Dostępna jest natomiast jednorodna seria terminowa dla wszystkich ośmiu walut: 3-miesięczny interbank (`IR3TIB01<ISO>M156N`, OECD, miesięczna), komplet 2015–2025.

**Decyzja:** Benchmark **nie jest** implementowany na zamienniku podjętym po cichu. Rozstrzygnięcie odkładamy do momentu, w którym stanie się wiążące, czyli do bramki 2 — wcześniej nie jest do niczego potrzebny, a wybór wejścia do benchmarku obowiązkowego zrobiony po zobaczeniu wyniku strategii byłby wyborem pod wynik.

Do bramki 2 obowiązują dwie reguły:

1. **Zapis o braku jest częścią wyniku.** Każdy raport powołujący się na §12 musi stwierdzać, że benchmark nie został policzony, i odsyłać do tego ADR-u. Milczenie jest tu gorsze niż brak liczby.
2. **Wariant zamienny musi być prerejestrowany PRZED bramką 2**, nowym ADR-em, który wskazuje jedną z dróg: (a) pozyskanie rentowności 2-letnich z innego źródła (OECD.Stat, dane banków centralnych, EBC SDW) — odcinek pracy porównywalny z kalendarzem; (b) podmiana `yield_2y` → `interbank_3m` z uzasadnieniem, dlaczego zmiana punktu krzywej nie zmienia sensu rankingu carry; (c) uznanie §12 za niewykonalny i wykreślenie go z kryteriów, z przyjęciem, że kontrola #5 z §10.2 odpada, a ciężar spada na kontrole #1 i #4.

**Uzasadnienie odłożenia:** ADR-019 uzasadnia benchmark tym, że ma udokumentowany prior i zerową liczbę stopni swobody. Zamiennik dobrany dziś „na oko” odbierałby mu dokładnie tę własność. Jednocześnie wymuszenie decyzji teraz, przy nieznanej jeszcze jakości źródeł alternatywnych, groziłoby wybraniem drogi (b) z wygody.

**Ryzyko przyjęte świadomie:** jeżeli do bramki 2 nikt nie zajmie się tym punktem, presja czasu popchnie ku wariantowi (b) albo (c). Dlatego termin jest twardy — prerejestracja przed bramką 2, nie przy niej.

---

## ADR-037 — Marża swapu: 0,5% i obowiązkowa oś wrażliwości zamiast wartości punktowej

**Status:** ACCEPTED · 2026-09-20 · **Koryguje:** ADR-035 pkt 4

**Kontekst:** ADR-035 prerejestrował marżę brokera na 1,0% rocznie i deklarował, że zabezpieczeniem przed dowolnością tej liczby jest jej widoczność w drabince 1×/2×/3× z §9. **To zabezpieczenie nie zostało zaimplementowane i nie mogło zostać** — ten sam ADR (i `validation/cost_sensitivity.py`) rozstrzyga, że finansowanie jest od wyniku odejmowane, ale mnożnikiem kosztu NIE skalowane, bo swap rośnie z dni trzymania i różnicy stóp, a nie z warunków brokera na spreadzie. Oba zapisy są poprawne osobno i sprzeczne razem: marża nie była stress-testowana niczym.

Pomiar, który ujawnił wagę problemu (2026-09-20, `src/execution/financing.py`):

| stop (2 × `atr_d1_14`) | marża 0,5% | 1,0% | 2,0% |
|---|---|---|---|
| 0,8% ceny | 0,024 R | 0,048 R | 0,096 R |
| 1,1% ceny | 0,017 R | 0,035 R | 0,070 R |
| 2,0% ceny | 0,010 R | 0,019 R | 0,038 R |

Przy typowym stopie 1,1% marża 1,0% kosztuje 0,035 R na transakcję — **3,3× więcej niż cały zmierzony koszt spreadu** (0,0106 R, bramka 0) i 35% progu bramki 2. Zestawienie z rzeczywistą medianą |różnicy stóp| w segmencie RESEARCH (EURUSD 1,19 pp, GBPUSD 0,58, USDJPY 0,83, AUDUSD 0,46, USDCAD 0,18, EURJPY 0,31) pokazuje, że dla USDCAD i EURJPY marża przy 1,0% **przewyższa medianę faktycznego carry trzy- do pięciokrotnie**. Wielkość bez sparsowanego źródła byłaby więc dla połowy par członem dominującym modelu finansowania.

**Decyzja:**

1. **Wartość punktowa spada do `cohort_a_markup_annual_pct: 0.5`.** Uzasadnienie: 1,0% zostało dobrane „bezpiecznie", zanim policzono jego koszt; przy znanej już skali jest to wartość karna, nie konserwatywna. 0,5% odpowiada konkurencyjnym warunkom detalicznym FX i nadal kosztuje 1,6× zmierzony spread, więc nie jest optymistyczne w rozumieniu ADR-024.

2. **Wynik punktowy nie wystarcza.** Każdy raport powołujący się na expectancy kohorty A niesie oś `costs.financing.cohort_a_markup_sensitivity: [0.5, 1.0, 2.0]`. Werdykt bramki zależny wyłącznie od wartości punktowej marży jest nieważny.

3. **Mechanizm:** `apply_financing()` zapisuje `fin_unit_r` — koszt w R na jeden punkt procentowy stawki rocznej. Stawka wchodzi we wzór liniowo, więc `refinanced()` przelicza marżę bez ponownego czytania stóp, przy niezmienionym carry i liczbie dni. Równoważność z liczeniem od zera jest przypięta testem.

4. **Drabinka kosztowa z §9 zostaje bez zmian:** finansowanie jest w niej odejmowane, ale nieskalowane. Marża ma własną oś, bo ma własną przyczynę.

**Odrzucone:**
- *Utrzymanie 1,0%.* Zjada 35% progu bramki 2 liczbą, której nie znamy; porażka H₁ nie byłaby wtedy informacją o sygnale.
- *2,0% jako maksymalny pesymizm.* 0,070 R przy typowym stopie praktycznie przesądza wynik bramki 2 z góry. Pesymizm, który uniemożliwia rozstrzygnięcie, nie jest ostrożnością — jest rezygnacją z pomiaru.
- *Sama oś, bez wartości punktowej.* Kryterium bramki 2 (`≥ +0,10 R`) wymaga jednej liczby; przedział bez punktu odniesienia przeniósłby decyzję na moment odczytu wyniku.

**Konsekwencje:** `costs` nie jest sekcją `frozen: true`, więc `frozen_sha256` = `2eab678f…` zostaje bez zmian i prerejestracja z ADR-027..031 jest nienaruszona. Żaden dotychczasowy wynik nie wymaga przeliczenia — finansowanie nie było jeszcze nałożone na żadną próbę.

---

## ADR-038 — Benchmark §12: carry mierzone `interbank_3m`, koszyk zawężony do walut kohorty A

**Status:** ACCEPTED · 2026-09-20 · **Zamyka blokadę:** ADR-036 · **Koryguje:** PROJECT_SPEC §12, ADR-019 · **Dotyczy:** kontrola #5 z §10.2

**Kontekst:** ADR-036 zablokował benchmark carry + trend i zobowiązał do prerejestracji wariantu zamiennego **przed** bramką 2, wskazując trzy drogi: (a) własne źródło rentowności 2-letnich, (b) podmiana `yield_2y` → `interbank_3m`, (c) wykreślenie §12. Zwiad przeprowadzono 2026-09-20, wynik w `reports/yield2y_sources.md`. Żaden przebieg strategii jeszcze nie istnieje (`trials.jsonl` ma jeden wpis, kontrolę bramki 0), więc decyzja zapada przed jakimkolwiek wynikiem V1a.

**Ustalenia zwiadu, na których opiera się ta decyzja:**

1. **OECD nie ma punktu 2-letniego w ogóle.** Struktura przepływu `OECD.SDD.STES/DSD_STES@DF_FINMARK` (SDMX) wymienia dokładnie trzy miary stóp: `IRLT` (≈10 lat), `IR3TIB` (3M) i `IRSTCI` (overnight). Brak 2Y na FRED nie był artefaktem fasady — droga (a) przez OECD.Stat jest zamknięta u źródła.

2. **2Y da się pozyskać, ale tylko z ośmiu różnych instytucji i w czterech różnych definicjach:** zero-kuponowy spot z modelu (EUR/ECB, GBP/BoE, CHF/SNB), par yield constant-maturity (USD/FRED), rentowność konkretnej obligacji benchmarkowej (CAD/BoC), interpolacja po krzywej benchmarków lub rynek wtórny (JPY/MoF, AUD/RBA, NZD/RBNZ). Kryterium „ta sama definicja dla wszystkich walut” jest tu niespełnialne, a benchmark §12 jest rankingiem **przekrojowym**, czyli operacją, w której stały bias per waluta się nie znosi.

3. **Trzy luki po stronie wydawcy, nie do obejścia parserem:** RBA przestało publikować dzienne rentowności AGS (ostatnia dzienna wartość 2023-06-07; następca `f2.1-data.csv` jest miesięczny); seria RBNZ `INM.DG102.NZZCF` ma w 2020 r. 28 obserwacji zamiast ~250; kostki SNB `rendoblid`/`rendoblim` mają ostatnią obserwację 2025-07-31 przy `PublishingDate` 2025-09-01, podczas gdy inne kostki tego samego API są bieżące (2026-09) — serie wyglądają na wygaszone, a dziura wypada wewnątrz zapieczętowanego hold-outu.

4. **§12 w literalnym brzmieniu jest niewykonalny niezależnie od rentowności.** Ranking „8 walut vs USD” wymaga NZDUSD i USDCHF. Kohorta A to sześć par pokrywających sześć walut (USD, EUR, GBP, JPY, AUD, CAD); NZD i CHF nie są pobierane, a CHF jest wykluczony wpisem `instruments.excluded.CHF` w sekcji z `frozen: true`. Dołożenie USDCHF oznaczałoby zmianę sekcji zamrożonej, czyli unieważnienie wszystkich dotychczasowych wyników i nowy `frozen_sha256` — za benchmark porównawczy.

5. **Pomiar podmiany punktu krzywej** (segment RESEARCH 2015-01…2021-12, hold-out nietknięty; przekrój miesięczny, ranking po 2Y vs ranking po `interbank_3m`):

| Zestaw | Miesięcy | Spearman mediana / min | Zgodna noga long | Zgodna noga short |
|---|---|---|---|---|
| 8 walut, top-2 / bottom-2 (§12 dosłownie) | 73/84 | 0,976 / 0,786 | 70% | 100% |
| 5 walut vs USD, top-1 / bottom-1 | 84/84 | 1,000 / 0,700 | 83% | 100% |
| 5 walut vs USD, top-2 / bottom-2 | 84/84 | 1,000 / 0,700 | 74% | 100% |

**Decyzja:**

1. **Miara carry:** `yield_2y` → `interbank_3m` (OECD `IR3TIB01<ISO>M156N` z FRED, seria miesięczna, komplet 132/132 dla wszystkich walut, już w `data/rates/fred.parquet`).

2. **Stopa z miesiąca poprzedzającego decyzję**, identycznie jak w ADR-035 pkt 2. Benchmark i strategia korzystają z tej samej konwencji, więc porównanie nie miesza dwóch reżimów informacyjnych.

3. **Uniwersum:** pięć walut kohorty A vs USD — **EUR, GBP, JPY, AUD, CAD**. Nie osiem. Uzasadnienie w ustaleniu 4: alternatywą jest ruszenie sekcji `frozen: true`.

4. **Nogi: long top-1, short bottom-1.** Przy ośmiu walutach §12 brało 2/8 = 25% uniwersum na nogę; przy pięciu 1/5 = 20% jest bliżej tej proporcji niż 2/5 = 40%. Pomiar z ustalenia 5 dodatkowo pokazuje, że przy top-1 podmiana miary psuje nogę long rzadziej (17% miesięcy) niż przy top-2 (26%).

5. **Reszta konstrukcji §12 bez zmian:** ranking po `carry + zwrot 3-miesięczny`, równe ryzyko, sizing przez ATR, brak stopów, rebalans tygodniowy. Zero parametrów swobodnych — to była cała wartość tego benchmarku wg ADR-019 i zostaje nienaruszona.

6. **Każdy raport porównujący V1a z benchmarkiem niesie zapis o zawężeniu** i odsyła do tego ADR-u. Obowiązek z ADR-036 pkt 1 („zapis o braku jest częścią wyniku”) przechodzi w obowiązek zapisu o podmianie: benchmark jest słabszy niż ten, który uzasadniał ADR-019.

**Koszty przyjęte świadomie:**

- *Noga long różni się od wersji 2-letniej w ~17% miesięcy.* Waluty na górze rankingu są ciasno skupione i punkt 2-letni potrafi je zamienić miejscami. Noga short jest identyczna w 100% miesięcy, więc rozjazd dotyczy wyłącznie tego, którą walutę koszyk kupuje.
- *Koszyk 1 long / 1 short ma wyższą wariancję idiosynkratyczną niż 2/2 z ośmiu.* Benchmark jest przez to bardziej hałaśliwy, a „system bije koszyk” jest słabszym dowodem. Dlatego porównanie na bramce 2 musi iść z przedziałem ufności różnicy, nie jako dwie liczby punktowe.
- *Prior z literatury (Lustig i in. 2011; Menkhoff i in. 2012) dotyczy koszyków G10.* Pięć walut to węższy przekrój niż w cytowanych pracach i prior stosuje się do niego słabiej. Zapisane, nie wygładzone.

**Odrzucone:**

- *Wariant (a), własne źródło 2Y.* Osiem parserów to odcinek pracy porównywalny z kalendarzem i byłby wykonalny, ale wynik i tak nie spełniałby kryterium jednej definicji (ustalenie 2) ani kompletności (ustalenie 3), a nie rozwiązywałby ustalenia 4. Nakład bez rozstrzygnięcia.
- *Wariant (c), wykreślenie §12.* Zasadny, gdyby carry nie dawało się zmierzyć wcale. Daje się — na innym punkcie krzywej i węższym uniwersum. Kontrola #5 zostaje, choć w słabszej postaci; wykreślenie przerzuciłoby cały ciężar na kontrole #1 i #4 bez potrzeby.
- *Dołożenie NZDUSD i USDCHF do kohorty A.* Zmiana sekcji `frozen: true` unieważniająca wszystkie wyniki, żeby policzyć benchmark. Odwrócenie hierarchii: benchmark ma mierzyć projekt, a nie przestawiać jego zbiór instrumentów.
- *`overnight` zamiast `interbank_3m`.* Seria overnight jest w projekcie już użyta do finansowania (ADR-035). Benchmark liczony z tej samej serii, co model kosztów strategii, dzieliłby z nią błąd; 3M jest niezależnym punktem krzywej i jest kompletny dla wszystkich ośmiu walut.
- *Rozstrzygnięcie przy bramce 2 zamiast teraz.* ADR-036 pkt 2 wyznaczył twardy termin właśnie po to, żeby nie wybierać wejścia do benchmarku po zobaczeniu wyniku strategii.

**Konsekwencje:** parametry benchmarku trafiają do `validation.benchmark_carry_trend`, sekcji **bez** `frozen: true` (zamrożone jest tylko `validation.acceptance_thresholds`), więc `frozen_sha256` = `2eab678f…` zostaje bez zmian i prerejestracja z ADR-027..031 jest nienaruszona. Cechy V1b `carry_2y` i `d_carry_20d` (SPEC §6, poz. 7–8) **nie są objęte tym ADR-em** — dla sześciu walut kohorty A rentowności 2-letnie są dostępne (poza AUD po 2023-06, gdzie zostaje seria miesięczna), więc decyzja o ich źródle zapadnie osobno, jeśli V1b kiedykolwiek ruszy. Benchmark nadal nie jest zaimplementowany; ten ADR usuwa blokadę, nie pisze kodu.

---

## ADR-039 — Interpretacja benchmarku §12: moment rebalansu, jednostka R, koszty i kryterium „pobity”

**Status:** ACCEPTED · 2026-09-20 · **Doprecyzowuje:** PROJECT_SPEC §12, ADR-019, ADR-038 · **Dotyczy:** kontrola #5 z §10.2

**Kontekst:** ADR-038 rozstrzygnął, CZYM mierzymy carry (`interbank_3m`) i na jakim uniwersum (5 walut kohorty A vs USD, long top-1 / short bottom-1). Nie rozstrzygnął, JAK koszyk liczyć. Spec §12 mieści się w sześciu wierszach — „raz w tygodniu”, „równe ryzyko, sizing przez ATR”, „musi zostać pobity” — i każdy z nich ma po kilka rozsądnych odczytów. Bez ich zapisania decyzje zapadłyby w trakcie pisania kodu, czyli po cichu i już po tym, jak zobaczylibyśmy pierwsze liczby.

To ten sam zabieg, co ADR-033 dla reguły V1a: jeden ADR, który czyta niejednoznaczne miejsca, zanim powstanie kod.

**Decyzja (każdy punkt to odczyt miejsca, w którym tekst był niejednoznaczny):**

| Punkt | Odczyt |
|---|---|
| Dzień rebalansu | **Pięć nakładających się portfeli, po jednym na dzień tygodnia** (pon–pt), każdy rebalansowany co 7 dni; wynik koszyka to średnia z pięciu. Usuwa datę formowania jako parametr — technika portfeli nakładających się (Jegadeesh & Titman 1993) |
| Chwila decyzji | Dzień kotwicy, 00:00 UTC; wejściem jest OSTATNI ZAMKNIĘTY bar H1 przed tą chwilą (`last_closed_bar`), nigdy arytmetyka na znacznikach |
| Jednostka R | `1 R = labels.sl_multiple × atr_d1_14` pary, z ostatniego zamkniętego dnia przed decyzją. Koszyk nie ma stopu, ale **jednostka musi być ta sama co w strategii** — inaczej kontrola #5 porównuje dwie różne skale |
| Kierunek waluty vs USD | Ekspozycja i zwrot dotyczą WALUTY, nie pary. Dla par USD-bazowych (USDJPY, USDCAD) long waluty = short pary |
| Zwrot 3-miesięczny | `bid_close` z barów D1: `(cena_dziś / cena_63_dni_roboczych_temu − 1) × 100`, ze znakiem waluty vs USD. 63 dni robocze ≈ 3 miesiące. Bid po obu stronach — to sygnał, nie fill |
| Carry | `interbank_3m(waluta) − interbank_3m(USD)` z miesiąca POPRZEDZAJĄCEGO decyzję (ADR-035 pkt 2, ADR-038 pkt 2) |
| Suma w rankingu | **Dosłowna, jak w §12**: carry w punktach procentowych rocznie plus zwrot w procentach. Bez normalizacji |
| Koszty | Spread i poślizg **tylko przy ZMIANIE pozycji** — waluta, która zostaje w koszyku, nie jest przehandlowana (stąd „znikomy obrót” z ADR-019). Finansowanie za każdy dzień trzymania wg ADR-035, z obowiązkową osią marży wg ADR-037 |
| Brak stopów | Pozycja żyje do następnego rebalansu, bez względu na obsunięcie |
| Blackout, rollover, piątek | **NIE stosowane.** To warunki NO TRADE reguły V1a. Koszyk jest harmonogramem; pomijanie rebalansu byłoby regułą uznaniową i dołożyłoby benchmarkowi stopni swobody, których ADR-019 mu odmawia |
| Brak danych | Tydzień, w którym którakolwiek z pięciu walut nie ma ATR albo zwrotu 3M, jest POMIJANY W CAŁOŚCI i policzony w raporcie. Ranking czterech walut to inny koszyk, nie ten sam z dziurą |
| Rozgrzewka | 63 dni robocze zwrotu + 14 dni ATR; pierwszy rebalans nie wcześniej niż `trade_start` przebiegu |
| Kategoria przebiegu | `kind="control"` (ADR-029). Koszyk benchmarkowy jest wejściem niezależnym od sygnału, więc NIE podnosi N w DSR ani nie zjada limitu prób |
| Oś porównania | Dzienne sumy R obu serii na wspólnej osi dni roboczych (`bootstrap.business_day`), ten sam segment i ten sam okres |
| Kryterium „pobity” | CI95 bootstrapu blokowego (20 dni roboczych) **różnicy** dziennych R, strategia minus koszyk, w całości powyżej zera |
| Hold-out | Ta sama pieczęć co wszędzie (`load_h1` / `load_m1`), bez `unseal` |

**Pomiar, który rozstrzygnął punkt „suma w rankingu”:** dla 17 poniedziałków 2016 r. z kompletem pięciu par (segment RESEARCH, jedyny okres z gotowymi barami w chwili pisania) przekrojowe odchylenie standardowe członu carry wyniosło 0,86 pp rocznie, a członu zwrotu 3-miesięcznego 3,61% — stosunek **4,2×**, mediana rozstępu odpowiednio 2,46 pp i 10,1%. Dosłowna suma jest więc rankingiem **zdominowanym przez momentum**, a carry rozstrzyga głównie remisy. To jest zapisane, a nie poprawiane: każda normalizacja odwracałaby proporcje w stronę, którą wybralibyśmy my.

**Uzasadnienie pięciu kotwic:** ADR-019 uzasadnia obowiązkowość tego benchmarku tym, że ma on „praktycznie zerową liczbę stopni swobody”. Pojedynczy dzień rebalansu byłby dokładnie jednym stopniem swobody — cichym, bo nikt by go nie nazwał parametrem, i nietestowanym, bo koszyk nie ma siatki wrażliwości takiej jak V1a (ADR-028). Uśrednienie po wszystkich pięciu dniach usuwa ten wybór, a nie dokłada obrotu: każdy podportfel trzyma piątą część kapitału i rebalansuje się raz w tygodniu.

**Uzasadnienie jednostki R:** V1a definiuje R jako odległość do stopu, czyli `2 × atr_d1_14`. Koszyk stopu nie ma, więc „1 R” trzeba mu nadać z zewnątrz. Nadanie `1 × atr_d1_14` byłoby wygodne i **dwukrotnie zawyżałoby** wynik koszyka względem strategii przy tej samej ekspozycji. Kontrola #5 porównuje dwie serie w R, więc R musi znaczyć to samo po obu stronach.

**Odrzucone:**
- *Jedna kotwica (np. poniedziałek), prerejestrowana.* Prostsze, ale wkłada do benchmarku obowiązkowego jeden nietestowany parametr. Benchmark z parametrem przestaje być tym, czym miał być.
- *Z-score obu członów przed sumowaniem.* Usuwa dominację momentum i daje „zrównoważony” ranking carry + trend. Odrzucone, bo §12 mówi o sumie, a normalizacja to wielkość dobrana przez nas — i to dobrana w momencie, w którym już znamy jej wpływ.
- *Annualizacja zwrotu 3-miesięcznego (×4).* Odwraca proporcję na korzyść momentum jeszcze silniej. Ten sam zarzut.
- *Koszyk bez kosztów.* Łatwiejszy do pobicia, czyli optymistyczny dla H₁ — dokładnie ten kierunek błędu, którego ADR-024 zabrania.
- *Przeniesienie na koszyk warunków NO TRADE z V1a (blackout, rollover, piątek).* Brzmi jak „sprawiedliwe porównanie”, w praktyce jest dostrajaniem benchmarku regułami strategii, którą ma oceniać.
- *Porównanie expectancy NA TRANSAKCJĘ.* Strategia ma transakcje, koszyk ma ciągłą pozycję — „na transakcję” nie ma po stronie koszyka wspólnego mianownika. Dzienne R jest jedyną osią, która istnieje po obu stronach.

**Konsekwencje:** parametry dopisane do `validation.benchmark_carry_trend`, sekcji **bez** `frozen: true`, więc `frozen_sha256` = `2eab678f…` zostaje bez zmian i prerejestracja z ADR-027..031 jest nienaruszona. Kryterium „pobity” jest ostrzejsze niż dosłowne brzmienie §10.2 („Musi zostać pobity”): wymaga przedziału ufności różnicy, a nie porównania dwóch liczb punktowych. Zaostrzenie jest świadome — ciężar dowodu leży po stronie H₁, a różnica dwóch hałaśliwych średnich rozstrzygnięta na trzecim miejscu po przecinku nie jest dowodem. Kod benchmarku nadal nie istnieje; ten ADR go opisuje, nie pisze.

---

## ADR-040 — Kontrola #5 rozstrzygana po Sharpie, nie po średniej dziennej R

**Status:** ACCEPTED · 2026-09-20 · **Koryguje:** ADR-039, wiersze „Oś porównania” i „Kryterium »pobity«” · **Dotyczy:** §10.2 #5, ADR-019

**Kontekst:** ADR-039 przyjął, że kontrolę #5 rozstrzyga różnica ŚREDNICH dziennych R między strategią a koszykiem. To porównanie jest przechylone, bo obie serie nie chodzą na tym samym budżecie ryzyka.

Pomiar (dry run V1a, 2016-01-05 → 2016-04-28, 6 par, 50 transakcji; `trades.parquet` przebiegu):

| | średnie jednocześnie otwarte ryzyko |
|---|---|
| V1a (limit portfela 6 R, ADR-033) | **4,38 R** |
| koszyk §12 (1 long + 1 short, ADR-038) | **2,00 R** |

Strategia trzyma więc średnio **2,2× większą ekspozycję**. Przy liniowym sizingu daje to wyższe średnie dzienne R **bez żadnej przewagi** — czyli błąd optymistyczny dla H₁, dokładnie ten kierunek, którego zakazuje ADR-024. Kontrola, która ma być progiem, sama by go obniżała.

Sprzeczność jest też z logiką ADR-019. Uzasadnia on obowiązkowość koszyka zdaniem „jeśli system nie bije koszyka poza próbą, przechodzimy na koszyk”. Przechodząc na koszyk, uruchomiłoby się go na WŁASNYM budżecie ryzyka, nie na jego. Pytanie brzmi więc „co daje więcej na jednostkę ryzyka”, a nie „co daje więcej”.

**Decyzja:**

1. **Statystyka porównania to Sharpe serii dziennych R**, liczony po obu stronach tak samo (`validation/dsr.sharpe`, na obserwację, bez annualizacji), na wspólnej osi dni roboczych (`bootstrap.business_day`). Bezskalowy, więc różnica budżetów ryzyka przestaje wchodzić do werdyktu.

2. **Kryterium:** CI95 bootstrapu blokowego (20 dni roboczych) **różnicy Sharpe'ów**, strategia minus koszyk, w całości powyżej zera.

3. **Bloki losowane RAZ i stosowane do OBU serii** w każdej replikacji. Niezależne losowanie zerwałoby korelację dzienną między strategią a koszykiem — obie handlują te same pary w tych samych dniach — i dałoby przedział ufności różnicy szerszy, niż wynika z danych.

4. **Raport niesie obowiązkowo także wielkości, które kryterium normalizuje:** średnie otwarte ryzyko obu serii w R, średnie dzienne R obu i Sharpe obu osobno. Bezskalowe kryterium nie może być pretekstem do ukrycia tego, że jedna strona handluje dwa razy większą ekspozycją.

5. **Raport podaje wynik koszyka osobno dla każdej z pięciu kotwic rebalansu** (ADR-039), a nie samą średnią. Rozrzut między kotwicami jest JEDYNĄ kontrolą wrażliwości, jaką ten koszyk ma — V1a ma siatkę z ADR-028, koszyk nie ma nic. Uśrednienie bez podania rozrzutu ukrywałoby dokładnie tę informację, dla której kotwic jest pięć.

6. **Werdykt rozstrzyga wartość punktowa marży (0,5%), ale idzie z całą osią** `cohort_a_markup_sensitivity` (ADR-037). Finansowanie obciąża obie strony, więc marża przesuwa obie — i to nie o tyle samo, bo koszyk z założenia carry OTRZYMUJE, a płaci marżę na dwóch nogach. Werdykt kontroli #5 zależny wyłącznie od wartości punktowej jest nieważny.

**Odrzucone:**

- *Różnica średnich dziennych R (ADR-039).* Przechylona 2,2× na korzyść strategii wielkością, która nie ma nic wspólnego z jakością sygnału.
- *Normalizacja obu serii do wspólnego otwartego ryzyka* (podzielenie dziennego R przez średnie otwarte R). Prostsze i zostaje w R, ale zakłada, że ryzyko rośnie liniowo z liczbą pozycji — a §8 przyjmuje ρ = 1 tylko WEWNĄTRZ bloku walutowego, nie między blokami. Sharpe bierze zmienność zrealizowaną i tego założenia nie potrzebuje.
- *Przeskalowanie koszyka do budżetu strategii (np. do 4,38 R).* Budżet strategii jest wynikiem jej własnych reguł i zmienia się z okresem i z wariantem siatki. Benchmark przestałby być stałym punktem odniesienia i zaczął zależeć od tego, co ocenia.
- *Sharpe na transakcję.* Koszyk nie ma transakcji w tym sensie — ma ciągłą pozycję przebudowywaną raz w tygodniu.
- *Rezygnacja z przedziału ufności.* Patrz ADR-039: różnica dwóch hałaśliwych statystyk rozstrzygnięta na trzecim miejscu po przecinku nie jest dowodem, a ciężar dowodu leży po stronie H₁.

**Konsekwencje:** zmienia się pole `validation.benchmark_carry_trend.comparison`, sekcja bez `frozen: true`, więc `frozen_sha256` = `2eab678f…` zostaje bez zmian. Żaden wynik nie wymaga przeliczenia — kontrola #5 nie została jeszcze policzona ani razu. Pozostałe wiersze ADR-039 (kotwice, jednostka R, koszty, brak blackoutu, pomijanie niepełnych tygodni) obowiązują bez zmian.

---

## ADR-041 — Niepełne doby nie wchodzą do szeregu dziennego; dostępność ATR przez asof

**Status:** ACCEPTED · 2026-09-20 · **Zmienia sekcję `frozen: true`** (`data.d1_boundary`) · **Dotyczy:** ADR-023, ADR-024 (test odporności granicy dnia), ADR-039 (jednostka R koszyka)

**Unieważnia `frozen_sha256` = `2eab678f8ea5d942d2751abd0a01404d4b895768318debf48eb014cc1cc47dcd`. Nowa pieczęć: `b77d0b69fa8d2d3d22a225915db6e66710d1da24a6420c90d0ed5092f4b55ec4`.**

**Kontekst:** rynek FX chodzi ciągle od niedzieli 21:00 UTC do piątku. `daily_bars()` grupuje bary H1 po dobie kalendarzowej, więc sesja niedzielna tworzy własny bar dzienny zbudowany z **3 godzin** i wchodzi do `atr(d1, 14)` jako pełnoprawny dzień. Co szósta doba w szeregu jest kikutem.

Pomiar w `reports/atr_sunday_stub.md`, wszystkie sześć par kohorty A, 2015-01-01 → 2016-04-28 (tyle barów jest zbudowane):

| Wielkość | Wynik |
|---|---|
| niedziel będących kikutem | **69/69 na każdej parze**, mediana 3 bary H1 wobec 24 |
| zakres niedzieli wobec doby pełnej | 19,6% – 25,8% |
| deflacja `atr_d1_14` (mediana parowana per dzień) | **−10,7% … −11,8%**, jednakowo na sześciu parach |
| udział etykiet TP | 10,2% → **6,5%** po naprawie (−36% względnie) |
| udział bariery czasowej | 52,1% → **62,6%** |
| średni `cost_r` | 0,01049 → 0,00898 (**zawyżony o 16,8%**) |

**Błąd jest podwójny.** Pierwszy: deflacja ATR dotyczy każdego dnia tygodnia, bo okno ATR14 obejmuje 14 kolejnych barów dziennych, z czego ~2,3 to kikuty (`2,3/14 × 0,8 ≈ 13%`). Drugi: `_attach_daily_volatility()` mapuje dzień D na D+1 przez join po dacie, a sobota nie ma bara, więc **bary niedzielne mają `atr_d1_14 = None`** i są wykluczone z handlu przypadkiem, a nie regułą.

**To nie jest błąd skali.** Gdyby deflacja była czystym przeskalowaniem jednostki R, znak expectancy by się nie zmienił i sprawa byłaby obojętna dla werdyktu. Ale bariery są zaciśnięte przy NIEZMIENIONYM horyzoncie czasowym, więc zmienia się geometria triple barrier — czyli skład próby, a nie tylko jednostka, w której jest wyrażona. Warunek poprawności z ADR-023 (`bariera ≈ σ√T`) był dotąd sprawdzany przeciwko zaniżonej σ.

**Decyzja:**

1. **Doba z mniej niż `min_h1_bars` barami H1 jest NIEPEŁNA i nie wchodzi do szeregu dziennego.** `data.d1_boundary.min_h1_bars = 12`. Granica doby zostaje **00:00 UTC**, bez zmian.

2. **Dostępność wartości dziennych liczona przez asof, nie przez join po dacie.** Bar H1 dostaje `atr_d1_14` i `vol_pct_252` z **ostatniej PEŁNEJ doby zamkniętej przed jego własną dobą**. Punkt 2 jest nierozłączny z punktem 1: samo odfiltrowanie niedziel zostawiłoby poniedziałki bez żadnej wartości, bo join szukałby wtedy nieistniejącego bara niedzielnego.

3. **Kryterium kompletności stosuje się do każdego wariantu granicy doby**, także do „17:00 NY” i „22:00 UTC” z testu odporności ADR-024.

4. **Bary sesji niedzielnej dostają odtąd `atr_d1_14`** (z piątku) i przestają być blokowane brakiem cechy. Ich wykluczenie z handlu przechodzi do jawnej reguły — ADR-042.

**Uzasadnienie progu 12:** wybrany z pomiaru zakresów dobowych, nie z liczby barów. Niedziela (3 bary) ma 20–25% zakresu doby pełnej, 25.12.2015 (8 barów) ~36%, piątek (21 barów) **99–116%** — piątek jest dniem pełnym, bo brakujące 3 godziny to martwy wieczór po zamknięciu Nowego Jorku. Prawdziwa przepaść leży więc między 8 a 21 barami, a nie między 3 a 21, jak sugerował pierwszy skan. Próg 12 („pół doby handlowej”) siedzi w jej środku; każda wartość 9–20 daje na tej próbie identyczny wynik, wartości ≤ 8 przepuszczają Boże Narodzenie.

**Dlaczego teraz, a nie na bramce 2:** `data.d1_boundary` ma prerejestrowany test odporności przeciwko „17:00 NY” i „22:00 UTC”. **Obie alternatywy kasują kikut całkowicie** — przy granicy przesuniętej przed 21:00 UTC sesja niedzielna wpada do poniedziałku i żadna doba nie jest 3-godzinna. Test w dotychczasowej postaci porównywałby więc „zepsuty ATR” z „dobrym ATR”, a nie trzy konwencje granicy doby, przy kryterium porażki „>30% różnicy” i zmierzonych wielkościach rzędu 17–36%. Werdykt „wynik zależy od granicy dnia” byłby w dużej części artefaktem. Kierunek tego błędu jest pesymistyczny dla H₁, więc nie łamie ADR-024 — ale fałszywe no-go kończy projekt tak samo skutecznie jak prawdziwe, a aparatura ma dawać liczbę z przedziałem ufności, nie werdykt przechylony w bezpieczną stronę.

**Koszt unieważnienia wynosi dziś zero.** Jedyny wpis w `trials.jsonl` (`20260919T134506Z-c4710e`, bramka 0) jest już unieważniony przez ADR-026. Po pierwszym prawdziwym przebiegu V1a ta sama naprawa kosztowałaby unieważnienie próby liczonej do N w DSR i do limitu 50.

**Odrzucone:**

- *Zostawić i polegać na teście odporności z bramki 2.* Test mierzyłby artefakt — uzasadnienie wyżej. Dodatkowo każda liczba w R pozostałaby zawyżona co do modułu o ~12%, a zmierzony na bramce 0 koszt 0,0106 R o ~17%.
- *Przesunięcie granicy doby na 22:00 UTC albo 17:00 NY.* Kasuje kikut przy okazji, ale to zmiana `d1_boundary.research` na jedną z trzech wartości prerejestrowanego testu odporności. Baseline stałby się równy alternatywie i test przestałby istnieć.
- *Próg tylko w kodzie, bez ruszania konfiguracji.* Zmiana semantyki zamrożonej wielkości bez zmiany `frozen_sha256`. Pieczęć istnieje po to, żeby taka zmiana była głośna; cicha naprawa jest gorsza od braku naprawy.
- *Wygładzanie kikuta zamiast wykluczania* (np. skalowanie zakresu niepełnej doby do 24 godzin). Wprowadza współczynnik dobrany przez nas i zakłada, że zmienność rozkłada się w dobie równomiernie — a sesja niedzielna to najcieńsza płynność tygodnia, nie 1/8 normalnego dnia.
- *Odłożenie do czasu przebudowy barów na pełnym zakresie.* Mechanizm jest strukturalny (co szósta doba to 3-godzinny kikut), a naprawa dziś nie unieważnia żadnego ważnego wyniku. Pomiar warto powtórzyć po przebudowie, ale decyzja od niego nie zależy.

**Konsekwencje:**

- `frozen_sha256` zmienia się na `b77d0b69…`. Wszystkie dotychczasowe wyniki są formalnie unieważnione; faktycznie unieważnia to jedynie przebieg `20260919T134506Z-c4710e`, już nieważny po ADR-026. Prerejestracja ADR-027..031 dotyczy sekcji `signal_v1a` i `validation`, których ta zmiana nie dotyka, ale **pieczęć jest jedna**, więc jej zmiana jest odnotowana jako jawne unieważnienie, a nie jako korekta redakcyjna.
- `daily_bars()` jest wspólne dla cech i dla benchmarku §12, więc naprawa wchodzi też do koszyka. Dwa skutki uboczne, oba pożądane: kotwica poniedziałkowa przestaje pomijać wszystkie tygodnie (w dry runie 16/16 — bar decyzyjny z niedzieli 23:00 nie miał ATR), a `momentum()` liczone jako 63 wiersze wstecz odpowiada wreszcie 63 dniom roboczym — przy szeregu z niedzielami było to ~6 wierszy na tydzień, czyli 63 wiersze ≈ 10,5 tygodnia zamiast 12,6.
- Bramka 0 wymaga przeliczenia od zera i tak — była do przeliczenia po ADR-026.
- Test odporności z bramki 2 zachowuje sens: po naprawie żaden z trzech wariantów granicy nie ma kikutów, więc mierzy konwencję, a nie defekt danych.

---

## ADR-042 — NO TRADE w sesji niedzielnej (warunek 10)

**Status:** ACCEPTED · 2026-09-20 · **Doprecyzowuje:** ADR-033, `no_trade_conditions` · **Wynika z:** ADR-041 pkt 4

**Kontekst:** do ADR-041 bary sesji niedzielnej (21:00–23:00 UTC) miały `atr_d1_14 = None`, więc `decision_frame()` oznaczał je jako `warmup` i nigdy nie dawały wejścia. Po ADR-041 dostają ATR z ostatniej pełnej doby i stają się normalnymi kandydatami. Zmierzone na 2015-01…2016-04, sześć par: z **1073 barów niedzielnych 302 (28,1%) niesie sygnał V1a** przy progach baseline (`mom_480 > 0`, `donch_pos_55 > 0,80`). To nie jest przypadek brzegowy.

**Decyzja:** dochodzi warunek NO TRADE **`10_sunday_open`** — **moment decyzji wypada w niedzielę czasu UTC**. Priorytet w logu decyzji: po `9_friday`, przed `split_boundary`.

**Reguła zaczepia się o moment DECYZJI, nie o etykietę bara.** To rozróżnienie zmienia wynik, bo `decision_time_for_bar()` przesuwa o godzinę: bary niedzielne 21:00 i 22:00 dają decyzję w niedzielę i są blokowane, a bar 23:00 daje decyzję w poniedziałek 00:00 UTC i przechodzi. Zmierzone: blokowanych jest **659 z 1073 barów niedzielnych (61%), w tym 182 z sygnałem**; przechodzi 414 barów, w tym 120 z sygnałem.

Tak ma być. Blokujemy transakcję, a transakcja zawiera się w chwili decyzji — to ten sam odczyt, co przy `8_rollover` i `9_friday`, które też dotyczą momentu decyzji, a nie bara. Poniedziałek 00:00 UTC to 09:00 w Tokio, czyli normalna płynność sesji azjatyckiej; blokowanie go byłoby już nie ostrożnością, lecz obcięciem próby.

**Strefa: UTC, nie Nowy Jork** — mimo że warunki 8 i 9 są zapisane w czasie NY. Powód jest zmierzony, nie estetyczny: tydzień FX otwiera się w niedzielę o 17:00 NY, więc test „niedziela czasu NY” blokowałby decyzje od 22:00 UTC aż do 04:59 UTC w poniedziałek, czyli **całą poranną sesję tokijską**. Kryterium w UTC pokrywa się natomiast dokładnie z granicą doby z `data.d1_boundary` („00:00 UTC”), która jest konwencją zamrożoną tego projektu. Test na dniu tygodnia w UTC nie ma przy tym problemu z DST, którego zakazuje ADR-034 pkt 4 — nie ma tu stałego offsetu do pomylenia, bo nie ma godziny zegarowej.

**Uzasadnienie:**

1. **Spójność z istniejącą listą.** `8_rollover` (16:45–17:15 NY) i `9_friday` (piątek od 15:00 NY) istnieją dokładnie po to, żeby nie wchodzić w cienką płynność i szeroki spread. Niedzielne otwarcie jest najcieńszym momentem tygodnia — mocniejszy przypadek niż oba już zapisane.
2. **Naprawa danych nie powinna po cichu otwierać nowej klasy wejść.** ADR-041 naprawia pomiar zmienności. Gdyby przy okazji odblokował handel w 2,1% barów, byłaby to zmiana reguły przemycona w zmianie danych — dokładnie ten rodzaj cichej decyzji, którym ADR-033 i ADR-039 mają zapobiegać.
3. **Stan faktyczny nie zmienia się wobec wszystkich dotychczasowych pomiarów.** Te bary i tak nigdy nie dawały wejścia. Zmienia się wyłącznie to, że blokuje je reguła, a nie brak cechy — czyli że blokada jest widoczna w logu decyzji i policzona w raporcie.

**Odrzucone:**

- *Zostawić bary niedzielne dopuszczone i pozwolić, żeby rozstrzygnął pomiar.* Kusi metodologicznie, ale przesłanka jest znana z góry: spread w niedzielny wieczór jest wielokrotnie szerszy niż podłoga kosztu z ADR-024, więc model kosztów zaniżałby koszt akurat w tych barach. Błąd optymistyczny dla H₁, zakazany kierunek.
- *Blokada po etykiecie bara zamiast po momencie decyzji.* Objęłaby też bar 23:00, czyli decyzję o 00:00 UTC w poniedziałek. Niespójne z warunkami 8 i 9 i obcina próbę bez powodu.
- *Kryterium w czasie NY, dla spójności z warunkami 8 i 9.* Blokuje poranną sesję tokijską — uzasadnienie wyżej.
- *Rozszerzenie `8_rollover` zamiast nowego warunku.* Inna przyczyna, inna pora, inny czas odniesienia. Sklejenie dwóch reguł w jedną utrudniłoby odczytanie z raportu, która z nich ile blokuje.

**Konsekwencje:** dochodzi pozycja `{id: 10}` w `no_trade_conditions` — sekcja **bez** `frozen: true`, więc ten ADR sam z siebie nie zmienia pieczęci (zmienia ją ADR-041). Log decyzji zyskuje kategorię `10_sunday_open`; raporty V1a sprzed tej zmiany jej nie mają. Kontrola #5 (koszyk §12) **nie jest objęta** — ADR-039 wprost wyklucza przenoszenie warunków NO TRADE V1a na benchmark, a moment rebalansu koszyka jest osobną sprawą, nierozstrzygniętą.

---

## ADR-043 — Moment rebalansu koszyka: 16:00 Europe/London zamiast 00:00 UTC

**Status:** ACCEPTED · 2026-09-20 · **Koryguje:** ADR-039, wiersz „Chwila decyzji” · **Dotyczy:** kontrola #5 z §10.2

**Kontekst:** ADR-039 przyjął, że podportfel rebalansuje się w dniu kotwicy o **00:00 UTC**, a wejściem jest ostatni zamknięty bar H1 przed tą chwilą. Wybór był domyślny — 00:00 UTC to granica doby z `data.d1_boundary` — i nie był uzasadniany płynnością.

Konsekwencja jest jednak taka, że koszyk transaguje w **najcieńszej godzinie każdej doby**. Decyzja o 00:00 UTC czyta bar 23:00 poprzedniego dnia, czyli godzinę po zamknięciu Nowego Jorku, kiedy Tokio jeszcze nie ruszyło. Dla kotwicy poniedziałkowej jest jeszcze gorzej: bar z niedzieli 23:00 to trzecia godzina tygodnia, otwarcie po weekendzie.

**Osobna sprawa, już naprawiona:** w dry runie kotwica poniedziałkowa pomijała 16/16 tygodni, bo bar z niedzieli 23:00 nie miał `atr_d1_14`. To był objaw niedzielnych kikutów i usunął go ADR-041 (po nim wszystkie pięć kotwic pomija 0 tygodni). Ten ADR **nie dotyczy tamtej awarii** — dotyczy realizmu momentu transakcji, który zostaje problemem niezależnie od ATR.

**Decyzja:**

1. **Moment rebalansu: 16:00 czasu Europe/London** w dniu kotwicy. Wejściem nadal jest ostatni zamknięty bar H1 przed tą chwilą (`last_closed_bar`), bez zmian.

2. **Trzymane jako czas lokalny + strefa, nigdy jako stały offset** (ADR-034 pkt 4). 16:00 w Londynie to 15:00 UTC latem i 16:00 UTC zimą; zapisanie stałego offsetu przesuwałoby moment o godzinę przez pół roku — dokładnie ten błąd, który przy EA_HICP_FLASH wyszedł na tickach.

3. Pola w `validation.benchmark_carry_trend`: `rebalance_time_local: "16:00"` i `rebalance_timezone: "Europe/London"` zastępują `rebalance_hour_utc`.

**Uzasadnienie wyboru godziny:** 16:00 w Londynie to **fixing WM/Reuters**, standardowy moment wyceny FX — po nim wyceniane są indeksy, fundusze i większość benchmarków walutowych. Przypada w nakładce sesji londyńskiej i nowojorskiej, czyli w najgłębszej płynności doby. Nie jest to wielkość dobrana przez nas pod wynik: to jedyna godzina w dobie FX, która ma status konwencji branżowej, i z tego samego powodu jest naturalnym momentem rebalansu dla koszyka, który ma być punktem odniesienia bez stopni swobody (ADR-019).

**Czy ta zmiana zapada pod wpływem wyniku:** nie, i to trzeba zapisać wprost, bo koszyk ma już za sobą dwa dry runy. Powód zmiany — nierealistyczna płynność o 23:00 UTC — został zapisany w `CLAUDE.md` jako propozycja **przed** ADR-041 i przed powtórzeniem dry runu. Jedyne istniejące liczby koszyka pochodzą z czterech miesięcy (ΔSharpe −0,0728, potem −0,1932, CI95 w obu przypadkach obejmuje zero), są jawnie oznaczone jako pozbawione znaczenia i nie mogą służyć za podstawę czegokolwiek. Kierunek wpływu tej zmiany na ΔSharpe nie był i nie jest znany z góry.

**Odrzucone:**

- *Zostawić 00:00 UTC.* Spójne z granicą doby, ale każe benchmarkowi handlować w najcieńszej godzinie doby i ponosić spread szerszy, niż modeluje podłoga z ADR-024. To czyni koszyk sztucznie łatwiejszym do pobicia — czyli błąd optymistyczny dla H₁, zakazany kierunek (ADR-024).
- *17:00 Nowy Jork (rollover).* Też konwencja, ale to moment naliczania swapu i rozszerzenia spreadu, a nie moment wyceny — V1a ma przeciwko niemu osobny warunek NO TRADE (`8_rollover`). Benchmark nie powinien celować w okno, którego strategia unika.
- *Godzina jako stały offset UTC (15:00 albo 16:00).* Prostsze w kodzie, ale przez pół roku trafia o godzinę obok fixingu. ADR-034 pkt 4 tego zabrania.
- *Osobna godzina per kotwica.* Dołożyłoby benchmarkowi pięć parametrów zamiast jednego. Cała wartość pięciu kotwic polega na usunięciu wyboru, a nie na pomnożeniu go.

**Konsekwencje:** zmiana dotyczy `validation.benchmark_carry_trend`, sekcji **bez** `frozen: true`, więc `frozen_sha256` = `b77d0b69…` (po ADR-041) zostaje bez zmian. Żaden wynik nie wymaga przeliczenia — kontrola #5 nie została jeszcze policzona na niczym, co ma znaczenie. Pozostałe wiersze ADR-039 i całe ADR-040 obowiązują bez zmian.

---

## ADR-044 — Kontrola #4: carry-only jako próg, buy & hold jako diagnostyka

**Status:** ACCEPTED · 2026-09-20 · **Doprecyzowuje:** PROJECT_SPEC §10.2 #4 i #9 · **Opiera się na:** ADR-038, ADR-039, ADR-040, ADR-043

**Kontekst:** §10.2 wymienia kontrolę #4 jednym wierszem — „**Buy & hold / carry-only** — musi zostać pobity". To są dwa różne obiekty rozdzielone ukośnikiem, jedno słowo kryterium i zero definicji. Bez ich rozpisania decyzje zapadłyby przy pisaniu kodu, czyli po cichu.

To ten sam zabieg, co ADR-033 dla reguły V1a i ADR-039 dla koszyka §12: ADR czyta niejednoznaczne miejsca, zanim powstanie kod. Spisany **przed** jakimkolwiek wynikiem V1a — `trials.jsonl` ma nadal jeden wpis, kontrolę bramki 0.

**Decyzja: kontrola #4 ma dwa ramiona o różnym statusie.**

### 4a — carry-only (ramię rozstrzygające)

Konstrukcja **identyczna z koszykiem §12** (ADR-038/039/040/043): te same pięć walut vs USD, te same pięć kotwic rebalansu, ten sam moment (16:00 Europe/London), ta sama jednostka `1 R = sl_multiple × atr_d1_14`, ten sam rachunek kosztu, to samo finansowanie z osią marży, ta sama reguła pomijania tygodni.

**Jedyna różnica: ranking liczy sam carry** — `interbank_3m(waluta) − interbank_3m(USD)` z miesiąca poprzedzającego decyzję — long top-1, short bottom-1. Człon zwrotu trzymiesięcznego znika.

Kryterium „pobity" **identyczne z kontrolą #5** (ADR-040): Sharpe serii dziennych R, bootstrap blokowy 20 dni roboczych z blokami losowanymi RAZ dla obu serii, CI95 różnicy (strategia − carry-only) w całości powyżej zera.

**Reguła pomijania tygodni zostaje z wymogiem policzalnego momentum**, mimo że carry-only go nie potrzebuje. Powód: #4a i #5 mają się różnić **dokładnie jedną rzeczą** — wejściem do rankingu — a nie także próbą. Carry-only niesie przez to 63-dniową rozgrzewkę, której nie używa; to nic nie kosztuje, bo strategia i tak ma własną, dłuższą (`vol_pct_252`).

### 4b — buy & hold (diagnostyka, NIE próg)

Long na każdej parze kohorty A, po 1 R (`sl_multiple × atr_d1_14` z wejścia), wejście w pierwszym momencie rebalansu okna, trzymane do końca, bez stopów. Jedna noga na parę, koszt raz, finansowanie za każdy dzień. Raportowane **per para** i jako suma równoważona, w R, obok sumarycznego R strategii.

**Nie jest progiem i nie jest porównywane Sharpe'em.** Dwa powody, oba zapisane:

1. **FX nie ma broniącego się kierunku pasywnego.** Long EURUSD jest dokładnie tak samo arbitralny jak short. „Przegrać z buy & hold" znaczyłoby wtedy tyle, że dolar akurat w tej próbie poszedł w jedną stronę — zdanie o próbie, nie o strategii. Dlatego §10.2 czyni #9 („buy & hold per instrument") obowiązkowym **na kohorcie B**: indeksy akcyjne mają realny dodatni dryf, a pary FX go nie mają, i to właśnie jest treść tej kontroli.
2. **Niezgodność przypisania w czasie.** Każde R w tym projekcie jest przypisane do dnia WEJŚCIA (`daily_frames`). Strategia i koszyk emitują wiele krótkich nóg, więc ich serie dzienne są porównywalne. Jedna noga na parę wrzuciłaby całe swoje R w jeden dzień i jej Sharpe byłby artefaktem przypisania. Wycena dzienna (mark-to-market) dałaby z kolei serię gładką tam, gdzie tamte są poszarpane — czyli systematycznie ją faworyzowała. Żadna z dwóch wersji nie jest porównywalna, więc Sharpe nie jest podawany wcale.

Zadanie 4b jest inne: **zmierzyć, ile z wyniku strategii dałby sam statyczny dryf kierunkowy**. To ta sama kwestia, co w kontroli #8 (expectancy osobno dla longów i shortów per instrument), widziana od zewnątrz zamiast od środka.

4b realizuje zarazem §10.2 #9 dla kohorty A. **#9 zostaje otwarte jako obowiązek dla kohorty B**, gdzie dopiero staje się progiem.

**Zapis o zawężeniu:** kryterium „musi zostać pobity" z §10.2 #4 stosuje się — wedle tego ADR-u — **wyłącznie do ramienia carry-only**. To jest zawężenie dosłownego brzmienia specyfikacji i jest świadome.

**Dlaczego #4 nie jest zbędne obok #5:** ranking koszyka §12 jest zdominowany przez momentum — zmierzone w ADR-039, człon zwrotu ma 4,2× większy rozrzut przekrojowy niż człon carry, a carry rozstrzyga głównie remisy. Pobicie #5 mówi więc niewiele o tym, czy strategia bije **carry**. Ablacja jest jedyną rzeczą, która to mierzy. Carry-only ma przy tym **zero parametrów swobodnych** — znika nawet okno 63 dni — czyli spełnia argument ADR-019 („praktycznie zerowa liczba stopni swobody") ostrzej niż sam koszyk §12.

**Odrzucone:**

- *Klasyczny carry: wszystkie pięć walut wedle znaku różnicy stóp.* Podręcznikowa postać, ale zmienia wobec #5 dwie rzeczy naraz — wejście do rankingu I liczbę nóg — więc różnicy między #4a a #5 nie dałoby się przypisać. Ablacja zmienia jedną.
- *Buy & hold jako próg.* Uzasadnienie w pkt 1 wyżej. Wysokość poprzeczki zależałaby od tego, w którą stronę poszedł dolar.
- *„Lepsza z dwóch stron" (long albo short) jako poprzeczka buy & hold.* Benchmark dobrany po obejrzeniu danych; podnosi poprzeczkę o wielkość wybraną z wyniku.
- *Rezygnacja z #4, skoro #5 jest policzone.* Patrz akapit wyżej — #5 mierzy głównie momentum.
- *Inne kryterium niż w #5.* Dwie kontrole na dwóch skalach zapraszałyby do wybrania tej, która lepiej wypadnie.
- *Mark-to-market dla 4b, żeby dało się policzyć Sharpe.* Dałoby serię gładką wobec poszarpanych — przewaga wynikająca z przypisania, nie z wyniku. Błąd w stronę benchmarku łatwiejszego do przegrania, czyli optymistyczny dla H₁ (ADR-024).

**Konsekwencje:** parametry w `validation.control_buy_hold_carry_only`, sekcji **bez** `frozen: true`, więc `frozen_sha256` = `b77d0b69…` (po ADR-041) zostaje bez zmian. Przebieg jest `kind="control"` (ADR-029), więc nie podnosi N w DSR ani nie zjada limitu prób. Kontrola #4 nie została jeszcze policzona ani razu; ten ADR ją opisuje, nie liczy.

---

## ADR-045 — Ręczna akceptacja godzin podejrzanych o awarię feedu

**Status:** ACCEPTED · 2026-09-21 · **Doprecyzowuje:** ADR-025, ADR-026, `data.quality` · **Wynika z:** przebieg `20260921T151443Z-187ab1`

**Kontekst:** `QualityReport.passes_gate_0()` blokuje werdykt, gdy `suspected_outages.height > 0`, z komunikatem „wymagają ręcznego sprawdzenia **przed akceptacją danych**". Sprawdzenie jest więc przewidziane — ale nie ma miejsca, w którym można zapisać jego wynik. Skutek: bramka 0 nie może przejść, choć wszystkie kryteria ADR-025 (a, b, c oraz spread z ticków) przechodzą. Na segmencie RESEARCH 2015–2021 detektor wskazuje trzy godziny. Kryterium bez mechanizmu akceptacji nie jest ostre — jest niespełnialne.

**Pomiar (2026-09-21, rozmiary plików `.bi5` w otoczeniu każdej godziny, wszystkie sześć par):** trzy godziny NIE są jednym zjawiskiem.

| Godzina UTC | Otoczenie | Odczyt |
|---|---|---|
| 2016-09-02 18:00 (piątek) | 17:00 = 4,5–8,9 kB, **18:00 = 0**, 19:00 = 20–40 kB | Dziura WEWNĄTRZ dnia handlowego. Dodatkowo 17:00 jest zapadnięte ~10× wobec 19:00, więc awaria obejmuje ~1–2 h. To prawdziwy podpis awarii feedu. |
| 2017-12-24 22:00 (niedziela, Wigilia) | 18:00–22:00 = 0, **23:00 = 0,5–1,7 kB** | Tydzień otworzył się godzinę później niż zwykle w czasie zimowym. Brak danych, bo nie było handlu — nie awaria. |
| 2019-05-26 22:00 (niedziela) | 18:00–22:00 = 0, 23:00 = 0–53 B, **00:00 = 6–34 kB** | To samo: opóźnione otwarcie tygodnia. Poniedziałek 2019-05-27 to Memorial Day i UK spring bank holiday. |

Wszystkie 18 plików (3 godziny × 6 par) istnieje na dysku i ma **0 bajtów**, a w `data/raw/manifest.jsonl` widnieją jako `status: "empty", bytes: 0` — serwer odpowiedział pustą treścią, nie błędem. To dokładnie ten przypadek, przed którym broni docstring `src/data/quality.py`, więc odczyt musi pochodzić z OTOCZENIA, nie z samego pliku.

Dowód uzupełniający: żadna z 237 transakcji bez etykiety w bramce 0 nie pochodzi z tych godzin (`reports/gate0_dropped.md`) — nie mają barów H1, więc nigdy nie weszły do puli kandydatów. Wkład tych godzin w gubienie próby jest dokładnie zerowy.

**Decyzja:**

1. Wprowadzamy jawną listę `data.quality.accepted_outages`. Każda pozycja niesie **godzinę UTC, powód, dowód i datę akceptacji**. `passes_gate_0()` nie blokuje na godzinach z listy; raport nadal je wypisuje, w osobnej sekcji „Zaakceptowane ręcznie", razem ze śladem akceptacji. Godzina nieujęta na liście blokuje jak dotąd.
2. Akceptujemy trzy godziny wymienione w tabeli wyżej.
3. **Detektora nie osłabiamy.** Nie dodajemy ogólnej reguły „pusty blok stykający się z weekendem = opóźnione otwarcie tygodnia", mimo że dwie z trzech godzin są dokładnie tym.

**Uzasadnienie:**

1. **Mechanizm jest już założony, brakuje tylko miejsca na wynik.** Komunikat `passes_gate_0()` mówi „przed akceptacją danych", czyli autor przewidział akceptację. Bez niej wiersz o lukach blokuje bramkę 0 na zawsze, niezależnie od tego, co pokaże symulator.
2. **Lista jawna, a nie automatyczna reguła** — bo docstring `quality.py` stawia sprawę wprost: „Zakodowanie godzin sesji ukryłoby dokładnie te luki, które mamy znaleźć". Reguła „pusto przy weekendzie jest w porządku" ukryłaby prawdziwą awarię w poniedziałkowy poranek. Detektor ma pozostać przeczulony, a koszt przeczulenia — trzy pozycje na siedem lat — jest znikomy.
3. **Skala.** Godzina piątkowa to 1 bar H1 na 43 634 na parę. Dwie niedzielne nie zabierają nic, bo tych barów nie ma w żadnym źródle — rynek stał.
4. **Lista jest stopniem swobody, więc musi być widoczna.** Pozycja dopisana po obejrzeniu wyniku strategii byłaby dopasowaniem danych do wyniku. Dlatego każdy wpis niesie dowód i datę, raport go drukuje, a akceptacja następuje PRZED jakimkolwiek przebiegiem `kind="strategy"` — `trials.jsonl` ma na dziś dwa wpisy, oba kontrole bramki 0.

**Odrzucone:**

- *Zdjąć wiersz o lukach z werdyktu bramki 0.* Znosi kryterium, zamiast je rozstrzygnąć. Następna awaria byłaby niewidoczna, a to jest jedyna rzecz, przed którą ten moduł broni.
- *Nauczyć klasyfikator opóźnionego otwarcia tygodnia.* Obejmuje 2 z 3 przypadków bez żadnej listy, więc kusi. Ukrywa jednak całą klasę prawdziwych awarii przy weekendzie — patrz pkt 2. Wolno to rozważyć osobnym ADR-em, jeśli lista urośnie na tyle, że jej prowadzenie stanie się uciążliwe.
- *Dociągnąć te godziny ponownie i rozstrzygnąć empirycznie.* Rozsądne dla godziny piątkowej, ale nie zmienia decyzji: pusta odpowiedź po ponowieniu znaczy dziurę w archiwum Dukascopy, a niepusta wymaga przebudowy barów i powtórzenia bramki. Do zrobienia przy `--retry-failed` po zakończeniu pobierania — jako uzupełnienie dowodu, nie warunek akceptacji.
- *Zaakceptować hurtowo wszystkie godziny `empty` u wszystkich par.* To zniesienie detektora inną drogą.
- *Zaakceptować tylko dwie niedzielne, a piątkową uznać za blokującą.* Konsekwentne, ale kryterium bramki 0 dotyczy tego, czy symulator mierzy uczciwie, a nie czy archiwum jest kompletne. Jeden brakujący bar H1 na 43 634 nie zmienia żadnej z liczb a/b/c, co pokazuje wkład zerowy w gubienie próby.

**Konsekwencje:** dochodzi `data.quality.accepted_outages` — sekcja **bez** `frozen: true`, więc pieczęć `frozen_sha256` = `b77d0b69…` (po ADR-041) zostaje bez zmian. `passes_gate_0()` zyskuje parametr z listą akceptacji, a raport jakości sekcję „Zaakceptowane ręcznie". Po zmianie kodu bramkę 0 należy przeliczyć, żeby werdykt w raporcie pochodził z kodu, a nie z komentarza — to kolejny przebieg `kind="control"`, nie podnosi N w DSR. Werdykt zależy wtedy wyłącznie od kryteriów ADR-025 a/b/c i wiersza o spreadzie, które przechodzą.

---

## ADR-046 — Operacjonalizacja kryterium bramki 1: trzy stany werdyktu, finansowanie wewnątrz rozkładu zerowego

**Status:** ACCEPTED · 2026-09-21 · **Doprecyzowuje:** `gates.gate_1` i §15 „Gate 1 — rozkład zerowy" (bez zmiany wartości `frozen: true`)

**Kontekst:** Kryterium brzmi „STOP, jeśli kontrola losowa daje dodatnie expectancy". Nie mówi trzech rzeczy: czy chodzi o średnią punktową, czy o wynik istotny; czy expectancy liczy się przed finansowaniem, czy po; ani co jest właściwym produktem bramki.

Bramka 0 zmierzyła na tej samej kontroli (run `20260921T161726Z-1e142d`, 2015–2021, 23 758 transakcji): netto **−0,0110 R**, CI95 [−0,0294; +0,0076], średni koszt 0,01156 R, połowa CI 0,0186 R. Szum średniej jest **większy** od mierzonej wielkości — to ta sama rozdzielczość, którą ADR-025 opisał dla bramki 0. Przy takim stosunku sama losowość wyrzuca punktową średnią nad zero mniej więcej raz na osiem przebiegów, nawet gdy symulator jest bez zarzutu.

**Decyzja:**

1. **Trzy stany werdyktu**, liczone na expectancy netto całej próby (bootstrap blokowy, dzień jako blok — §10.2 #6):

| Stan | Warunek | Co znaczy |
|---|---|---|
| `STOP` | dolny koniec CI95 > 0 | kontrola losowa zarabia istotnie — mierzymy nie to, co myślimy; projekt się kończy |
| `NIEROZSTRZYGNIĘTE` | średnia ≥ 0, ale CI95 zawiera 0 | plus mieści się w szumie; rozstrzyga człowiek, nie skrypt |
| `PRZECHODZI` | średnia < 0 i CI95 nie leży w całości powyżej zera | losowe wejścia tracą, tak jak mają |

2. **Expectancy liczy się po koszcie I po finansowaniu** (ADR-035). Raport podaje obok liczbę sprzed finansowania (`r + financing_r`), porównywalną z bramką 0.

3. **Produktem bramki jest rozkład zerowy**, nie werdykt: średnia R z każdego powtórzenia, zapisana jako `null.parquet` (ADR-013). Rozkład z mniej niż **30 powtórzeń** albo o zerowym rozrzucie nie jest produktem — werdykt `NIEROZSTRZYGNIĘTE` niezależnie od średniej.

4. Ten rozkład **nie zastępuje** kontroli #1 w przebiegu V1a. Rozrzut średnich skaluje się jak 1/√(liczba transakcji w powtórzeniu), a bramka 2 porównuje strategię z kontrolą o tej samej liczebności co strategia (§10.2 #1) — tę liczy sam `run_v1a`.

**Uzasadnienie:**

- **Stan środkowy jest asymetrycznie tani.** Automatyczny `STOP` na punktowej średniej kończyłby projekt na podstawie szumu raz na osiem prawidłowych przebiegów. Automatyczne przejście („średnia nad zerem, ale nieistotna, więc w porządku") chowałoby prawdziwy błąd symulatora za szerokim CI — dokładnie ten błąd, który bramka ma łapać. Oba tryby awarii są ciche, więc stan środkowy jest jawny i wraca do człowieka z liczbą.
- **Ta sama konstrukcja co w bramce 0** (ADR-025: wynik z CI szerszym od progu to „nierozstrzygnięte", nie „przechodzi"). Dwie bramki mierzące tę samą kontrolę nie powinny mieć dwóch różnych filozofii werdyktu.
- **Finansowanie w środku**, bo rozkład zerowy musi żyć w tym samym świecie kosztów co wynik, z którym go porównujemy — tak samo robi kontrola #1 w `strategy/runner.py`. Swap jest kierunkowy, więc musi wejść przed jakąkolwiek statystyką.
- **Próg 30 powtórzeń** bierze się z ziarnistości empirycznego p-value, 1/(1 + liczba powtórzeń): poniżej tego rozkład nie ma ogonów, a „rozkład zerowy" jest nazwą na kilka liczb. Domyślnie skrypt robi 200 powtórzeń.

**Odrzucone:**

- *Dwa stany, literalnie: każda dodatnia średnia to STOP.* Prostsze i surowsze, ale kończy projekt szumem raz na osiem przebiegów. Ciężar dowodu leży po stronie H₁ — to nie to samo co zgoda na losowy werdykt w drugą stronę.
- *Próg tolerancji („STOP dopiero powyżej +0,02 R").* Wprowadza nową stałą, której nie da się wyprowadzić z niczego, co już jest prerejestrowane. CI95 jest wyprowadzalne z danych.
- *Expectancy przed finansowaniem.* Inny świat kosztów niż wynik, z którym rozkład ma być porównywany w bramce 2.
- *Wykluczenie blackoutu makro (§7.2) i limitu jednej pozycji na parę z puli kontroli.* Kusi, bo zbliża pulę do uniwersum strategii, ale kontrola #1 w `run_v1a` losuje z pełnej puli — rozkład bramki 1 przestałby być porównywalny z tym, co zobaczy bramka 2.

**Konsekwencje:** dochodzą `src/validation/gate1.py` i `scripts/gate1.py` (kod wyjścia 0 = przechodzi, 1 = STOP, 3 = nierozstrzygnięte, 2 = brak danych). Przebieg jest `kind="control"`, więc nie podnosi N w DSR ani limitu prób. Nic w konfiguracji się nie zmienia — pieczęć `frozen_sha256` = `b77d0b69…` zostaje.

---

## ADR-047 — Szereg stóp zaczyna się miesiąc przed splitem; pokrycie sprawdzane dniami decyzji

**Status:** ACCEPTED · 2026-09-22 · **Doprecyzowuje:** ADR-035 i kontrolę wstępną z `strategy/runner.py`

**Kontekst:** Pierwszy przebieg bramki 1 przeszedł kontrolę wstępną, policzył wszystkie 200 powtórzeń (10 minut) i wywrócił się dopiero w `apply_financing`: `brak stopy overnight dla USD na 2015-01-22 (szukano wpisu <= 2014-12-01)`.

Obie strony działały zgodnie ze swoim opisem, tylko mierzyły co innego. `rate_on()` celowo czyta miesiąc POPRZEDZAJĄCY dzień decyzji — seria miesięczna dla stycznia to średnia ze stycznia, znana dopiero po jego końcu, więc użycie jej do styczniowej transakcji byłoby zaglądaniem w przyszłość. Kontrola wstępna `require_coverage()` sprawdzała natomiast miesiące `[start, end]` przebiegu. Szereg z FRED pobrano `--years 2015 2025`, czyli dokładnie od początku splitu badawczego. Styczeń 2015 był więc pokryty jako miesiąc serii i niepokryty jako dzień decyzji.

Bramka 0 tego nie złapała, bo `gate0.py` w ogóle nie liczy finansowania. `run_v1a.py` też nie — jego domyślna pierwsza decyzja to 2016-01-01, a grudzień 2015 w szeregu jest. Dziura była widoczna wyłącznie dla przebiegu startującego w pierwszym miesiącu splitu, czyli praktycznie tylko dla bramki 1.

**Decyzja:**

1. Szereg stóp pobieramy **od roku poprzedzającego split badawczy**. Domyślny zakres `scripts/fetch_rates.py` to `--years 2014 2025`. Dociągnięto 2014 (442 wiersze); **zero wartości z 2015–2025 nie zmieniło się**, zero ubytków — porównane wiersz po wierszu wobec kopii sprzed pobrania.
2. Kontrola wstępna liczy pokrycie **dniami decyzji, nie miesiącami serii**: `require_coverage_for_decisions()` przesuwa oba końce zakresu o `_prev_month()`. Używają jej `scripts/gate1.py` i `preflight()` w `strategy/runner.py`.

**Uzasadnienie:**

- **Kontrola wstępna ma sprawdzać to, co kod naprawdę przeczyta.** Kontrola, która przepuszcza przebieg wywracający się 10 minut później, nie jest kontrolą wstępną — jest drugim źródłem prawdy o tym samym. Przesunięcie o miesiąc wpisane jest w `rate_on()`, więc musi być wpisane i w to, co sprawdzamy przed `start_run`.
- **Awaria była głośna, ale mogła być cicha.** Tu wyszedł `KeyError`, bo `rate_on()` traktuje brak stopy jako błąd, nie jako zero — i to jedyny powód, dla którego nie policzyliśmy stycznia 2015 przy zerowym swapie. Gdyby kiedyś ktoś dołożył `fillna(0)`, ta sama dziura przeszłaby przez bramkę bez śladu.
- **Kolejność ma znaczenie dla licznika prób.** Wszystko, co może unieważnić przebieg, idzie przed `start_run()` (`scripts/gate1.py` §komentarz). Dla `kind="control"` upadek po wpisie kosztuje tylko czas, ale dla `kind="strategy"` wpis liczy się do N w DSR także wtedy, gdy przebieg skończył się błędem (ADR-029 pkt 3). Kontrola wstępna, która puszcza dalej zły przebieg, jest więc wprost kosztem w limicie 50 prób.
- **Rok wstecz zamiast miesiąca wstecz**, bo granica splitu nie jest jedynym miejscem, gdzie to wyjdzie: tańiej mieć zapas niż powtarzać tę diagnozę przy kohorcie B albo przy zmianie `carry_kind` na serię o innym opóźnieniu.

**Odrzucone:**

- *Zacząć bramkę 1 od 2015-02-01 albo od 2016-01-01.* Zabiera miesiąc (albo rok) z rozkładu zerowego, żeby ominąć brak jednego wiersza w pliku z danymi. Zakres pomiaru dopasowany do luki w danych, a nie do pytania.
- *Przyjąć zerowy swap tam, gdzie brakuje stopy.* Zero to nie „brak danych", tylko konkretna, fałszywa stopa. Jawnie odrzucone już w `rate_on()`.
- *Zostawić kontrolę wstępną i tylko dociągnąć 2014.* Naprawia ten jeden przypadek i zostawia rozbieżność między tym, co sprawdzamy, a tym, co czytamy — do następnego odkrycia przy okazji.

**Konsekwencje:** `data/rates/fred.parquet` ma 5270 wierszy zamiast 4828. Dochodzi `require_coverage_for_decisions()` i cztery testy w `tests/test_rates.py`, w tym jeden na prawdziwym pliku z dysku — gdyby szereg znowu zaczynał się 2015-01, test upada. Nic w konfiguracji się nie zmienia, pieczęć `frozen_sha256` = `b77d0b69…` zostaje, N w DSR zostaje 1.

---

## Decyzje otwarte (do rozstrzygnięcia empirycznie)

| # | Pytanie | Rozstrzyga |
|---|---|---|
| O-1 | Czy edge istnieje? | Gate 2 |
| O-2 | Czy carry daje incremental value? | Gate 3 |
| O-3 | Czy blackout makro redukuje ogon strat bez utraty expectancy? | Gate 3 |
| O-4 | Czy logit bije regułę deterministyczną? | Gate 3 |
| O-5 | Czy jakość darmowych danych wystarcza do wiarygodnej symulacji? | Gate 0 |
| O-6 | Jakie `r%`? | Po Gate 4, z rozkładu drawdownu |
| O-7 | Czy M15 entry timing poprawia R? | V2 |
| O-8 | Czy FVG ma wartość predykcyjną w FX? | V2 |
| O-9 | Czy edge replikuje się na kohorcie B? | Gate 5 |
| O-10 | Czy skrócenie horyzontu na kohorcie B do 5 dni opłaca się mimo utraty ruchu? | V2 |
| O-11 | Czy pooling kohort A + B bije oba modele osobne? | V2 |
