---
paths:
  - "src/features/**"
  - "src/labels/**"
  - "src/validation/**"
  - "src/execution/**"
  - "src/strategy/**"
---

# Checklista leakage'u (§10.4 PROJECT_SPEC.md)

Przed każdym raportowanym wynikiem dotykającym tych ścieżek:

- [ ] Wszystkie normalizacje w oknie rozszerzającym, tylko przeszłość
- [ ] Żaden `fit()` nie widział danych testowych (w tym skaler, imputer, kalibrator)
- [ ] Makro przez ALFRED z `realtime_start` = data decyzji
- [ ] Bar H1 zamknięty przed momentem decyzji (kontrola off-by-one) —
      używać `last_closed_bar()`, nigdy ręcznej arytmetyki na znacznikach czasu
- [ ] Symulator fillów nie widzi cen po momencie decyzji
- [ ] Kolejność barier: tickowo lub pesymistycznie, nigdy optymistycznie
- [ ] Bid/ask osobno, **nigdzie mid**
- [ ] Brak modeli stanu ze smoothingiem (`predict()` Viterbi, `smoothed_marginal_probabilities`)
- [ ] Zbiór instrumentów zamrożony
- [ ] Parametry zapisane w YAML z hashem git **przed** uruchomieniem
- [ ] `trials.jsonl` zaktualizowany automatycznie
- [ ] **Żadne wejście do backtestu nie pochodzi od LLM**
- [ ] Kontrole 2 i 3 z §10.2 przeszły

Pełny kontekst i uzasadnienia: `docs/PROJECT_SPEC.md` §10.4 i §10.2.
