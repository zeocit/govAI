# CHANGELOG — Pipeline v1.0 → v2.0

Refatoração após auditoria cruzada (auditoria interna FL sobre relatório Gemini).
Cada item indica: (a) o que mudou; (b) por quê; (c) qual ponto da auditoria.

---

## ✨ NOVO

### `04c_amostrar_para_label_studio.py`
Script novo cobrindo lacuna identificada na auditoria. Implementa amostragem
estratificada (250 representativos + 250 fronteira) conforme Manual v14 §4.1
e Pré-registro OSF §3.4. Suporta sementes 42/123/2026 (DA-05) e exporta JSON
no formato Label Studio, separadamente para projeto cluster e projeto epi.

### `utils/logging_setup.py`
Helper Python para logging estruturado com timestamp, nível, módulo, gravando
em console + arquivo rotacionado simultaneamente.

### `utils/parquet_io.py`
Helper Python centralizando: gravação atômica, schema pyarrow explícito,
hash SHA-256 em snapshot.json, validação cross-language Python↔R.

### `utils/parallel_safe.R`
Helper R para `mclapply` com guarda contra BLAS-fork deadlock em macOS
(Accelerate framework) — `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`,
`RcppParallel::setThreadOptions`.

---

## 🛠 REFATORADO

### `01a_coleta_openalex.py`

#### Função `reconstruct_abstract`
**Antes**: pré-alocava `words = [""] * (max_pos + 1)` — vulnerável a OOM se
o OpenAlex devolvesse índice corrompido (ex.: `position=99999999`).

**Depois**:
- Mapeamento esparso via `dict[int, str]` em vez de lista contígua
- Constante nomeada `MAX_TOKEN_POSITION = 10_000` (circuit breaker)
- Logging de anomalias em vez de catch-all silencioso

**Origem**: Gemini ✓ aprovado com refinamentos (constante nomeada, logging).

#### Gravação final
**Antes**: `df.to_parquet(output_path, ...)` direto.

**Depois**:
- Atomic write (`.tmp` → `rename`) para evitar arquivos parciais corruptos
- Hash SHA-256 + entrada em `dados/intermediarios/snapshot.json`

**Origem**: rodada senior FL.

---

### `02_limpeza_estrutural.py`

#### Função `desserializar_json_col`
**Antes**: `json.loads` builtin + `.apply()` do pandas — overhead dobrado.

**Depois**:
- `orjson.loads` (parser C, 3-10x mais rápido)
- List comprehension (evita overhead `.apply`)
- Guard de idempotência: se a coluna já é object (parquet via pyarrow), no-op

**Origem**: Gemini ✓ aprovado com refinamentos (guard de contexto, claim de
"50x" rebaixada para "3-10x" realista).

#### Normalização de tipos
**Antes**: `Int64` nullable do pandas.

**Depois (REJEITAMOS a sugestão Gemini de degradar para float64)**:
- `Int32` nullable (mais econômico que Int64, suficiente para anos 2000-2024 e citações)
- **Distinção 0 vs NA preservada em `citacoes`** — Gemini fundia em `fillna(0)`,
  o que descarta informação cientometricamente importante (afeta IPC e
  normalizações por citação)
- Sanity assertion: anos fora de [2000, 2024] geram erro explícito
- Comentário documentando a decisão arquitetural contra a sugestão Gemini

**Origem**: Gemini ✗ rejeitado. Refinamento: rodada senior FL.

#### Gravação
Mesma melhoria de 01a: atomic write + SHA-256 + snapshot.json.

---

### `04a_classificar_clusters_llm.py` e `04b_classificar_epi_llm.py`

Sem mudanças funcionais (já implementam corretamente os dois prompts LLM
independentes — DA-04). Apenas pequenas correções de formatação.

---

### `05_processar_anotacoes.py`

**Validado**: implementação local de Krippendorff α em Python está
matematicamente correta. Gemini propôs migrar para pacote R `icr` —
**REJEITADO** porque (a) o Manual fixa `irrCAC`, não `icr`; (b) o filtro
de NAs proposto introduz viés que Krippendorff originalmente evita.

Sem mudanças — implementação Python atual mantida.

**Origem**: Gemini ✗ rejeitado.

---

### `06a_treinar_clusters.py` e `06b_treinar_epi.py`

