# 2026-06-29 — OSF Addendum 2: two-axis design, calibration floor raise, DN disjunctive rule

## Context

Pre-registration v2.0 and Addendum 1 are signed. Five pre-annotation deviations accumulated since Addendum 1 require formal registration before calibration begins. Addendum 2 drafted and submitted for Profa. Cunha sign-off.

## Deviations registered

**Deviation 4 — Two-axis orthogonal design (postura_proeminente retired).**
Single-axis summary `postura_proeminente` replaced by two orthogonal axes:
- Axis 1 `orientacao_proeminente`: derived from EE and IC flags only; values {positivista, interpretativa, mixed, nenhuma}. DN never enters Axis 1.
- Axis 2 `epi_doutrinario_normativa`: independent binary flag.
- `inconclusiva` = 1 iff EE=IC=DN=0 (distinct from `nenhuma`, which holds whenever EE=IC=0 including DN-only cases).
Derivation: `utils/derive_orientacao.py` (pipeline_v7), single source of truth, 8/8 truth-table self-test.

**Deviation 5 — Calibration viability floor raised; floor/gate inversion registered.**
`ALPHA_CALIB_DN_FLOOR`: 0.40 (Addendum 1) → 0.667.
Deliberate inversion: `ALPHA_CALIB_DN_FLOOR (0.667) > ALPHA_GATE_EPI (0.55)`.
Rationale: 0.667 is Krippendorff's threshold for tentative conclusions; strict calibration floor concentrates QC at the inexpensive pre-annotation stage.

**Deviation 6 — DN disjunctive rule (OR logic).**
DN=1 if `dn:modo` (doctrinal register) OR `dn:norm` (normative-prescriptive orientation). Conjunctive rule rejected.
Diagnostic subcodes `dn:modo`, `dn:norm`, `dn:ambos` in `notas` field.
Grounded in: Sartori (1970), Goertz (2006), Hutchinson & Duncan (2012), Gregor & Hevner (2013).

**Deviation 7 — Confidence scale 1–3 (level 0 eliminated).**
`confianca` ∈ {1, 2, 3}. Level 0 eliminated; minimum valid code = 1. Enforced in `utils/derive_orientacao.py` (validar_linha()).

**Deviation 8 — H4 reformulation.**
- Component 4a (confirmatory): Cramér's V on 6×4 table (cluster × orientacao_proeminente). Threshold V < 0.30 unchanged.
- Component 4b (exploratory): Fisher exact test on 2×2 table (disciplina_juridica × epi_doutrinario_normativa_pred). IV = `disciplina_juridica` whitelist (75 articles, 59 verified venues), not `cluster_origem=='Law'` (contaminated: ~358/360 articles were STEM mislabels).

## Artifacts
- `OSF_Addendum_2.docx` — submitted for Profa. Cunha sign-off.

## Next
- Profa. Cunha sign-off → deposit on OSF → begin calibration (Vittorio, 20–30 articles, `anotacao_calibracao.csv`).
- After calibration: confirm `ALPHA_CALIB_DN_FLOOR` and `POS_WEIGHT_CAP` empirically.
