# PROGRESS_ARCHIVE.md — materiał zamknięty

Przeniesione z `docs/PROGRESS.md` 2026-09-21, żeby bieżący stan dał się
przeczytać w całości na starcie sesji. Treść bez zmian.

**Nie jest źródłem prawdy** — decyzje trwałe są w `docs/DECISIONS.md`
jako ADR, obowiązująca specyfikacja w `docs/PROJECT_SPEC.md`.

---

### ROZSTRZYGNIĘTE 2026-09-20: `atr_d1_14` zaniżone o ~12% (ADR-041, ADR-042)

> Liczby niżej są z okna 2015-01…2016-04. Pomiar powtórzono 2026-09-21 na
> pełnym segmencie RESEARCH — `reports/atr_sunday_stub.md` §9, wynik ten sam.

Sesja niedzielna (21:00–24:00 UTC) tworzyła własny bar dzienny z **3 godzin**
i wchodziła do ATR14 jako pełny dzień. Pomiar powtórzony na **wszystkich
sześciu parach** — raport `reports/atr_sunday_stub.md`:

| | wynik |
|---|---|
| niedziel będących kikutem | **69/69 na każdej parze**, mediana 3 bary H1 wobec 24 |
| zakres niedzieli vs doba pełna | 19,6% – 25,8% |
| deflacja ATR14 (mediana parowana) | **−10,7% … −11,8%**, jednakowo na sześciu parach |
| udział etykiet TP | 10,2% → **6,5%** po naprawie (−36% względnie) |
| udział bariery czasowej | 52,1% → **62,6%** |
| średni `cost_r` | 0,01049 → 0,00898 (**zawyżony o 16,8%**) |

Rozstrzygnięcie kluczowego pytania „kosmetyka czy nie”: **nie**. Bariery były
zaciśnięte przy NIEZMIENIONYM horyzoncie, więc zmieniał się skład próby,
a nie tylko jednostka. Zmierzony na bramce 0 koszt 0,0106 R zgadza się
z ramieniem „z kikutami” co do trzeciego miejsca — ta liczba była zawyżona.

**ADR-041** (zmienia sekcję `frozen: true`): doba z < 12 barami H1 wypada
z szeregu dziennego; dostępność wartości dziennych liczona przez **asof**
(ostatnia pełna doba zamknięta przed dobą bara), nie przez join po dacie.
Oba punkty są nierozłączne — samo odfiltrowanie niedziel zostawiłoby
poniedziałki bez ATR. Granica doby bez zmian, 00:00 UTC.

Próg 12 z pomiaru zakresów, nie z liczby godzin: niedziela (3 bary) 20–25%
zakresu doby pełnej, **25.12 (8 barów) ~36%**, piątek (21 barów) **99–116%**.
Prawdziwa przepaść leży między 8 a 21 barami, nie między 3 a 21 — pierwszy
skan (próg ≤ 6) tego nie pokazywał.

**Nowa pieczęć: `frozen_sha256` = `b77d0b69…`** (było `2eab678f…`).
Unieważnienie jest jawne i kosztowało przeliczenie niczego — jedyny wpis
w `trials.jsonl` był już nieważny po ADR-026.

**ADR-042**: bary sesji niedzielnej zyskały ATR, więc przestały być blokowane
przypadkiem. Dochodzi jawny warunek NO TRADE `10_sunday_open` — **moment
decyzji w niedzielę czasu UTC**. Zaczepione o decyzję, nie o bar: bary 21:00
i 22:00 są blokowane, bar 23:00 daje decyzję w poniedziałek 00:00 UTC
i przechodzi. UTC, nie NY — „niedziela NY” obejmowałaby decyzje do 04:59 UTC,
czyli poranną sesję tokijską.

Skutek uboczny ADR-041, sprawdzony dry runem: **kotwica poniedziałkowa
koszyka §12 pomija teraz 0/16 tygodni** (było 16/16). Dodatkowo `momentum()`
liczone jako 63 wiersze wstecz odpowiada wreszcie 63 dniom roboczym — przy
szeregu z niedzielami było to ~10,5 tygodnia zamiast 12,6.

Pomiar z 2015-01…2016-04 (tyle barów jest zbudowane). Mechanizm jest
strukturalny, ale warto powtórzyć po przebudowie na pełnym zakresie.

---

Gotowe (528 testów):
- `src/data/` — downloader, resampling `tick → M1 → H1`, raport jakości
  (święta 25.12/1.01 rozpoznawane, nie liczone jako awarie)
- `scripts/build_bars.py` — Parquet `data/bars/{m1,h1}/symbol=/year=`,
  raport `reports/data_quality.md` (2015–16: bramka 0 przechodzi)
- `src/execution/simulator.py` — fill bid/ask, luki, pesymistyczna
  kolejność barier, podłoga kosztu (ADR-024). Naprawione: spread był
  liczony dwa razy (w cenach fillów i w `cost`); teraz od `gross`
  odejmowana jest tylko dopłata do podłogi, `cost` = max(spread, podłoga)
- `decision_time_for_bar()` w `resample.py` — odwrotność `last_closed_bar()`
- `src/features/technical.py` — 6 cech, test kauzalności;
  `compute_features(h1, donchian=55)` → kolumna `donch_pos_{n}` (siatka).
  ADR-041: `daily_bars(h1, min_bars=12)` wyrzuca doby niepełne,
  `_attach_daily_volatility()` łączy przez asof (ostatnia pełna doba
  zamknięta przed dobą bara). `MIN_H1_BARS_PER_DAY` musi się zgadzać
  z `data.d1_boundary.min_h1_bars` — pilnuje tego test
- `src/labels/triple_barrier.py` — etykiety z `t1`, `overlap_fraction`,
  `effective_sample_size`
- `src/validation/` — `cpcv.py` (grupy = całe dni, purge po `t1` +
  podłoga 10 dni rob., embargo 5 dni od ostatniego `t1` testu),
  `dsr.py` (PSR/DSR, `n_obs` = efektywne n), `pbo.py` (CSCV, N ≥ 2),
  `controls.py` (losowe wejścia dopasowane per (para, kierunek), rozkład
  zerowy, p-value), `bootstrap.py` (bloki 20 dni roboczych, weekend →
  poniedziałek). Test martyngałowy: losowe wejścia dają E[R] = −koszt
- `src/harness/registry.py` — `start_run(purpose, params)`: katalog
  `runs/<ts>-<hex>/` (kopia configu, `run.json`, `metrics.json`,
  `diff.patch` gdy drzewo brudne), wpis `start` do `trials.jsonl` PRZED
  kodem badawczym, `end` w `finally` (ok/error/interrupted). `n_trials()`
  = N wg ADR-029: suma `n_variants` po przebiegach `kind="strategy"`
  (wpisy bez `kind` = strategy); `n_runs()` = wszystkie starty.
  `kind` ∈ {strategy, control, infra} obowiązkowe. Hash commita, sha256 configu i osobno
  sekcji `frozen: true`, commit zamrożenia. `trials.jsonl` nie liczy się
  jako brudne drzewo
