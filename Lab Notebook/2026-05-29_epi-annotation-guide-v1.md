# 2026-05-29 — Epistemological Postures Annotation Guide v1.0

## Context

Gold-standard construction phase for the SciBERT classifier (Digital Governance corpus). Human annotators need a procedural guide to label the **epistemological posture** of each article (positivist / interpretive / EPI_NA) from abstract and metadata. This guide is the sibling of the Disciplinary Clusters guide and operationalizes the epi instrument designed in the previous step.

## What Was Done

Produced `guia_anotacao_posturas.docx` (Avenir Next; code in Menlo; portrait guide + landscape annex). Structure: §0 about/relation to clusters guide; §1 objective and why annotation quality caps model performance; §2 the Golden Rule; §3 operational definitions; §4 abstract-cue heuristics; §5 decision tree; §6 edge cases and tiebreakers; §7 formal rules R1–R4; §8 practical procedure; §9 worked examples; §10 self-test; Anexo A reproduces the comparative table in full.

Key procedural decisions recorded in the guide:

- **Golden Rule:** classify by claim type and method, never by topic — because epistemological posture is implicit (unlike the discipline, which announces itself). The same topic admits all three postures.
- **Reading protocol:** read once, then re-read targeting the method zone and the conclusion/contribution zone; apply the single diagnostic question (causal / comprehensive / normative).
- **Abstract-cue heuristics** split into lexical vs. structural-and-method cues per posture, plus a "false friends" table (descriptive case study ≠ interpretive; lay "interpretation" ≠ interpretive; "critique" alone ≠ EPI_NA; qualitative content analysis on large N = positivist; shallow descriptive survey = still positivist).
- **5-gate decision tree:** Gate 1 (empirical evidence present?) → Gates 2/3 (positivist? / interpretive?, non-exclusive) → Gate 4 (EPI_NA derivation: pos=0 AND interp=0 AND no data AND doctrinal-normative AND prescriptive) → Gate 5 (R1 contradictions and genuine ambiguity → 'uncertain').
- **Tiebreaker order for poor/short abstracts:** metadata → diagnostic question → minimal empirical marker → 'uncertain'. Explicit instruction NOT to use the ~80–90% positivist base rate as a shortcut for indeterminate cases (would contaminate the agreement metric).
- **Worked examples** are composite illustrations explicitly flagged as non-citations (positivist, interpretive, EPI_NA, mixed, programmatic→'uncertain').

## Results / Observations

- The guide reinforces, at every gate, that EPI_NA is **derived** (never directly annotated); annotators set only the two binaries.
- Operational agreement target stated: Krippendorff α ≥ 0.40 for the epi layer; epi annotated in a session separate from clusters, ≥ 24h apart (R4).
- Document validated; orientation switch (portrait guide → landscape annex) confirmed in render.

## Next Steps

- Run calibration session(s) with the supervisor and annotators using §9/§10; measure α and revise tiebreakers if divergence concentrates on specific edge cases.
- Derive the candidate lexicons (lexical + structural cues from §4) into machine-readable dictionaries for co-occurrence features.
- Feed the same decision criteria into the LLM pre-classification prompt (script 04a) to keep human annotator and LLM auxiliary under one theoretical criterion.
