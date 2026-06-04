# 2026-06-03 — Ternary epistemological typology propagated across all project documents

## Context

Following the decision to treat the epistemological layer as ternary multi-label with
doutrinario_normativa as a positive, directly annotated flag (entry
2026-06-03_long-names-calibration-setup), the change had to be propagated from the pilot
code into the full documentation set. Several documents still described the prior scheme
(two binary flags positivista/interpretativa plus EPI_NA derived by exclusion) and the
two-output epi classifier. This entry records the document-level migration.

## What was done

### Documents fully migrated to the ternary positive scheme

- Manual Operacional v18 → v19: §0 typology, calibration rationale, annotation scheme,
  threshold (epi calibration floor alpha >= 0.40 on doutrinario_normativa), LLM pre-pass
  (added score_doutrinario_normativa), Label Studio interface (2 → 3 checkboxes),
  Transformer epi classifier (num_labels 2 → 3; label vector and metrics include the third
  dimension), inference (epi_na_pred derived → epi_doutrinario_normativa_pred direct),
  postura_dominante derivation (count-based: 2+ flags = mixed, 0 = inconclusivo), glossary.
- Protocolo de Anotação v9 → v10: removed (EE)/(IC) parentheticals; then migrated the full
  EPI_NA treatment — §1 table and rules, §1.2 overview, glossary, §2 decision tree, §3.3
  (retitled "Doutrinário-normativa — em detalhe"), §3.5 rules R1/R3, worked examples,
  §5.3/§5.4 decision trees, self-test answer keys. epi_status value 'na' removed
  (doutrinario_normativa = 1 is now "classificado"); 'incerto' reserved for the
  all-zero/inconclusive case.
- Codebook v2.2 → v2.3: DA-02 ternary; gold_standard and predictions schemas
  (epi_doutrinario_normativa direct flag; postura_dominante value set); LLM-score schema
  (added score_doutrinario_normativa; entropy over 3 dimensions).
- Guia de Anotação de Posturas v3 → v4: full structural rewrite (dual-key scheme dropped;
  three direct flags; examples and quiz updated).
- Fundamentação Transformer v7 → v8: "duas dimensões" → três; num_labels 2 → 3;
  epi_na_pred derived → epi_doutrinario_normativa_pred direct.
- Gabarito Plano de Experimentos v7 → v8: classifier 2 → 3 dimensions; metrics third F1.
- Checklist Semanal v5 → v6: epi layer described as ternary; changelog updated; stale
  cross-references (Manual v14, Protocolo v7) made version-agnostic.
- Mapa de Navegação v4 → v5: camada 2 description; DA-02 row.
- Clusters Disciplinares Mapeamento v2 → v3: single descriptive mention updated.
- Posturas Epistemológicas Mapeamento v1 → v2: theoretical argument INVERTED — the
  document had argued for EPI_NA as a derived residual (definition by exclusion), two
  sigmoid heads + symbolic derivation, and prohibited coexistences. Rewritten to argue the
  positive definition of doutrinario_normativa, three independent sigmoid heads with direct
  prediction, and admissible coexistences (positivista/interpretativa + doutrinario_normativa).
  The cost of the new design (lower prevalence of doutrinario_normativa, concentrated in Law;
  attention to positive-class sufficiency) is stated explicitly.

### Archived to legacy/

- 4_3 Posturas Epistemológicas — Guia de Anotação V1 → legacy/posturas_guia_anotacao_v1_SUPERSEDED.docx
  Superseded by Guia v4. Also referenced SciBERT as the deployed model and used the EE/IC/EPI_NA scheme.

### Modeling decision recorded

- The epi Transformer classifier migrates from 2 to 3 output dimensions (BCEWithLogitsLoss
  over [positivista, interpretativa, doutrinario_normativa]). Confirmed by F. Leite.
  Risk noted across documents: doutrinario_normativa is likely sparser and concentrated in
  the Law cluster; monitor per-class F1 and consider class weighting or targeted sampling.

## Observations / review findings

- SciBERT is a legitimate comparison baseline in the project (BERTimbau, SciBERT,
  XLM-RoBERTa are the three compared encoders; BERTimbau is the deployed winner). SciBERT
  references in the Manual, Fundamentação and Gabarito are correct and were left intact.
  A stray SciBERT reference in the Posturas Mapeamento (conceptual passage) was made
  model-agnostic.
- Threshold consistency verified across documents: calibration floor alpha >= 0.40
  (doutrinario_normativa); Gold Standard gates alpha >= 0.55 (epi) and alpha >= 0.67
  (cluster); inconclusive-rate alert at 15%.
- Open item flagged to F. Leite: postura_dominante collapses 2+ flags to "mixed", which
  groups positivista+doutrinario_normativa with empirical mixed-methods; this affects H4
  (cluster × stance association). Decision pending on whether "mixed" should be reserved
  for positivista+interpretativa only.
- Clean documents (no epi-scheme content): Clusters Guia V1, Cartão de Bolso, the two
  field-summary documents, References, the pilot Colab notebook, the timeline HTML.

## Next steps

1. F. Leite decision on postura_dominante "mixed" semantics (affects H4).
2. F. Leite decision on Codebook version label (v2.3 per compact vs v3.0 per the document's
   own SemVer rule, since a column semantics change occurred).
3. Profa. Cunha sign-off on OSF Addendum 1 before annotation begins.
