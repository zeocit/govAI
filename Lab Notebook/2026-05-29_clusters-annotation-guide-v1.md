# 2026-05-29 — Disciplinary Clusters Annotation Guide v1.0

## Context

Gold-standard construction for the SciBERT classifier (Digital Governance corpus), disciplinary-cluster layer. Human annotators need a procedural guide to label the disciplinary cluster of each article (SI, PS, STS, Law, PA, BCS) from abstract + metadata. Built as the sibling of the Epistemological Postures guide, reusing its exact template (structure, tone, visual identity), with content drawn from the clusters mapping article.

## What Was Done

Produced `guia_anotacao_clusters.docx` (Avenir Next; code in Menlo; portrait guide + landscape annex), reusing the postures-guide build infrastructure verbatim so formatting is identical (blue §-headings, ALERTA/REGRA DE OURO/NOTA callouts, blue-grey table headers, bullets, monospace verdicts). Sections: §0 about/independence-from-posture; §1 objective (cluster_primario obligatory + cluster_secundario optional; α ≥ 0.50 target); §2 Golden Rule of Clusters; §3 operational definitions of the six clusters by doxa; §4 cue tables (authors/frameworks + vocabulary/methods) + shared-vocabulary table; §5 tiebreaker manual (13-pair matrix + three editorial decisions); §6 primary/secondary labeling mechanics; §7 decision tree; §8 formal rules + cognitive hygiene; §9 worked examples; §10 self-test; Anexo A reproduces the full 7-column integrated clusters table.

Key procedural decisions recorded in the guide:

- **Golden Rule of Clusters:** inverse of the postures guide — "the discipline announces itself; epistemology hides." Classify by explicit markers (lexicon, frameworks, canonical authors), which lead to the doxa fundamental. But markers are means; the doxa (what each tradition maximizes) is the deep criterion. Shared surface vocabulary (transparency, smart city, accountability, open government) does not decide.
- **Doxa as what each cluster maximizes:** SI = engineering of integration; PS = democratic legitimacy; STS = understanding socio-technical co-constitution; Law = protection of fundamental rights; PA = state capacity; BCS = explanation/prediction of individual adoption.
- **Primary/secondary mechanics (§6):** cluster_primario always; cluster_secundario only for genuine hybridity (two doxas substantively active), never for internal tensions, shared topics, or annotator doubt. Worked hybrid example: data-protection paper combining doctrinal reading (Law) + institutional-capacity analysis (PA) → Law primary, PA secondary.
- **Tiebreaker manual (§5):** the article's 6×6 friction matrix (13 active pairs) converted into a practical "X if…, Y if…" desempate table, plus the three consolidated editorial decisions (smart cities → STS vs PA; algorithms → Law vs STS; open government → PS vs PA) as fixed-rule callouts.
- **Cognitive hygiene (§8, R-IND):** cluster annotated strictly independently of epistemological posture, in a separate session, without consulting the posture label — preserving project orthogonality.

## Results / Observations

- Document validated; portrait→landscape orientation switch confirmed; formatting byte-compatible with the postures guide (same template code).
- Internal title of the source mapping article remains "Governança Digital" (the uploaded filename "Democracia Digital" is a filename variant only); used "Governo/Governança Digital" consistently.

## Next Steps

- Calibration session with supervisor + annotators on §9/§10; track α (target ≥ 0.50); refine the matrix where divergence concentrates on specific pairs.
- Keep cluster and epi annotation sessions ≥24h apart (R-IND / R4) to preserve orthogonality for the Quarter-4 cross-tab test.
- Align the LLM pre-classification prompt (04a) with §5 tiebreaker rules and editorial decisions.
