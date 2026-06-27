# 2026-05-31 — Centralize agreement thresholds (α gate = 0.667, κ ref = 0.61)

## Context
Round 3 surfaced three conflicting sets of inter-annotator thresholds across the
project (0.67/0.55 in code, 0.50/0.40 in the schema, 0.50 in the pilot),
allowing silent post-hoc drift. After reviewing the Krippendorff and Landis &
Koch literature, Fernando decided the canonical values and asked to implement
them.

## What was done
- New utils/thresholds.py as the single source of truth:
  - ALPHA_GATE = 0.667 — Krippendorff's alpha, the canonical acceptance gate
    (DA-06). 0.667 is Krippendorff's floor for tentative conclusions.
  - KAPPA_REF = 0.61 — Fleiss' kappa as a DIAGNOSTIC reference only (Landis &
    Koch "substantial" floor). Not a gate: kappa suffers the prevalence paradox,
    which is why Gwet AC1 is reported alongside.
  - faixa_krippendorff(): classifies alpha into reliable / tentative /
    insufficient.
- 05_processar_anotacoes.py now imports these constants; the acceptance gate is
  alpha-only (cluster and epi use the same standard); kappa moved to a separate
  kappa_diagnostico block; the report adds the Krippendorff band per dimension
  and a prevalence-paradox flag (AC1−κ>0.15) with a log warning. status_gate now
  serializes native JSON booleans. All loose literals removed.
- New tests/test_thresholds_centralizados.py locks the centralization (canonical
  values, no loose literals in 05, gate keyed on alpha only).

## Result / observations
On the synthetic e2e corpus the gate now reads cleanly: α≈0.62 → "insuficiente"
→ gate False, with kappa reported separately as diagnostic. Values reflect
synthetic noise, not code behavior. 25/25 compile; 5 test suites green.

Rationale (cite primary sources, not secondary): Krippendorff (2004),
Reliability in Content Analysis, HCR 30(3):411-433, p.241; Krippendorff (2013),
Content Analysis 3rd ed., ch.12. Landis & Koch (1977), Biometrics 33(1):159-174.
Krippendorff bands: ≥0.800 reliable; 0.667-0.800 tentative; <0.667 insufficient.
Note: the 0.667-0.800 band is "tentative conclusions" in Krippendorff's own
terms — do not relabel it "substantial" (that is Landis-Koch kappa vocabulary).

## Decisions / open item for Fernando
The epistemic layer uses the SAME gate (0.667), not a lower one — if pos/interp
agreement falls short, that is genuine information (revise the codebook and
re-annotate), not grounds to relax the gate.

ACTION REQUIRED: 0.667 > the 0.50 the pilot pre-registers. Raising the gate is an
AMENDMENT to the OSF pre-registration — date it, justify it from the literature,
and clear it with Profa. Cunha BEFORE collecting annotations. Ex ante it is
clean; post-hoc it becomes a researcher degree of freedom.

## Files
- codigo/python/utils/thresholds.py (new)
- codigo/python/05_processar_anotacoes.py (gate refactor)
- tests/test_thresholds_centralizados.py (new)
