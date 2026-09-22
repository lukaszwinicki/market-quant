# market-quant

Aparatura pomiarowa do rozstrzygnięcia jednej hipotezy — **nie jest botem
tradingowym ani platformą**.

> **H₁:** Istnieje prosta, deterministyczna strategia swingowa na 6 głównych
> parach FX, o expectancy istotnie większym od zera po realistycznych kosztach
> i po korekcie na liczbę przeprowadzonych prób.
>
> **H₀ (domyślna): takiej strategii nie ma.** Ciężar dowodu po stronie H₁,
> prior niski.

Sukcesem jest **liczba z przedziałem ufności**, nie działający system. Wynik
„H₁ odrzucone" jest pełnoprawnym sukcesem.

---

## Gdzie jest prawda

| Plik | Rola |
|---|---|
| `docs/PROJECT_SPEC.md` | Obowiązująca specyfikacja. W razie sprzeczności — wygrywa |
| `docs/DECISIONS.md` | Log decyzji (ADR). **Wpisy są niezmienne**; zmiana = nowy ADR |
| `config/v1_baseline.yaml` | Prerejestrowane parametry |
| `docs/AUDIT_REPORT.md` | Uzasadnienia; dlaczego rzeczy zostały usunięte |
| `docs/research/` | Materiał historyczny, **nieobowiązujący** |
| `docs/PROGRESS.md` | Bieżący stan (nie prawda — log). Czytać na starcie sesji dot. danych/strategii/walidacji |

Historia rozmów nie jest źródłem prawdy. Jeśli coś ma przetrwać — trafia do
`DECISIONS.md` jako ADR.

---

## Reguły, których nie wolno złamać

**Konfiguracja jest zamrożona.** Zmiana czegokolwiek z `frozen: true`
unieważnia wszystkie dotychczasowe wyniki i wymaga nowego ADR. Po zobaczeniu
pierwszego wyniku backtestu plik jest skażony — każda późniejsza zmiana jest
decyzją podjętą pod wpływem wyniku.

**Żadne wejście do backtestu nie pochodzi od LLM.** Model, którego dane
treningowe obejmują okres testu, zna wynik. Tego nie da się naprawić promptem
ani zmierzyć. Dotyczy scoringu tekstu, klasyfikacji zdarzeń, generowania cech.

**Każda próba jest logowana.** `trials.jsonl`, zapis automatyczny przez harness.
Każda iteracja wspomagana LLM jest próbą. Bez prawdziwego licznika Deflated
Sharpe Ratio nic nie znaczy.

**Hold-out 2024-2025 jest zapieczętowany** do bramki 4. Jedno uruchomienie,
potem projekt się kończy — go albo no-go.

**Bid i ask osobno, nigdzie mid.** Kolejność barier rozstrzygana tickowo albo
pesymistycznie, nigdy optymistycznie.

**Etykieta bara = początek przedziału.** Bar 09:00 (H1) zamyka się o 10:00.
Decyzja o 10:00 może użyć wyłącznie bara 09:00. Używać `last_closed_bar()`,
nigdy ręcznej arytmetyki na znacznikach czasu.

**`scripts/run_v1a.py` bez `--dry-run` to PRAWDZIWA próba.** Dokłada 7 do N
w Deflated Sharpe Ratio i do limitu 50 prób (`max_trials_before_gate_2`),
nieodwracalnie. Uruchamiać wyłącznie po zamknięciu bramki 0 i za wyraźną
zgodą użytkownika. Do sprawdzania okablowania służy `--dry-run KATALOG`.

**Aktualna pieczęć: `frozen_sha256` = `79ca85df…`** (ADR-048, unieważniła
`b77d0b69…`). Niezgodność hasha w przebiegu = wynik jest nieważny.

Pełna checklista leakage'u: `PROJECT_SPEC.md` §10.4 i `.claude/rules/leakage.md`.

---

## Bramki