#### `TrainingArguments`
**Antes**: `fp16=False`, `bf16=False`, `use_mps_device=True` (correto).

**Depois (adições explícitas contra a sugestão Gemini)**:
- `dataloader_num_workers=0` (Gemini sugeriu `=4` — REJEITADO, MPS não tolera)
- `dataloader_pin_memory=False` (Gemini sugeriu `=True` — REJEITADO, memória
  unificada Apple Silicon torna pin_memory sem sentido)
- `full_determinism=False` (MPS não tem determinismo completo; ~0,5% variação F1
  entre runs é esperado e absorvido pelas três sementes)
- Comentários inline documentando cada decisão MPS

**Origem**: Gemini ✗ rejeitado totalmente (configurações CUDA-céntricas que
quebrariam o pipeline em MPS). Refinamento: rodada senior FL.

#### `compute_metrics` (cluster)
**Antes**: apenas F1-macro + F1 por classe.

**Depois**: adicionado
- F1 weighted (sensibilidade a desbalanceamento)
- Accuracy (sanity check)
- ECE (Expected Calibration Error, 10 bins, Guo et al. 2017)
- Brier score multi-classe (calibração probabilística)

**Origem**: rodada senior FL.

#### `compute_metrics_epi` (multi-label binário)
**Antes**: F1 por dimensão + F1 macro.

**Depois**: adicionado
- Hamming loss (proporção de rótulos errados, padrão multi-label)
- Jaccard score por amostra
- Brier score por dimensão

**Origem**: rodada senior FL.

---

### `07_aplicar_modelo.py`

#### Calibração isotônica condicional
Adicionadas funções `carregar_calibrador()` e `aplicar_calibracao()`:
- Convenção: 06a/06b persiste `calibrador.pkl` em `<model_dir>/` se ECE > 0,10
- Em inferência, se calibrador existe é aplicado; senão probs brutas
- Suporta scikit-learn `IsotonicRegression` por classe (multinomial calibrado
  + renormalização) ou `CalibratedClassifierCV`

**Origem**: rodada senior FL.

---

### `07c_extrair_termos.R`

#### Função opcional `anotar_com_udpipe()`
Adicionada implementação vetorizada de udpipe para uso opcional:
- Passa vetor completo de textos (otimização C++)
- `parser = "none"` (sem análise sintática — não precisamos no projeto)
- **Flag `incluir_verbos = TRUE` por default** — verbos carregam sinal
  metodológico para a camada epi (e.g., "modelamos"=positivista,
  "interpretamos"=interpretativa). Gemini propunha excluir VERB.
- Separação por idioma (modelos português-bosque e english-ewt)

**Origem**: Gemini ⚠️ aprovado com refinamento (preservar VERB por default,
opcional desativar).

---

## 🚫 REJEITADOS (do relatório Gemini)

1. **`reconstruct_abstract` com `max_pos > 10000` hardcoded** —
   refinado para constante nomeada.

2. **"50x de aceleração com orjson"** — claim rebaixada para 3-10x realista;
   guard de contexto adicionado (parquet via pyarrow já desserializa).

3. **`Int64` → `float64` em ano e citações** — degradaria schema semântico
   (ano não pode ser 2023.5) e perderia distinção 0/NA em citações.

4. **Amostragem `df.sample()` simples para Label Studio** — violaria
   pré-registro OSF; substituído por amostragem estratificada (04c).

5. **Pacote R `icr` para Krippendorff** — Manual fixa `irrCAC`; filtragem
   de NAs proposta introduz viés.

6. **`fp16=True` para fine-tuning** — quebra training em MPS (NaN em
   gradientes); mantido `fp16=False`.

7. **`dataloader_num_workers=4`** — múltiplos workers disputam handles MPS;
   mantido `=0`.

8. **`dataloader_pin_memory=True`** — sem sentido em memória unificada
   Apple Silicon; mantido `=False`.

9. **udpipe filtrando apenas NOUN/ADJ/PROPN** — exclui verbos que carregam
   sinal para camada epi; flag `incluir_verbos=TRUE` por default.

---

## ⚠️ PENDENTES

- Adoção dos helpers `utils/logging_setup.py` e `utils/parquet_io.py` nos
  scripts existentes (refator incremental, não-bloqueante).
- Atomic writes ainda não aplicados em 02b, 02c, 02d, 02f, 04a, 04b, 05, 07
  (implementáveis via `utils/parquet_io.write_parquet_atomic`).
