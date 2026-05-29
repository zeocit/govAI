# 2026-05-29 — Notion task organization: floating tasks, Categoria review, dependencies

## Context

Continuation of the Notion database maintenance session. After consolidating reading tasks under "2.1 Revisão de Literatura" (previous entry), this session addressed the remaining 8 parent items visible in the project structure: 01 Processo FAPESP, 02 Metodologia, 03 Infraestrutura e Ferramentas, 04 Pesquisa - Banco de Dados, 05 Pesquisa - Análise e Modelagem, 06 Entregas, 07 Disseminação.

---

## What was done

### 1. Parent item IDs confirmed

| Section | ID |
|---|---|
| 01 Processo FAPESP | `34e8cc5e-f607-803b-957e-fd9632c443fe` |
| 02 Metodologia | `34e8cc5e-f607-808f-a636-cd04d8ca8ce4` |
| 03 Infraestrutura e Ferramentas | `34e8cc5e-f607-80fa-bd9d-c3e6fe137265` |
| 04 Pesquisa - Banco de Dados | `34e8cc5e-f607-808a-950a-d78fde667e30` |
| 05 Pesquisa - Análise e Modelagem | `34e8cc5e-f607-80da-9155-d70c3933b55d` |
| 06 Entregas | `34e8cc5e-f607-8089-8094-ecca42fc8377` |
| 07 Disseminação | `34e8cc5e-f607-809e-90da-f1ef5a57c78c` |

### 2. Floating tasks identified and moved (~32 tasks total)

Floating tasks were concentrated in the 3688cc5e and 3698cc5e ranges (created in late May 2026 sessions without parent assignment). Most tasks in 34e8cc5e, 3618cc5e, 3638cc5e ranges were already parented.

| Destination | Count | Task types |
|---|---|---|
| 04 Pesquisa - Banco de Dados | 18 | [MINERAÇÃO v2] pipeline scripts 01b–09; annotation setup (adjudicação, log, kappa window, anotador profile); disambiguation test |
| 02 Metodologia | 11 | [REFAC v2] Manual v14 (2 parts), Protocolo v7, Codebook v1→v2+v2.1, Mapa Navegação, Fundamentação Transformer, Workshops supervisora (2×), PROTOCOLO D1, PROTOCOLO D3 |
| 05 Análise e Modelagem | 3 | [REFAC v4] Executar 04a LLM; implementar 07_aplicar_modelo.py; Gate T4 V de Cramer |
| 03 Infraestrutura | 1 | [REFAC v2] Reconfigurar Label Studio |
| 06 Entregas | 2 | [PRÉ-REGISTRO] OSF v2; §4.4.3 pré-registrar protocolo LLM |
| 01 FAPESP | 1 | [REFAC v2] Projeto FAPESP v21→v22 |

### 3. Categoria corrections (5 tasks)

| Task | Old Categoria | New Categoria |
|---|---|---|
| Codebook v2→v2.1 | Documentos | **Protocolo de Anotação** |
| Workshop supervisora Codebook | Tradições/Clusters | **Protocolo de Anotação** |
| Workshop supervisora Positivista×Interpretativa | Validação metodológica | **Protocolo de Anotação** |
| Implementar 07_aplicar_modelo.py | Experimento comparativo | **BERTimbau** |
| Fundamentação Modelos Transformer | Documentos | **Conceitos e técnicas** |

### 4. Date assignments for tasks without dates

| Task | Trimestre | Dates assigned | Rationale |
|---|---|---|---|
| Workshop supervisora Positivista×Interpretativa | T1 | 16–17/10/2026 | After Workshop Codebook (15/10) |
| Mapa de Navegação v3→v4 | T2 | 15–16/01/2027 | Early T2, before training begins |
| Gate T4 V de Cramer | T4 | 16–18/06/2027 | After corpus classification complete |
| Coletar perfil anotadores | T1 | 05–07/10/2026 | Before annotation begins |
| Configurar painel adjudicação | T1 | 08–10/10/2026 | Before annotation begins |
| Implementar log de ambiguidade | T1 | 13–14/10/2026 | Before annotation begins |
| Implementar janela deslizante kappa | T1 | 15–17/10/2026 | Before annotation begins |

### 5. Dependencies configured (3 new Blocked by relations)

| Task | Blocked by |
|---|---|
| [REFAC v4] Executar 04a LLM | 01d_reconciliar_multifonte.py (corpus must be ready) |
| Implementar 07_aplicar_modelo.py | Treinar BERTimbau + Executar 04a LLM |
| Gate T4 V de Cramer | Implementar 07_aplicar_modelo.py |

---

## Observations

- The overwhelming majority of pre-existing tasks (34e8cc5e, 3618cc5e, 3638cc5e ranges) were already correctly parented to sub-organizers within their sections. The actual floating tasks came from recent sessions (3688cc5e, 3698cc5e ranges created 22–23 May 2026) where no parent was assigned during creation.
- Several [REFAC v2 — CONCLUÍDO] tasks are historical (Status: Pronto, dates in May 2026) and correctly reflect completed work; no changes made to those.
- The task "Debater tradições vs clusters" (`3628cc5e-f607-80c9`) was found archived — its dependency link with Sessão A (Revisão de Literatura) could not be configured.

---

## Remaining items

- Manual deletion of ~55 tasks marked `[EXCLUIR...]` (use Notion filter: `Tarefa contains "[EXCLUIR"`)
- Verify that tasks in 02 Metodologia's original sub-item list that belong in other sections (03–06) are correctly placed — most appear correctly assigned based on random-sample checks
- Confirm the dependency between [PRÉ-REGISTRO] OSF and the Gold Standard annotation start (gate condition not yet formalized as a Blocked by relation)
