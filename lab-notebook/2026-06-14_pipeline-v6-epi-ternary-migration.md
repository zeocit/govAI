# 2026-06-14 | pipeline_v6 audit and ternary epistemological migration

## Context

pipeline_v6 is the full production codebase hosted in Google Drive
(folder `govai/pipeline_v6/`, created 2026-06-02). It predates the ternary
epistemological migration completed in the git repository between 2026-06-03
and 2026-06-11. This entry records: (a) the full audit of which scripts were
outdated relative to the three-positive-flag scheme; (b) the threshold-regime
reconciliation; (c) the class-imbalance decision for the DN flag; and (d) the
migration of the five epi-layer scripts, producing pipeline_v7.

## What was done

### Diagnostic

Audited all pipeline_v6 scripts for dependence on the deprecated binary+derived
epi scheme (`epi_na` residual, `postura_dominante`, softmax scores summing to 1).

**Outdated — epi sub-pipeline, substantive rewrite required:**
- `utils/thresholds.py`: single `ALPHA_GATE = 0.667` for both layers; no
  separate epi gate, no DN calibration floor.
- `04b_classificar_epi_llm.py`: third category `epi_na` as softmax residual;
  three scores sum to 1.0; prompt frames DN as absence, not positive evidence;
  `epi_status_llm` with value `na`.
- `05_processar_anotacoes.py`: Label Studio template field `epi_na` (radio
  TRUE/FALSE); Krippendorff alpha computed only for `epi_positivista` and
  `epi_interpretativa` (no alpha for DN); gate uses single `ALPHA_GATE`; Gold
  Standard output columns `epi_positivista / epi_interpretativa / epi_na`.
- `06b_treinar_epi.py`: `EPI_CATS = ["positivista", "interpretativa"]`;
  `num_labels = 2`; docstring "EPI_NA e derivado"; `BCEWithLogitsLoss` without
  `pos_weight`; labels matrix of 2 columns only.
- `07_aplicar_modelo.py`: 2 epi output dims; `epi_na_pred` derived by exclusion
  (both `_pred == 0`); synthesis field named `postura_dominante` with values
  `misto` / `na`.

**Clean — cluster layer or pure network, unaffected:**
`07c_extrair_termos.R` (reads only `id` and `cluster_primario_pred`),
`07d_rede_coautoria.R`, `07e_07f_redes_citacao.R`, `07g_cooccurrencia_termos.R`,
`08_metricas_redes.R`, `08a_validade_convergente.R`, `utils/output_validator.py`
(generic, receives schema as parameters; no hardcoded epi column names).

**Lightly outdated — cosmetic only, no functional column access:**
`09_exportar_csv_consolidado.R`: Zenodo manifest description string names
`postura_dominante` and "Codebook v2.1"; script copies parquet to CSV wholesale
without accessing columns by name; does not break.

