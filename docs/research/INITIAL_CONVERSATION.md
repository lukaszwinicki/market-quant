# Forex Signal Bot — materiał wejściowy do audytu koncepcji

> **Status:** materiał przedimplementacyjny
>
> **Cel pliku:** przekazać Claude Opus kontekst, który powstał podczas dotychczasowej dyskusji. Ten dokument jest materiałem źródłowym, a nie zatwierdzoną specyfikacją. Wszystkie założenia mogą i powinny zostać zakwestionowane podczas audytu.
>
> **Ważne:** dokument jest uporządkowaną rekonstrukcją ustaleń i decyzji z rozmowy, a nie technicznym logiem wszystkich wiadomości 1:1. Należy traktować go jako source material.

---

## 1. Intencja projektu

Chcemy stworzyć lokalną aplikację/bota do analizy rynku FX, której głównym zadaniem jest wyszukiwanie niewielkiej liczby potencjalnie wysokiej jakości setupów swing tradingowych i wysyłanie alertów na Discord.

Nie chcemy skalpingu ani setek transakcji dziennie.

Docelowy styl:

- minimum wejścia: **M15**,
- prowadzenie i ocena setupu: **H1 / H4**,
- kontekst rynku: **D1**,
- preferowane są pojedyncze dobre wejścia,
- pyramiding jest dodatkiem i nie jest priorytetem pierwszej wersji,
- najważniejsze są jakość setupów, risk management i możliwość obiektywnego przetestowania przewagi.

W pierwszym etapie system nie ma automatycznie wykonywać transakcji za prawdziwe pieniądze. Priorytetem są research, backtesting, paper trading, alerty i monitoring.

---

## 2. Pierwotna koncepcja użytkownika

Bot miał łączyć kilka funkcjonalności:

### 2.1 Analiza techniczna

Analiza danych z wykresu i ruchu ceny w celu określenia możliwego kierunku rynku oraz znalezienia miejsca wejścia.

Początkowo rozważane były wskaźniki i cechy takie jak:

- trend,
- momentum,
- RSI,
- MACD,
- ATR,
- ADX,
- średnie,
- struktura ceny,
- breakout,
- pullback,
- support/resistance,
- volatility.

Późniejszy kierunek dyskusji: nie używać bezrefleksyjnie wielu wskaźników; traktować je jako cechy, a nie jako niezależne „głosy”.

### 2.2 Analiza fundamentalna / makro

System ma analizować:

- kalendarz ekonomiczny,
- actual,
- consensus/forecast,
- previous,
- surprise,
- dane historyczne,
- decyzje Fed, ECB, BoE, BoJ,
- minutes,
- komunikaty,
- wystąpienia bankierów centralnych,
- zmiany oczekiwanej ścieżki stóp procentowych.

W dalszej dyskusji przyjęto, że sama wartość danych makro nie musi być wystarczająca. Znacznie bardziej interesujące jest:

**actual vs consensus vs previous + zmiana oczekiwań rynku + różnica polityki monetarnej pomiędzy walutami.**

Rozważana cecha:

`surprise = actual - consensus`

oraz jej normalizacja historyczna.

Ważny wniosek: system nie powinien zakładać prostego schematu „dobra inflacja = BUY waluty”. Liczy się również to, co było już wycenione i jak zmieniły się oczekiwania.

### 2.3 Sentyment społecznościowy

Początkowo rozważano X/Twitter, Investing.com i inne źródła opinii.

Późniejsza decyzja: **w wersji budżetowej i pierwszej wersji systemu social sentiment odkładamy / usuwamy.**

Powód: opinie tłumu nie są dla nas wystarczającym źródłem przewagi względem ceny, danych makro i oficjalnych informacji. Nie chcemy ponosić kosztów, komplikacji i ryzyka jakości danych bez dowodu, że taki komponent wnosi incremental value.

Nie oznacza to, że tekst i informacje fundamentalne są całkowicie odrzucone. Oficjalne komunikaty banków centralnych i dane makro pozostają ważne.

### 2.4 Money management

Ważne jest określenie:

