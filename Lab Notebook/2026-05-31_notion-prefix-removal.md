# 2026-05-31 — Notion: removal of operational prefixes from task titles

## Context

All task titles in the "Marcos e Tarefas" database had accumulated operational prefixes of the form `[TYPE vN — QUALIFIER]` during development. These cluttered the task view and were no longer needed since the encoded information is captured in dedicated fields (Status, Trimestre, Categoria) or is historical. The user requested their removal.

## Prefixes removed

| Prefix pattern | Count (approx.) | Original purpose |
|---|---|---|
| `[REFAC v2]`, `[REFAC v4]` | ~25 | Tasks created during refactoring to two-classifier architecture |
| `[REFAC v2 — CONCLUÍDO + DECISÃO DOCUM.]` | ~3 | Refactoring tasks marked complete with documented decisions |
| `[MINERAÇÃO v2]`, `[MINERAÇÃO v4 — TESTE EXECUTADO]` | ~15 | Data pipeline scripts written for pipeline_v2 |
| `[MINERAÇÃO v2 — CONCLUÍDO]` | 1 | Completed pipeline script batch |
| `[CONCLUÍDO 28/mai]` | 2 | Prompt LLM tasks completed on 28 May |
| `[DEPRECATED — ...]`, `[DEPRECATED v2.0 — ...]` | ~8 | Tasks superseded by architectural decisions |
| `[REVISÃO FERNANDO — ...]` | ~3 | Self-review tasks scheduled for specific dates |
| `[REVISÃO — CONCLUÍDA]` | 1 | Completed review task |
| `[PROTOCOLO — D1]`, `[PROTOCOLO D3 — CONCLUÍDO]` | 2 | Protocol doubt-resolution sessions |
| `[LÉXICO]` | 1 | Lexicon validation task |
| `[PROMPT v3 — GATE OPERACIONAL]` | 1 | Operational gate for LLM prompt versioning |
| `[PRÉ-REGISTRO — CRÍTICO]` | 1 | OSF pre-registration submission |
| `[2.1 Revisão de Literatura — LEITURA OBRIGATÓRIA]` | 1 | Gwet (2014) mandatory reading — also moved to 2.1 |
| `[2.1 Revisão de Literatura — FORMAÇÃO OPERACIONAL]` | 1 | irrCAC tutorial — also moved to 2.1 |
| `[2.1 Revisão de Literatura]` | 1 | Sim & Wright (2005) reading |
| `[REFAC]` (without version) | 1 | References and Courses v5 update |

**Total: ~67 tasks updated.**

## Method

Iterative database-scoped Notion search → identify bracketed prefix → strip `[...]` from title start while preserving full content verbatim. Executed via `notion-update-page` (update_properties on the `Tarefa` field).

The `[EXCLUIR — DUPLICATA]` and `[EXCLUIR — COBERTO POR SESSÃO X]` markers were intentionally preserved — they serve as deletion markers for the pending manual cleanup (Notion filter: `Tarefa contains "[EXCLUIR"`).

## Convergence signal

Final search rounds returned only clean titles with no bracketed prefixes in results, confirming completion.
