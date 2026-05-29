# Pipeline v2 — Code Review & Patches

**Date:** 2026-05-28  
**Phase:** T1 — Infrastructure  
**Category:** Pipeline Development

---

## Context

Full audit of `pipeline_v2` scripts. Eight issues identified across five scripts. One is strictly blocking for end-to-end tests.

## Issues & Patches

| # | Script | Issue | Fix | Blocking? | Est. |
|---|--------|-------|-----|-----------|------|
| 1 | `04c` | Missing patch 3.3 — pipeline halts | Apply patch 3.3 | **YES** | 30 min |
| 2 | `utils/` | No atomic I/O utility | Create `safe_io.py`; refactor `parquet_io.py` | No | 1 h |
| 3 | `04a` | Non-atomic writes; asymmetric error handling; missing `cluster_primario` | Apply patch 3.4 | No (critical for production) | 1 h |
| 4 | `06a` | No dispute filter | Apply patch 3.5 — affects F1 on training | No | 15 min |
| 5 | `08a` | Convergent validity can silently return wrong result | Replace with patch 3.6 | No | 30 min |
| 6 | `05` | NaN propagation (finding #5); column validation gap (finding #6) | Audit — hardening | No | 1 h |
| 7 | `05` | `irrCAC` vs manual Cohen's κ for Codebook DA-06 | Architecture decision pending | No | — |
| 8 | all | `basicConfig` logging scattered | Centralize via `setup_logging()` | No | 30 min |

## Action

Minimum patch set to unblock end-to-end tests: **items 1 + 3 + 5** (`04c`, `04a`, `08a`) ≈ 2 hours.

## Pending

- [ ] Apply blocking patch (#1) before next test run
- [ ] Decide: `irrCAC` (item #7) — architectural decision, not a bug fix
- [ ] Production run (~21k articles) requires item #3 to be applied first