- ryzyka pojedynczej transakcji,
- SL,
- TP,
- wielkości pozycji,
- ekspozycji na wspólną walutę,
- ograniczeń korelacyjnych,
- ochrony przed drawdownem.

Początkowo rozważano wartości rzędu 0.25–0.50% equity risk per trade jako ostrożny obszar testowy, ale nie jest to zatwierdzona „najlepsza” wartość. Ma być parametrem podlegającym badaniu.

### 2.5 Pyramiding

Pyramiding jest dodatkiem.

Założenie użytkownika: w silnym trendzie można dokładać do pozycji korzystając z niezrealizowanego zysku, ale tylko jeśli:

- trend jest silny,
- korekty są płytkie,
- struktura pozostaje nienaruszona,
- zmienność nie wymknęła się spod kontroli,
- całkowite ryzyko całej struktury pozycji pozostaje bezpieczne.

W dyskusji przyjęto, że system ma liczyć pyramiding jako **łączną ekspozycję jednego trade idea**, a nie jako kilka niezależnych transakcji.

Przykładowo rozważano:

- initial risk,
- niewielkie dodatki,
- twardy total risk cap,
- automatyczne wyłączenie pyramidingu przed/po ważnych wydarzeniach makro, przy skoku zmienności lub złamaniu struktury.

Nie jest to element MVP.

---

## 3. Styl i hierarchia timeframe'ów

Później doprecyzowano dokładniej docelowy sposób pracy:

```text
D1  = szeroki kontekst rynku
H4  = główny trend / struktura
H1  = setup / potwierdzenie
M15 = timing wejścia
```

Nie chcemy M1 i M5 w pierwszej wersji.

Logika:

- **D1:** jaki jest kontekst?
- **H4:** czy istnieje sensowny kierunek i struktura?
- **H1:** czy powstaje setup?
- **M15:** czy jest dobre miejsce do wejścia teraz?

To ma być swing trading, nie scalping.

Nie chcemy sztucznego dziennego limitu transakcji. Zero transakcji w danym dniu ma być prawidłowym wynikiem, jeśli nie ma przewagi.

---

## 4. Signal engine — koncepcja

Nie chcemy finalnie prostego:

```text
Technical = 40%
Macro = 30%
Sentiment = 30%
=> BUY
```

Wstępnie preferowany jest system oparty na:

```text
market data
    ↓
technical features
    ↓
regime detection
    ↓
macro features
    ↓
statistical / ML model
    ↓
probability / EV
    ↓
risk engine
    ↓
signal
```

Nie chcemy, aby LLM był głównym sędzią sygnału w MVP.

Jedna z głównych idei: nie przewidywać po prostu „cena wzrośnie/spadnie”, lecz konkretny scenariusz, np.:

`P(TP before SL within horizon)`

Ważne równanie:

`EV = P(win) * AvgWin - P(loss) * AvgLoss - Costs`

Win rate nie jest główną metryką.

---

## 5. Market regime

Jeden z najważniejszych pomysłów.

System powinien najpierw określić, w jakim reżimie znajduje się rynek, np.:

- trend + niska/średnia zmienność,
- trend + wysoka zmienność,
- range + niska zmienność,
- range + wysoka zmienność,
- event-driven / shock.

Rozważane metody:

- HMM / Hidden Markov Models,
- Markov Switching,
- volatility regime,
- klasyczne cechy trend/volatility.

Nie jest założone, że HMM musi być użyty. Ma zostać zbadane, czy regime detection faktycznie poprawia wynik out-of-sample.

---

## 6. Macro engine

Docelowo chcemy przechowywać dane w sposób point-in-time.

Dla eventu:

```text
actual
consensus
previous
publication_timestamp
event_timestamp
source_timestamp
vintage / revision information where available
importance
currency
```

Przykład logicznego rekordu:

```text
US CPI
actual
consensus
previous
surprise
historical standardized surprise
```

Dla banków centralnych interesuje nas:

- poprzednia komunikacja,
- aktualna komunikacja,
- zmiana tonu,
- oczekiwana ścieżka stóp,
- faktyczny ruch stóp,
- różnica względem oczekiwań rynku,
- relatywna polityka monetarna waluty bazowej i kwotowanej.