| | Tydzień | Kryterium |
|---|---|---|
| 0 | 4 | Strategia losowa daje expectancy ≈ −koszt |
| 1 | 5 | Rozkład zerowy z kontroli losowej |
| **2** | **8** | **Główna.** Expectancy ≥ +0,10 R, t ≥ 2, DSR ≥ 0, PBO ≤ 0,30 |
| 3 | 10 | Każdy komponent ≥ +0,03 R albo usunięty |
| 4 | 11 | Zapieczętowany hold-out, jedno uruchomienie |
| 5 | 15 | Replikacja na kohorcie B |

**Porażka bramki 2 oznacza koniec.** Nie dodajemy macro, ML ani reżimów.
Nie stroimy parametrów.

---

## Praca z kodem

```bash
.venv/bin/python -m pytest tests/ -q          # testy
.venv/bin/python scripts/download_ticks.py    # pobieranie (wznawialne)
```

Środowisko: `.venv`, Python 3.12, polars + numpy + scikit-learn + pyarrow.
Dane w `data/` — ignorowane przez gita, odtwarzalne z downloadera.

**Testy symulatora egzekucji i cech pisz na danych syntetycznych.** Na
prawdziwych tickach nie znasz poprawnej odpowiedzi, więc nie wiesz, czy kod
działa — widzisz tylko, że coś zwraca.

Zakazane w V1: xgboost, lightgbm, HMM, PostgreSQL, Redis, FastAPI, React,
Docker, MCP, Discord, TA-Lib. Pełna lista w `config/v1_baseline.yaml`.

---

## Commity

Po angielsku, sam temat, bez body — chyba że „dlaczego" nie widać z diffa
(np. zmiana wartości `frozen: true`: wtedy nazwij ADR i unieważniony hash).

Prefiksy: `docs:` `config:` `feat:` `fix:` `test:` `chore:`

Przed commitem: `git add -A --dry-run`. Wpis `data/` w `.gitignore` bez
ukośnika ignorował kiedyś `src/data/` — czyli kod.

---

## Stan — PROJEKT ZAMKNIĘTY (2026-09-22)

**Bramka 2 nie przeszła. H₁ odrzucone, H₀ zostaje w mocy. ADR-049 jest
terminalny.** Run `20260922T200750Z-b57ab5`: expectancy netto −0,0560 R
wobec wymaganych +0,10 R, wszystkie dwanaście kryteriów na czerwono,
kontrola losowa niepobita (p = 0,80 przy progu 0,05).

To jest wynik, nie porażka — projekt był aparaturą do rozstrzygnięcia jednej
hipotezy i ją rozstrzygnął.

**Co to znaczy dla każdej kolejnej sesji w tym repozytorium:**

- **Nie stroić parametrów V1a, nie dodawać macro, ML ani reżimów.** §15
  zabrania tego wprost, a zobowiązanie zostało podpisane przed pierwszym
  backtestem. Każda taka zmiana byłaby teraz wybrana ze znajomością wyniku.
- **Nie uruchamiać `run_v1a.py`, kohorty B ani §15 „warunku awaryjnego"**
  bez świadomej decyzji człowieka zapisanej jako nowy ADR.
- **Hold-out 2024–2025 zostaje zapieczętowany na stałe.** Służył bramce 4,
  do której projekt nie dotarł.
- **Nowa hipoteza ekonomiczna to NOWY projekt** — nowa prerejestracja, nowy
  licznik prób, nowa pieczęć. Nie kontynuacja tego i nie dopisek tutaj.

Reguły powyżej obowiązują nadal — opisują, dlaczego temu wynikowi można
wierzyć. Pełny werdykt z granicami wniosku: **`docs/PROGRESS.md`**
i **ADR-049** w `docs/DECISIONS.md`. Ten plik trzyma tylko reguły trwałe;
nie dopisywać tu przebiegu prac ani wyników.
