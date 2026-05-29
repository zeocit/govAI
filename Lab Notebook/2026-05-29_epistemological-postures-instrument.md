# 2026-05-29 — Design of the Epistemological Postures Instrument (epi layer)

## Context

Consolidation of the analytical categories for the scientometric mapping project of the Digital Governance field. Alongside the **disciplinary clusters layer**, the project operates an independent **epistemological layer**. This entry documents the design of the comparative framework for the three postures (positivist, interpretive, EPI_NA), in symmetry with the clusters framework and the annotation manual previously developed (chat "Pós-doc. Manual + Reforma + Tradições/Clusters").

## What Was Done

Instrument structure decisions, based on a critical review of the columns inherited from the clusters framework:

- **Removed** the "Main Authors/Nature" column. Rationale: epistemological postures are not "owned" by field authors (any cluster can be positivist or interpretive); the column has low value for feature extraction.
- **Retained and renamed** the column to "Type of claim and inferential logic", **incorporating the nomothetic/idiographic axis** (Windelband) alongside the claim type (causal / comprehensive / normative). Mapping: positivist → nomothetic; interpretive → idiographic; EPI_NA → neither (universalist-principled pretension, not empirical).
- "Central Objects" **reframed** as "Construction of the object" (how the posture *constitutes* what is researchable).
- **Added mandatory sub-cell** "Structural/rhetorical markers" to the Typical Lexicon. Central adaptation for NLP: postures are discriminated by argumentative structure, not by topic.
- "Derivation Rules" make explicit the **multi-flag** nature of the epi layer: `epi_positivist` and `epi_interpretive` as independent binaries; mixed = both = 1; **EPI_NA = ¬positivist ∧ ¬interpretive** (derived, never directly annotated).

**Final structure (8 columns):** Posture · Type of claim and inferential logic · Construction of the object · Internal Tensions and Disputes · Typical Lexicon [Canonical frameworks / Technical vocabulary / Preferred methods / Empirical terms / Structural/rhetorical markers] · Fundamental Doxa · Overlaps and Points of Friction · Derivation Rules.

**Deliverable:** `posturas_epistemologicas.docx` (Avenir Next; code in Menlo; landscape; formatting symmetric to the clusters framework). Generated with docx-js; validated.

## Results / Observations

- **Epistemic-methodological difference recorded:** clusters are discriminated by substantive (topical) vocabulary; postures are discriminated by structural/rhetorical markers (hypothesis/N/statistics vs. deep case/*thick description* vs. absence of data + normative proposition). Implication for feature engineering: in the epi layer, prioritize structural and claim-type features over topical vocabulary.
- **Boundary case resolved:** a low-quality positivist paper (shallow descriptive survey) remains positivist — the criterion is the presence of systematized empirical evidence, not quality. EPI_NA requires the *absence* of data.
- **Escalation case:** programmatic/instrumental paper without testing → 'uncertain', not EPI_NA.
- **Meta-theoretical anchors cited (verifiable):** Heeks & Bailur (2007), Meijer & Bekkers (2015), Bannister & Connolly (2015); interpretive side — Klein & Myers (1999), Walsham (1995, 2006), Orlikowski, Weick, Sen; positivist side — Davis (1989, TAM), Venkatesh et al. (2003, UTAUT), Layne & Lee (2001), DeLone & McLean; EPI_NA — Floridi (philosophy of information). Unverified specific references were avoided; exemplary studies were characterized by type.

## Next Steps

- Validate the framework with the supervisor and calibrate with annotators in a **separate epi annotation session** from the clusters session, with ≥ 24h interval (rule R4 — layer independence).
- Derive dictionaries/lexicons from the sub-cells (vocabulary, empirical terms, structural markers) for co-occurrence analysis and classifier features.
- Test empirically (Quarter 4) whether a cluster "forces" a posture or whether the two axes vary independently — a result that constitutes, in itself, a methodological contribution of the project.
