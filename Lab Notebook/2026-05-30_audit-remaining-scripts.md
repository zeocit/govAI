# 2026-05-30 — Audit of remaining pipeline scripts (phase 01–02 + R)

## Context
Second audit pass, covering the scripts not deeply reviewed in the first
(v4→v5) pass: the collection/cleaning Python scripts (01a, 02, 02b, 02c, 02d,
02f), the epistemic LLM classifier (04b), and all R scripts (03 text cleaning,
07c–07g networks, 08 metrics, 09 export, parallel_safe util).

## What was done
- Read every remaining script in full.
- Installed R base in the sandbox to run `parse()` on all 9 R scripts (syntax
  validation without needing arrow/igraph/cld3).
- Verified the cld3 API against ropensci's official docs before changing the
  language-detection code (avoided guessing function signatures).
- Applied 8 fixes (2 CRITICAL, 4 MAJOR, 1 MINOR, +1 doc); re-ran Python tests.

## Result / observations
Two execution-breaking defects:
- **09 (R)** had an un-commented "Dependencies appendix" of free prose + shell
  commands after the CLI block. In R this is invalid syntax — the whole script
  fails. Confirmed empirically: `parse()` of the v4 file returns FAILURE, the
  v5 file returns OK.
- **03 (R)** used `detect_language_mixed()` for per-document language detection.
  That function is NOT vectorized: it concatenates the whole vector into one
  text and returns the top `size` (3) languages of the *set*. Assigning that
  1–3-row result back to N documents recycles values and corrupts detection.
  Replaced with the vectorized `detect_language()`.

Robustness/repro fixes: `07e_07f` used `%||%` (rlang, not loaded) — breaks under
Rscript; `02b`/`02c`/`04b` overwrote their single corpus/output without atomic
writes; `04b` repeated 04a's checkpoint-cadence bug on resume. Minor: `02b`'s
"errata" regex contained Cyrillic а/т and never matched.

Scripts audited and left unchanged (correct): 01a, 02d, 02f, 07c, 07d, 07g, 08,
parallel_safe.R, logging_setup.py.

Validation: Python py_compile 21/21 and both test suites pass (no regression);
R parse 9/9 OK on v5.

## Decisions
- For 03's language confidence, set 1.0 for successful detections and NA for
  unreliable ones (cld3 returns NA when unreliable) rather than fabricating a
  probability, since the vectorized `detect_language()` exposes none.
- Left `01a`'s `IDIOMAS` filter deliberately inert (documented), because 02
  intentionally keeps articles with no declared language for detection in 03.
  Changing it would alter sampling — flagged as a decision for Fernando.

## Next steps (open decisions for Fernando)
- 01a language-filter intent (inert vs. applied).
- eigen_centrality on disconnected graphs (07d/07e_07f): compute per component?
- `construir_coupling` no-op filter (07e_07f): clarify intended filter.
- Co-occurrence network weight in 08: `n_co_artigos` vs `npmi`.
- Whether to standardize all scripts onto `logging_setup.setup_logging`.

## Files
- `RELATORIO_AUDITORIA_v5.md` — full findings (both rounds).
- `CHANGELOG.md` — v5 second-round entry.
- `pipeline_v5.zip` — corrected pipeline.
