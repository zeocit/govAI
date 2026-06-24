# 2026-06-23 — Epistemological orientation reframed as two axes; deterministic prominence from flags

## Context
The epistemological-orientation layer (ternary multi-label EE/IC/DN) carried three
incompatible rules for deriving the single prominence label (fixed priority,
DN-dominates, argmax over LLM scores), producing different statistical objects.
The construct also conflated planes: positivist/interpretive are empirical
epistemologies; doctrinal-normative is a register. H4 had been specified on the
collapsed label rather than on the DN flag.

## Decisions
- Construct renamed: "postura epistemologica" -> "orientacao epistemologica".
- Two orthogonal axes:
  - Axis 1 (empirical epistemology): epi_positivista (EE), epi_interpretativa (IC).
  - Axis 2 (doctrinal-normative register): epi_doutrinario_normativa (DN).
- orientacao_proeminente (renamed from postura_proeminente) = label of axis 1 only,
  f(EE, IC), values {positivista, interpretativa, misto, nenhuma}. No priority rule,
  no continuous scores. DN never enters it. (Option "a".)
- Second layer "orientacao doutrinario-normativa" = the DN flag, read independently;
  applies on top of any axis-1 orientation. (1,0,1) = positivista + DN, not collapsed.
- inconclusiva = derived flag, set iff all three markers are 0.
- H4 dependent variable = the binary DN flag (not the collapsed label).
- DN sub-distinction (diagnostic): when DN=1, annotator records dn:modo / dn:norm /
  dn:ambos in notas (doctrinal mode vs normative orientation). Feeds the calibration
  disagreement analysis that will decide whether to split DN into two markers.
- confianca = human ordinal 1-3 (integer), distinct from LLM prepass confidence
  (separate continuous column conf_llm). notas mandatory when confianca=1 (naming the
  uncertain marker) and when DN=1 (dn: tag).
- Orthogonality test (cluster x epi) now run as two tests, one per axis.

## Artifacts
- Annotation guide rewritten: 4_3_Orientacoes_Epistemologicas___Guia_de_Anotacao___V_3.docx
  (supersedes the binary 4_3 V1 and the ternary 3_Guia_Anotacao_Posturas_v4; retire both).
- Canonical derivation utility: utils/derive_orientacao.py
  (single source of truth; replaces the three divergent rules; truth-table self-test
  passes 8/8; ships annotation QA validar_linha()).

## Rationale (selected)
- Two axes dissolve the "which dominates" choice for any cell with empirical content.
- Deriving prominence from flags (not LLM scores) keeps the descriptive label coherent
  with the canonical Gold Standard and avoids importing LLM miscalibration.
- Construct defined before reliability, not the reverse; the DN split is decided from
  disagreement analysis, treated as construct validity rather than circularity.

## Next steps
- OSF Addendum 2 (rename, two axes, H4 on DN flag, possible DN split); needs Profa.
  Cunha sign-off (Addendum 1 signed off verbally 2026-06-23).
- Codebook v3.0 bump: DA-08/DA-09 two axes, deterministic recode, rename, DN
  sub-distinction, confianca semantics.
- Propagate canonical field names (epi_ee/epi_ic/epi_dn -> full names) across scripts/docs.
- Wire derive_orientacao.py into 04b / 07; R export (09) consumes its columns, no re-derive.
- Open: alpha_DN gate value (0.40) still undocumented; dn:ambos catch-all risk to monitor;
  umbrella-name looseness accepted (orientacao epistemologica houses a non-epistemological axis).
- Separate pending step: Law stratum contamination remediation.