- `src/harness/market.py` — `load_m1(symbol, start, end, cfg)` czyta tylko
  potrzebne lata; zakres dotykający hold-outu → `SealedHoldoutError`
  (wyjście: `unseal=True`, bramka 4). `cost_model_for()` z configu
  (EURJPY = cross, podłoga 2,5). `load_h1()` — ta sama pieczęć
- `slice_window()` w `resample.py` (search_sorted); `label_events` podaje
  symulatorowi tylko okno [decyzja, bariera czasowa]
- `src/validation/gate0.py` + `scripts/gate0.py` — bramka 0 na harnessie:
  losowe wejścia zrównoważone long/short per para, memo transakcji
  (deterministyczne w (symbol, ts, kierunek)). Kryteria wg ADR-025:
  a) rachunek kosztu per transakcja (`cost_r = max(spread_r, podłoga)`,
  `r = gross_r − dopłata`; etykiety niosą `gross_r`, `spread_r`),
  b) test martyngałowy uruchamiany przez skrypt, c) CI95 przed kosztem
  ∋ 0 i połowa CI ≤ 0,05 R (szerszy = NIEROZSTRZYGNIĘTE). Plus spread
  z ticków i raport luk H1. Wynik w `runs/<id>/gate0.md` + `labels.parquet`
- Symulator, ADR-026: bariera czasowa w czasie zamkniętego rynku →
  `TIME_BARRIER` po ostatnim barze (`market_closed_between`). Zamknięcie:
  weekend, 25.12, 1.01; ogon dnia przed nim tylko od 20:00 UTC w piątek
  i od 17:00 w wigilię/sylwestra — wcześniejsze urwanie danych to awaria
  (`NO_DATA`). Progi godzinowe to doprecyzowanie implementacyjne ADR-026

Bramka 0 — pierwszy przebieg, NIEAKTUALNY po ADR-026 (`20260919T134506Z-c4710e`, pierwszy wpis
w `trials.jsonl`, drzewo brudne → `diff.patch`): 2015-01 → 2016-04-28,
6 par, 20 × 100 wejść na (para, kierunek), 23 719 transakcji, 11 min.
PRZECHODZI: netto −0,0010 R [−0,037; +0,034], brutto +0,0096 R
[−0,027; +0,045], koszt 0,0106 R, 0 naruszeń podłogi.
Moc: połowa CI = 3,4× koszt — na prawdziwych danych test NIE odróżnia
kosztu policzonego od pominiętego; to robi test martyngałowy + podłoga
per transakcja. Wykrywa tylko duży bias brutto (look-ahead, kolejność barier).

