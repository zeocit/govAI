# 2026-05-29 — Methodological Article: Epistemological Postures as an Orthogonal Classification Axis

## Context

Drafting the theoretical-methodological section of a methods paper (target: high-impact scientometrics venue) presenting the epistemological-postures classifier for the Digital Governance corpus. The article mirrors the companion Disciplinary Clusters framework in register and structure, and argues for the epistemological axis as a contribution in its own right.

## What Was Done

Produced `artigo_posturas.docx` (and Markdown source `artigo_posturas.md`): five sections plus an integrated comparative table. Pipeline: Markdown → pandoc → .docx, with a custom reference doc (Avenir Next) and post-processing to place the wide comparative table in a landscape section.

Article-level theses and methodological commitments recorded:

- **Orthogonality thesis (§1):** discipline and epistemological posture are, in principle, independent axes. Their association is to be measured, not assumed. Annotating them separately is the precondition for testing empirically whether a cluster "forces" a posture — itself a finding about the field's intellectual structure.
- **Defense of EPI_NA (§2.3):** the doctrinal-normative register is a legitimate, field-constitutive mode of knowledge production (esp. Law, normative democratic theory, applied ethics, philosophy of information), not a coding failure. Defined by **logical exclusion** (Positivista=0 ∧ Interpretativa=0) rather than a positive textual signature — chosen to avoid reifying a heterogeneous category, to make the annotation judgment asymmetric/robust (ascertain absence of empirical engagement), and to encode the field's empirical-first hierarchy. "Residual" = logical, not evaluative.
- **Doxa as demarcation criterion (§3):** the three postures differ on what authorizes a conclusion (measured/replicable datum vs. articulated situated meaning vs. principle/norm coherence). The epistemological doxa cross-cuts the disciplinary doxa, grounding orthogonality philosophically.
- **Friction heuristics (§4):** EE↔IC (qualitative method without hermeneutic intent), EE↔NA (weak empirical vs. doctrine; presence-of-evidence gate before claim-type gate; quality irrelevant to label), IC↔NA (empirically-anchored critique vs. pure normative critique); mixed = pos=1 ∧ interp=1; programmatic-instrumental → 'incerto'; pos+NA / interp+NA logically impossible → 'incerto'.

## Results / Observations — key architectural decisions (§5)

- **Two independent binary (sigmoid) classifiers** for epi_positivista and epi_interpretativa, NOT a 3-class softmax. Rationale: EPI_NA has no positive textual signature; a softmax would force the model to hallucinate a "normative prototype" and collapse heterogeneous doctrinal/ethical/philosophical texts.
- **EPI_NA as a deterministic hard constraint** (neuro-symbolic): EPI_NA = ¬positivista ∧ ¬interpretativa, derived by a symbolic rule, never predicted. Guarantees logical consistency, concentrates learning on the two well-separated empirical postures, and makes EPI_NA precision an interpretable function of the two heads' recall.
- **Construct validity / collinearity:** the epi classifier's discriminative signal is structural/rhetorical (hypotheses, N, statistics; thick description; normative propositions), NOT topical — unlike the cluster classifier, where topical vocabulary is the signal. The [CLS] representation must encode argument form, a more abstract signal; anticipated as the binding constraint on epi F1. Annotation in sessions separate from clusters to avoid leakage; epi inter-annotator target α ≥ 0.40 (vs. 0.50 for clusters), reflecting the more implicit nature of posture.

## Next Steps

- Internal review with supervisor; integrate into the full methods paper alongside the clusters section.
- Implement the two-head + symbolic-derivation design in the pipeline; align the LLM pre-classification prompt (04a) with the same criteria to keep human/LLM collinearity interpretable.
- Empirically test axis orthogonality (Quarter 4): cross-tabulate cluster × posture on the gold standard.
