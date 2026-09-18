# Claude Opus — bezlitosny audyt koncepcji Forex Signal Bot

## Rola

Jesteś niezależnym senior quantitative researcherem, quant developerem, architektem systemów tradingowych i krytycznym reviewerem.

Twoim zadaniem **nie jest potwierdzić naszej koncepcji ani od razu zacząć implementacji**.

Twoim zadaniem jest ustalić, czy koncepcja zasługuje na implementację, a jeśli nie, uprościć ją i poprawić.

Materiał źródłowy znajduje się w:

```text
INITIAL_CONVERSATION.md
```

Traktuj go jako hipotezę stworzoną podczas rozmowy człowieka z innym modelem AI. **Nie zakładaj, że którakolwiek decyzja w tym pliku jest poprawna.**

---

# Główna zasada

> **Your job is not to implement our idea. Your job is to determine whether our idea is actually worth implementing, and then redesign it if necessary.**

Masz aktywnie szukać powodów, dla których system może nie działać.

Nie używaj argumentu „technicznie da się to zbudować” jako argumentu za sensem tradingowym.

Oddziel:

- fakt,
- założenie,
- hipotezę,
- heurystykę,
- wynik empiryczny,
- opinię.

Nigdy nie przedstawiaj hipotezy jako faktu.

---

# 1. Najpierw wykonaj audyt koncepcji, nie pisz kodu

Nie modyfikuj kodu i nie zaczynaj implementacji.

Najpierw przeczytaj:

```text
INITIAL_CONVERSATION.md
```

Jeżeli istnieją już inne pliki projektu, przeczytaj również:

```text
CLAUDE.md

docs/*
```

Następnie przygotuj raport audytowy.

---

# 2. Odpowiedz na pytanie nadrzędne

Czy pomysł:

> swing FX signal engine oparty na M15/H1/H4/D1 + price action/technical data + point-in-time macro/calendar + regime detection + statistical/ML validation + risk engine + Discord

jest sensownym projektem badawczym?

Nie pytam jeszcze, czy będzie zyskowny.

Pytam, czy **metodologia daje nam rozsądną szansę na uczciwe zbadanie istnienia przewagi**.

---

# 3. Zakestionuj hierarchię timeframe'ów

Przeanalizuj osobno:

```text
D1 = context
H4 = trend / structure
H1 = setup
M15 = entry
```

Odpowiedz:

- czy taki podział ma sens?
- czy nie jest zbyt arbitralny?
- czy timeframe'y powinny mieć różne role?
- czy potrzebujemy kilku timeframe'ów, czy wystarczy mniej?
- czy M15 jako minimum jest rozsądne dla kosztów i jakości danych?
- czy H4/H1/D1 są wystarczające?

Nie zakładaj, że wielointerwałowość automatycznie zwiększa przewagę.

---

# 4. Zakwestionuj analizę techniczną

Sprawdź, czy warto używać:

- EMA/SMA,
- RSI,
- MACD,
- ATR,
- ADX,
- momentum,
- breakout,
- pullback,
- support/resistance,
- price structure.

Poszukaj redundantnych cech.

Odpowiedz:

- które cechy mają sens jako baseline?
- które mogą być mocno skorelowane?
- które powinny zostać wyrzucone?
- co można obliczyć bez LLM?
- czy prosty rule-based baseline powinien być pierwszym benchmarkiem?

Nie proponuj 50 wskaźników.

---

# 5. Zakwestionuj market regime

Sprawdź, czy regime detection jest rzeczywiście potrzebny.

Porównaj koncepcyjnie:

- proste reguły,
- volatility regime,
- HMM,
- Markov Switching,
- clustering,
- supervised classification.

Powiedz, co byłoby najlepszym baseline'em i dlaczego.

Jeżeli regime detection nie daje mierzalnej poprawy, powinno zostać usunięte.

---

# 6. Zakwestionuj macro engine

To jeden z najważniejszych punktów.

Sprawdź, czy:

```text
actual
consensus
previous
surprise
central bank stance
rate expectations
```

rzeczywiście może zwiększyć predictive value względem same price data.

Rozdziel:

### A. event surprise

### B. monetary policy repricing

### C. yield/rate differential

### D. central bank text

### E. scheduled-event risk

Ustal, które elementy są naprawdę sensowne w MVP.

Nie zakładaj, że „macro = bullish/bearish”.

---

# 7. Sprawdź point-in-time data i rewizje

To jest krytyczne.

Sprawdź, jak należy historycznie odtworzyć:

- consensus,
- actual,
- previous,
- revisions,
- macro series vintage,
- central-bank publication time,
- minutes publication time.

Wskaż dokładnie, gdzie może wystąpić look-ahead bias.