- `src/data/calendar.py` — schemat kalendarza (bez wartości), lista
  zamknięta serii HIGH per waluta, `coverage_gaps()` (każda seria w każdym
  roku), `blackout()` (ADR-032: 30 min przed … 120 min po zdarzeniu).
  `scripts/fetch_calendar.py` — cache surowych stron w
  `data/raw/calendar/`, wynik `data/calendar/<źródło>.parquet`, raport
  pokrycia. Źródło `fomc`: 2016–2025, 79 planowanych posiedzeń, godzina
  z komunikatu („For release at 2:00 p.m. EST”), nadzwyczajne pominięte.
  Źródło `fred` (`calendar_fred.py`): daty = pierwsza publikacja okresu
  z ALFRED (`output_type=4`) — 12/rok, GDP 4/rok (advance); serie
  CPIAUCSL, PAYEMS, PCEPI, RSAFS, GDPC1 sprawdzane vs id publikacji.
  Godziny z `config/calendar_times.yaml` — bez `verified: true` seria
  nie daje zdarzeń. Klucz: `FRED_API_KEY` w `.env` (gitignore).
  Źródło `bea` (`calendar_bea.py`): PCE i GDP advance z archiwum bea.gov,
  godzina z nagłówka embarga KAŻDEJ publikacji, daty zgodne z ALFRED co do
  dnia (inaczej błąd). 117 PCE + 40 GDP. PCE: 10 publikacji o 10:00/9:30
  ET zamiast 8:30 — stała godzina byłaby błędna.
  Źródło `bls` (`calendar_bls.py`): CPI i NFP z rocznych kalendarzy
  `bls.gov/schedule/<rok>_sched.htm`, zapisanych RĘCZNIE przez użytkownika
  do `data/raw/calendar/bls/` (bls.gov: 403 dla skryptów). 119 + 119,
  wszystkie 8:30 ET, daty zgodne z ALFRED.
  Źródło `census` (`calendar_census.py`): sprzedaż detaliczna — 2016–2019
  z archiwalnych PDF (`pypdf`, dwa układy nagłówka), 2020+ z rocznych
  kalendarzy wskaźników. 119, wszystkie 8:30 ET, daty zgodne z ALFRED.
  Źródło `ecb` (`calendar_ecb.py`): 8 posiedzeń/rok z konferencją.
  Konferencja — godzina z każdego komunikatu; decyzja — z ecb.pr220627
  (13:45 → 14:15 od 21.07.2022, spójność z konferencją sprawdzana).
  „CET” u EBC = czas lokalny Frankfurtu, potwierdzone na tickach EURUSD 2016.
  Źródło `boc` (`calendar_boc.py`): 80 decyzji. Daty z komunikatów
  `fad-press-release-RRRR-MM-DD`, godzina z rocznego komunikatu
  „…schedule…” („at 09:45 (ET)”; wcześniej 10:00). Godzina dla daty
  z NAJPÓŹNIEJSZEGO harmonogramu, który ją wymienia — 2024 dzieli się
  5 × 10:00 i 3 × 09:45. Każda data harmonogramu musi mieć komunikat.
  Źródło `statcan` (`calendar_statcan.py`): CA_CPI, 120 publikacji.
  Daty z `dai-quo/ssi/homepage/schedule-key_indicators-eng.json`, godzina
  z nagłówka PDF każdej publikacji („Released at 8:30 a.m. Eastern time”),
  data w nagłówku sprawdzana z JSON-em.
  Źródło `boe` (`calendar_boe.py`): 83 posiedzenia MPC 2016–2025. Lista
  przez `POST /_api/Search/RefreshContentPageSearchList`; slug `<miesiąc>-<rok>`
  = planowe (13march-2020 i „special … 19 march 2020” odpadają), data
  z „Published on …”, wymagany czwartek. Godzina 12:00 tylko z konwencji
  → `calendar_times.yaml` (BOE_RATE, `verified: false` — zdarzeń brak).
  Źródło `ons` (`calendar_ons.py`): UK_CPI 119 + UK_LABOUR 119. Kalendarz
  `releasecalendar?keywords=…` ma godzinę KAŻDEJ publikacji (`data-gtm-release-*`);
  9:30 do 2020, potem 7:00. Kalendarz zaczyna się w lutym 2016 — styczeń
  2016 (CPI 19.01, praca 20.01) z biuletynów, godzina z `calendar_times.yaml`
  (ONS_BULLETIN, `verified: false`), stąd 11 zamiast 12 publikacji w 2016.
  Źródło `rba` (`calendar_rba.py`): 104 decyzje (11/rok do 2023, 8 od 2024).
  rba.gov.au daje skryptom 403, więc strony czytane z kopii Wayback —
  harmonogram zapisany PRZED rokiem dowodzi zarazem planowości. Dwa układy:
  tekstowy („media release issued at 2.30 pm” + dni) i od 2024 lista
  z godziną i strefą per posiedzenie. 2018 nie ma zapisu harmonogramu:
  planowość z treści komunikatu („At its meeting today”). Nieplanowe
  19.03.2020 pominięte.
  Źródło `abs` (`calendar_abs.py`): AU_CPI, 41 publikacji (kwartalne, od
  X 2025 miesięczne). Godzina z każdej strony wydania: nowy układ
  („Release date and time … 11:30am AEDT”, skrót sprawdzany ze strefą),
  ausstats do 06.2020 („Released at 11:30 AM (CANBERRA TIME)”).
  Źródło `jp` (`calendar_jp.py`): JP_CPI, 120 publikacji. Harmonogram
  `data/kouhyou/e-stat_cpi.xml` (UTF-16) ma datę i godzinę (8:30 JST);
  lata 2016–2021 z kopii Wayback rocznych plików. Klucz = rok i miesiąc
  odniesienia (zmiana ery 平成→令和 zmienia nazwę), termin z najnowszej
  kopii (plik z 2017 zapowiadał styczeń 2018 na 2.03, wyszło 23.02).
  Źródło `boj` (`calendar_boj.py`): 79 decyzji. BoJ podaje godzinę
  ogłoszenia tylko do 2015 („Announced at 12:17 p.m.”), metadane PDF nie są
  publikacją (29.01.2016: ModDate 13:59, rynek 12:38). Znacznik = koniec
  posiedzenia z nagłówka protokołu (`minu_<rok>/g*.pdf`, od 2018 `.htm`);
  publikacja ~7 min później (zmierzone na M1 USDJPY 2016), więc mieści się
  w oknie −30/+120. Nadzwyczajne (16.03 i 22.05.2020) rozpoznane po
  zwrotach „Unscheduled Monetary Policy Meeting” / „brought forward” —
  w latach 2016–2025 żaden inny protokół ich nie ma; 2020 ma 7 planowych.
  Źródło `eurostat` (`calendar_eurostat.py`): EA_HICP_FLASH, 121 publikacji
  (12 na każdy rok 2016–2025 + grudzień 2025 wydany w 2026, poza zakresem).
  Kalendarz Eurostatu sięga 2025, portlet listy daje 403, więc sondowane są
  trwałe adresy `products-euro-indicators/w/2-DDMMYYYY-<sufiks>` (dni robocze
  24. → 7. następnego miesiąca, sufiksy ap/bp/cp — wyszło 106/14/1); brak
  komunikatu = `<title>EU Login`. Flash rozpoznaje tytuł („Euro area annual
  inflation …”, odczyt finalny brzmi inaczej i wypada w połowie miesiąca).
  Sondowanie kończy się na pierwszym trafieniu w miesiącu, brak trafienia
  w całym oknie = błąd. ~550 adresów w cache, więc powtórny przebieg jest bez
  sieci. Kontrola metody: dla 2025 (jedyny rok z kalendarzem Eurostatu)
  sondowanie dało te same 12 dat co kalendarz. Godzina: 11:00 czasu
  Europe/Luxembourg Z DST, nie stały CET — wyszło 71 zdarzeń o 09:00 UTC
  (lato) i 49 o 10:00 UTC (zima). Rozstrzygnięte dwoma dowodami: kalendarz
  2025 podaje „11:00Z” i zimą, i latem (więc to czas lokalny, nie UTC),
  a na M1 EURUSD zakres minuty / mediana dnia daje 7,3× o 10:00 UTC w 6 dniach
  zimowych i 3,7× o 09:00 UTC w 8 letnich (pozostałe minuty ≤ 2,2×).
  ec.europa.eu odpowiada 429 i zrywa połączenia — pauza 2,5 s i ponawianie
- `src/strategy/v1a.py` — reguła V1a + NO TRADE wg ADR-033:
  `decision_frame()` (warunki per bar), `run_v1a()` (sekwencyjnie: limity
  bloków walutowych, portfela, jedna pozycja na parę do `t1`), log decyzji
  z powodem dla KAŻDEGO bara. `rules_from(cfg)`, `grid_from(cfg)`.
  ADR-042: warunek `10_sunday_open` — moment DECYZJI w niedzielę czasu UTC
  (bar 23:00 daje decyzję w poniedziałek 00:00 UTC i przechodzi).
  Testy tylko na syntetyku; na prawdziwych danych jeszcze nie uruchamiane

ADR-043: rebalans koszyka §12 przeniesiony z 00:00 UTC na 16:00
Europe/London (fixing WM/Reuters). Powód: decyzja o 00:00 UTC czytała bar
23:00, godzinę po zamknięciu NY i przed otwarciem Tokio — najcieńszą godzinę
doby, gdzie spread jest szerszy niż modeluje podłoga ADR-024, czyli koszyk
był sztucznie łatwiejszy do pobicia. Czas lokalny + strefa, nigdy offset.
Sekcja niezamrożona, `frozen_sha256` bez zmian.

ADR-044: kontrola #4 ma dwa ramiona. **4a carry-only** rozstrzyga —
ablacja koszyka §12 (ranking bez momentum), kryterium identyczne z #5.
Potrzebna obok #5, bo ranking §12 jest zdominowany przez momentum
(ADR-039: 4,2× większy rozrzut przekrojowy), więc pobicie #5 nie mówi,
czy strategia bije sam carry. **4b buy & hold** to diagnostyka bez werdyktu:
FX nie ma broniącego się kierunku pasywnego, więc poprzeczka zależałaby od
tego, w którą stronę poszedł dolar w próbie. Zawężenie §10.2 #4 („musi
zostać pobity" stosuje się tylko do 4a) jest świadome i zapisane.
Sekcja niezamrożona, `frozen_sha256` bez zmian.

