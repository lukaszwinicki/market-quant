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
