# 2026-05-30 — Notion: comprehensive sweep of all floating tasks

## Context

Continuation of the Notion database reorganization. After the initial pass (2026-05-29), the user confirmed that the screenshot showed only a sample. This session performed a systematic sweep across all task ranges to find and move every floating task (no Parent item) to the correct parent section.

---

## Method

Repeated database-scoped searches using distinct keyword clusters covering:
- §3.4, §4.4.3, §7.x, §9.x prefixed tasks
- [REFAC v2/v3/v4] task patterns
- Action verb clusters (Calcular, Verificar, Implementar, Produzir, etc.)
- Thematic clusters (BEPE/Krems, BERTopic, ERGM, SBM, IPC, corpus, annotation, LLM)
- Range-specific sweeps (3658cc5e, 3688cc5e, 3698cc5e, 3628cc5e, 3598cc5e, 35c8cc5e)

For each candidate: verified parent status via fetch before moving. Stopped when consecutive searches returned only already-parented tasks.

---

## Tasks moved (~50 additional tasks)

### → 03 Infraestrutura e Ferramentas (1)
- §3.4 — Verificar acesso WebService SOAP CNPq/Lattes

### → 04 Pesquisa - Banco de Dados (16)
- §3.4 C1 — Confirmar snapshot OpenAlex pós-correção
- §3.4 C2 — Implementar last-author anomaly test
- §3.4 C3.1 — Validação ORCID
- §3.4 C3.2 — Validação Lattes
- §3.4 C4 — Coerência semântica embeddings + silhouette
- §4.4.3 — Sortear amostra 100 artigos (50+50)
- §4.4.3 — Anotação cega 100 artigos
- [REFAC v2] Auditoria 10% sênior (Kappa ≥ 0,65)
- [REFAC v2 CONCLUÍDO] 05_processar_anotacoes.py (Krippendorff α)
- §9.3bis — Depositar corpus + escores + grafos Zenodo
- [MINERAÇÃO v2] Coletar perfil anotadores (from previous session)
- [MINERAÇÃO v2] Configurar adjudicação (from previous session)
- [MINERAÇÃO v2] Log de ambiguidade (from previous session)
- [MINERAÇÃO v2] Janela deslizante kappa (from previous session)

### → 05 Pesquisa - Análise e Modelagem (28)
- §4.4.3 — Calcular H_LLM e D_H; estimar ρ Spearman IC bootstrap
- §7.5.2bis — Comparar MDL flat vs nested; selecionar modelo principal
- §7.5.2bis — Estimar nested OSBM (NestedBlockState)
- §7.5.2bis — Estimar DC-SBM benchmark + OSBM flat
- §7.5.2bis — Estabilidade multi-semente (10 exec, ARI≥0,70)
- §7.5.2bis — Caracterizar blocos pelo perfil médio T
- §7.6.4 — Construir rede coautoria com atributos T e IPC
- §7.6.4 — Estimar ERGM principal vetorial (14 termos)
- §7.6.4 — Estimar cenário A e cenário B
- §7.6.4 — Diagnóstico convergência MCMC
- §7.6.4 — Análise de robustez (coeficientes A vs B)
- §7.6.6 — Interpretação bourdieusiana IPC e homofilia vetorial
- §7.7.1 — Calcular matriz densidade inter-tradições 4×4
- §7.7.1 — Heatmap 4×4 ggplot2 + triangulação ERGM+OSBM+BERTopic
- §7.3bis P0 — Construir grafo direcionado de citações
- §7.3bis — Calcular Dimensões I/II/III do IPC
- §7.3bis — Calcular IPC desagregado por tradição
- §7.3bis — Sensibilidade IPC Camada I (4 cenários + Kendall τ)
- §7.3bis — Sensibilidade IPC Camada II (simplex ~231 pontos)
- §7.3bis — Sensibilidade IPC Camada III (Sobol SALib N=1024)
- §9.3bis — Desambiguação T5: sensibilidade ERGM cenários A/B
- [PROMPT v3 GATE] Re-rodar 04a quando piloto começar
- [VALIDADE CONVERGENTE] Executar 08a_validade_convergente.R
- [REFAC v4] Executar 04a + 04b corpus completo (~42k chamadas LLM)
- [REFAC v2] Implementar 06a_treinar_clusters.py (9 células × 3 seeds)
- [REFAC v2] Implementar 06b_treinar_epi.py (arquitetura vencedora × 3 seeds)
- [CONCLUÍDO] Prompt LLM cluster (v1→v3, SHA-256 hash)
- [CONCLUÍDO] Prompt LLM epi (DA-04, binário Pos×Int + NA)

### → 06 Entregas (5)
- §7.5.2bis — Pré-registrar OSF: flat vs nested |ΔΣ|>10 nats
- §7.6.4 — Pré-registrar OSF: ERGM vetorial + critério robustez
- §9.3bis — Verificar 4 refs antes submissão
- §9.3bis — Checklist 24 itens antes submissão artigo
- §9.3bis — Criar repositório GitHub + README + release v1.0

### → 07 Disseminação (2)
- §9.3bis — Verificar transferibilidade método corpus BEPE (Krems)
- **Estágio KREMS** (organizador-pai com 10 sub-itens): Confirmar datas Viale Pereira, Confirmar HPC Danube, Redigir artigo coautoria, Apresentar seminários Danube, Solicitar BEPE FAPESP, Manter reuniões mensais Cunha, etc.

### → 02 Metodologia (1)
- [LÉXICO] Validar lexico_clusters.csv (204 lemas) com supervisora

### → 2.1 Revisão de Literatura (1)
- Ler Sim & Wright (2005) — kappa statistic Physical Therapy

---

## Key finding: Estágio KREMS

"Estágio KREMS" (`34e8cc5e-f607-8039-8900-e90feb7ca656`) was a floating parent-task with 10 nested sub-items (all BEPE activities). Moving the parent automatically brought all sub-items into 07 Disseminação hierarchy.

---

## Convergence signal

By the final search rounds, all queries returned exclusively already-parented tasks. The database root is now clean of floating tasks with research content. The only items potentially remaining at root are the 8 parent section headers themselves (01–07 + 2.1) and tasks marked `[EXCLUIR...]` awaiting manual deletion.

---

## Next steps

- Delete all `[EXCLUIR...]` tasks manually via Notion filter
- Verify the Lab Notebook entry for the previous session is pushed (2026-05-29)