- Logging estruturado idem (substituir `logging.basicConfig` por
  `setup_logging()`).

Estes itens são melhorias incrementais — os scripts atuais continuam
funcionais sem elas.

## 28/maio/2026 — atualizações pós-Quadro Integrado

### Mudanças no `04a_classificar_clusters_llm.py`
- **SYSTEM_PROMPT enriquecido** com Doxa Fundamental, sinalizadores e métodos por
  cluster, mais 13 pares de fricção inter-cluster (de ~3.5 KB para ~9.6 KB).
- Output JSON **inalterado** — compatibilidade total com 04c, 05 e downstream.
- `prompt_versao_cluster` (hash SHA-256[:12]) muda automaticamente; resultados
  anteriores precisam ser regerados se a comparação for relevante.

### Novos artefatos
- `codigo/r/08a_validade_convergente.R` — calcula Jaccard e cobertura entre
  tópicos BERTopic e léxico de cluster. Critério em Protocolo §7.6.1.
- `protocolo/lexico_clusters.csv` — 204 lemas distribuídos entre os 6 clusters,
  extraídos do Quadro Integrado (Apêndice M do Protocolo).

### Inputs/outputs adicionados
- Input novo: `dados/intermediarios/bertopic_topics_por_cluster.parquet`
  (produzido pelo pipeline BERTopic — Parte VI).
- Output novo: `dados/intermediarios/validade_convergente.parquet` e
  `relatorios/validade_convergente_resumo.csv`.

## 28/maio/2026 — pipeline_v3: patches da auditoria QA

Esta versão aplica os patches bloqueantes identificados na auditoria QA do
pipeline_v2 (Staff QA Engineer & Code Architect), além de mudanças de
robustez de impacto secundário.

### Patches bloqueantes (sem os quais o pipeline não roda end-to-end)

**`04c_amostrar_para_label_studio.py:103-118` — bug fatal de schema corrigido**
- O script buscava colunas com prefixo `score_*` para calcular top1/top2/entropia.
- 04a (desde a refatoração v2) escreve colunas com prefixo `cluster_<c>_llm`.
- Resultado: `score_cols` vazia, `scores_mat` matriz N×0, IndexError ao acessar
  `[:, 0]`. **O 04c jamais rodou end-to-end com output real do 04a.**
- Patch: detecção automática do schema (suporta as duas convenções, com
  preferência para `cluster_<c>_llm`); falha rápida com mensagem clara se
  nenhum padrão completo for encontrado.

**`08a_validade_convergente.R` — reescrita completa**
- Removida metaprogramação frágil (`bquote(...) + !!!setNames(...)` dentro de
  `rowwise()`), substituída por loop explícito com `vapply` (idiomático,
  estável, vetorizado).
- Mapeamento `cluster_max_jaccard` tornado imune à ordem das colunas geradas
  por `across()` — agora referencia explicitamente `paste0("jaccard_", CLUSTERS)`.
- Normalização de termos expandida (`ñ`, diacríticos europeus, underscore).
- Schema de `top_terms` robusto a lista / vetor / string única delimitada.
- Atomic write para o parquet de detalhe e o CSV de resumo.
- Aviso explícito quando algum cluster vier com léxico vazio (anteriormente
  resultava em validade zerada silenciosamente).

**`04a_classificar_clusters_llm.py` — atomicidade + simetria de erros**
- `call_llm()` agora trata `RateLimitError`, `APIConnectionError` e
  `APIStatusError` uniformemente: backoff exponencial com jitter, todos
  caem no fallback após esgotar retries (antes RateLimit caía silenciosa,
  APIError crashava — comportamento assimétrico).
- `cluster_primario_llm` agora respeita a declaração explícita do LLM no JSON;
  cai para argmax somente se a declaração for ausente ou fora do vocabulário,
  caso em que marca `fallback_parsing_cluster = True` para rastreio.
- `save_checkpoint()` e a gravação final do output passam a usar atomic write
  (`.tmp` → `fsync` → `rename`). Protege contra perda de horas de chamadas LLM
  pagas em caso de crash durante a gravação.

### Patches de robustez (não bloqueantes)

