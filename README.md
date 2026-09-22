# market-quant

**Aparatura pomiarowa do rozstrzygnięcia jednej hipotezy. Nie jest botem
tradingowym ani platformą.**

Projekt postawił jedno pytanie, zmierzył je rygorystycznie i odpowiedział
„nie". **Jest zamknięty.**

---

## Hipoteza

> **H₁:** Istnieje prosta, deterministyczna strategia swingowa na 6 głównych
> parach FX, o expectancy istotnie większym od zera po realistycznych
> kosztach i po korekcie na liczbę przeprowadzonych prób.
>
> **H₀ (domyślna): takiej strategii nie ma.** Ciężar dowodu po stronie H₁,
> prior niski.

Sukcesem miała być **liczba z przedziałem ufności**, nie działający system.

## Wynik

```
Expectancy netto:  −0,0560 R na transakcję
CI95:              [−0,1225; +0,0119]
Wymagane:          ≥ +0,10 R
```

**H₁ odrzucone. H₀ zostaje w mocy.** Bramka główna (nr 2) nie przeszła
żadnego z dwunastu kryteriów. Werdykt: [ADR-049](docs/DECISIONS.md),
pełny raport: `runs/20260922T200750Z-b57ab5/v1a.md`.

Rozstrzyga kontrola losowa: **160 z 200** losowych powtórzeń — te same pary,
kierunki, liczba transakcji, wyjścia i koszty, losowy tylko moment wejścia —
wypadło **nie gorzej** niż badana reguła (p = 0,80 przy wymaganym progu
0,05). Sygnał nie szkodzi; on po prostu nie niesie informacji.

Ujemne są wszystkie siedem wariantów parametrycznych i wszystkie trzy
podokresy. Nie ma czego stroić i nie chodzi o epokę.

## Dlaczego „nie" jest sukcesem

Projekt był zbudowany tak, żeby **nie dało się oszukać samego siebie**:
prerejestrowane kryteria podpisane przed pierwszym backtestem, zamrożona
konfiguracja pod pieczęcią SHA-256, licznik prób wpięty w Deflated Sharpe
Ratio, zapieczętowany hold-out i log decyzji, którego wpisów nie wolno
zmieniać.

Taka konstrukcja ma dokładnie jeden cel: żeby odpowiedź „nie" była możliwa
do usłyszenia. Zdecydowana większość publikowanych strategii to wynik
przeszukiwania, które nigdy nie miało jak zwrócić „nie".

## Dlaczego tej odpowiedzi można wierzyć

Zanim zmierzyliśmy strategię, zmierzyliśmy przyrząd:

| Bramka | Pytanie | Wynik |
|---|---|---|
| 0 | Czy aparatura mierzy uczciwie? | **PRZECHODZI** — losowe wejścia dają expectancy ≈ −koszt, brak śladu wycieku z przyszłości |
| 1 | Jak wygląda rozkład zerowy? | **PRZECHODZI** — losowe wejścia tracą istotnie, całe CI95 pod zerem |
| **2** | **Czy edge istnieje?** | **NIE PRZECHODZI** — 12 z 12 kryteriów na czerwono |

Gdyby przewaga istniała, ten sam przyrząd by ją pokazał. Wyjaśnienie
„źle zmierzyliśmy" jest niedostępne i to było celem bramek 0 i 1.

## Czego ten wynik NIE mówi

Połowa przedziału ufności to 0,067 R, więc pomiar był zbudowany na wykrycie
przewagi rzędu wymaganych **+0,10 R**. Przewaga rzeczywista rzędu
**+0,02…0,03 R byłaby w tych danych niewidoczna**.

Uczciwe zdanie brzmi: *„nie ma przewagi tej wielkości, jakiej wymagaliśmy"*,
a nie *„nie ma żadnej przewagi"*. Przy koszcie 0,0116 R na transakcję i tylko
**172 niezależnych obserwacjach** z 889 transakcji (nakładanie 96%) przewaga
zbyt mała, by ją tu wykryć, byłaby i tak zbyt mała, by się nią handlowało —
ale to argument o użyteczności, nie o istnieniu.

