# 2026-05-31 — Round 4 audit: environment, coverage, observability

## Context
Fourth QA pass on the pipeline (now v6). Round 4 targeted what the previous
three rounds explicitly did not cover: reproducible environments, error-path test
coverage, output schema validation, observability for long runs, cross-language
type safety, and static analysis.

## What was done

### F — Reproducible environment (CRITICAL for Open Science)
No dependency management file of any kind existed. Created: requirements.txt
(9 Python packages pinned), pyproject.toml (project metadata + ruff config),
INSTALL.md (full setup instructions for Python, R, system deps, env vars, data
directory structure, and compatibility notes).

### G — Error-path coverage
The existing five test suites covered only happy paths. Found one real bug in the
process: 05_processar_anotacoes.py raises `KeyError: 'id_artigo'` when the Label
Studio export is empty — exposed by writing the test before the fix. Added
_gravar_gs_vazio() as early return and wrote test_error_paths_round4.py (10 tests
covering: malformed/empty/schema-incomplete LLM responses; corrupted checkpoint;
empty/single-annotator LS export; output_validator edge cases).

### H — Output schema validation
Zero scripts validated what they wrote. Created utils/output_validator.py
(lightweight, no new dependencies): checks required columns, all-NaN columns,
row-count plausibility, and probability columns summing to ≈1.0. Applied in 04a.

### I — Observability for long executions
04a had no pre-run estimate or post-run summary. Added: token/time estimate
before the first paid API call (with explicit caveat to check current pricing);
ETA updated at every checkpoint; end-of-run summary (wall time, fallback rate,
cluster distribution, frontier count).

### J — Cross-language type safety
Created test_type_roundtrip.py (5 tests + 1 conditional R test): verifies that
Int8 nullable, bool nullable, float NaN, string/None, and probability sums
survive the pandas→parquet→pandas round-trip. R test skips if arrow is absent.
All five Python tests pass; R test skipped (arrow not installed in sandbox).

### K — Static analysis
Installed ruff 0.15.15 and ran on all Python scripts. Found 17 issues: 11
auto-fixed (unused imports: pyarrow, numpy, math, classification_report, irrCAC
functions; unused variable n_before; redefined numpy; missing newline). 6
remaining: 2 are genuine false positives (fleiss_kappa/krippendorff accessed via
NamedTuple attributes, not direct calls); 4 are intentional E702 (double
assignments aligned to mirror the scalar if/elif in derivar_postura_vetorizado).
Config fixed in pyproject.toml.

## Result / observations
29/29 Python compile; 8/8 R parse; 7 test suites green (35 passed, 1 skipped).
The most important finding was the empty-export bug in 05 (G-1): it would have
crashed silently in a realistic scenario where a Label Studio export was
mistakenly empty, producing no Gold Standard with no useful error message.

## Meta-analysis (4 rounds, patterns)
1. Silent failure: every round's worst bug returned plausible-but-wrong results.
   Rule: every alternative input path must have an explicit test.
2. Atomic write inconsistency: 3 scripts caught in rounds 1-2. Rule candidate for
   linting: any write that overwrites its own input or follows a paid operation
   must use .tmp → rename.
3. Implicit contracts: most bugs were interface bugs between scripts. The GS↔06
   contract test formalizes this; candidates to extend: 04a↔04c, 03↔04.
4. Documentation as afterthought: README/INSTALL/CHANGELOG built retroactively.
   Rule for Open Science: new scripts must have corresponding INSTALL.md and
   CHANGELOG.md entries in the same commit.

## Not covered (by design)
Training (GPU/MPS required), real LLM calls (paid), full R execution (arrow/igraph
absent in sandbox), CI/CD (out of scope).

## Files
- requirements.txt, pyproject.toml, INSTALL.md (new)
- codigo/python/utils/output_validator.py (new)
- codigo/python/05_processar_anotacoes.py (_gravar_gs_vazio, early return)
- codigo/python/04a_classificar_clusters_llm.py (pre-run estimate, ETA, post-run)
- tests/test_error_paths_round4.py, test_type_roundtrip.py (new)
- RELATORIO_AUDITORIA_ROUND4.md