**`06a_treinar_clusters.py` + `06b_treinar_epi.py` — filtro de disputas funcional**
- Versão anterior filtrava por `tem_disputa`, coluna que `05` nunca escreve.
  `05` escreve `concordancia_cluster` com valor `"disputa_pendente"`.
  Filtro estava silenciosamente inerte: artigos disputados (com
  `cluster_primario=None`) vazavam para o treino, derrubando F1.
- Patch substitui pelo filtro coerente com o schema real do GS.

**`05_processar_anotacoes.py` — proteção contra NaN + marcação de anotação única**
- `epi_na_vals = [int(v) for v in grupo["epi_na"]]` crashava com TypeError se
  algum anotador não preenchesse `epi_na` (valor `pd.NA`). Tratamento
  defensivo: `int(v) if pd.notna(v) else 0`.
- Artigos com um único anotador eram silenciosamente marcados como `"unanime"`
  (porque 1 == 1). Agora marcam como `"anotacao_unica"` para auditoria
  downstream — não corrompe métricas mas separa o caso semanticamente.

**Novo: `utils/safe_io.py`**
- Primitivas de I/O atômico e idempotente compartilhadas: `atomic_write_bytes`,
  `atomic_write_json`, `sha256_file` (chunked), `file_lock` (POSIX + Windows).
- Razão para existir: a auditoria QA encontrou três pontos de falha por
  ausência de atomicidade (`04a:to_parquet`, `save_checkpoint`,
  `snapshot.json`) e uma race condition latente em `registrar_snapshot`
  (lost-update entre 04a e 04b paralelos).

**`utils/parquet_io.py` — refatorado sobre `safe_io`**
- Delegação para `safe_io.sha256_file` (chunked, escalável).
- `registrar_snapshot` agora opera sob `file_lock` — seguro para execução
  paralela de scripts (DA-04: 04a + 04b são independentes por construção).
- Snapshot corrompido é movido para `.corrupt.bak` antes de ser recriado
  (anteriormente perdia história silenciosamente).

### Adoção pelos scripts críticos

A auditoria identificou que `utils/parquet_io.write_parquet_atomic` e
`utils/logging_setup.setup_logging` existiam mas não eram usados pelos
scripts críticos. O patch v3 corrige isto onde mais importa:

- `04a` usa atomic write inline (independente de `parquet_io` para evitar
  acoplamento circular durante checkpoint frequente).
- `04c`, `05`, `06a`, `06b` permanecem com `to_parquet` direto por enquanto;
  estes são gravações únicas no fim do script, baixo risco. Migração para
  `write_parquet_atomic` é trivial e pode ser feita incrementalmente.

### Achados Médios/Baixos da auditoria QA — não aplicados

Os seguintes achados foram identificados mas considerados não-bloqueantes;
ficam para iteração futura:

- Regex JSON sem aninhamento em `parse_response` (04a:304) — schema atual é
  plano, baixo risco.
- Implementação manual de Fleiss/Krippendorff em `05` convive com `irrCAC`
  (DA-06). Decisão arquitetural pendente.
- `Counter.most_common(1)` em caso de empate não é determinístico
  (`05:328-331`). Para reprodutibilidade total, ordenar alfabeticamente.
- Anti-padrão `iterrows()` em `04a:427` — performance OK na escala atual.
- Explosão combinatória de estratos em `04c:94-100` — risco metodológico
  documentado, requer análise do tamanho efetivo do corpus piloto.

Relatório completo da auditoria disponível na conversa do projeto.

## 28/maio/2026 — pipeline_v4: irrCAC como fonte canônica (DA-06)

### Motivação
O Codebook v2.2 DA-06 declara `irrCAC` como pacote canônico para métricas de
concordância. A implementação manual de Fleiss/Krippendorff em `05_processar_anotacoes.py`
(~88 linhas, pipeline_v3) contradiz essa decisão e expõe riscos em edge cases.
Análise técnica completa disponível na conversa do projeto.

### Mudanças

**`utils/metrics.py` (NOVO)**
Wrapper fino sobre `irrCAC.raw.CAC` com API externa idêntica às funções manuais.
Principais adições em relação à implementação manual:
  - IC95% assintótico (confidence_interval) nativo — sem bootstrap ad-hoc.
  - p-valor — para reportar no artigo metodológico.
  - Gwet's AC1 — diagnóstico do paradoxo de Kappa (Apêndice C do Protocolo).
  - Suporte nativo a missings (None/NaN por posição).
  - Rastreabilidade: IRRCAC_VERSION gravado no snapshot.json.
  - metricas_completas(): calcula α + κ + AC1 em uma única passagem (eficiência).