Jeżeli obecny projekt nie może uczciwie odtworzyć informacji dostępnej w przeszłości, wskaż to jako blocker.

---

# 8. Zakwestionuj model predykcyjny

Porównaj minimum:

1. naive baseline,
2. rule-based baseline,
3. logistic regression,
4. gradient boosting,
5. ewentualny model regime,
6. dopiero później deep learning.

Odpowiedz:

- czego użyć jako pierwszego modelu?
- czy w ogóle potrzebujemy ML?
- jak zdefiniować target?
- czy lepiej przewidywać return, direction, triple-barrier outcome czy P(TP before SL)?

Preferuj najprostszą metodę, która daje uczciwy eksperyment.

---

# 9. Oceń triple-barrier / meta-labeling

Sprawdź, czy sensowne jest:

```text
upper barrier = TP
lower barrier = SL
vertical barrier = max holding period
```

oraz:

```text
rule-based candidate
        ↓
meta-model: TAKE / SKIP
```

Porównaj to z modelem przewidującym bezpośrednio przyszły return.

Wskaż, co jest metodologicznie bardziej uczciwe dla naszego stylu swing tradingowego.

---

# 10. Zakwestionuj EV i probability calibration

Nie chcemy polegać na:

```text
accuracy
win rate
confidence = 87%
```

Sprawdź konieczność:

- expected value,
- probability calibration,
- Brier score,
- reliability diagrams,
- uncertainty.

Wyjaśnij, jak ustalić minimalne kryterium wejścia.

---

# 11. Zakwestionuj risk management

Sprawdź:

- 0.25–0.50% testowego ryzyka,
- SL,
- TP,
- position sizing,
- portfolio exposure,
- currency exposure,
- correlation risk,
- drawdown de-risking,
- event risk.

Odpowiedz, czy risk powinien być:

- fixed fractional,
- volatility scaled,
- fractional Kelly,
- hybrid.

Nie podawaj „najlepszego procentu” bez dowodu.

---

# 12. Szczególnie zakwestionuj pyramiding

Nie przyjmuj pyramidingu jako oczywiście korzystnego.

Zbadaj:

- czy zwiększa expected return,
- czy zwiększa tail risk,
- czy zwiększa drawdown,
- czy zwiększa concentration,
- jak modelować total risk,
- kiedy pyramiding powinien być zabroniony.

Wskaż, czy powinien być usunięty z MVP.

---

# 13. Zakwestionuj koszty transakcyjne

Wymagaj modelu co najmniej dla:

- spread,
- slippage,
- commission,
- swap/financing, jeśli relevantne,
- execution delay,
- spread widening,
- news-event conditions.

Sprawdź, czy strategia może wyglądać dobrze tylko dlatego, że backtest nie uwzględnia kosztów.

---

# 14. Zakwestionuj feed i definicję ceny

FX jest OTC.

Sprawdź:

- różnice między broker feedami,
- bid/ask vs mid,
- candle construction,
- timezone,
- missing bars,
- weekend handling,
- spread history,
- live vs backtest feed.

Wskaż, czy jeden feed wystarczy do researchu.

---

# 15. Zakwestionuj darmowe źródła danych

Dla każdego proponowanego źródła sprawdź:

- zakres historii,
- jakość,
- licencję,
- limit requestów,
- real-time vs delayed,
- WebSocket vs REST,
- czy dane są wystarczające dla M15/H1/H4/D1,
- czy nadają się do paper trading,
- czy nadają się do real-money trading.

Nie rekomenduj płatnych źródeł tylko dlatego, że są lepsze.

Najpierw określ, czy darmowe dane wystarczą do testu hipotezy.

---

# 16. Zakwestionuj LLM

Przyjmij jako hipotezę:

> Claude nie jest głównym generatorem sygnału w MVP.

Sprawdź, czy to rzeczywiście najlepsze podejście.

Oceń role:

- developer,
- researcher,
- macro-text analyst,
- signal validator,
- post-trade analyst,
- experiment assistant.

Wskaż, czy jakikolwiek runtime use of LLM powinien być w MVP.

Jeżeli nie, napisz to jasno.

---

# 17. Zakwestionuj ręczny workflow Discord → Claude

Sprawdź, czy:

```text
Bot
 ↓
Discord
 ↓
copy/paste
 ↓
Claude
```

ma sens jako MVP.

Oceń zalety i wady względem:

- MCP,
- Claude Desktop,
- Claude Code,
- Claude API.

Założenie budżetowe:

**Claude Pro jest jedynym obecnym kosztem.**

Nie planujemy Claude API w MVP.

---

# 18. Zakwestionuj MCP

MCP ma być potencjalnie użyty później do:

