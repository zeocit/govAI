# 2026-05-29 — Epistemological Typology: SOTA Coding Evidence + Decision Pilot Protocol

## Context

Evaluating whether to replace the current epistemological scheme (EE/IC as independent binary flags + DN derived by exclusion, `DN ⟺ pos=0 ∧ interp=0`, mixed allowed) with a ternary mutually-exclusive typology (EE / IC / DN). Verified the actual coding practices of the two canonical metatheoretical surveys and designed an evidence-first pilot.

## What Was Done

Read the primary sources (incl. the original Orlikowski & Baroudi working-paper PDF) and built a pre-registered pilot protocol (`protocolo_piloto_tipologia.docx`).

### Findings on the cited references (verifying a previously-flagged unknown)

- **Orlikowski & Baroudi (1991):** classified 155 *empirical* IS articles by underlying epistemology (positivist / interpretive / critical, following Chua 1986) — 96.8% positivist (descriptive empirical = 23.9% of that subtotal), 3.2% interpretive, 0% critical. **Each empirical paper coded into exactly one paradigm — no "mixed paradigm" code.** Research *design/method* analyzed as a separate axis. Critically, **conceptual/framework (non-empirical) papers were excluded from the analysis entirely** — there is no doctrinal-normative category; their third category is "critical."
- **Chen & Hirschheim (2004):** 1,893 articles, 1991–2001; positivism = 81% of *empirical* research. Same pattern: paradigm assigned within empirical work (mutually exclusive), method tracked separately, non-empirical set apart. (Exact label for a "mixed-methods" method code not confirmed.)

### Implications recorded

- The SOTA precedent supports mutual exclusivity **at the epistemology level, not the method level**. Our "misto" (EE=1 ∧ IC=1) is largely an artifact of operationalizing EE/IC by method/empirical markers rather than by dominant epistemology. Coding by dominant epistemology → misto rare; by method → misto common. This makes "misto prevalence" partly a definitional choice, to be measured under both criteria.
- **Neither study supports a normative third category.** Earlier "alignment with SOTA" claim for the ternary is only half-right: structure (mutual exclusivity) aligns; the normative third category does not — the canonical third is "critical," and normative work is excluded.

### Task 2 conclusion (which third category for Digital Governance)

- **Critical:** SOTA-canonical but wrong fit — critical DG work is mostly empirical/interpretive (already IC); standalone non-empirical critical is ~0%.
- **"Normative" alone:** under-specified (empirical papers carry normative conclusions); over-captures.
- **Doctrinal-normative (DN):** correct fit for the DG residue (Law-heavy field). Recommendation: DN by name and theoretical recognition, but operationally kept as the *derived residue* — which is exactly how O&B treat non-empirical work (exclusion, not co-equal paradigm). **Reinforces path 3-A** (rename + conceptual elevation; keep multi-label + derivation operationally).

### Pilot protocol (decision-first)

Dual annotation (≈150 representative + ≈50 DN-enriched) in two keys: Key A (current binaries, mixed allowed, DN derived) and Key B (single label EE/IC/DN + a "forcing" 1–3 field). Measures: (a) misto prevalence (Wilson CI) + forcing cost + sensitivity to coding criterion; (c) DN separability via three probes — human α for DN, unsupervised silhouette in BERTimbau embeddings, and a cross-validated probe comparing F1_DN under softmax (B1) vs. derivation (B2). Pre-registered decision thresholds: ternary pure if misto <~10% AND α_DN ≥ 0.50 AND F1_DN(softmax) ≥ F1_DN(derivation); primary+secondary (3-B) if misto ≥10% but DN cohesive; keep multi-label + derivation (3-A) if α_DN < 0.50 OR F1_DN(softmax) < F1_DN(derivation). Rename/elevation (EE/IC/DN) adopted regardless.

## Next Steps

- Run the pilot (≈2–3 weeks) before committing to any structural change; report the three metrics and apply §5 criteria.
- Decide the annotation coding criterion (epistemology-dominant vs. method) explicitly in the protocol — it drives misto prevalence.
- Discuss the SOTA finding and the 3-A default with the supervisor.
