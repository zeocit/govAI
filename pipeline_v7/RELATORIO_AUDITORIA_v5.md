# Relatório de Auditoria — pipeline_v4 → pipeline_v5

**Data:** 2026-05-30
**Escopo:** 13 scripts Python + 6 utils + 9 scripts R + 2 testes
**Método:** auditoria estática + validação empírica (testes executados; API irrCAC 0.4.4 verificada contra a biblioteca real; assinaturas de TrainingArguments tratadas por inspeção em runtime)
**Resultado:** 11 correções aplicadas (3 CRÍTICAS, 4 MAJOR, 4 MINOR). Todos os scripts compilam; ambas as baterias de teste passam.

---

## Resumo executivo

A v4 continha dois defeitos que o próprio teste end-to-end mascarava: a leitura do corpus em `05` abortava com `ArrowInvalid`, e a amostragem representativa em `04c` colapsava para zero em silêncio. Ambos foram confirmados executando o teste e2e da v4 (que falha) e corrigidos na v5 (que passa, saltando de 7 para 57 tarefas amostradas). Além disso, os scripts de treino (`06a`/`06b`) não fixavam as RNGs antes de instanciar o modelo — falha de reprodutibilidade que invalidava parcialmente o desenho de 27 rodadas × 3 sementes. Os módulos de métricas (`metrics.py`), I/O atômico (`safe_io.py`, `parquet_io.py`) e validade convergente (`08a.R`) estavam corretos.

---

## Achados e correções

### [CRÍTICO] C-1 — `05`: leitura do corpus aborta por coluna inexistente
- **Local:** `main()`, merge de metadados
- **Problema:** pedia `periodico_nome`; o corpus textual expõe `periodico_source_id`. O pyarrow aborta a leitura inteira (`ArrowInvalid`). Confirmado: o teste e2e da v4 quebra neste ponto.
- **Correção:** leitura defensiva do schema (`pq.read_schema`) e seleção apenas das colunas presentes antes do merge.

### [CRÍTICO] C-2 — `04c`: amostra representativa colapsa para zero
- **Local:** `amostrar_representativos()`
- **Problema:** chave de estrato com 5 dimensões → quase todo estrato vira singleton → `StratifiedShuffleSplit` (exige ≥2 por estrato) retorna conjunto vazio, silenciosamente. O teste v4 alegava "passou" entregando 0 representativos.
- **Correção:** recuo progressivo de granularidade — pleno → cluster×quartil → cluster — com o nível efetivamente usado registrado em log (rastreabilidade para o pré-registro OSF §3.4). No teste: 7 → 57 tarefas.

### [CRÍTICO] C-3 — `06a`/`06b`: RNGs não fixadas antes de instanciar o modelo
- **Local:** `treinar_celula_semente()` / `treinar_epi_semente()`
- **Problema:** a cabeça de classificação é inicializada aleatoriamente; `TrainingArguments(seed=...)` só age após a construção. Sem `set_seed()` antes, as 3 sementes não controlavam a inicialização — a variância entre rodadas misturava ruído de init com efeito de semente, comprometendo o experimento comparativo.
- **Correção:** `transformers.set_seed(semente)` imediatamente antes de `from_pretrained`.

### [MAJOR] M-1 — `06b`: NameError latente em `existing`
- **Local:** `main()`, bloco final
- **Problema:** `existing` definido só dentro de `if todas_metricas:`, mas referenciado fora; quando todas as rodadas já estavam completas, o script quebrava no fim.
- **Correção:** `existing` carregado uma única vez, antes de qualquer escrita; eliminada a releitura do arquivo recém-gravado.

### [MAJOR] M-2 — `06a`/`06b`: incompatibilidade de versão do transformers
- **Local:** `TrainingArguments(...)`
- **Problema:** `evaluation_strategy` foi renomeado para `eval_strategy` (≥4.46); `use_mps_device`/`no_cuda` foram depreciados. O nome fixo quebra conforme a versão instalada.
- **Correção:** construção dos kwargs por inspeção de assinatura em runtime (`inspect.signature`), usando o nome efetivamente aceito. Não introduz parâmetros inexistentes. NOTA: não foi possível verificar a versão exata do ambiente do M5 Max; a solução é robusta a ambas as convenções.

