# govAI

**AI for Scientometric Analysis in Digital Governance**  
Post-doctoral research project · FGV EAESP · FAPESP

---

## Project

This repository documents the research project *Inteligência Artificial para a análise cientométrica do campo de Governança Digital: tradições disciplinares, agendas temáticas e hierarquia da produção científica*.

The project applies NLP/AI methods — supervised classification (BERTimbau), unsupervised topic modeling (BERTopic), and network analysis (SBM/ERGM) — to map disciplinary traditions and thematic hierarchies in the Digital Governance literature, framed within Bourdieusian field theory.

**Supervisor:** Profa. Dra. Maria Alexandra Viegas Cortez da Cunha (CEAPG / FGV EAESP)  
**International collaborator:** Profa. Gabriela Viale Pereira (Danube University Krems)  
**Funding:** FAPESP Post-Doctoral Fellowship

---

## Repository Structure

```
govAI/
├── lab-notebook/       # Scientific lab notebook — decisions, progress, open questions
├── pipeline/           # Data processing and classification pipeline (pipeline_v2)
├── codebook/           # Annotation codebook and inter-rater reliability protocols
├── corpus/             # Corpus construction scripts and metadata
├── models/             # BERTimbau fine-tuning and BERTopic configurations
├── analysis/           # Network analysis (SBM, ERGM), prestige index
└── docs/               # Project documents, FAPESP proposal, roadmap
```

---

## Lab Notebook

The lab notebook follows the protocol defined in the project's methodological manual (§10.1). Each entry covers a single decision, development, or open question.

**Convention:** `lab-notebook/YYYY-MM-DD-slug.md`

### Recent Entries

| Date | Entry | Status |
|------|-------|--------|
| 2026-05-28 | [Reading sessions reorganization](lab-notebook/2026-05-28-reading-sessions-reorganization.md) | ✅ Done |
| 2026-05-28 | [Pipeline v2 — code review & patches](lab-notebook/2026-05-28-pipeline-v2-code-review.md) | ⚠️ Patch pending |
| 2026-05-28 | [Institutional infrastructure of digital government](lab-notebook/2026-05-28-institutional-infrastructure-digital-gov.md) | ✅ Done |
| 2026-05-28 | [Disciplinary clusters — integrated framework](lab-notebook/2026-05-28-disciplinary-clusters-integrated-framework.md) | ✅ Done |
| 2026-05-28 | [Scientific prestige index — open question](lab-notebook/2026-05-28-scientific-prestige-index-open-question.md) | 🔍 Under analysis |

---

## Status

**Current phase:** T1 — Project setup, conceptual grounding, pipeline infrastructure  
**Fellowship start:** September 2026 (pending FAPESP approval)
