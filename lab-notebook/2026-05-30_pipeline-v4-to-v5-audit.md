# 2026-05-30 — Pipeline v4 → v5: correction audit

## Context
Full code-quality audit of `pipeline_v4` (13 Python scripts + 6 utils + 9 R
scripts + 2 tests) using a structured "senior research software reviewer"
prompt, executed with the most capable available model. Goal: find and fix
bugs and optimize before the gold-standard annotation phase produces real data
that flows through 04c → 05 → 06 → 07.

## What was done
- Extracted the pipeline; verified structure against project memory.
- Installed `irrCAC==0.4.4` and empirically verified the `CAC` API surface used
  by `utils/metrics.py` (`.krippendorff()["est"]["coefficient_value"]`,
  `confidence_interval`, `p_value`, `.ratings`; tolerance of None/NaN missings).
- Ran the v4 test suite as a baseline: metrics cross-validation passed (6/6),
  but the end-to-end test **failed** at two points.
- Read and audited the high-risk scripts in full (04a, 04c, 05, 06a, 06b, 07,
  08a.R) plus the utils.
- Created `pipeline_v5` and applied 11 fixes (3 CRITICAL, 4 MAJOR, 4 MINOR).
- Re-ran both test suites against v5.

## Result / observations
Two v4 defects were masked by the test harness itself:
- **05** requested a non-existent corpus column (`periodico_nome`); pyarrow
  aborts the whole read with `ArrowInvalid`. The v4 e2e test crashed here.
- **04c** stratified-sampling collapsed to **0 representatives** silently
  whenever the 5-dimension stratum key produced mostly singletons
  (`StratifiedShuffleSplit` requires ≥2 per stratum). The v4 test reported
  "passed" while returning an empty representative sample.

Reproducibility defect:
- **06a/06b** did not call `set_seed()` before model instantiation, so the
  random init of the classification head was uncontrolled by the 3 seeds —
  init noise was confounded with the seed effect across the 27-run design.

After fixes, the v5 end-to-end test passes (04c → 05), with the representative
sample rising from 7 to 57 tasks on the synthetic 100-article corpus. The
κ/α values (~0.62) reflect synthetic-data noise, not code behavior.

Modules audited and found correct (no change): `metrics.py`, `safe_io.py`,
`parquet_io.py`, `08a_validade_convergente.R`.

Empirical validation: `py_compile` 21/21; metrics cross-validation 6/6
(|Δα| < 0.005 preserved); end-to-end passes.

## Decisions
- `TrainingArguments` is now built via runtime signature inspection to tolerate
  both `eval_strategy` (transformers ≥ 4.46) and `evaluation_strategy`, plus the
  deprecation of `use_mps_device`/`no_cuda`. The exact transformers version on
  the M5 Max workstation was not verifiable in this session, hence the
  version-robust construction rather than a fixed rename.
- `07` consolidation was vectorized; the scalar `derivar_postura` decision tree
  was reproduced exactly in `derivar_postura_vetorizado`.

## Next steps
- **Open decision:** the new 04c stratification fallback (full → cluster×quartil
  → cluster) deviates from the pre-registered full-stratum design (OSF §3.4).
  For the ~21k real corpus it likely never triggers, but decide whether to (a)
  document the deviation in the pre-registration, or (b) adopt another strategy.
- Re-run the audit prompt on the phase-02 scripts (02, 02b–02f) and the R
  network scripts (07c–09), not fully audited this session.
- Confirm the transformers version on the workstation and, if pinned, simplify
  the TrainingArguments construction accordingly.

## Files
- `RELATORIO_AUDITORIA_v5.md` — full findings table.
- `CHANGELOG.md` — v5 entry.
- `pipeline_v5.zip` — corrected pipeline.
