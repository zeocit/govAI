# 2026-06-23 — postura_proeminente: DN co-activation rule, three-way inconsistency, conceptual grounding

## Context
Open question on how to resolve epi-flag co-activations involving `epi_doutrinario_normativa` (DN) when collapsing the ternary multi-label typology (`epi_positivista`, `epi_interpretativa`, `epi_doutrinario_normativa`) into the single field `postura_proeminente`. `mixed` is already canonically fixed as (pos=1, int=1, DN=0) and is already committed (see 5dcf557). The unresolved item is the DN co-activation rule, which feeds the dependent variable of H4.

## What was done
- Verified the remote state of `zeocit/govAI` with a fresh token. Remote is current through 2026-06-15; no orphaned local commits from prior sessions. The "GitHub blocked / pending pushes" note carried in the session COMPACT is stale: the ternary migration, the Law-stratum contamination audit, the Addendum 1 commit, and `mixed = pos+int` are all already on `origin/main`.
- Audited the derivation logic actually present in the repo and compared it against the session-state notes. Found three mutually inconsistent rules live across artifacts:
  1. COMPACT session state: priority positivista > interpretativa > DN (DN wins only as the sole flag).
  2. Project memory of migrated scripts 04b/07 (not in repo; Drive only): DN-dominates, including (1,1,1).
  3. Repo `pilot/llm_prepass.py`: `postura_proeminente_llm` = argmax of the three continuous scores; `mixed` if score_pos >= 0.5 AND score_int >= 0.5; exact tie resolves to positivista.
  These three disagree on every flag pattern containing DN plus at least one other flag.
- Targeted literature check on the epistemic status of doctrinal-normative scholarship, to test whether external warrant exists for treating DN as a dominating third axis. Verified sources: Smits (2017, "What is Legal Doctrine?") characterises doctrinal scholarship as serving description, prescription and justification jointly, not as purely normative. Bódig (2021) and the argument in "Doctrinal Legal Science: A Science of Its Own?" position doctrinal work as methodological interpretivism / ontological hermeneutics, i.e. a species of the interpretive tradition rather than orthogonal to it. Van Hoecke (ed., 2011) documents that the field openly debates whether legal scholarship is descriptive, hermeneutical, normative or explanatory.

## Result / observation
- No literature consensus adjudicates the collapse rule; this is an operationalisation decision internal to the instrument. The relevant literature in fact destabilises the premise that DN is a clean third axis: under the interpretivist reading of doctrine, int+DN overlap heavily, so the only genuinely contested cell is pos+DN.
- The choice interacts with measurement reliability. DN-dominates maximises the DN cell of `postura_proeminente` and routes DN's coding error (calibration gate alpha >= 0.40, the lowest of the three flags) maximally into H4's Cramer's V. Priority-with-DN-last contains that error but systematically undercounts DN, biasing any DN association toward null.
- Stronger methodological point: collapsing the multi-label structure to a mono-label dependent variable for a hypothesis test discards information precisely in the cells that matter. If H4 concerns DN's association, it should be tested on the binary `epi_doutrinario_normativa` flag directly, not on the collapsed `postura_proeminente`. The collapse is appropriate for descriptive typology distribution, not for inference about a single dimension.

## Next steps
- Decide the construct definition of `postura_proeminente` (dominant empirical-epistemology axis vs primary intellectual-register axis). This determines the collapse rule.
- Recommendation (pending decision): use the binary flags for H4 inference; reserve `postura_proeminente` for descriptive distribution; for the descriptive collapse, do not adopt blanket DN-dominates. Whatever rule is chosen must be identical across the Codebook, the deterministic derivation in 04b/07, and the `llm_prepass` prompt, and stated as a construct decision with explicit rationale.
- Defer empirical confirmation of DN reliability to post-calibration alpha.
- Security: rotate the GitHub PAT used this session; any token that appeared in plaintext in working context should be treated as compromised and revoked.