**Key finding — blast radius:** H4 (cluster x postura, Cramer's V) is not
implemented in any pipeline_v6 script. No R script reads epi columns from
`predicoes_corpus.parquet`. The `postura_dominante -> postura_proeminente`
rename therefore has no functional impact on existing R code. The migration
scope is contained in the five Python epi scripts listed above.

### Threshold regime reconciliation

Identified a conflict between the documents regime (OSF pre-registration
section 6, Codebook v3.0) and the pipeline_v6 `thresholds.py`, which had
consolidated three separate gate sets into a single `ALPHA_GATE = 0.667`
for both layers, on the grounds of aligning with OSF before data collection.

**Decision (Fernando Leite, 2026-06-14):** documents regime is authoritative.

Canonical gates:
- `ALPHA_GATE_CLUSTER = 0.67` — Krippendorff alpha, disciplinary layer
- `ALPHA_GATE_EPI = 0.55` — Krippendorff alpha, epistemological layer
- `ALPHA_CALIB_DN_FLOOR = 0.40` — viability floor for DN calibration phase
  (not a Gold Standard acceptance gate)
- `KAPPA_REF = 0.61` — Fleiss kappa, diagnostic reference only (prevalence
  paradox; Gwet AC1 reported alongside)

Methodological caveat recorded in `thresholds.py` docstring: the epi gate
(0.55) falls below Krippendorff's conventional "insufficient" band floor
(0.667). This is a pre-registered choice, not an error. `faixa_krippendorff()`
(descriptive) and the epi acceptance gate are kept distinct; both are reported
by `05_processar_anotacoes.py`.

The single `ALPHA_GATE` constant was deliberately removed from `thresholds.py`
to force per-layer selection on first import (raises `ImportError` in any
un-migrated consumer).

### Class-imbalance decision for the DN flag

DN (`doutrinario_normativa`) has low expected prevalence, concentrated in the
Law cluster. Three candidate mechanisms were evaluated for `06b_treinar_epi.py`:

1. Simple duplication of DN instances in the training fold.
2. `WeightedRandomSampler` (PyTorch) — equivalent to `pos_weight` but acting
   on batch composition rather than the gradient.
3. `pos_weight` in `BCEWithLogitsLoss`, computed per flag at runtime from
   `y_train` (`n_neg / n_pos`), clamped by `POS_WEIGHT_CAP`.

**Decision (Fernando Leite, 2026-06-14):** option 3 (`pos_weight` only).
Rationale: acts per-flag independently, no collateral distortion of the
positivista and interpretativa flags, no double-counting, compatible with
multiclass BCE. `POS_WEIGHT_CAP = 10.0` is provisional; to be confirmed after
calibration, when the observed prevalence of DN in the Gold Standard is known.

### Synthesis sub-decisions (postura_proeminente)

Three independent binary flags yield 8 combinations. The five-value synthesis
collapses them by the following rule (identical across 04b / 05 / 06b / 07):

- `doutrinario_normativa` if `epi_doutrinario_normativa = 1` (DN dominates,
  including the combination (1,1,1), to preserve the Law-DN signal for H4).
- `mixed` if `epi_positivista = 1` AND `epi_interpretativa = 1` AND
  `epi_doutrinario_normativa = 0`.
- `positivista` or `interpretativa` for the remaining single-flag cases.
- `inconclusivo` for (0, 0, 0).

The three raw flags are preserved in the parquet regardless.

Auxiliary metrics redefined for independent multilabel output:
- `incerteza_epi` (04b): mean binary entropy of the three scores.
- `is_fronteira_epi` (04b): any score within 0.15 of the 0.5 threshold.
- `epi_certeza` (07): `mean(2 * |prob - 0.5|)`, in [0, 1].

### Migration

Rewrote the five scripts to produce pipeline_v7:
- `utils/thresholds.py`: split gates, `POS_WEIGHT_CAP`, `faixa_krippendorff()`.
- `04b_classificar_epi_llm.py`: three independent scores (sigmoid, not softmax);
  `score_positivista / score_interpretativa / score_doutrinario_normativa`;
  `postura_proeminente_llm`; DN described as positive evidence in the prompt;
  `incerteza_epi` and `is_fronteira_epi`.
- `05_processar_anotacoes.py`: Label Studio template updated to three epi
  checkboxes (no `epi_na`); alpha computed for all three flags; per-layer
  gates; `postura_proeminente` in Gold Standard output.
- `06b_treinar_epi.py`: `num_labels = 3`; `WeightedTrainer` with
  `BCEWithLogitsLoss(pos_weight=...)`; `pos_weight` computed from `y_train`
  with clamp; `compute_metrics_epi` covers F1 and Brier per flag plus
  macro-F1, Hamming loss, and Jaccard.
- `07_aplicar_modelo.py`: 3 epi output dims (sigmoid); `postura_proeminente`
  (not `postura_dominante`); `epi_certeza` as decisiveness; DN-dominates rule
  applied last in vectorized synthesis.

Contract with `utils/metrics.py` verified: `metricas_completas(ratings_dict)`
returns `MetricasCompletas` NamedTuple with the fields consumed by `05`
(`krippendorff_alpha`, `fleiss_kappa`, `gwet_ac1`, `alpha_ci_lower/upper`).
`IRRCAC_VERSION` exported.

## Result / observation

Pipeline_v7 constitutes a coherent ternary epi sub-pipeline. Cluster-layer
scripts (07c–09) and infrastructure utils are unaffected. Two runtime
verification points flagged for first run:

1. `WeightedTrainer.compute_loss` signature sensitivity to `transformers`
   version drift (the `**kwargs` absorbs `num_items_in_batch` in recent
   versions; re-check if the library is upgraded in Colab).
2. Corpus metadata column names in `05` (`periodico_nome`, `periodico_source_id`):
   a defensive filter is in place (reads schema before merging; missing columns
   are silently skipped rather than raising an error). Confirm against the
   actual schema of `corpus_limpo_textual.parquet` on first run.

## Next steps

- Upload pipeline_v7 scripts to Google Drive under `govai/pipeline_v7/`.
- Update `04c_amostrar_para_label_studio.py` if it reads the old column names
  (`epi_*_llm`, `epi_status_llm`) from `escores_llm_epi.parquet`.
- Fix `09_exportar_csv_consolidado.R` manifest description string
  (`postura_proeminente`; three epi dims; current Codebook version).
- Confirm corpus metadata column names against `corpus_limpo_textual.parquet`.
- Confirm `POS_WEIGHT_CAP` and the DN calibration floor empirically after
  the calibration session.
- Recruit second annotator; run calibration with `anotacao_calibracao.csv`
  (25 articles, seed 42, stratified by `cluster_origem`).