Ważne: minutes są publikowane z opóźnieniem, więc backtest musi respektować rzeczywisty timestamp publikacji. Nie wolno wykorzystywać informacji, która historycznie nie była jeszcze dostępna.

---

## 7. Claude — rola w projekcie

Kluczowe ustalenie:

**Nie chcemy używać Claude API w MVP jako ciągłego generatora sygnałów.**

Claude Pro ma być głównym narzędziem do:

- implementacji,
- researchu,
- code review,
- analizy backtestów,
- debugowania,
- metodologii,
- ręcznej analizy wybranych komunikatów makro,
- analizy przyczyn porażek systemu.

Potencjalne przyszłe role runtime Claude:

- second opinion,
- validator,
- analiza wyjątkowych eventów,
- analiza komunikatów banków centralnych,
- analiza historii transakcji,
- pomoc w eksperymentach.

Ale to ma być opcjonalne i mierzalne.

Najważniejszy model pracy:

```text
Quant engine działa samodzielnie
+
Claude jest researcherem / programistą / audytorem
```

---

## 8. Discord + ręczna analiza Claude

Rozważany budżetowy workflow:

```text
LOCAL BOT
    ↓
market + macro analysis
    ↓
interesting setup
    ↓
Discord alert
    ↓
użytkownik kopiuje alert
    ↓
Claude Project / Claude Code
    ↓
pogłębiona analiza
```

Discord nie powinien wysyłać tylko `BUY GBPJPY`.

Alert powinien zawierać gotowy snapshot, np.:

- instrument,
- timestamp,
- D1 state,
- H4 state,
- H1 state,
- M15 state,
- trend,
- structure,
- momentum,
- ATR / volatility,
- regime,
- macro state,
- upcoming events,
- model probability,
- EV,
- proposed SL,
- proposed TP,
- risk,
- data quality,
- reasons for and against the setup.

Dzięki temu użytkownik może wkleić całość do Claude bez dodatkowego API.

---

## 9. Claude jako część development workflow

Planowany sposób pracy:

### Opus

- architektura,
- analiza metodologii,
- trudne problemy,
- audyt koncepcji,
- audyt backtestera,
- search for look-ahead bias / leakage / overfitting,
- trudny debugging,
- review całego modułu.

### Sonnet

- codzienna implementacja,
- Python,
- FastAPI,
- DB,
- Docker,
- frontend,
- API adapters,
- testy,
- refaktoryzacja.

Preferowany workflow:

```text
Opus -> plan / challenge
Sonnet -> implementation
Opus -> review
Python/tests -> verification
Backtest -> empirical verification
```

---

## 10. VS Code, Claude Code i jeden chat

Użytkownik chce pracować przede wszystkim w VS Code z Claude Code, a nie prowadzić projekt głównie w przeglądarce.

Preferencja:

- jedno główne repozytorium,
- jeden główny projekt developerski,
- jeden główny chat/sesja Claude Code na danym etapie,
- pliki projektu jako trwałe źródło prawdy.

Nie należy polegać wyłącznie na historii chatu.

Przewidziane pliki:

```text
CLAUDE.md
docs/
    PROJECT_SPEC.md
    ARCHITECTURE.md
    STRATEGY.md
    RISK_MANAGEMENT.md
    BACKTESTING.md
    DATA_SOURCES.md
    DECISIONS.md
```

Historia chatu ma być materiałem źródłowym, a nie jedynym repozytorium wiedzy.

---

## 11. Pomysł na audyt tej koncepcji przez Opusa

Zamiast powiedzieć Opusowi „zbuduj to”, chcemy powiedzieć:

> potraktuj wcześniejszą koncepcję jako hipotezę i spróbuj ją obalić.

Opus powinien odpowiedzieć m.in. na pytania:

- Czy D1/H4/H1/M15 jest sensowną hierarchią dla swing tradingu?
- Czy macro rzeczywiście daje incremental predictive value względem same price action?
- Czy regime detection ma wartość?
- Czy ML jest potrzebny?
- Czy prosty model/reguły mogą być lepsze?
- Czy RSI/ADX/ATR/EMA są redundantne?
- Jak uniknąć look-ahead bias?
- Jak uniknąć data leakage?
- Jak poprawnie odtworzyć consensus/actual historycznie?
- Jak traktować rewizje danych?
- Jak modelować spread/slippage/commission/swap?
- Jak traktować różnice pomiędzy feedami?
- Czy correlated exposure na kilku parach może sztucznie powiększać ryzyko?
- Czy pyramiding powinien być w ogóle w MVP?
- Czy darmowe źródła są wystarczające do researchu?
- Czy architektura nie jest zbyt złożona względem spodziewanej przewagi?
- Które komponenty należy usunąć, jeśli nie dają mierzalnej poprawy?

---

## 12. Główna filozofia projektu

1. Nie zakładamy, że system jest zyskowny.
2. Nie zakładamy, że AI daje przewagę.
3. Nie zakładamy, że więcej cech = lepiej.
4. Nie zakładamy, że macro poprawi wynik.
5. Nie zakładamy, że regime detection poprawi wynik.
6. Każdy dodatkowy komponent musi zostać empirycznie zweryfikowany.
7. Backtest ma być point-in-time i out-of-sample.
8. Koszty transakcyjne muszą być modelowane.
9. Paper trading poprzedza real-money trading.
10. „NO TRADE” jest prawidłowym wynikiem.
11. Prostota jest preferowana, jeżeli nie tracimy mierzalnej wartości.
12. LLM nie może zastępować statystycznej walidacji.
13. Wyniki repozytoriów GitHub nie są dowodem własnej skuteczności.

---

## 13. Wstępny stack techniczny

### Backend

- Python 3.x
- FastAPI
- Pydantic

### Quant

- NumPy
- pandas / Polars
- scikit-learn
- statsmodels
- XGBoost / LightGBM
- ewentualnie PyTorch później
- TA-Lib / własne obliczenia

### Data

- PostgreSQL
- ewentualnie TimescaleDB
- Redis

### Frontend

- React / Next.js
- TypeScript
- TradingView Lightweight Charts

### Infrastructure

- Docker
- Docker Compose
- Git

### Notifications

- Discord webhook/bot

### Possible data sources for MVP

- darmowy provider FX, do weryfikacji aktualnej jakości i limitów,
- FRED/ALFRED,
- oficjalne źródła Fed/ECB/BoE/BoJ,
- darmowy lub lokalnie pobierany kalendarz, jeśli licencja i jakość na to pozwalają.

Nie ma obowiązku użycia wszystkich dostawców. Architektura powinna posiadać adaptery, aby można było później wymienić feed na płatny bez przebudowy całego systemu.

---

## 14. Kandydaci / projekty open source, które zostały sprawdzone

### ForexFlow

Interesujące elementy:

- Forex,
- OANDA,
- live data,
- WebSocket,
- Lightweight Charts,
- risk management,
- Claude runtime,
- MCP.

Wniosek: dobry materiał do architektury integracyjnej i MCP, ale nie należy przyjmować jego użycia Claude jako dowodu przewagi tradingowej.

### Claude Trader

Interesujące elementy:

- D1/H4/H1 + M15,
- multi-agent Claude,
- position monitoring,
- risk management.

Wątpliwości:

- deklarowane wyniki nie są wystarczającym dowodem,
- backtest mechaniczny nie musi odtwarzać prawdziwego działania agentów,
- potrzebna jest niezależna walidacja kosztów i look-ahead.

### ForexAI Bot

Interesujące elementy:

- próba ML/LightGBM,
- późniejsze odejście od ML w głównym systemie,
- structural setups,
- regime detection,
- drawdown/risk/correlation controls.

Wniosek: ważna lekcja, że ML nie musi poprawiać strategii.

### AlphaFX

Interesujące elementy:

- regime detection,
- risk management,
- correlated exposure,
- position sizing,
- backtesting.

Wniosek: dobry materiał ilościowy, ale krótkie próbki nie wystarczają do potwierdzenia przewagi.

### TradingAgents

Interesujące elementy:

- multi-agent architecture,
- technical/fundamental/sentiment decomposition,
- LLM orchestration.

