# 2026-05-30 — Postures Guide V2 (DN named) + Pilot Operations (sampling, abstracts)

## Context

Operationalizing the typology pilot: (1) Fernando will use a human second annotator (resolves α validity); (2) postures annotation guide updated to V2; (3) article-selection instructions; (4) code + instructions to download abstracts.

## What Was Done

- **Guide V2 (`guia_anotacao_posturas_v2.docx`).** Adopts EE/IC/DN nomenclature (drops "EPI_NA"); gives DN a positive operational definition (§3.3); introduces dual-key annotation for the pilot — Key A (binaries epi_positivista/epi_interpretativa, misto allowed, DN derived) and Key B (single label EE/IC/DN + forcing 1–3). §0 states explicitly that the structural decision (mutual exclusivity) is NOT taken — the pilot decides it. Decision tree (§5) now fills both keys; worked examples (§8) show both keys incl. a misto case with forcing=3; Anexo A is the EE/IC/DN comparative table (landscape). Integrity-preserving: cheap changes (rename + DN positive definition) adopted now; mutual exclusivity deferred to the pilot.
- **`pilot/sample_selection.py`.** Stratified proportional draw of the representative subsample (~150) + DN-enriched booster (~50, e.g. cluster==Law), fixed seed; the booster is kept separate from the prevalence estimate.
- **`pilot/download_abstracts.py`.** OpenAlex-based abstract download (free, no key; abstract reconstructed from inverted index) by DOI list or by OpenAlex filter; SciELO/Crossref noted for Brazilian journals with weak OpenAlex coverage. Runs on the user's machine/Claude Code/Colab (api.openalex.org not reachable in chat sandbox).
- **`pilot/SELECTION_AND_DATA.md`.** Operational instructions tying selection → abstract download → annotation → metrics.

## Results / Observations

- Guide V2 validated; annex column widths fixed to fit landscape (was overflowing ~2050 twips, clipping the derivation column).
- Scripts parse-checked. No corpus yet; the user provides `corpus.csv` (doc_id + strata) and obtains abstracts via the script.

## Next Steps

- Fernando: assemble `corpus.csv`, run sample_selection + download_abstracts, recruit the second annotator, double-annotate per Guide V2 (both keys).
- Then run_labels (prevalence + α_DN) and run_analysis (separability + probe); apply pre-registered decision rule (config.py).
