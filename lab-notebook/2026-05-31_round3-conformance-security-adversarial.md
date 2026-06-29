# 2026-05-31 — Round 3 audit: conformance, security, adversarial input

## Context
Third QA pass on pipeline_v5. Rounds 1–2 covered per-file bugs and cross-script
contracts. Round 3 targets what those cannot reach: code↔protocol conformance,
empirical reproducibility, adversarial/degenerate input, and security — including
prompt injection into the LLM classifiers.

## What was done
- Front D (security): inspected how 04a/04b build the LLM prompt. Title+abstract
  (untrusted third-party text) were interpolated with no instruction/data
  separation — a prompt-injection vector. Added boundary markers
  (<<<ARTICLE_BEGIN/END>>>) plus an INPUT BOUNDARY instruction in the system
  prompt, and stripped forged closing markers from the text. Same in 04b.
- Front C (adversarial): found pd.qcut(duplicates="drop") in 04c returns an
  all-NaN column when citations have no variance (small/all-zero corpus),
  silently degrading the stratum key. Added collapse detection → single quartile
  + warning.
- Front A (conformance): protocolo/ in the zip only has lexico_clusters.csv, but
  the repo's pilot/config.py pre-registers ALPHA_DN_MIN=0.50 and
  MISTO_THRESHOLD=0.10. Cross-checked against 05's gates (α≥0.67 cluster, ≥0.55
  epi). Three different threshold sets coexist — reported as a divergence for
  Fernando, not changed.
- Added tests/test_adversarial_round3.py (qcut degeneracy + injection delimiting).
- Verified secrets: OPENROUTER_API_KEY comes from env with a clear error; no
  hardcoded keys.

## Result / observations
The injection fix changes SYSTEM_PROMPT and therefore PROMPT_VERSION
(04a: fb6fda56a4b8 → 0d27875c2fe0). This is traceability working as intended —
scores from old vs. new prompts are distinguishable — but it is a change to
scientific output and must be a conscious decision (re-run 04a/04b, or version
the prompt). Flagged under Open Questions.

Validation: py_compile 23/23; metrics 6/6; contract 4/4; adversarial 4/4; e2e
PASS. No regression.

## Decisions
- Treated prompt injection and qcut collapse as BUGS and fixed them.
- Treated the α-gate divergence (0.67 vs pre-registered 0.50) as a
  scientific/protocol choice — reported, not changed.
- Did NOT run fronts B (LLM/training reproducibility — paid calls/GPU) or full R
  execution (arrow/igraph/cld3 absent); instrumentation checked instead.
  Front E (Hypothesis property tests) proposed, not implemented.

## Next steps (for Fernando)
- Decide the α gate vs. OSF pre-registration (0.67/0.55 vs 0.50).
- Approve the prompt-injection mitigation (it bumps PROMPT_VERSION; implies
  re-running 04a/04b) or version it explicitly.
- Optionally: implement Hypothesis property tests; run the pipeline twice with a
  fixed seed and diff output hashes once a real environment is available.

## Files
- RELATORIO_AUDITORIA_ROUND3.md — validation log, conformance table, findings.
- tests/test_adversarial_round3.py — new.
- pipeline_v5.zip — updated.