**`utils/metrics_manual.py` (NOVO — referência/testes)**
Implementação original movida para `utils/metrics_manual.py` com marcação
"LEGADO". Usada exclusivamente em `tests/test_metrics_crossvalidation.py`
como bateria de testes de regressão.

**`05_processar_anotacoes.py` — migrado para `utils/metrics`**
  - Substituídas as chamadas às funções manuais por chamadas via `utils/metrics`.
  - Relatório `relatorio_concordancia.json` enriquecido com:
    IC95%, p-valor, Gwet's AC1, versão do irrCAC, α das dimensões epi.
  - `status_gate` expandido: inclui `epi_pos_alpha_ok` e `epi_int_alpha_ok`.

**`tests/test_metrics_crossvalidation.py` (NOVO)**
Bateria de 6 testes de validação cruzada (irrCAC × manual):
  - Concordância perfeita: ambas retornam 1.0000 exatamente.
  - Concordância aleatória: ambas retornam −0.0260 (idênticas).
  - Caso típico (500 artigos, 80% acordo): |Δα| = 0.000005 (<<threshold de 0.005).
  - Prevalência alta: AC1=0.7996 > κ=0.7014 — paradoxo confirmado.
  - Missings: irrCAC aceita sem crash.
Todos os 6 testes PASSARAM. Relatório em tests/crossval_report.json.

**`tests/test_end_to_end.py` (NOVO)**
Teste end-to-end com 100 artigos sintéticos cobrindo 04c → 05.
Sem API externa — simula output do 04a com escores sintéticos.
Resultados observados no container de CI:
  - 04c: rodou sem crash (confirma correção do bug fatal de schema do v3).
  - Achado Médio-#9 CONFIRMADO empiricamente: com 100 artigos, 94% dos
    estratos são singletons. Comportamento esperado: desaparece com 21k artigos.
  - 05 com irrCAC:
    α cluster = 0.6711 (≥0.67 ✓), κ = 0.6694 (≥0.60 ✓), AC1 = 0.6773.
    IC95% α = [0.563, 0.779], irrCAC 0.4.4.

### Dependência adicionada
```
irrCAC>=0.4.4   # Gwet (2014) — ver DA-06 do Codebook v2.2
```
Adicionar a `requirements.txt` ou `pyproject.toml`.

## 30/maio/2026 — pipeline_v5: auditoria de correção (Opus 4.8) + otimização

### Motivação
Auditoria completa do pipeline_v4 com o prompt "Senior Research Software
Reviewer". Validação empírica: o teste end-to-end do v4 falhava em dois pontos
(05 abortava na leitura do corpus; 04c entregava 0 representativos em silêncio).

### Correções (11 — 3 CRÍTICAS, 4 MAJOR, 4 MINOR; detalhes em RELATORIO_AUDITORIA_v5.md)

**CRÍTICAS**
- **05**: leitura defensiva do schema do corpus — `periodico_nome` (inexistente)
  fazia o pyarrow abortar (`ArrowInvalid`). Agora mescla só colunas presentes.
- **04c**: recuo progressivo de estratificação (pleno → cluster×quartil →
  cluster) quando a chave plena colapsa em singletons. Antes: amostra
  representativa = 0 silenciosamente. Nível usado registrado em log.
- **06a / 06b**: `transformers.set_seed(semente)` antes de instanciar o modelo.
  Sem isso, a inicialização aleatória da cabeça de classificação não era
  controlada pelas sementes — variância de init misturada ao efeito de semente.

**MAJOR**
- **06b**: corrigido NameError latente em `existing` (definido fora de escopo);
  removida releitura do arquivo recém-gravado.
- **06a / 06b**: `TrainingArguments` robusto a versão via inspeção de assinatura
  (eval_strategy vs evaluation_strategy; use_mps_device/no_cuda depreciados).
- **07**: consolidação vetorizada (substitui iterrows em ~21k artigos); nova
  `derivar_postura_vetorizado` equivalente exata à escalar.
- **07**: `main()` recebe output_path explícito (sem mutar global); write atômico.
- **04a**: contador `n_processados` corrige cadência de checkpoint ao retomar.