Prerejestracja przed V1a (ADR-027..031; config `frozen_sha256` był
`2eab678f…`, od ADR-041 jest `b77d0b69…`): DSR ≥ 0,95; siatka 7 wariantów jeden-parametr-naraz
w `signal_v1a.sensitivity_grid`, płaskowyż = każdy sąsiad ≥ 50% E[R]
baseline, ten sam znak; N = warianty w przebiegach `strategy` (kontrola
oceniająca sygnał V1a to też `strategy`); wejście tylko gdy cały horyzont
mieści się w splicie (każda granica); CPCV 6/2 = 15 podziałów, 5 ścieżek.
ADR-032: blackout 30 min przed … 120 min po, tylko zdarzenia planowane,
terminy wyłącznie parsowane ze źródeł. ADR-033: interpretacja V1a/NO TRADE.
ADR-034 (doprecyzowuje 032): kopie Wayback jako nośnik strony oficjalnej,
znacznik BoJ = koniec posiedzenia z protokołu, kryteria planowości per źródło,
godzina jako czas lokalny + strefa (nigdy stały offset).

Kalendarz (2026-09-20): KOMPLETNY dla kohorty A, 1740 zdarzeń, 16 serii,
`coverage_gaps()` puste dla 2016–2025 (sprawdzane też przez `require_coverage()`).
Per seria: FOMC 79, US_CPI 119, US_NFP 119, US_PCE 117, US_RETAIL_SALES 119,
US_GDP_ADVANCE 40; ECB_RATE 80, ECB_PRESS_CONF 80, EA_HICP_FLASH 120;
BOE_RATE 83, UK_CPI 120, UK_LABOUR 120; BOJ_RATE 79, JP_CPI 120;
RBA_RATE 104, AU_CPI 41; BOC_RATE 80, CA_CPI 120.

Trzy godziny, których źródła nie podają przy publikacji, są prerejestrowane
w `config/calendar_times.yaml` i zweryfikowane przez użytkownika 2026-09-20
(`verified: true`): BOE_RATE 12:00 Londyn, ONS_BULLETIN 9:30 Londyn (tylko
styczeń 2016, przed startem kalendarza ONS), EA_HICP_FLASH 11:00
Europe/Luxembourg. Każdy wpis niesie cytat, dowód i wynik testu na tickach.
Wniosek metodologiczny: godzina jest trzymana jako czas lokalny + strefa,
nigdy jako stały offset — dla HICP flash stały CET dawałby latem błąd godziny.

Rok 2015 nie jest potrzebny (rozgrzewka; FOMC 2015 nie podaje godziny).
Runner V1a ma wołać `require_coverage(events, symbole, start, end)` przed
liczeniem czegokolwiek — brak serii wygląda w `blackout()` tak samo jak brak
zdarzenia (ADR-032 pkt 4).
Kopie z Wayback (`web.archive.org/web/<znacznik>id_/<adres>`) są używane
tam, gdzie serwis blokuje skrypty (RBA) albo usunął pliki (roczne
harmonogramy stat.go.jp) — treść jest wierną kopią strony oficjalnej,
a znacznik zapisu bywa dowodem, że termin był znany z wyprzedzeniem.

Ustalenia z danych:
- Rozgrzewka: `vol_pct_252` wymaga 252 dni → pierwszy handlowalny bar
  ~rok po starcie danych (2016-01). Rok 2015 to tylko historia dla cech.
- Nakładanie etykiet ~99% przy horyzoncie 10 dni: efektywne n jest
  o rząd wielkości mniejsze od nominalnego. Do testów istotności
  używać `effective_sample_size`, nie liczby wierszy.
- Spready 2015 (mediana `spread_close`): EURUSD 0,3, USDJPY 0,4,
  pozostałe 0,8–1,2 pipsa. Podłoga 1,5 / 2,5 pipsa zwykle wiąże.
- `data/raw/dukascopy/EURUSD/2019,2020` — było 130 godzin próbek z testów
  dekodera; NIEAKTUALNE, downloader przeszedł przez 2019 i 2020, wszystkie
  pary mają komplet. Partycje barów zbudowane wtedy z tych próbek (118
  barów H1 za 2019, 6 za 2020) zostały usunięte — to był cichy zaniżacz
  próby, patrz `src/data/provenance.py`.

- Wydajność (2026-09-20): ~1,5 ms na transakcję w najgorszym przypadku
  (pełne okno 10 dni = 14 tys. barów M1, żadna bariera nietrafiona);
  wcześniej ~32 ms. Dwie zmiany: `_first_event()` szuka pierwszego bara
  z barierą wektorowo (numpy, 0,03 ms zamiast 29 ms), a `simulate_trade`
  wycina okno przez `slice_window()` (wyszukiwanie binarne) zamiast
  `filter` (6,4 ms). Stąd wymóg: `m1` posortowane po `ts` — sprawdzane,
  bo cichy zły wycinek byłby gorszy niż błąd. Logika i kolejność barier
  bez zmian; test porównuje `_first_event` z naiwnym skanem na losowych
  ścieżkach (200 przypadków na stronę).

- `src/data/provenance.py` + `require_fresh_bars()` w `harness/market.py` —
  obok każdej partycji `source.json` z liczbą godzin cache, z których
  powstała; runner odrzuca partycję zbudowaną z wycinka (`StaleBarsError`).
  `scripts/gate0.py` woła to przed `start_run`, żeby nieudana próba nie
  szła do `trials.jsonl`. Ucieczka: `--allow-stale-bars`
- `src/validation/controls.py` — komplet kontroli #1, #2, #3, #7 (§10.2):
  `shuffled_label_null()` (tasowanie WEWNĄTRZ grup (symbol, kierunek);
  rozkład zerowy jest wyśrodkowany na średniej puli, nie na zerze),
  `shift_features()` (tylko cechy modelujące, `atr_d1_14` nietknięte),
  `permutation_max_drawdown()` (permutacja kolejności DNI, nie transakcji)
- `src/validation/cost_sensitivity.py` — drabinka 1×/2×/3× (§9).
  Symulator raportuje teraz `slippage` osobno (`slip_r` w etykiecie), więc
  mnożnik skaluje cały modelowany koszt, nie sam spread. Przy 1× wynik
  jest identyczny z `r` symulatora — pilnuje tego test. Podpięte do
  raportu bramki 0
- `src/data/rates.py` + `scripts/fetch_rates.py` — stopy z FRED,
  `data/rates/fred.parquet`, raport `reports/rates_coverage.md`.
  Overnight (OECD `IRSTCI01<ISO>M156N`) komplet 132/132 miesiące
  2015–2025 dla całej kohorty A. `rate_on()` bierze miesiąc POPRZEDNI —
  średnia stycznia nie jest znana w styczniu