Wniosek: dobry materiał architektoniczny, ale nie do kopiowania jako gotowa strategia.

### Jesse

Interesujące elementy:

- backtesting,
- Monte Carlo,
- significance testing,
- MCP.

Wniosek: dobra inspiracja metodologiczna.

### OpenBB

Interesujące elementy:

- data aggregation,
- financial research,
- MCP/AI integration.

Wniosek: potencjalnie przydatna warstwa danych później, niekonieczna w MVP.

---

## 15. Najważniejsze ryzyka koncepcyjne

### Data leakage

Model nie może używać informacji, która nie była znana w momencie decyzji.

### Look-ahead bias

Dotyczy szczególnie macro, central bank minutes, rewizji i danych consensus.

### Overfitting

Nie wolno wybierać strategii po najlepszym historycznym wyniku spośród setek testowanych wariantów.

### Non-stationarity

Relacje rynkowe mogą zmieniać się pomiędzy reżimami i okresami.

### Transaction costs

Spread, slippage, commission, swap i execution asymmetry mogą zniszczyć mały edge.

### Correlation

Kilka pozycji może być jedną ekspozycją na USD/JPY/GBP itd.

### Feed mismatch

Backtest i live feed mogą mieć różne ceny, spread i zasady tworzenia świec.

### LLM overconfidence

LLM może wygenerować wiarygodnie brzmiącą analizę bez wartości predykcyjnej. Ma obowiązek odróżniać dane, interpretację i hipotezy.

---

## 16. Kryteria potencjalnego sukcesu

Nie używać wyłącznie win rate.

Wymagane metryki:

### Trading

- expectancy,
- EV/trade,
- net return,
- max drawdown,
- Sharpe,
- Sortino,
- Calmar,
- profit factor,
- average R,
- tail risk.

### Prediction

- probability calibration,
- Brier score,
- precision/recall tam, gdzie mają sens,
- stability over time.

### Robustness

- walk-forward,
- out-of-sample,
- różne okresy,
- różne reżimy,
- sensitivity to costs,
- sensitivity to parameters,
- multiple feeds where possible.

---

## 17. Docelowa filozofia sygnału

Przykład koncepcyjny:

```text
GBPJPY

D1:
 bullish context

H4:
 bullish trend

H1:
 pullback / continuation setup

M15:
 entry trigger

Macro:
 supportive / neutral / adverse

Regime:
 trend / range / high-vol

Historical model:
 P(TP before SL) = X
 EV = Y R

Risk:
 0.25–0.50% test range

Decision:
 TRADE / WATCH / NO TRADE
```

To jest tylko przykład struktury, nie ustalony algorytm.

---

## 18. Ostateczny cel MVP

Zbudować lokalny system, który:

1. pobiera dane FX,
2. buduje M15/H1/H4/D1,
3. pobiera i zapisuje dane makro,
4. oblicza cechy techniczne i makro,
5. wykrywa reżim,
6. generuje kandydatów,
7. ocenia ich statystycznie,
8. stosuje risk engine,
9. zapisuje każdy sygnał i wynik,
10. wysyła wybrane alerty do Discord,
11. pokazuje wykres i stan pozycji,
12. umożliwia backtesting i paper trading,
13. pozwala Claude analizować system przez repozytorium i/lub później MCP,
14. pozostaje niezależny od Claude API w MVP.

---

## 19. Najważniejsza instrukcja dla audytora

**Ten dokument nie jest specyfikacją, którą należy bezkrytycznie wdrożyć. Jest hipotezą.**

Najpierw sprawdź, czy ta hipoteza ma sens.

Jeżeli część architektury jest niepotrzebna — usuń ją.

Jeżeli założenie jest błędne — zmień je.

Jeżeli nie ma wystarczających danych — zaznacz to.

Jeżeli czegoś nie można rzetelnie zweryfikować — nie przedstawiaj tego jako faktu.

Największym sukcesem nie jest implementacja całego pomysłu. Sukcesem jest znalezienie **najprostszej architektury, która ma szansę przejść rygorystyczną walidację empiryczną**.
