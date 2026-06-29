# Pipeline v6 — Gabarito de Scripts (pós-auditoria Round 4 (ambiente + cobertura + observabilidade))

**Projeto FAPESP** — Mapeamento Cientométrico da Governança Digital com IA
**Versão:** 6.0 — 31 de maio de 2026
**Pesquisador:** Fernando Leite (FGV EAESP) — Supervisora: Profa. Maria Alexandra Viegas Cortez da Cunha

> **v5 (30/maio/2026):** auditoria de correção (11 fixes: 3 CRÍTICAS, 4 MAJOR, 4 MINOR). Corrigidos dois defeitos que o teste e2e do v4 mascarava (05 abortava na leitura do corpus; 04c entregava 0 representativos). set_seed antes da instanciação do modelo em 06a/06b. Ver `RELATORIO_AUDITORIA_v5.md` e `CHANGELOG.md`.
> **v4 (28/maio/2026):** irrCAC como fonte canônica (DA-06 Codebook v2.2). Bateria de testes de regressão (6 testes, todos passados, |Δα|<0.005). Relatório enriquecido com IC95%, p-valor, Gwet AC1. Teste end-to-end com 100 artigos sintéticos.
> Sem eles, o pipeline não rodava end-to-end (bug fatal de schema entre `04a` e `04c`).
> Detalhes em `CHANGELOG.md`.

---

## Estrutura

```
pipeline_v6/
├── codigo/
│   ├── python/                    # 13 scripts Python
│   │   ├── 01a_coleta_openalex.py
│   │   ├── 02_limpeza_estrutural.py
│   │   ├── 02b_detectar_retracoes.py
│   │   ├── 02c_dedup_fuzzy.py
│   │   ├── 02d_extrair_autores.py
│   │   ├── 02f_extrair_referencias.py
│   │   ├── 04a_classificar_clusters_llm.py    # patches v3 (atomicidade + simetria erros)
│   │   ├── 04b_classificar_epi_llm.py
│   │   ├── 04c_amostrar_para_label_studio.py  # patch v3 crítico (bug fatal de schema)
│   │   ├── 05_processar_anotacoes.py          # patch v3 (NaN guard, anotacao_unica)
│   │   ├── 06a_treinar_clusters.py            # patch v3 (filtro de disputas funcional)
│   │   ├── 06b_treinar_epi.py                 # patch v3 (idem)
│   │   ├── 07_aplicar_modelo.py
│   │   └── utils/
│   │       ├── safe_io.py                      # v3 (atomic I/O + file lock)
│       ├── metrics.py                     # NOVO v4 (irrCAC wrapper)
│       └── metrics_manual.py              # NOVO v4 (referência/testes)
│   │       ├── parquet_io.py                   # refatorado sobre safe_io
│   │       └── logging_setup.py
│   └── r/                         # 8 scripts R + utils
│       ├── 03_limpeza_textual.R
│       ├── 07c_extrair_termos.R
│       ├── 07d_rede_coautoria.R
│       ├── 07e_07f_redes_citacao.R
│       ├── 07g_cooccurrencia_termos.R
│       ├── 08_metricas_redes.R
│       ├── 08a_validade_convergente.R         # reescrito v3 (sem metaprogramação frágil)
│       ├── 09_exportar_csv_consolidado.R
│       └── utils/
│           └── parallel_safe.R
├── protocolo/
│   └── lexico_clusters.csv                    # léxico do Quadro Integrado (204 lemas)
├── README.md   (este arquivo)
└── CHANGELOG.md
```

## Ordem canônica de execução

```
01a → 02 → 02b → 02c → 03 (R) → 02d → 02f
    → 04a → 04b → 04c → [anotação Label Studio] → 05
    → 06a → 06b → 07
    → 07c (R) → 07d (R) → 07e+07f (R) → 07g (R)
    → 08 (R) → 08a (R, validade convergente BERTopic) → 09 (R)
```

## Mudanças v2 → v3 (resumo)

Aplicação dos patches bloqueantes da auditoria QA. Detalhes em `CHANGELOG.md`.
Pontos críticos:

- **04c**: corrigido bug fatal de schema (procurava `score_*`, 04a escreve `cluster_*_llm`).
  Detecção automática agora suporta as duas convenções.
- **04a**: tratamento simétrico de erros API (RateLimit + APIError + jitter),
  atomic write para checkpoint e output final, `cluster_primario_llm` respeita
  a declaração explícita do LLM.
- **08a**: reescrito sem metaprogramação frágil (`bquote + !!!setNames` removido);
  mapeamento de cluster imune à ordem de coluna; atomic write; normalização
  expandida.
- **06a / 06b**: filtro de disputas funcional (era inerte por buscar coluna
  inexistente `tem_disputa`).
- **05**: proteção contra NaN em `epi_na_vals`; marcação explícita de
  `anotacao_unica` (antes silenciosamente confundido com `unanime`).
- **utils/safe_io.py NOVO**: primitivas de I/O atômico e file-lock —
  parquet_io refatorado sobre este helper.

## Mudanças v1 → v2 (resumo)

- **01a**: circuit breaker contra OOM em `reconstruct_abstract` (Gemini ✓)
- **02**: `orjson` + list comp (Gemini ✓), MANTIDO `Int32` nullable (Gemini ✗)
- **04c NOVO**: amostragem estratificada para Label Studio (lacuna identificada)
- **06a/06b**: `dataloader_num_workers=0`, `dataloader_pin_memory=False`
  explícitos para MPS (Gemini sugeriu o oposto, REJEITADO)
- **06a/06b**: `compute_metrics` enriquecido com ECE, Brier, Hamming, Jaccard
- **07**: calibração isotônica condicional ao ECE
- **07c (R)**: função opcional `anotar_com_udpipe()` vetorizada com flag VERB
- **utils/**: helpers Python (logging, parquet_io) e R (parallel_safe)

## Dependências

### Python
```bash
pip install pyalex tqdm pyarrow pandas openai rapidfuzz \
            transformers torch scikit-learn scipy \
            orjson tenacity
```

### R
```r
install.packages(c(
  "data.table", "arrow", "igraph", "stringi", "cld3",
  "tidyverse", "ggraph", "tidygraph",
  "udpipe"          # opcional (para 07c POS filtering)
))
```

## Execução

Cada script tem CLI próprio. Para ver opções:

```bash
python codigo/python/01a_coleta_openalex.py --help
Rscript codigo/r/03_limpeza_textual.R --help
```

## Reprodutibilidade

Todos os outputs Parquet têm hash SHA-256 registrado em
`dados/intermediarios/snapshot.json`. A partir da v3 este snapshot é gravado
atomicamente sob lock — seguro para execução paralela de 04a + 04b.

```bash
sha256sum dados/brutos/corpus_openalex.parquet  # deve bater com snapshot.json
```

## Hardware esperado

- **Treinamento (06a, 06b)**: MacBook Pro M5 Max (Apple Silicon, MPS).
  `fp16=False` e `bf16=False` são obrigatórios — ver Fundamentação v7 §5.2.
- **Demais scripts**: qualquer Mac/Linux com ≥16 GB RAM.

## Documentação de referência

- Manual Operacional v16 Completo (versão única, sem volumes separados)
- Protocolo de Anotação v9 (com Apêndice M — Quadro Integrado)
- Codebook v2.2 (Apêndice 6 declara Quadro como fonte canônica)
- Fundamentação Transformer v7 (§2.5 cita o Quadro)
- Pré-registro OSF v1 (hipóteses e limiares)
- Cartão de Bolso de Clusters (referência rápida operacional)
