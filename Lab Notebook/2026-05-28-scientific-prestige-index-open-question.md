# Scientific Prestige Index (IPE/IPC) — Open Question

**Date:** 2026-05-28  
**Phase:** T2 — Analytical Design  
**Category:** Methodology / Composite Indicators  
**Status:** ⚠️ Under analysis — not adopted, not rejected

---

## Context

An external proposal for a composite Scientific Prestige Index (IPE) was reviewed. The index combines citation counts, journal impact factor, and network centrality (PageRank) into a single score, with weights calibrated by PCA.

## Problems Identified

**1. Normalization by global μ_Año**  
The proposed formula normalizes citation counts against the global annual mean. This ignores the structural heterogeneity between PA and IS subfields, which have radically different citation distributions. Standard practice: normalization by **field × year** (cf. SNIP — Moed 2010; FWCI — Elsevier).

**2. PCA for weight calibration (ω₁, ω₂)**  
Using the first principal component to derive weights is methodologically invalid for composite indicators. PCA returns the direction of maximum variance, not a normatively justified weighting scheme. This is a known problem in the composite indicators literature — see: OECD/JRC *Handbook on Constructing Composite Indicators* (2008); Saisana & Tarantola.

**3. PageRank weighted by disciplinary tradition — underspecified**  
The proposal mentions tradition-weighted PageRank but does not specify the mechanism: Does tradition enter as an edge weight multiplier? As a teleportation vector personalization? Without this, the formula cannot be implemented or reproduced.

## Status

The index is not rejected — the core intuition (prestige as a multi-dimensional network property) is sound. But the formula as proposed cannot be adopted without addressing the three issues above.

## Pending

- [ ] Reformulate normalization using field×year logic
- [ ] Replace PCA weighting with an explicit, theoretically justified weighting scheme (equal weights as a transparent baseline, or expert elicitation)
- [ ] Specify the mechanism by which disciplinary tradition enters the PageRank computation
- [ ] Consult OECD/JRC Handbook (2008) as the normative reference for the revised specification