### [MAJOR] M-3 — `07`: loop iterrows em ~21k artigos
- **Local:** `main()`, consolidação do DataFrame
- **Problema:** `corpus.iloc[i]` linha a linha → O(n) com alto overhead Python por artigo.
- **Correção:** construção colunar vetorizada; nova `derivar_postura_vetorizado()` equivalente exata à versão escalar (mesma árvore de decisão, mesmo threshold).

### [MAJOR] M-4 — `07`: mutação de variável global OUTPUT_PATH
- **Local:** bloco `__main__`
- **Problema:** `OUTPUT_PATH = args.output` reatribuía o global lido por `main()` — frágil.
- **Correção:** `main()` recebe `output_path` como parâmetro explícito; gravação tornada atômica (.tmp → rename).

### [MAJOR] M-5 — `04a`: cadência de checkpoint desalinha ao retomar
- **Local:** loop de classificação
- **Problema:** `(len(rows) - len(ids_done)) % INTERVAL` assume que o tamanho inicial de `rows` é igual a `len(ids_done)`, o que nem sempre vale ao retomar — checkpoint dispara cedo demais ou de menos.
- **Correção:** contador explícito `n_processados` de itens desta execução.

### [MINOR] m-1 — `05`: concordância epi parcial
- `concordancia_epi` gravava só a dimensão positivista. Agora grava `concordancia_epi_pos` e `concordancia_epi_int`.

### [MINOR] m-2 — `05`: `%` literal no log de IC95
- `"IC95%=(...)"` no `%`-formatting do logging dispara erro de conversão. Escapado para `%%`.

### [MINOR] m-3 — `05`: comentário duplicado no header `# ── Main# ── Main`.

### [MINOR] m-4 — `metrics.py`: imports mortos (`math`, `numpy`) removidos.

---

## O que estava correto (sem alterações)
- `utils/metrics.py` — API do irrCAC verificada contra a v0.4.4 real (`.krippendorff()["est"]["coefficient_value"]`, `confidence_interval`, `p_value`, `.ratings` existem; missings tolerados).
- `utils/safe_io.py`, `utils/parquet_io.py` — atomicidade, file-lock e hash chunked corretos.
- `r/08a_validade_convergente.R` — robusto a top_terms lista/vetor/string; mapeamento de cluster imune à ordem de colunas; atomic write.

## Validação empírica
- `py_compile`: 21/21 arquivos Python OK.
- `tests/test_metrics_crossvalidation.py`: 6/6 PASSOU (|Δα| < 0.005 mantido).
- `tests/test_end_to_end.py`: PASSOU end-to-end (04c → 05) — antes quebrava.

## Pendência para decisão (Fernando)
O fallback de estratificação de `04c` (C-2) desvia da estratificação plena pré-registrada (OSF §3.4). Para o corpus real (~21k) provavelmente nunca dispara, mas convém: (a) documentar o desvio no pré-registro, ou (b) adotar outra estratégia. Decisão pendente.

---

# Segunda rodada — scripts faltantes (fase 01–02 + R)

**Data:** 2026-05-30
**Escopo:** 01a, 02, 02b, 02c, 02d, 02f, 04b (Python) + 03, 07c–07g, 08, 09, parallel_safe (R)
**Validação adicional:** R base instalado; `parse()` executado em todos os 9 scripts R (captura erros de sintaxe sem exigir os pacotes).

## Achados e correções (segunda rodada)

### [CRÍTICO] C-4 — `09_exportar_csv_consolidado.R`: apêndice não comentado quebra o script
- **Local:** linhas 278+ (após o bloco CLI)
- **Problema:** um "Apêndice — Dependências completas" com prosa e comandos shell/R estava como texto cru, sem `#`. Em R isso é sintaxe inválida: o script inteiro falha ao rodar. Confirmado: `parse()` da v4 retorna FALHA; da v5, OK.
- **Correção:** apêndice comentado integralmente (conteúdo preservado como referência).

