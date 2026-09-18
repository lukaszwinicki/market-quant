# Forex Signal Bot — pliki startowe

W tym pakiecie są dwa podstawowe dokumenty:

## `INITIAL_CONVERSATION.md`

Uporządkowany materiał z dotychczasowej dyskusji: cele, założenia, proponowana architektura, timeframe'y, risk management, rola Claude, workflow Discord oraz problemy metodologiczne.

To **nie jest zatwierdzona specyfikacja**. Jest to materiał wejściowy dla audytu.

## `OPUS_AUDIT_PROMPT.md`

Instrukcja dla Claude Opus. Ma najpierw przeczytać materiał i przeprowadzić bezlitosny audyt, a dopiero po jego zakończeniu przygotować poprawioną specyfikację.

## Zalecany workflow w VS Code

1. Utwórz repozytorium projektu.
2. Włóż oba pliki do `docs/research/`.
3. Otwórz repozytorium w VS Code.
4. Uruchom Claude Code.
5. Upewnij się, że pracujesz na modelu Opus.
6. Wydaj polecenie:

```text
Read docs/research/INITIAL_CONVERSATION.md and docs/research/OPUS_AUDIT_PROMPT.md.
Do not implement anything yet.
Execute the audit exactly as instructed.
First produce the audit report and a revised project specification.
Do not assume any previous decision is correct.
Try to falsify the strategy and architecture before proposing implementation.
```

7. Po audycie niech Opus utworzy/zaktualizuje:

```text
PROJECT_SPEC.md
DECISIONS.md
AUDIT_REPORT.md
```

8. Dopiero po tym rozpoczynamy implementację.

## Ważne

Nie chcemy, aby Claude „przyklepał” wcześniejszą koncepcję. Najcenniejszym wynikiem audytu może być usunięcie części funkcjonalności albo uproszczenie systemu.