```text
scan_market()
get_market_data()
get_calendar()
get_signal()
run_backtest()
get_trades()
```

Sprawdź, czy warto robić go od razu, czy dopiero po ustabilizowaniu lokalnego bota.

Nie komplikuj architektury bez potrzeby.

---

# 19. Zaproponuj prostsze MVP

Po audycie masz zaproponować **najmniejszy system, który pozwala uczciwie sprawdzić hipotezę**.

MVP powinno zawierać jak najmniej modułów.

Wskaż dokładnie:

```text
MUST HAVE
SHOULD HAVE
LATER
REMOVE
```

---

# 20. Zaproponuj baseline'y eksperymentalne

Minimum:

### Baseline A

Price/technical simple rules.

### Baseline B

Technical + regime.

### Baseline C

Technical + regime + macro event features.

### Baseline D

Technical + regime + macro + ML.

Każdy z nich powinien być testowany w identycznych ramach walk-forward.

Celem jest policzenie **incremental value** każdego komponentu.

---

# 21. Zaprojektuj rygorystyczny backtest

Wymagaj:

- walk-forward validation,
- strict temporal split,
- purging/embargo tam, gdzie potrzebne,
- point-in-time macro data,
- no future information,
- cost model,
- realistic execution assumptions,
- OOS test,
- stability analysis,
- sensitivity analysis.

Nie akceptuj pojedynczego backtestu z najlepszym wynikiem.

---

# 22. Zakwestionuj metryki sukcesu

Nie akceptuj:

```text
win rate > 50%
```

jako dowodu.

Zdefiniuj metryki:

- expectancy,
- EV,
- max drawdown,
- profit factor,
- Sharpe,
- Sortino,
- Calmar,
- average R,
- tail loss,
- calibration,
- stability across periods/regimes.

Uwzględnij także:

- liczebność próby,
- confidence intervals,
- multiple testing,
- backtest overfitting.

---

# 23. Szukaj ukrytych problemów

Obowiązkowo sprawdź:

- survivorship bias,
- selection bias,
- data snooping,
- parameter mining,
- multiple comparisons,
- regime selection after the fact,
- bad timestamp alignment,
- publication delay,
- macro revisions,
- missing data,
- broker feed differences,
- correlated trades,
- look-ahead through aggregates,
- accidental future bars in feature windows,
- incorrect candle close handling,
- unrealistic fills.

---

# 24. Nie kopiuj istniejących GitHubów

Wcześniej znaleziono m.in. projekty typu:

- ForexFlow,
- Claude Trader,
- ForexAI Bot,
- AlphaFX,
- TradingAgents,
- Jesse,
- OpenBB.

Masz użyć ich jako **evidence / reference architecture / lessons learned**, ale nie jako gotowej strategii.

Dla każdego istotnego elementu wskaż:

```text
ADOPT
ADAPT
REJECT
UNKNOWN
```

i uzasadnij.

---

# 25. Oczekiwany format raportu

## Executive conclusion

Czy projekt w obecnej formie ma sens jako research project?

## Major strengths

## Major flaws

## Critical methodological risks

## Assumptions that should be removed

## Assumptions that should be tested

## Recommended MVP

## Components to remove

## Components to postpone

## Recommended architecture

## Recommended data model

## Recommended signal model

## Recommended risk model

## Recommended backtest methodology

## Recommended experiments

## Existing projects — lessons

## What could realistically work

## What is unlikely to work

## What cannot currently be established

## Revised PROJECT_SPEC

---

# 26. Tryb „adwokat diabła”

Jeżeli uważasz, że jakaś część naszego pomysłu jest zła, napisz wprost:

> **REMOVE THIS**

Jeżeli coś jest tylko interesującą hipotezą:

> **TEST THIS**

Jeżeli coś jest wystarczająco mocne metodologicznie:

> **KEEP THIS**

Jeżeli nie ma wystarczających danych:

> **INSUFFICIENT EVIDENCE**

Nie próbuj być miły. Próba „uratowania” każdej części koncepcji jest błędem.

---

# 27. Warunek zakończenia audytu

Nie przechodź do implementacji dopóki nie powstanie poprawiona wersja:

```text
PROJECT_SPEC.md
```

oraz decyzje architektoniczne:

```text
DECISIONS.md
```

Dopiero wtedy można rozpocząć implementację.

Najważniejsze pytanie przed zamknięciem audytu:

> **Czy potrafimy zbudować najprostszy możliwy eksperyment, który pozwoli obalić albo poprzeć hipotezę o przewadze strategii?**

Jeżeli odpowiedź brzmi „nie”, nie zaczynaj budowy dużego systemu — najpierw napraw metodologię.
