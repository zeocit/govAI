# 2026-06-29 — Confidence scale 1–3 and two-axis orientation reconciliation across operational docs

## Context
Two coupled decisions had to be propagated across the whole document/script set:
1. `confianca` (human annotator confidence) scale locked at **1–3** (1 = baixa, 2 = razoável, 3 = alta). The old `0 = nenhuma` level is dropped; the all-zero/uncertain annotation floors at 1.
2. The single-axis field `postura_proeminente` is retired in favour of the **two-axis** model (`orientacao_proeminente` + independent `epi_doutrinario_normativa` + `inconclusiva`), per the Addendum 2 design.

Goal: make both uniform across every document and script, leaving the signed OSF record untouched.

## What was done

### Confidence scale 1–3
- `utils/derive_orientacao.py` (`validar_linha`): validation range `(0,1,2,3)` → `(1,2,3)`; error message and docstring updated. The `c <= 1` / `c > 1` rules are unchanged (correct once 1 is the floor).
- Codebook: four fields (`confianca_cluster_a/b`, `confianca_epi_a/b`) `0 a 3` → `1 a 3`.
- Tutorial: §3.4 scale (dropped the `0 — nenhuma` bullet), fill instruction, and field table → 1–3.
- Manual: two references (`confiança (0 a 3)` → `(1 a 3)`).
- `05_processar_anotacoes.py` left unchanged: its `*_confianca` is the categorical LLM field (alta/media/baixa), a different variable.
- Guia de Anotação v4 and Calibration Protocol v2 were already 1–3.

### Two-axis migration (`postura_proeminente` → `orientacao_proeminente`)
- **Codebook v4.0** (full regeneration): three schemas migrated (`orientacao_proeminente_llm` in §2.4; `orientacao_proeminente` + `inconclusiva` + `dn_subtag` in §2.6 GS; `orientacao_proeminente` + `inconclusiva` in §2.8 predictions). Added **DA-08** (ternary multi-label typology) and **DA-09** (two-axis derivation), which were cited by the protocol and scripts but absent from the Codebook. Header note + changelog updated.
- **Fundamentação Transformer v9**: the one schema reference migrated.
- **Manual v22**: H4 cross-tab variable → `orientacao_proeminente`; the v19 "mixed" priority rule (positivista > interpretativa > doutrinario_normativa) rewritten to the two-axis logic (no priority); the R `case_when` rewritten (dropped the `~ 'doutrinario_normativa'` value line, `'inconclusivo'` → `'nenhuma'`, added a separate `inconclusiva` column); ~20 code/network-attribute references renamed; an Addendum 2 note added. Historical Addendum 1 notes (changelog v19/v20 and the §0.2 Addendum 1 paragraph) deliberately preserved with `postura_proeminente`, since that is what Addendum 1 introduced.
- **Protocolo de Anotação v11**: five references migrated (T4 colinearity gate, adjudication example, Appendix G mutual-information code); in the example, the old `na` vote (EPI_NA) → `nenhuma` and "Regra anti-NA" → "Regra anti-nenhuma"; restored the `$` lost in the Appendix G R block during extraction.

### Audit (uniformity check)
- All seven scripts (`04b`, `05`, `06b`, `07`, `derive_orientacao.py`, `llm_prepass.py`, `09_exportar_csv_consolidado.R`) were already uniformly two-axis: `orientacao_proeminente` {positivista, interpretativa, mixed, nenhuma} + `inconclusiva`, no `postura_proeminente` residual. The scripts are the reference the docs were aligned to.
- OSF Pre-registration v2.0 (`dominant_stance`) and Addendum 1 (`postura_proeminente`) were NOT edited: they are signed, and the change is the registered deviation in Addendum 2.

## Key points
- `orientacao_proeminente` is a function only of EE (`epi_positivista`) and IC (`epi_interpretativa`): positivista (1,0), interpretativa (0,1), mixed (1,1), nenhuma (0,0). `epi_doutrinario_normativa` never enters axis 1.
- `inconclusiva` = 1 iff all three flags are 0, and is distinct from `orientacao_proeminente = nenhuma`, which holds whenever EE=0 and IC=0 (including DN-only articles, 0,0,1).
- Manual H4 empirical component now crosses `cluster_primario × orientacao_proeminente` (6×4, V < 0,30); the doctrinal-normative/juridical H4 component remains deferred to Addendum 3.

## Next
- Push migrated scripts + these docs to `zeocit/govAI`.
- Manual and Protocolo structural rebuilds (three-flag decision trees, `dn:` worked examples) remain separate pending tasks.
- Addendum 2 still needs Profa. Cunha sign-off before annotation begins.
