# Corpus Size and Cluster Allocation Design for Pilot Annotation

**Date:** 2026-05-31
**Project:** Cientometria 2.0 (FAPESP 2023/13163-7)
**Session type:** Methodological decision

---

## Context

The project requires a raw corpus (corpus.csv) extracted via the OpenAlex API, covering the Digital Governance field from 1984 (founding of *Government Information Quarterly*) to the present. The corpus must support a 200-article pilot annotation sample structured as follows:

- **150 articles** drawn by proportional random sampling across 5 disciplinary clusters (SI, PA, BCS, STS, PS), to estimate the real-field prevalence of epistemological stances.
- **50 articles** oversampled exclusively from the Law cluster, to enable robust textual validation of the Doutrinário-Normativa (DN) posture, which is rare in the broader corpus.

The corpus size and per-cluster allocation needed to be determined before initiating the API pull.

---

## Decision

**Total corpus size: N = 6,000 articles.**

| Cluster | Historical Weight (est.) | N to Extract | N in Pilot |
|---|---|---|---|
| SI | 32% | 1,920 | 51 |
| PA | 27% | 1,620 | 43 |
| BCS | 17% | 1,020 | 27 |
| STS | 10% | 600 | 16 |
| PS | 8% | 480 | 13 |
| Law | 6% | 360 | 50 * |
| **Total** | **100%** | **6,000** | **200** |

\* Law articles are oversampled exclusively; they do not enter the proportional draw of 150.

---

## Rationale

### Historical weights
Estimated from domain knowledge of the Digital Governance / e-government literature. SI and PA dominate historically (combined ~59%), grounded in the GIQ tradition and the NPM-era convergence with public administration. BCS reflects the TAM/UTAUT wave accelerated post-2010. STS, PS, and Law are niche clusters with lower absolute volume and more specialized anchor journals.

These are **estimates, not empirically derived counts**. A validation extraction of 200–500 articles per cluster in OpenAlex is required before the full pull.

### Total corpus size (N = 6,000)
- **Statistical floor:** corpus-to-pilot ratio = 30:1. The smallest non-Law cluster (PS, N = 480) yields a 37:1 buffer before any abstract-density filter, preserving random sampling quality.
- **Processing ceiling:** a 6,000-row CSV with abstracts (~250 words average) occupies approximately 9–10 MB — well within notebook-friendly limits for pandas, BERTimbau embedding batches, and BERTopic inference.
- **Cost-benefit optimum:** below 3,000, minority clusters (Law, PS, STS) become fragile to quality filters; above 8,000, marginal statistical gain does not justify increased LLM pre-pass and embedding costs.

### Law cluster guarantee
With 360 articles extracted (6% natural proportion) and a conservative 60% dense-abstract rate, the effective Law pool before oversampling draw is approximately 216 articles — a safety factor of **4.3×** over the 50 required. Even at a pessimistic 50% density, the factor remains 3.6×.

---

## Flags and Caveats

1. **Epistemic status of weights:** proportions are domain-knowledge priors, not OpenAlex-derived counts. They should be validated and recalibrated if any cluster deviates by more than ±5 percentage points.
2. **OpenAlex coverage of Law:** legal journals may have uneven indexing. Recommended mitigation: dual-strategy query combining concept tags (*digital governance*, *data protection*, *AI regulation*, *e-government law*) with an explicit ISSN list of Law anchor journals. A Law-specific pilot pull should be run before the full corpus extraction.
3. **BCS temporal skew:** BCS articles are sparse before 2000 and dense post-2010. If the 1984–2000 window is included without adjustment, BCS may be underrepresented relative to its contemporary weight. This does not affect the design but should be noted in methodological reporting.

---

## Next Steps

- [ ] Run a pilot OpenAlex extraction of 200–500 articles per cluster to validate historical weight estimates.
- [ ] Build Law cluster query with dual strategy (concepts + ISSN list); run Law pull first as a feasibility check.
- [ ] Recalibrate cluster allocations if any empirical proportion deviates > ±5 p.p. from estimates.
- [ ] Document final OpenAlex query strings and filter parameters as a separate Lab Notebook entry before initiating the full pull.
