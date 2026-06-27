# 2026-05-31 — Round 2 audit: cross-script contracts & silent failures

## Context
Second QA pass on pipeline_v5, driven by a revised audit prompt. Round 1 fixed
per-file bugs; Round 2 targets the defects that survive single-file review:
data-contract mismatches between scripts, silent failures (wrong-but-plausible
output), and anything only provable by execution. Bilingual scope (Python + R).

## What was done
- Built the full data-contract table for the DAG: for every script, the columns
  it reads vs. writes, with the Gold Standard (05→06) contract checked in detail.
- Hunted silent failures: any step that can return empty/recycled/degenerate
  output and still "succeed".
- Installed R base and ran parse() on all 9 R scripts; ran the Python test
  suites; added a new contract test.

## Result / observations
The DAG contract is largely sound — the two historical mismatches (periodico_nome
in 05; tem_disputa in 06) were already fixed. The 04a→04c contract checks out:
confianca_cluster/gap_top1_top2/entropia_llm are DERIVED inside 04c, not read.

One genuine silent-failure of scientific consequence remained in 06b: if the
Gold Standard lacked the epi columns, the loader silently created
epi_positivista/epi_interpretativa = 0 for every row. That trains the epistemic
layer to predict "all negative" — a degenerate model with a plausible F1 but no
validity. Replaced with explicit schema validation (raise KeyError). Same
fragile pattern `gs.get("col", scalar)` in 06a/06b filters (returns the Series
if present, the scalar if not — a scalar bool in gs[mask] breaks obscurely)
replaced with direct access guarded by a required-columns check.

Added tests/test_contrato_gs_06.py: it extracts (via AST) the columns 05 writes
and asserts they cover what 06a/06b require, and that 06 keeps explicit schema
validation. Sanity-checked: simulating the old gs.get pattern makes the test
fail as intended.

Validation: Python py_compile 21/21; metrics 6/6; e2e PASS; contract test 4/4;
R parse 9/9. No regression.

## Decisions
- Treated 06b's epi-column gap as a BUG (degenerate labels) and fixed it.
- Treated the remaining items as scientific choices and did NOT change them:
  04c stratification fallback vs OSF pre-registration; eigen_centrality on
  disconnected graphs; construir_coupling no-op filter; co-occurrence edge
  weight (n_co_artigos vs npmi); 01a inert language filter. All under Open
  Questions for Fernando.

## Next steps
- Add analogous contract tests for 04a↔04c and 03↔04 once schemas stabilize.
- Resolve the five Open Questions (see RELATORIO_AUDITORIA_ROUND2.md).
- Optionally run the R half under a full R environment (arrow/igraph/cld3) to
  validate execution, not just parse.

## Files
- RELATORIO_AUDITORIA_ROUND2.md — validation log, contract table, findings.
- tests/test_contrato_gs_06.py — new cross-script contract test.
- pipeline_v5.zip — updated.