### [CRÍTICO] C-5 — `03_limpeza_textual.R`: detecção de idioma com função não-vetorizada
- **Local:** `detectar_idioma()`
- **Problema:** usava `detect_language_mixed()`, que NÃO é vetorizada — concatena todo o vetor num único texto e devolve as `size` (3) línguas predominantes do conjunto. Atribuir esse resultado de 1–3 linhas a N documentos (`resultado$...[mask] <- detected$language`) recicla valores e corrompe a detecção por documento. Verificado contra a doc oficial do cld3 (ropensci).
- **Correção:** uso de `detect_language()` (vetorizada, um ISO por documento). Como ela não expõe probabilidade, a confiança passa a 1.0 para detecções válidas e NA para as não confiáveis (que a cld3 marca como NA), sem inventar número espúrio.

### [MAJOR] M-6 — `07e_07f_redes_citacao.R`: operador `%||%` inexistente em base R
- **Local:** bloco CLI (`script_name <- ... %||% ...`)
- **Problema:** `%||%` vem de rlang/purrr, não carregados (só data.table e igraph). Dispara `could not find function "%||%"` ao rodar via Rscript.
- **Correção:** detecção de `ofile` via `tryCatch`, sem `%||%`.

### [MAJOR] M-7 — `02b`/`02c`: sobrescrita in-place sem atomicidade
- **Local:** gravações do corpus em `02b_detectar_retracoes.py` (1×) e `02c_dedup_fuzzy.py` (3×)
- **Problema:** ambos sobrescrevem o único corpus limpo com `df.to_parquet(input_path)` direto; um crash durante a escrita corromperia o corpus.
- **Correção:** escrita atômica (`.tmp → rename`); em 02c, helper `_gravar_atomico`.

### [MAJOR] M-8 — `04b`: output final sem atomic write
- **Local:** `main()` de `04b_classificar_epi_llm.py`
- **Problema:** diferente de 04a, gravava o output (fruto de chamadas LLM pagas) sem atomicidade.
- **Correção:** `.tmp → fsync → rename`, com remoção do checkpoint só após sucesso.

### [MAJOR] M-9 — `04b`: cadência de checkpoint desalinha ao retomar
- Mesmo defeito de 04a (M-5): `len(rows) % INTERVAL` com rows pré-carregado. Corrigido com contador `n_processados`.

### [MINOR] m-5 — `02b`: regex de "errata" com caracteres cirílicos
- `\berrата\b` continha "а" (U+0430) e "т" (U+0442) cirílicos; nunca casava a palavra latina. Corrigido para `\berrata\b`.

## Auditado e correto (sem alteração)
- `01a` (reconstrução de abstract robusta a índice anômalo; atomic write + snapshot SHA-256).
- `02d`, `02f` (extração de autoria/referências vetorizada e defensiva).
- `07c` (TF-IDF), `07g` (PMI/NPMI com matriz esparsa) — matematicamente corretos.
- `07d` (coautoria), `08` (métricas de rede), `parallel_safe.R`, `logging_setup.py`.

## Pendências para decisão (Fernando)
1. **`01a` filtro de idioma:** `IDIOMAS` é declarado mas deliberadamente NÃO aplicado na query (mantido inerte e documentado), pois 02 retém artigos sem idioma para detecção em 03. Confirmar se essa é a intenção.
2. **`07d`/`07e_07f` eigen_centrality em grafo desconexo:** concentra centralidade no maior componente (~0 nos demais). closeness e Louvain já são por componente; eigen não. Decidir se deve ser calculada por componente.
3. **`07e_07f` `construir_coupling`:** `dt[id_citante %in% unique(id_citante)]` é no-op — a intenção de filtro (só citantes do corpus?) não se concretiza. Esclarecer a intenção.
4. **`08` peso da rede de co-ocorrência:** usa `n_co_artigos` (contagem bruta); `npmi` seria semanticamente mais adequado. Decisão metodológica.
5. **`logging_setup.py`:** existe mas nenhum script o usa (todos repetem basicConfig). Padronizar é opcional.

## Validação (segunda rodada)
- Python: py_compile 21/21 OK; testes 6/6 + e2e OK (sem regressão).
- R: parse 9/9 OK na v5; `09` da v4 confirmadamente FALHA no parse.
