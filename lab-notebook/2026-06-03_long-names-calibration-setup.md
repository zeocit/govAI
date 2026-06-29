# 2026-06-03 — Column renaming (EE/IC/DN → full Portuguese names) and calibration setup

## Context

The pilot directory was originally designed around a binary decision probe (run_analysis.py)
and used abbreviated column names (epi_ee, epi_ic, epi_dn; score_ee, score_ic, score_dn;
B_label values EE/IC/DN). The typological decision probe has been superseded by a
calibration-first approach: annotators first demonstrate sufficient inter-rater agreement
on the ternary multi-label scheme before proceeding to full Gold Standard annotation.

This entry records two simultaneous changes made in session 2026-06-03:
(a) abolition of EE/IC/DN abbreviations across the entire pilot directory;
(b) reconfiguration of config.py to reflect calibration thresholds rather than the old
    pilot decision thresholds.

## What was done

### 1. Column and value renaming (canonical, project-wide)

| Old name (abolished) | New canonical name |
|---|---|
| `epi_ee` | `epi_positivista` |
| `epi_ic` | `epi_interpretativa` |
| `epi_dn` | `epi_doutrinario_normativa` |
| `score_ee` | `score_positivista` |
| `score_ic` | `score_interpretativa` |
| `score_dn` | `score_doutrinario_normativa` |
| `postura_dominante_llm` values `EE/IC/DN` | `positivista/interpretativa/doutrinario_normativa/mixed` |
| `B_label` values `EE/IC/DN` | (column abolished — see §3) |

Motivation: abbreviated codes were opaque in outputs and inconsistent with the full
Portuguese nomenclature used in all written documents (codebook, annotation guides, OSF).
Full names are self-documenting and reduce annotation error risk.

### 2. config.py — threshold update

Removed: `MISTO_THRESHOLD`, `ALPHA_DN_MIN`, `PROBE_MARGIN` (tied to the old pilot probe logic).

Added:

| Constant | Value | Meaning |
|---|---|---|
| `CALIB_ALPHA_DN_FLOOR` | 0.40 | Minimum Krippendorff α for `epi_doutrinario_normativa` in the 25-article calibration sample. Below this → revise annotation guide. |
| `ALL_ZERO_RECONSIDER_RATE` | 0.15 | If > 15 % of articles receive (0,0,0) → reconsider category scheme. |
| `GS_ALPHA_GATE_EPI` | 0.55 | Krippendorff α gate for epistemological posture (Gold Standard phase). |
| `GS_ALPHA_GATE_CLUSTER` | 0.67 | Krippendorff α gate for disciplinary cluster (Gold Standard phase). |

The CALIB_ALPHA_DN_FLOOR of 0.40 represents a diagnostic floor, not a quality target.
It is lower than the OSF-registered Gold Standard gate (0.55) because calibration is
an exploratory inter-rater alignment exercise, not final quality certification.
Rationale: consistent with Krippendorff (2004) recommendation that α ≥ 0.667 is required
for reliable coding and α ≥ 0.40 is acceptable for tentative conclusions during
instrument development.

### 3. ANN_COLS schema — pilot dual-key abolished

The old pilot used a dual-key scheme (Key A: multi-label binary A_pos/A_int; Key B:
mutually exclusive B_label/B_forcing). This has been replaced by the ternary multi-label
scheme as the single annotation layer:

```python
ANN_COLS = [
    "doc_id", "subsample", "annotator",
    "epi_positivista", "epi_interpretativa", "epi_doutrinario_normativa",
]
```

Three independent binary flags; any combination valid; (0,0,0) = inconclusive
(does not imply doutrinario_normativa by residual logic).

### 4. Scripts modified

- `pilot/config.py`: new thresholds and ANN_COLS (see §§2-3 above)
- `pilot/llm_prepass.py`: prompt and output columns renamed; POSTURA_VALORES updated
- `pilot/run_labels.py`: rewritten for calibration gate logic (α per posture, all-zero
  alert, gate verdict) — removed old Q-a/Q-c pilot probe logic
- `pilot/sample_selection.py`: defaults changed (n_prev=25, n_boost=0); output renamed
  to sample_calib.csv; subsample values changed to calibracao/calibracao_juridica;
  dn_filter replaced by juridica_col (maps to subpopulacao_juridica column)
- `pilot/README.md`: rewritten to document calibration phase

### 5. Files moved to legacy/

- `pilot/run_analysis.py` → `legacy/run_analysis.py`
  Reason: implements the B1/B2 typological decision probe (misto prevalence + separability),
  which is superseded by the calibration-first approach.
- `/mnt/project/1_protocolo_piloto_tipologia.docx` → `legacy/protocolo_piloto_tipologia_v1.docx`
  Reason: this document specified the old pilot decision logic; archived for traceability.

### 6. sample_calib.csv generated

Command:
```
python sample_selection.py corpus.csv --strata cluster_origem --n_prev 25 --n_boost 0 --seed 42
```

Result: 25 articles, stratified by cluster_origem:

| subsample | stratum | n |
|---|---|---|
| calibracao | BCS | 5 |
| calibracao | PA | 6 |
| calibracao | PS | 2 |
| calibracao | SI | 9 |
| calibracao | STS | 3 |

Note: LAW cluster not present because cluster_origem==Law maps to subpopulacao_juridica;
with n_boost=0, no juridica articles were sampled. The LAW subsample can be added in
future calibration rounds by passing --n_boost N.

## Observations

- All changes applied cleanly; no pipeline re-run required (scripts 04a/04b on the full
  corpus are unaffected — they are upstream of the annotation layer).
- The CALIB_ALPHA_DN_FLOOR=0.40 threshold exceeds the OSF v1 pre-registered value of 0.50
  for the Gold Standard gate — wait, no: 0.40 < 0.50. The 0.40 floor is for calibration
  only; the Gold Standard gate (GS_ALPHA_GATE_EPI=0.55) is the binding OSF threshold.
  No OSF amendment is required for the calibration floor, as it governs an instrument-
  development phase not covered by the original pre-registration.
- OSF amendment is still required for GS_ALPHA_GATE_CLUSTER=0.67 (up from 0.50 as
  pre-registered). Sign-off from Profa. Cunha pending.

## Next steps

1. Profa. Cunha sign-off on OSF amendment (ALPHA_GATE 0.50 → 0.67 for cluster)
2. Regenerate written documents (Codebook v2.3, Protocolo v10, Guia v4, OSF Addendum 1)
   with canonical long names replacing EE/IC/DN
3. Annotation begins ~T1/October 2026 with sample_calib.csv
