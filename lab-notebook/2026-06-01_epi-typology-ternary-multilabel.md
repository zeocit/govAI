# 2026-06-01 — Epistemological typology switched to ternary multi-label with positive DN

## Context

The epistemological stance layer had two competing designs: the incumbent multi-label
binary scheme (positivist/interpretive flags with DN derived by logical exclusion) and a
mutually exclusive ternary EE/IC/DN. A formal decision pilot (~200 articles, dual-key
annotation, prevalence and separability probes) had been specified to choose between them.

During methodological discussion, the derivation of DN by exclusion was identified as
logically underdetermined: the complement of {EE ∪ IC} is not necessarily doctrinal-
normative (it may include pure conceptual work, critical theory, or formal modelling).
A third option — ternary **multi-label** with three positive, non-exclusive markers — was
evaluated and judged the most defensible on conceptual grounds, consistent with the
positively defined paradigm categories in Orlikowski & Baroudi (1991) and Chen &
Hirschheim (2004).

## Decision

Adopt the ternary multi-label typology (EE, IC, DN as independent positive binary flags;
any combination valid; DN annotated directly, never derived). Do **not** run the formal
decision pilot. Replace it with a smaller calibration session whose only purpose is to
verify, before full annotation, that DN is reliably identifiable as a positive class.

Threshold decision (pending sign-off, Profa. Cunha): calibration entry floor α_DN ≥ 0.40,
explicitly distinct from and below the Gold Standard acceptance gate (epi α ≥ 0.55, per OSF
v2 §6 and Codebook DA-06). all-zero rate ≳ 15% triggers reconsideration of the scheme.

Naming decision: rename pipeline columns epi_positivista → epi_ee, epi_interpretativa →
epi_ic, epi_na → epi_dn (the last changing from derived to directly annotated). One-time
rename for consistency with the EE/IC/DN vocabulary; epi_ee/epi_ic semantics unchanged.

## What was done

Updated or created the following artefacts (delivered as .docx via pandoc with Avenir Next;
sources in markdown):

- **Protocolo de Calibração da Camada Epistemológica v1** (new) — replaces the formal pilot;
  20–30 stratified articles, independent annotation, α per category, entry criterion.
- **Guia de Anotação de Posturas v4** (rewrite of v3) — single ternary multi-label scheme,
  positive DN, non-exclusive decision tree, six worked examples, updated Annex A.
- **OSF Addendum 1** (new, English) — filed under v2 §8 deviation policy; documents the
  operationalization change, the calibration procedure, and what stays unchanged.
- **Codebook v2.3** — DA-02 revised, DA-08 added, DA-06 clarified (calibration floor vs.
  acceptance gate), three epi schemas renamed, changelog.
- **Protocolo de Anotação v10** — global rename epi_positivista/epi_interpretativa →
  epi_ee/epi_ic; §0.1, §0.3, §1.2, §1.4, §3.0–§3.5, §5.3–§5.4, examples and self-test keys
  updated; EPI_NA/epi_status='na' removed in favour of positive epi_dn.
- **govai_calibracao_colab.ipynb** — pilot notebook repurposed for calibration; sample
  selection and α-per-category analysis made self-contained (pandas + krippendorff inline);
  typological-decision logic (B1/B2 probe, TF-IDF) removed; embeddings marked optional.
- **04b_prompt_update.md** — updated LLM prompt and output schema for three positive flags
  (score_ee/ic/dn), with pipeline find-replace notes. To be applied in the repo.

## Result / observation

- Discrepancy flagged and resolved in favour of the documents: the canonical epi acceptance
  gate is α ≥ 0.55 (OSF v2 §6; Codebook DA-06), not the 0.667 / 0.50 figures carried in the
  prior session summary. Documents are authoritative; the 0.667 figure applies to cluster
  (α ≥ 0.67), not epi.
- No confirmatory hypothesis (H1–H4) is added, removed, or rethresholded; only the stance
  variable operationalization and the pre-annotation validation procedure change.

## Next steps / pending

- Profa. Cunha sign-off on (a) the OSF addendum and (b) the α_DN ≥ 0.40 calibration floor,
  before any annotation begins.
- Apply the rename and three-head changes in the repo (04b, 06b, utils/thresholds.py,
  05_processar_anotacoes.py); verify krippendorff.alpha signature against the installed
  version; keep irrCAC (R) as canonical for the record.
- Run the calibration session (sample_calib.csv) and produce the calibration report.
- Confirm naming choice (epi_ee/ic/dn vs. keeping epi_positivista/epi_interpretativa).
- Archive the former pilot protocol (1_protocolo_piloto_tipologia) as a historical record.
