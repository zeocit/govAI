# 2026-05-29 — Pilot Pipeline Code (typology decision) + Execution Boundary

## Context

Building the runnable pipeline for the typology decision pilot (misto prevalence + DN separability) so the human-in-the-loop cost is minimized. Recorded what is and is not executable without fabricating data.

## What Was Done

Added `pilot/` to the repo: `config.py` (pre-registered thresholds: misto<10%, α_DN≥0.50, probe margin 0.02; BERTimbau = neuralmind/bert-base-portuguese-cased), `run_labels.py` (misto prevalence + Wilson CI + Krippendorff α incl. DN-vs-rest + Cohen κ; no HF needed), `embeddings.py` (BERTimbau mean-pooled embeddings; needs huggingface.co), `run_analysis.py` (Sonda 2 silhouette/KMeans-ARI + Sonda 3 CV probe comparing B1 softmax vs B2 two-sigmoid+derivation, F1_DN with fold variance; TF-IDF fallback needs no HF), `llm_prepass.py` (exploratory LLM triage via Anthropic API — explicitly NOT gold standard), `README.md`. Smoke-tested `run_labels.py` with a throwaway fixture (deleted); code executes end-to-end.

## Results / Observations — execution boundary (important)

- **Irreducible human input:** misto prevalence and α_DN require human annotation; α needs ≥2 annotators. No script substitutes for this; labels must not be fabricated (would invalidate the very thing the pilot tests).
- **Sandbox network limit:** the chat sandbox cannot reach huggingface.co, so BERTimbau (`embeddings.py`) runs in Claude Code / Colab / local, not in chat. `run_labels.py` and `run_analysis.py --tfidf` run anywhere. `llm_prepass.py` uses the Anthropic API (reachable; needs ANTHROPIC_API_KEY).
- **Legitimate time-saver:** an exploratory LLM pre-pass (project step 04a) gives a *provisional* read on misto/DN distribution and enables unsupervised separability on real abstracts — to scope or short-circuit the human pilot. It does NOT provide human α_DN.
- No corpus/annotations exist in the repo yet; the pipeline awaits abstracts (+ labels).

## Next Steps

- Obtain abstracts CSV (doc_id, abstract) → run `llm_prepass.py` for a provisional read; run `embeddings.py` + `run_analysis.py` for unsupervised separability.
- Decide minimal human annotation design (single annotator → provisional prevalence only; or 2 annotators / human + LLM-second-rater with caveats → α_DN).
- Apply pre-registered decision rule (config.py) once misto% and α_DN are in.