- `src/execution/financing.py` — swap FX (ADR-035, ADR-037): `rollover_days()`
  ze środą liczoną potrójnie (tydzień = 1+1+3+1+1 = 7),
  `financing_r()` kierunkowe, `apply_financing()` dokłada `financing_r`
  i pomniejsza `r` (wynik sprzed korekty = `r + financing_r`).
  Marża `cohort_a_markup_annual_pct: 0.5` to JEDYNA liczba w modelu
  kosztów bez sparsowanego źródła, więc NIE wolno jej raportować
  punktowo: każdy wynik idzie z osią `cohort_a_markup_sensitivity`
  [0,5; 1,0; 2,0] przez `markup_ladder()` (ADR-037). `refinanced()`
  przelicza marżę z `fin_unit_r` bez ponownego czytania stóp

ADR-037: marża swapu 0,5% + OBOWIĄZKOWA oś wrażliwości [0,5; 1,0; 2,0].
Koryguje ADR-035 pkt 4, który deklarował zabezpieczenie przez drabinkę
1×/2×/3× — nieistniejące, bo finansowanie świadomie nie jest nią skalowane.
Powod: przy stopie 1,1% ceny marża 1,0% kosztuje 0,035 R, czyli 3,3× cały
zmierzony spread i 35% progu bramki 2; dla USDCAD i EURJPY przewyższa
medianę faktycznego carry 3–5×.
ADR-035: finansowanie kohorty A modelowane jawnie (pominięcie warte
~0,13 R przy różnicy stóp 2,8 pp i stopie 1,1% ceny — więcej niż CAŁY
próg bramki 2, i kierunkowe, więc podszywa się pod sygnał).
ADR-036: FRED nie ma rentowności 2-letnich poza USD, więc benchmark
carry + trend (§12, ADR-019) jest NIEWYKONALNY zgodnie ze spec.
Zamiennik musi być prerejestrowany przed bramką 2 — nie teraz, żeby nie
wybierać wejścia do benchmarku po zobaczeniu wyniku strategii.
`frozen_sha256` bez zmian (wtedy `2eab678f…`) — `costs` nie jest zamrożone.

ADR-038 zamyka blokadę z ADR-036 (raport `reports/yield2y_sources.md`,
zwiad 2026-09-20). Ustalenia: 2Y da się pozyskać, ale z ośmiu instytucji
i w czterech różnych definicjach (zero-kuponowy spot z modelu — EUR/ECB,
GBP/BoE spline, CHF/SNB; par yield CMT — USD/FRED; konkretna obligacja
benchmarkowa — CAD/BoC; interpolacja/rynek wtórny — JPY/MoF, AUD/RBA,
NZD/RBNZ), więc kryterium „ta sama definicja” jest niespełnialne, a §12
to ranking PRZEKROJOWY, w którym stały bias per waluta się nie znosi.
Trzy luki po stronie wydawcy: RBA skończyło dzienne AGS na 2023-06-07
(następca `f2.1-data.csv` jest MIESIĘCZNY), RBNZ ma w 2020 28 obserwacji
zamiast ~250, kostki SNB `rendoblid`/`rendoblim` stoją na 2025-07-31
(inne kostki tego API są bieżące — serie wygaszone). OECD nie ma punktu
2-letniego w ogóle: `CL_MEASURE` przepływu `DSD_STES@DF_FINMARK` wymienia
tylko `IRLT` (≈10 lat), `IR3TIB` (3M), `IRSTCI` (overnight).
Druga blokada, niezależna od rentowności: §12 chce 8 walut vs USD, czyli
NZDUSD i USDCHF, a CHF jest wykluczony w `instruments` (`frozen: true`) —
literalne §12 wymagałoby ruszenia sekcji zamrożonej.
Pomiar przed wyborem (RESEARCH 2015-01…2021-12, hold-out nietknięty;
przekrój miesięczny, ranking po 2Y vs po `interbank_3m`): Spearman
mediana 0,976–1,000, noga short identyczna w 100% miesięcy, noga long
rozjeżdża się w 17–30% (waluty na górze są ciasno skupione).
Decyzja: carry mierzone `interbank_3m` (miesiąc poprzedni, jak ADR-035),
uniwersum 5 walut kohorty A vs USD (EUR, GBP, JPY, AUD, CAD), long top-1
/ short bottom-1. Parametry w `validation.benchmark_carry_trend` — sekcja
NIE jest zamrożona, `frozen_sha256` bez zmian (wtedy `2eab678f…`).
Cechy V1b `carry_2y`/`d_carry_20d` NIE są objęte ADR-038.

ADR-039 operacjonalizuje §12 (to, czym ADR-033 był dla V1a) — spisany PRZED
kodem i przed jakimkolwiek wynikiem strategii. Kluczowe: rebalans to PIĘĆ
nakładających się portfeli (kotwica pon–pt, wynik = średnia), bo pojedynczy
dzień byłby cichym stopniem swobody w benchmarku, którego jedyną zaletą wg
ADR-019 jest ich brak; `1 R = sl_multiple × atr_d1_14`, czyli TA SAMA
jednostka co w strategii (przy `1 × ATR` koszyk miałby wynik zawyżony 2×);
suma w rankingu dosłowna — zmierzone na 17 czystych tygodniach 2016, że
zwrot 3M ma 4,2× większy rozrzut przekrojowy niż carry (SD 3,61% vs 0,86 pp),
więc ranking jest zdominowany przez momentum, a carry rozstrzyga remisy;
koszty tylko przy ZMIANIE pozycji plus finansowanie za każdy dzień; blackout
i warunki NO TRADE V1a NIE są przenoszone na koszyk; tydzień bez kompletu
5 walut pomijany w całości; przebieg to `kind="control"`, więc nie podnosi N.
Kryterium „pobity” jest ostrzejsze niż dosłowne §10.2: wymaga przedziału
ufności RÓŻNICY, nie dwóch liczb punktowych.
Parametry w `validation.benchmark_carry_trend`, `frozen_sha256` bez zmian.

- `src/validation/benchmark.py` — koszyk §12 ZAIMPLEMENTOWANY (kontrola #5).
  `spec_from(cfg)`, `usd_pairs()` (long waluty na parze USD-bazowej = short
  pary), `ranking()` (None = tydzień niepełny → pomijany w całości),
  `run_anchor()` / `run_benchmark()` (pięć podportfeli), `daily_series()`
  (wspólna oś, koszyk = ŚREDNIA z kotwic), `compare()` (różnica Sharpe'ów,
  wspólne bloki), `mean_open_risk()`. Koszyk emituje transakcje w TYM SAMYM
  schemacie co strategia, więc `apply_financing`, `cost_ladder`,
  `markup_ladder` i bootstrap działają na nim bez wyjątków; `sl` jest
  syntetyczne (dokładnie 1 R od wejścia), bo tego wymaga `apply_financing`.
  Rachunek kosztu identyczny z symulatorem; poślizg po obu stronach liczony
  mnożnikiem WEJŚCIOWYM, bo wyjście to zlecenie rynkowe, nie stop.
  Podpięte do runnera jako kontrola #5 (`--no-benchmark` wyłącza, raport
  oznacza wtedy werdykt jako niepełny). Testy: `tests/test_benchmark.py`,
  tylko syntetyk.
