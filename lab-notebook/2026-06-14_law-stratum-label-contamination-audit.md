# Law-stratum label contamination: audit and commit block

Date: 2026-06-14

## Context
A calibration design change was requested: guarantee a floor of `subpopulacao_juridica == 1`
articles in `anotacao_calibracao.csv`, to make the Krippendorff alpha for
`epi_doutrinario_normativa` (DN) estimable (calibration drew zero Law-cluster articles).
While pulling the boost articles, all five sampled "Law" items were physics/engineering,
triggering this audit.

## What was done
Descriptive audit of `cluster_origem == "Law"` (n=360) against `subpopulacao_juridica == 1`
on `corpus.csv`; journal-based classification; indirect lexical-polysemy probe (term
enrichment Law vs rest); stratified validation sample export. No original files modified;
outputs written to `work/audit/`. Cluster-assignment code is not in this repo (upstream
pipeline), so the labeling mechanism could not be inspected directly.

## Result / observation
- `Law` and `subpopulacao_juridica == 1` are identical sets (n=360, symmetric diff 0).
  The juridical subpopulation is just a Law indicator and is equally contaminated. [Certain]
- Only 2/360 (0.6%) sit in a plausibly legal journal; top journals are IEEE Power Delivery,
  Astrobiology, Radiation Protection Dosimetry, Medical Physics, Nuclear Fusion. Estimated
  false-positive rate ~99%. [Certain]
- Enrichment vs rest: radiation/dose 26x, space/astro 46x, superconductivity/quantum 44x,
  lightning/discharge 14x. The "law"-token / power-law probe is weak (2.3x, base 0.8%).
  Lexical polysemy on "law" is NOT the cause; the pattern is a mislabeled heterogeneous STEM
  cluster. This revises the earlier polysemy hypothesis. [Probable]

## Impact
- Juridical calibration floor: invalid on this corpus. Forcing 5 "Law" articles injects STEM
  abstracts that cannot exercise DN. Blocked.
- Sampler decision to exclude Law from the prevalence pool as "DN-rich": premise void.
- `mixed = pos+int` rationale (06-11), which invokes a Law--DN association H4 should detect:
  premise methodologically compromised pending a valid juridical label.
- H4 (if it relies on `cluster_origem == "Law"` / `subpopulacao_juridica`): suspended pending
  relabeling.

## Decision
COMMIT BLOCKED for the juridical floor, `config.py`, `anotacao_calibracao.csv` and
`SELECTION_AND_DATA.md`. Label correction required before any calibration change.

## Next steps
1. Obtain the upstream cluster-assignment script + `lexico_clusters.csv`; confirm mechanism.
2. Redefine `subpopulacao_juridica` from a reliable signal (verified legal-journal whitelist;
   manual validation of candidates), independent of DN to avoid circularity.
3. Separate two dimensions: `disciplina_juridica` (field) vs `postura_doutrinario_normativa`
   (epistemic stance). DN must not be inferred from discipline.
4. Re-derive DN positives for calibration from the 04a/04b pre-pass (DN-likely across all
   clusters) once it has run, not from a disciplinary label.
5. Flag H4 and the 06-11 `mixed` rationale to Profa. Cunha as label-dependent.
