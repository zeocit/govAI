# Relatório de Auditoria — pipeline_v5 · Round 2 (deep debug)

**Data:** 2026-05-31
**Foco:** contratos entre scripts, falhas silenciosas, validação por execução.
**Resultado:** 3 correções (1 integridade científica, 2 robustez de contrato) + 1 teste de contrato novo. Sem regressão.

---

## 1. Log de validação

| Verificação | Comando | Resultado |
|---|---|---|
| Compilação Python | `py_compile` em 21 arquivos | 21/21 OK |
| Sintaxe R | `parse()` em 9 scripts (R base instalado) | 9/9 OK |
| Testes de métricas | `test_metrics_crossvalidation.py` | 6/6 PASSOU |
| Teste end-to-end | `test_end_to_end.py` (04c→05) | PASSOU |
| Contrato GS↔06 (novo) | `test_contrato_gs_06.py` | 4/4 PASSOU |
| Sanity do teste novo | regressão simulada em /tmp | detecta a falha ✓ |

Validado por execução: todo o caminho Python (compilação + 3 baterias). R: parse-level (pacotes arrow/igraph/cld3 não instalados — checagem estática + parse).

## 2. Tabela de contratos de dados (DAG)

| Script | Lê | Escreve |
|---|---|---|
| 01a | protocolo/periodicos_source_ids.txt | brutos/corpus_openalex.parquet (id, doi, titulo, abstract, ano, periodico_source_id, periodico_nome, citacoes, idioma, autores, referencias, concepts, is_retracted) |
| 02 | brutos/corpus_openalex.parquet | intermediarios/corpus_limpo.parquet (+ano:Int32, citacoes:Int32, is_retracted:bool; JSON desserializado) |
| 02b | corpus_limpo.parquet | corpus_limpo.parquet (+flag_retratado, motivo_retracao) [atomic] |
| 02c | corpus_limpo.parquet | corpus_limpo.parquet (+dedup_grupo, dedup_motivo) [atomic] |
| 02d | corpus_limpo.parquet [id, autores, ano] | redes/nodes_autores.csv, edges_autores_artigos.csv |
| 02f | corpus_limpo.parquet [id, referencias, ano] | redes/edges_citacoes.csv |
| 03.R | corpus_limpo.parquet | corpus_limpo_textual.parquet (+titulo_limpo, abstract_limpo, idioma_detectado, idioma_confianca, abstract_n_palavras) [atomic] |
| 04a | corpus_limpo_textual.parquet [id, titulo_limpo, abstract_limpo] | escores_llm_clusters.parquet (cluster_*_llm, cluster_primario_llm, cluster_secundario_llm, entropia_cluster, is_fronteira_cluster, fora_do_campo_llm) |
| 04b | corpus_limpo_textual.parquet [id, titulo_limpo, abstract_limpo] | escores_llm_epi.parquet (epi_*_llm, epi_status_llm, entropia_epi, is_fronteira_epi) [atomic] |
| 04c | escores_llm_clusters.parquet + corpus_limpo_textual.parquet [id, titulo_limpo, abstract_limpo, ano, idioma_detectado, periodico_source_id, citacoes] | anotacoes/amostra_gs_*.json + .parquet de metadados |
| 05 | anotacoes/label_studio_export.json + corpus_limpo_textual.parquet [seleção defensiva] | gold_standard_final.parquet (ver contrato GS abaixo) + relatorio_concordancia.json + desacordos.csv |
| 06a | gold_standard_final.parquet + corpus_limpo_textual.parquet [id, titulo_limpo, abstract_limpo, idioma_detectado] | resultados/modelo_cluster_* + metricas_long.parquet |
| 06b | idem 06a (camada epi) | resultados/modelo_epi_* + metricas_long.parquet |
| 07 | modelos + corpus_limpo_textual.parquet [id, titulo_limpo, abstract_limpo] | resultados/predicoes_corpus.parquet |
| 07c–09.R | predicoes_corpus.parquet, redes/*.csv, gold_standard/* | nodes_termos, redes, metricas, export zip |

**Contrato do Gold Standard (05 → 06a/06b):**
05 escreve 17 colunas; 06a exige {id, cluster_primario, cluster_status, concordancia_cluster}; 06b exige {id, cluster_status, concordancia_cluster, epi_positivista, epi_interpretativa}. ✓ Todas presentes.

**Mismatches encontrados:** nenhum novo. Os dois históricos (periodico_nome em 05; tem_disputa em 06) já corrigidos em rodadas anteriores. Contrato 04a→04c verificado: confianca_cluster/gap_top1_top2/entropia_llm são DERIVADAS em 04c, não lidas — sem mismatch.

## 3. Achados e correções

### [CRÍTICO — integridade científica] R2-1 — 06b cria epi=0 silenciosamente
- **Local:** `carregar_dados_epi()`
- **Problema:** `for col in [epi_positivista, epi_interpretativa]: if col not in df.columns: df[col]=0`. Se o GS perdesse essas colunas (divergência de schema com 05), o treino da camada epi aprenderia "tudo negativo" — modelo degenerado com F1 plausível mas inválido. Falha silenciosa clássica.
- **Correção:** validação explícita de `cols_obrigatorias` com `raise KeyError`; fallback silencioso removido.

### [MAJOR — robustez de contrato] R2-2 — 06a/06b: gs.get(col, escalar)
- **Local:** filtros do GS em ambos
- **Problema:** `gs.get("cluster_status", "classificado")` num DataFrame devolve a Series se a coluna existe, mas o ESCALAR se não — e um bool escalar em `gs[mask]` quebra de forma obscura. Mascarava ausência de coluna.
- **Correção:** acesso direto `gs["col"]` precedido de validação `cols_obrigatorias`.

### [MELHORIA] R2-3 — teste de contrato GS↔06
- Novo `tests/test_contrato_gs_06.py`: extrai via AST as colunas que 05 escreve e confere contra o que 06a/06b exigem; também detecta regressão ao padrão `gs.get(escalar)`. Sanity-checked (a regressão simulada é detectada).

## 4. Open Questions (decisões científicas — NÃO alteradas)

1. **04c — fallback de estratificação** desvia da estratificação plena pré-registrada (OSF §3.4). Documentar o desvio ou mudar a estratégia? *Recomendação: documentar; para 21k o fallback raramente dispara.*
2. **07d / 07e_07f — eigen_centrality em grafo desconexo:** concentra centralidade no maior componente. closeness/Louvain já são por componente; eigen não. *Recomendação: calcular por componente para coerência.*
3. **07e_07f — `construir_coupling` no-op:** `dt[id_citante %in% unique(id_citante)]` não filtra nada. Esclarecer a intenção (limitar a citantes do corpus?).
4. **08 — peso da rede de co-ocorrência:** usa `n_co_artigos` (contagem); `npmi` seria semanticamente melhor. *Decisão metodológica.*
5. **01a — filtro de idioma inerte** (documentado): intencional, pois 02 retém artigos sem idioma para 03. Confirmar.

## 5. Status de regressão
Todas as baterias passam após as correções. Teste de contrato adicionado para travar a classe de bug 05↔06. Recomenda-se adicionar, no futuro, um contrato análogo 04a↔04c e 03↔04 quando o schema estabilizar.