- `daily_frames()` i `block_indices()` w `bootstrap.py` — wspólna oś dni dla
  wielu serii i jedno losowanie bloków dla obu stron porównania.

ADR-040 koryguje ADR-039 w jednym punkcie: porównanie idzie po SHARPIE serii
dziennych R, nie po ich średniej. Powód zmierzony na dry runie — V1a trzyma
średnio **4,38 R** jednocześnie otwartego ryzyka (limit portfela 6 R),
a koszyk zawsze dokładnie 2,00 R, więc różnica średnich faworyzowałaby
strategię 2,2× bez grama przewagi (błąd optymistyczny dla H₁, zakazany
przez ADR-024). Bloki bootstrapu losowane RAZ i stosowane do OBU serii —
niezależne losowanie zerwałoby korelację dzienną (te same pary, te same dni)
i rozdęłoby CI różnicy. Raport MUSI mimo bezskalowego kryterium podawać
średnie otwarte ryzyko i średnie dzienne R obu serii, wynik per kotwica
rebalansu (rozrzut po kotwicach to jedyna kontrola wrażliwości, jaką koszyk
ma — V1a ma siatkę ADR-028, koszyk nie ma nic) oraz całą oś marży.

- `src/strategy/runner.py` + `scripts/run_v1a.py` — runner V1a, GOTOWY,
  ale na prawdziwych danych jeszcze NIE uruchomiony jako próba.
  Kolejność: `preflight()` (pokrycie kalendarza + stóp; waluty z par
  przebiegu, nie z całej kohorty) i `require_fresh_bars()` PRZED
  `start_run(kind="strategy", n_variants=7)`, żeby zła konfiguracja nie
  zjadała limitu prób. Dalej 7 wariantów (cechy raz na wartość kanału,
  pamięć symulatora dzielona między 5 geometrii barier),
  `apply_financing()` przed JAKĄKOLWIEK statystyką, drabinka 1×/2×/3×,
  oś marży, bootstrap, DSR (N z `n_trials()`, `n_obs` = efektywne n,
  wariancja Sharpe'a MIĘDZY wariantami), PBO na macierzy dzień × wariant,
  płaskowyż ADR-028, podokresy, kontrole #1/#2/#3/#7. Raport
  `runs/<id>/v1a.md` + `trades.parquet` + `decisions.parquet`.
  `Window` rozdziela trzy daty: `data_start` (2015 — rozgrzewka cech, bez
  decyzji), `trade_start` (2016-01-01 — pierwsza decyzja; kalendarz musi
  pokrywać DOPIERO to), `split_end` (granica ADR-030).
  **`--dry-run KATALOG`** — pełne okablowanie do katalogu tymczasowego,
  BEZ wpisu do `trials.jsonl`; raport sam się oznacza jako dry run.
  Sprawdzone tak na 2016-01…04 (6 par, 50 transakcji, 12 059 decyzji,
  28 s): wszystkie sekcje raportu, wszystkie kategorie powodów poza
  `7_data_gap` i `no_fill`, `trials.jsonl` nietknięty.
  Testy tylko na syntetyku, z testem integracyjnym całej siatki.
- Ścieżki CPCV są przy V1a ZDEGENEROWANE: reguła niczego nie dopasowuje,
  więc transakcje grupy są identyczne w każdym podziale, w którym grupa
  jest testowa — 5 ścieżek (ADR-031) odtwarza pełną próbę i nie mierzy
  niczego. Raport podaje rozrzut po 15 PODZIAŁACH i udział próby zjadany
  przez purge/embargo, i mówi o degeneracji wprost.
- Drobiazg do zapamiętania: `5_portfolio` pojawia się w logu decyzji
  (~1,4% barów), choć ADR-033 mówi, że limit 6 R „nigdy nie wiąże”.
  Oba są prawdziwe — warunek `len(open_pos)+1 > 6` spełnia się przy
  sześciu otwartych pozycjach, ale wtedy blokuje też `6_open_position`.
  Decyzja jest ta sama, różni się tylko przypisany powód (priorytet
  z ADR-033: 5 przed 6). Nie zmieniać bez nowego ADR-u.

- `src/validation/control4.py` — kontrola #4 wg ADR-044, DWA ramiona.
  **4a carry-only** (rozstrzygające): `spec.carry_only()` to ablacja koszyka
  §12 — ta sama konstrukcja, ranking bez członu momentum, zero parametrów
  swobodnych. Tygodnie pomijane wedle tej samej reguły co §12, łącznie
  z wymogiem policzalnego momentum: oba ramiona mają różnić się rankingiem,
  nie próbą. Kryterium identyczne z #5 (ADR-040).
  **4b buy & hold** (diagnostyka): jedna długa noga na parę kohorty A,
  1 R, od pierwszego rebalansu do końca okna. BEZ werdyktu i BEZ Sharpe'a —
  FX nie ma broniącego się kierunku pasywnego, a jedna noga wrzuca całe R
  w dzień wejścia, więc jej Sharpe byłby artefaktem przypisania.
  Realizuje §10.2 #9 dla kohorty A. Testy tylko na syntetyku.
- `compare_carry_only()` zwraca `(porównanie | None, powód)`. Ranking po samym
  carry jest stabilny (stopy zmieniają się raz na miesiąc), więc na krótkim
  oknie to ramię handluje rzadko i oś dzienna bywa za krótka na bloki —
  wtedy brak liczby jest ZAPISANY, nie wyrzucony wyjątkiem. Kontrola #5
  zachowuje się inaczej celowo: tam za krótka oś znaczy, że za krótkie jest
  całe okno przebiegu.

Czego NADAL nie ma (spec wymaga): kontrola §10.2 nr 10 (rozkład zerowy
per kohorta); skrypty bramek 1–5; cała kohorta B.
(#5 / benchmark §12 — ZROBIONA, `src/validation/benchmark.py`.
 #4 — ZROBIONA, `src/validation/control4.py`.
 #9 — zrobiona dla kohorty A jako ramię 4b; dla kohorty B otwarta.)

Dry run runnera (2016-01-05 → 2016-04-30, 6 par, `--allow-stale-bars`),
po ADR-041/042/043/044: wszystko liczy się do końca.

- **Wszystkie pięć kotwic rebalansu pomija 0 tygodni.** Przed naprawą ATR
  kotwica poniedziałkowa pomijała 16/16 — decyzja o 00:00 UTC czytała bar
  z niedzieli 23:00, a ten nie miał `atr_d1_14`.
- Koszyk §12 po przeniesieniu rebalansu na fixing 16:00 Londyn (ADR-043):
  ΔSharpe −0,0649, CI95 [−0,2674; +0,1834]; przed zmianą −0,1932.
  **Uczciwie: zmiana wyszła na korzyść strategii.** ADR-043 był napisany
  przed uruchomieniem, motywacją jest płynność, a CI w obu przypadkach
  obejmuje zero i okno ma cztery miesiące — to nie jest wynik, tylko
  sprawdzenie okablowania.
- Kontrola #4: ramię 4a (carry-only) **bez porównania** — oś dzienna ma
  32 dni, bootstrap potrzebuje 40. Powód jest wypisany w raporcie.
  To właściwość ramienia, nie awaria: ranking po samym carry zmienia się
  raz na miesiąc. Na pełnym segmencie RESEARCH dni będzie dość.
  Ramię 4b policzone: buy & hold długi na sześciu parach daje −8,15 R,
  V1a −4,93 R (te liczby nic nie znaczą na czterech miesiącach).

Niezależnie od ATR: rebalans w niedzielę o 23:00 UTC był nierealistyczny —
to najcieńsza płynność tygodnia. Rozstrzygnięte przez ADR-043 na 16:00
Europe/London (fixing WM/Reuters), trzymane jako czas lokalny + strefa,
nigdy stały offset (ADR-034 pkt 4).

- Raport V1a podaje w logu decyzji DWIE kolumny: „pierwszy” (powód o najwyższym
  priorytecie ADR-033) i „zadziałał” (ile barów warunek obejmował niezależnie
  od priorytetu). Bez tej drugiej `10_sunday_open` miał zero mimo działania
  na 138 barach — warunki o niskim priorytecie znikały z raportu.
  To samo ujawniło, że `8_rollover` obejmuje 502 bary, będąc pierwszym na 8.
- `make_evaluator` wymusza stałą kolejność kolumn wyniku. `memo` jest dzielone
  między `run_v1a` a kontrolą losową, a te podają te same kolumny zdarzenia
  w RÓŻNEJ kolejności, więc kolejność kolumn zależała od historii wywołań
  i `pl.concat` powtórzeń kontroli potrafił się wywrócić. Błąd utajony,
  ujawniony przez ADR-042 (inne transakcje → inna historia memo).

Następne (gdy pobieranie dojdzie do końca 2021): `download_ticks.py
--retry-failed`, `build_bars.py`, potem `scripts/gate0.py` — przebieg
zamykający bramkę 0 (nowy symulator, kryteria ADR-025; kolejna próba
w `trials.jsonl`). Sprawdzić w raporcie: liczbę „bez wyniku" (po ADR-026
powinna spaść z ~1,2% prawie do zera) i połowę CI ≤ 0,05 R. Symulator jest
już zwektoryzowany (~1,5 ms na transakcję), więc 7 lat nie wymaga dalszej
optymalizacji przed bramką 0.

Uwaga do `trials.jsonl`: jedyny wpis (`20260919T134506Z-c4710e`) powstał
przed ADR-029 i nie ma pola `kind`, więc `n_trials()` liczy go jako próbę
strategii (N = 1), choć był kontrolą. Zachowawczo — zawyża N, nie zaniża.
`scripts/gate0.py` deklaruje już `kind="control"`.

---

### Kwestie rozstrzygnięte przy zamykaniu bramki 0

**1. 237 transakcji „bez wyniku" to ostatni bar
tygodnia.** Raport `reports/gate0_dropped.md`. **215 z 237 (91%)** to bar
piątkowy, którego moment decyzji wypada po zamknięciu rynku o 17:00 czasu
Nowego Jorku: w czasie letnim bar 21:00 odpada w 100% przypadków, w zimowym
bar 22:00 — rozkład miesięczny zgadza się z datami zmiany czasu co do
przypadku. Dalsze 9 to zamknięcia świąteczne (24.12, 25.12, 31.12), 13 to
pojedyncze godziny cienkiej płynności (głównie 21:00 UTC w dzień powszedni).
**Z 3 godzin podejrzanych o awarię feedu nie pochodzi ANI JEDNA** — nie mają
barów H1, więc nigdy nie weszły do puli kandydatów.

Werdykt: gubienie zależy wyłącznie od znacznika czasu wejścia, nie od
przyszłego przebiegu ceny — nie ma look-aheadu ani biasu optymistycznego.
Ostrzeżenie ADR-026 się nie realizuje.

To NIE jest luka w regułach. Warunek `9_friday` („piątek po 15:00 NY",
`config/v1_baseline.yaml:357`, `src/strategy/v1a.py:161`) obejmuje wszystkie
te decyzje — wypadają o 17:00–18:00 czasu NY. Widać je w bramce 0 tylko
dlatego, że kontrola losowa świadomie NIE stosuje warunków NO TRADE: testuje
symulator, nie strategię, więc losuje też z barów, których V1a nigdy nie
zagra. Dla bramki 0 to kierunek zachowawczy. **Nowy ADR niepotrzebny.**

Metoda na przyszłość: `evaluate.memo` (`src/validation/gate0.py:114`) trzyma
transakcje bez etykiety jako wartości `None`, więc listy NIE trzeba odtwarzać
przez powtórzenie losowania. UWAGA: kolumna „luki" w raporcie bramki 0 to
`gap_share` (`src/validation/gate0.py:244`) — udział transakcji domkniętych
**luką cenową** przez SL/TP, a NIE udział transakcji bez wyniku.

**2. 3 godziny bez danych — ADR-045, zaimplementowane.**
Pomiar otoczenia pokazał, że nie są jednym zjawiskiem: **2016-09-02 18:00**
(piątek) to prawdziwa dziura wewnątrz dnia handlowego (~1–2 h, 17:00 też
zapadnięte), a **2017-12-24 22:00** i **2019-05-26 22:00** to opóźnione
otwarcie tygodnia — cały blok 18:00–22:00 pusty, dane wracają o 23:00.
Wszystkie 18 plików (3 × 6 par) ma 0 bajtów, w manifeście `status: "empty"`,
więc odczyt musi pochodzić z otoczenia, nie z pliku.

ADR-045: jawna lista `data.quality.accepted_outages` (godzina + powód +
dowód + data), `passes_gate_0()` nie blokuje na pozycjach z listy, raport
je nadal drukuje ze śladem akceptacji. Detektor NIE jest osłabiany — żadnej
ogólnej reguły „pusto przy weekendzie jest OK", bo ukryłaby awarię
w poniedziałkowy poranek.

Kod w `src/data/quality.py` (`AcceptedOutage`, `accepted_outages_from()`,
`partition_outages()`), podpięty w `scripts/gate0.py` i `scripts/build_bars.py`.
`build_bars.py --report-only` przelicza raport jakości bez przebudowy barów.
8 nowych testów, wszystkie na syntetyku; sprawdzone czterema mutacjami kodu,
że faktycznie upadają (m.in. „lista akceptuje wszystko" i „akceptacja usuwa
godzinę z detekcji"). Pozycja listy niedopasowana do żadnej wykrytej godziny
nie blokuje, ale jest drukowana jako ostrzeżenie — literówka w dacie nie
może zniknąć po cichu.

---

### Bramka 0: wcześniejsze przebiegi i rozbicie kosztu (przeniesione 2026-09-21)

Werdykt bramki 0 to run `20260921T161726Z-1e142d`. Wcześniejsze przebiegi
tego samego pomiaru, zachowane w `trials.jsonl`: `20260921T151443Z-187ab1`
(przed ADR-045, werdykt blokowany wierszem o lukach) i
`20260921T160904Z-17fbe1` (po kodzie ADR-045, ale przed jego commitem —
`git_dirty`, dlatego powtórzony). `20260919T134506Z-c4710e` to pierwszy
przebieg, nieaktualny po ADR-026.

**Koszt: ADR-041 działa, potwierdzone.** Na CAŁYM zakresie średni `cost_r`
wychodzi 0,01156 R, czyli WIĘCEJ niż 0,0106 z pierwszego przebiegu — to nie
regresja. Na dokładnie tym samym oknie co pierwszy przebieg
(2015-01-01…2016-04-28, 4397 transakcji) koszt to **0,00906 R**, czyli
**−14,5%** i zgodnie z `reports/atr_sunday_stub.md`. Reszta to późniejsze
lata, gdzie spread jest większy w stosunku do zmienności: 2015 0,00909 →
2019 **0,01503** → 2021 0,01311.

---

### Powtórzenie pomiaru niedzielnych kikutów (przeniesione 2026-09-22)

`reports/atr_sunday_stub.md` §9, pełny segment RESEARCH, sześć par. **Pomiar,
nie próba.** ADR-041 potwierdzone na 7 latach (deflacja ATR14 −10,3…−11,9%,
zawyżenie `cost_r` +16,0%); **żadna liczba nie ruszyła decyzji ani pieczęci**.

Jedno doprecyzowanie operacyjne, które nadal obowiązuje: margines progu
`min_h1_bars` to **11–20**, nie 9–20 jak podaje ADR-041 („na tej próbie") —
na 7 latach są trzy Boże Narodzenia po 10 barów. Próg 12 zostaje w środku
przepaści, nowy ADR niepotrzebny, ale **nie wolno zejść poniżej 11**,
powołując się na ADR-041.

---

### Pomiar czasu przebiegu V1a — rozbicie (przeniesione 2026-09-22)

Dry run, pełny rok decyzji (2016), prawdziwe kontrole `--control-reps 200
--pool-per-group 3000`: **3 min 17 s**, 735 MB RAM. Rozkład: 7 wariantów 13 s,
kontrole #1/#2/#7 + przesunięte cechy **160 s**, koszyk §12 10 s, kontrola #4
11 s, reszta 3 s. Zmierzona osobno faza wariantów na całym segmencie
RESEARCH: **67 s** (baseline 889 transakcji).

Ekstrapolacja na pełny przebieg: koszt kontroli #1 rośnie liniowo z liczbą
transakcji (200 × 142 → 200 × 889 etykietowań), ale **kontrola #2 nie rośnie
wcale** — `--pool-per-group 3000` tnie ją do 12 × 3000 niezależnie od zakresu.
Doliczając droższe etykietowanie na 7-letnich ramkach M1 (3,4 ms vs 2,5 ms):
**ok. 15 minut, z zapasem 10–25.** RAM rzędu 3–4 GB przy 10 GB wolnych.

---

Przeniesione z `docs/PROGRESS.md` 2026-09-22 po zamknięciu bramki 2.
Treść bez zmian.

## Niedzielne kikuty — jedno ustalenie, które nadal obowiązuje

Margines progu `min_h1_bars` to **11–20**, nie 9–20 jak podaje ADR-041
(„na tej próbie") — na 7 latach są trzy Boże Narodzenia po 10 barów. Próg 12
zostaje w środku przepaści, ale **nie wolno zejść poniżej 11**, powołując się
na ADR-041. Cały pomiar: `docs/PROGRESS_ARCHIVE.md`.

---

---

## Ile potrwa przebieg V1a — ZMIERZONE (2026-09-21)

**Ok. 15 minut na pełnym segmencie RESEARCH, z zapasem 10–25**, RAM 3–4 GB.
Zmierzone dry runem na roku 2016 (3 min 17 s) — kontrola #2 nie rośnie
z zakresem, bo `--pool-per-group 3000` tnie ją do 12 × 3000. Pełne rozbicie
na fazy: `docs/PROGRESS_ARCHIVE.md`.

**Wniosek: `run_v1a.py` NIE wymaga optymalizacji.** To minuty, nie godziny —
nie robić kolejnych dry runów „dla pewności".

**Podgląd wyniku — do wiadomości.** Pomiar zaczął się jako dry run na CAŁYM
segmencie RESEARCH, przerwany po fazie wariantów; zdążył wypisać expectancy
trzech z siedmiu wariantów (baseline, D−, D+). Asystent te liczby widział,
użytkownik nie, `trials.jsonl` jest nietknięty i **N w DSR się nie zmienia**:
dry run nie loguje próby, a podglądnięta została dokładnie ta sama robota,
którą zaloguje przebieg właściwy (ten sam kod, dane i ziarno) — nie jest to
osobna próba. **Warunek: nic nie zostaje zmienione w reakcji na te liczby.**
Zmiana parametru, konfiguracji albo reguły przed przebiegiem właściwym byłaby
decyzją podjętą pod wpływem wyniku i wymaga ADR, który to nazywa. Liczby są
do odtworzenia na żądanie — świadomie nie wpisane tutaj.

---

---

## Stopy procentowe — dziura znaleziona i zamknięta (ADR-047, 2026-09-22)

Pierwszy przebieg bramki 1 padł po 200 powtórzeniach: `brak stopy overnight
dla USD na 2015-01-22`. Szereg z FRED zaczynał się dokładnie tam, gdzie split,
a `rate_on()` czyta miesiąc wcześniejszy. Pełna diagnoza: **ADR-047**.

Naprawione: dociągnięty 2014 (teraz domyślny zakres `fetch_rates.py`) i nowe
`require_coverage_for_decisions()` w `gate1.py` oraz w `preflight()` runnera.
**Żadna wartość 2015–2025 się nie zmieniła** — porównane wiersz po wierszu
wobec kopii sprzed pobrania: 442 dołożone, zero zmienionych, zero usuniętych.

`run_v1a.py` tej dziury **nie dotykał** (pierwsza decyzja 2016-01-01). Gdyby
dotykał, byłoby drogo: przebieg `kind="strategy"` liczy się do N także wtedy,
gdy kończy się błędem (ADR-029).

W `trials.jsonl` został wpis przerwanego przebiegu `20260922T180657Z-3acbf1`
(`kind="control"`, `status="error"`). Rejestr jest append-only, N to nie rusza.

---