**MINOR**
- **05**: grava concordância das duas dimensões epi (pos + int); escapa `%`
  literal no log de IC95; remove comentário duplicado de header.
- **metrics.py**: remove imports mortos (math, numpy).

### Validação
- py_compile: 21/21 OK.
- test_metrics_crossvalidation: 6/6 PASSOU (|Δα| < 0.005 mantido).
- test_end_to_end: PASSOU (04c → 05) — antes quebrava.

### Sem alterações (auditado, correto)
metrics.py (API irrCAC 0.4.4 verificada), safe_io.py, parquet_io.py, 08a.R.

### Pendência
Fallback de 04c desvia da estratificação plena do pré-registro OSF §3.4 —
decidir entre documentar o desvio ou adotar outra estratégia.

## 30/maio/2026 — pipeline_v5: segunda rodada (scripts faltantes: fase 01–02 + R)

Auditoria dos scripts não cobertos na primeira rodada. R base instalado para
validar sintaxe (parse) de todos os 9 scripts R.

### Correções (8 — 2 CRÍTICAS, 4 MAJOR, 1 MINOR; +1 doc)

**CRÍTICAS**
- **09 (R)**: apêndice de dependências estava como texto cru (sem #), tornando
  o script inválido em R. Confirmado: parse() da v4 FALHA, da v5 OK. Comentado.
- **03 (R)**: detecção de idioma usava detect_language_mixed (NÃO vetorizada),
  corrompendo a atribuição por documento. Trocado por detect_language
  (vetorizada). Confiança ajustada (1.0/NA) sem inventar probabilidade.

**MAJOR**
- **07e_07f (R)**: removido operador %||% (rlang, não carregado) que quebrava
  o Rscript; substituído por tryCatch sobre ofile.
- **02b / 02c**: sobrescrita in-place do corpus agora atômica (.tmp → rename).
- **04b**: output final com atomic write (.tmp → fsync → rename).
- **04b**: contador n_processados corrige cadência de checkpoint ao retomar
  (mesmo defeito de 04a).

**MINOR**
- **02b**: regex de "errata" tinha caracteres cirílicos (а/т) — nunca casava.
- **metrics.py**: (já na 1ª rodada) imports mortos removidos.

### Pendências (decisão de Fernando)
01a filtro de idioma inerte; eigen_centrality em grafo desconexo (07d/07e_07f);
no-op em construir_coupling; peso da rede de co-ocorrência (08); adoção de
logging_setup. Detalhes em RELATORIO_AUDITORIA_v5.md.

### Validação
Python 21/21 + testes OK (sem regressão). R: parse 9/9 OK.

## 31/maio/2026 — pipeline_v5: centralização dos limiares de concordância

Decisão metodológica (Fernando + auditoria): reconciliados os três conjuntos
divergentes de threshold de α/κ num single source of truth.

### Mudanças
- NOVO utils/thresholds.py: ALPHA_GATE=0.667 (Krippendorff α — gate canônico de
  decisão, DA-06), KAPPA_REF=0.61 (Fleiss κ — referência diagnóstica, Landis &
  Koch "substantial"), + faixa_krippendorff() (confiável/tentativo/insuficiente).
- 05_processar_anotacoes.py:
  - Gate de aceitação agora é SOMENTE α≥0.667 (cluster e epi, mesmo padrão).
    κ deixou de ser gate — é diagnóstico, reportado em bloco kappa_diagnostico.
  - Relatório ganha faixa_krippendorff por dimensão e detecção de paradoxo de
    prevalência (AC1−κ>0.15) com warning no log.
  - Removidos os limiares soltos antigos (0.67/0.55/0.60/0.50).
  - status_gate serializa booleanos JSON nativos (antes saíam como string).
- NOVO tests/test_thresholds_centralizados.py: trava a centralização (valores
  canônicos, ausência de limiares soltos, gate baseado só em α).

### Fundamentação (Krippendorff 2004, p.241; 2013 cap.12; Landis & Koch 1977)
α≥0.800 confiável; 0.667≤α<0.800 tentativo (qualificar conclusões no texto);
α<0.667 insuficiente. κ como referência por ser sensível ao paradoxo de
prevalência (daí AC1).

### PENDENTE — ação de Fernando
0.667 > 0.50 do pré-registro OSF/pilot. Subir o gate é EMENDA ao pré-registro:
datar, justificar e fechar com a Profa. Cunha ANTES da coleta. Feito ex ante,
impecável; post-hoc, vira grau de liberdade.

### Validação
py_compile 25/25; 5 suítes verdes (métricas, contrato GS↔06, adversarial,
thresholds, e2e).

## 31/maio/2026 — pipeline_v5: decisões aprovadas (injeção, redes)

Implementação das decisões de Fernando sobre as questões pendentes do Round 3.
Estado do pipeline: 04a/04b ainda NÃO rodaram no corpus final; anotação não
começou — logo as mudanças entram sem custo de comparabilidade.

### Prompt injection (04a/04b) — "sinalizar + revisar antes de classificar"
- NOVO utils/injection_guard.py: detector heurístico (regex PT+EN, sem LLM) de
  padrões de injeção. Triagem barata antes da primeira chamada paga.
- 04a/04b: abstracts suspeitos são SEGREGADOS (não classificados) e gravados em
  injecao_para_revisao_{clusters,epi}.csv para revisão humana. Combina com a
  delimitação <<<ARTICLE_BEGIN/END>>> já existente (defesa em duas camadas).
- Teste: test_adversarial_round3 agora cobre o detector (pega 4 vetores de
  ataque, libera benignos incl. caso-armadilha "acting as a platform").

### Redes (decisões 2a/2b)
- 07d (coautoria): eigen_centrality agora restrita ao componente gigante (LCG),
  NA fora dele. Antes era calculada no grafo inteiro desconexo (autovetor
  concentra no maior componente e zera os demais).
- 07e_07f (co-citação + coupling): adicionado PageRank por nó (page_rank()$vector,
  peso = co-citações/refs compartilhadas). Robusto a desconexão; preferível ao
  autovetor para redes de citação. (Ambas as redes são não-dirigidas no pipeline;
  não há citação direta dirigida.)
- 07g (co-ocorrência): peso canônico passa a ser weight = NPMI restrito a NPMI>0;
  n_co_artigos (contagem bruta) preservado como coluna para sensibilidade.
- 08: prioriza coluna weight (=NPMI em co-ocorrência), fallback npmi/n_co_artigos.

### Validação
R parse 9/9 OK; Python 26/26 compila; 5 suítes verdes. page_rank()/eigen API
conferida contra doc oficial do igraph (r.igraph.org).

### Pendência (inalterada)
Gate α 0.667 ainda exige emenda formal ao pré-registro OSF (ex ante, com Cunha).

## 31/maio/2026 — pipeline_v6: Round 4 (ambiente, cobertura, observabilidade)

### Correções / novos artefatos

**F — Ambiente reprodutível (CRITICAL, Open Science)**
- NOVO requirements.txt: 9 pacotes Python com versões fixadas.
- NOVO pyproject.toml: metadados + config ruff (E/F/W, ignora E501/E702).
- NOVO INSTALL.md: instruções completas Python, R, deps de sistema, env vars,
  estrutura de dados, notas de compatibilidade MPS.

**G — Bug real descoberto pelos novos testes**
- 05: `KeyError: 'id_artigo'` com export Label Studio vazio → corrigido com
  early return e `_gravar_gs_vazio()`.
- NOVO tests/test_error_paths_round4.py (10 testes): LLM com JSON inválido/
  vazio/incompleto; checkpoint corrompido; export vazio e anotador único;
  output_validator com prob errada e coluna faltante.

**H — Schema validation de outputs**
- NOVO utils/output_validator.py: valida colunas, NaN total, contagem de linhas
  e probabilidades que somam ≈1. Aplicado em 04a.

**I — Observabilidade para execuções longas (04a)**
- Estimativa pré-run: tokens estimados + horas antes da 1ª chamada paga.
- ETA atualizado a cada CHECKPOINT_INTERVAL.
- Resumo pós-run: tempo total, fallback rate, distribuição de clusters.

**J — Type safety cross-language**
- NOVO tests/test_type_roundtrip.py: 5 testes Python + 1 condicional R,
  verificando Int8/bool nullable, float NaN, string/None e probs no round-trip.

**K — Linting estático**
- 11 achados ruff auto-corrigidos (imports mortos, variável não usada,
  import duplicado, newline ausente).
- Config permanente em pyproject.toml.

### Validação
Python 29/29; R parse 8/8; 7 suítes verdes (35 passam, 1 skip legítimo).
