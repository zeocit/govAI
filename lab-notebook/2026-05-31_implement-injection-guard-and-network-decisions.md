# 2026-05-31 — Implement injection guard + network metric decisions

## Context
Fernando approved the three open Round-3 questions. Pipeline state: 04a/04b have
NOT run on the final corpus and annotation has not started, so all changes enter
with zero comparability cost.

Decisions:
1. Prompt injection → "flag + review before classifying".
2. eigen_centrality → PageRank (citation) + LCG-restricted (coauthorship).
3. Co-occurrence weight → NPMI>0 as production default, raw count kept as column.

## What was done
- utils/injection_guard.py (new): heuristic regex detector (PT+EN), no LLM.
  Catches "ignore previous instructions", forged role turns/markers,
  output-forcing ("set cluster_si to 1", "classify as X"), etc.
- 04a/04b: before any paid LLM call, suspicious abstracts are SEGREGATED (not
  classified) into injecao_para_revisao_{clusters,epi}.csv for human review.
  Second layer on top of the existing <<<ARTICLE_BEGIN/END>>> delimiting.
- 07d (coauthorship, undirected): eigen_centrality now computed only on the
  largest connected component (LCG), NA outside it — eigenvector is ill-defined
  on disconnected graphs.
- 07e_07f (co-citation + coupling): added per-node PageRank (page_rank()$vector,
  weight = shared citations). Robust to disconnection. Note: both nets are
  undirected here; there is no directed direct-citation network in the pipeline.
- 07g (co-occurrence): canonical edge weight is now weight = NPMI restricted to
  NPMI>0; raw n_co_artigos kept as a column for sensitivity analysis.
- 08: prefers the weight column (=NPMI for co-occurrence), falls back to
  npmi / n_co_artigos.

## Result / observations
The detector behaves well on a manual battery: catches four attack vectors,
passes benign academic abstracts including the trap "government acting as a
platform" (does not match a bare "act as"). Locked by a new test.

Verified the igraph API against the official docs (r.igraph.org) before using
it: page_rank(graph, ..., weights=NULL) returns a list whose $vector holds the
scores, and weights are interpreted as connection strengths — exactly the
intended semantics. Did not invent the signature.

Validation: R parse 9/9; Python 26/26 compile; 5 test suites green
(metrics, contract, adversarial+injection, thresholds, e2e).

## Decisions / rationale
- Co-occurrence: chose NPMI>0 as the production weight (normalizes for marginal
  frequency, unlike raw counts) but kept the raw count so the sensitivity
  analysis (Round-3 option C) remains possible at write-up without re-running.
- Citation centrality: PageRank rather than per-component eigenvector because
  it is well-defined under disconnection and is the standard citation-centrality
  measure.

## Next steps
- Run the injection detector over the 21k abstracts once collected to get a
  concrete count of segregated items before the first paid LLM call.
- Still pending (unchanged): formal OSF amendment for the α=0.667 gate, ex ante,
  with Profa. Cunha.

## Files
- codigo/python/utils/injection_guard.py (new)
- codigo/python/04a_*, 04b_* (segregation)
- codigo/r/07d, 07e_07f, 07g, 08 (network metrics)
- tests/test_adversarial_round3.py (detector coverage)