Wniosek dotyczy **jednej reguły**: wybicia z kanału Donchiana (55 barów) na
H1, z barierami skalowanymi ATR-em, horyzontem 10 dni roboczych, na sześciu
głównych parach FX, w latach 2016–2021, po realistycznych kosztach. O innych
horyzontach, rynkach i mechanizmach nie mówi nic.

## Gdzie jest prawda

| Plik | Rola |
|---|---|
| [docs/PROJECT_SPEC.md](docs/PROJECT_SPEC.md) | Obowiązująca specyfikacja. W razie sprzeczności — wygrywa |
| [docs/DECISIONS.md](docs/DECISIONS.md) | 49 ADR-ów. Wpisy są **niezmienne**; zmiana = nowy ADR |
| [docs/PROGRESS.md](docs/PROGRESS.md) | Stan końcowy i pełny werdykt z granicami wniosku |
| [config/v1_baseline.yaml](config/v1_baseline.yaml) | Prerejestrowane parametry, pieczęć `79ca85df…` |
| `trials.jsonl` | Rejestr prób. Wersjonowany celowo — bez historii DSR jest niewiarygodne |
| `runs/` | Raporty przebiegów. Parquety poza repo, raporty w repo |
| [CLAUDE.md](CLAUDE.md) | Reguły trwałe dla asystenta AI |

Historia rozmów nie jest źródłem prawdy.

## Jak to uruchomić

```bash
.venv/bin/python -m pytest tests/ -q        # 556 testów
.venv/bin/python scripts/download_ticks.py  # dane (wznawialne, ~10 GB)
.venv/bin/python scripts/build_bars.py      # bary H1 i M1 z ticków
```

Python 3.12, `polars` + `numpy` + `scikit-learn` + `pyarrow`. Dane w `data/`
nie są wersjonowane — są odtwarzalne z downloadera.

Przebiegi bramek (`scripts/gate0.py`, `scripts/gate1.py`,
`scripts/run_v1a.py`) dopisują się do `trials.jsonl` i **`run_v1a.py` bez
`--dry-run` jest prawdziwą próbą** — dokłada 7 do licznika, nieodwracalnie.
Zużyto 8 z 50 prób.

## Czego nie robić

Gdybyś wracał do tego repozytorium — albo gdyby robił to asystent AI:

- **Nie stroić parametrów V1a.** Wszystkie 7 wariantów ujemne.
- **Nie dodawać macro, ML ani reżimów.** §15 zabrania tego wprost, a
  zobowiązanie podpisano przed pierwszym backtestem. Każda taka zmiana
  byłaby teraz wybrana ze znajomością wyniku.
- **Nie odpieczętowywać hold-outu 2024–2025.** Służył bramce 4, do której
  projekt nie dotarł. Zostaje nietknięty.
- **Nie uruchamiać kohorty B** bez świadomej decyzji człowieka jako ADR.

**Nowa hipoteza ekonomiczna to nowy projekt** — nowa prerejestracja, nowy
licznik prób, nowa pieczęć. Nie kontynuacja tego. Ponowne użycie tych samych
siedmiu lat danych obciąża nową hipotezę skumulowanym kosztem wielokrotnego
testowania i musi to jawnie uwzględniać.

## Co zostaje

Strategia była tanią częścią. Droga część jest wielokrotnego użytku: dane
tickowe, broker-agnostyczny model kosztów, rozstrzyganie kolejności barier
bez optymistycznego przechyłu, bid/ask nigdy mid, ochrony przed zaglądaniem
w przyszłość, zapieczętowany hold-out, rejestr prób, CPCV/PBO/DSR oraz 556
testów pisanych na danych syntetycznych, gdzie poprawna odpowiedź jest znana
z góry.

Aparatura, która potrafi powiedzieć „nie" i udowodnić, że ma do tego prawo,
jest rzadsza niż strategia, która dobrze wygląda na backteście.

---

*Status: zamknięty 2026-09-22 (ADR-049).*
