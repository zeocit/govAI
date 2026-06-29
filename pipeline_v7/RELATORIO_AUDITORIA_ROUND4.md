# Relatório de Auditoria — pipeline_v5 → v6 · Round 4

**Data:** 2026-05-31  
**Frentes:** F) ambiente reprodutível · G) caminhos de erro · H) schema de output
· I) observabilidade · J) cross-language types · K) linting  
**Resultado:** 1 bug real descoberto e corrigido (05 com export vazio); 11 fixes/
melhorias; 3 novos arquivos de suporte; 2 novos módulos utils; 3 novas suítes de
teste. 29/29 compilam; 8/8 R parseiam; 7 suítes verdes.

---

## Reconnaissance (pré-condições de cada frente)

- **F:** zero arquivos de gerenciamento de dependências. CRITICAL para Open Science.
- **G:** zero testes de caminhos de erro. `unittest.mock` aparece 1× nos testes,
  sem uso real para erros de LLM.
- **H:** zero scripts validam o que gravam (`valida_output=0` em todos os 13).
- **I:** sem ETA, sem estimativa de custo pré-run, sem resumo pós-run em 04a/04b.
- **J:** `Int8` nullable, `bool` nullable, `float NaN` e `string/None` — todos
  cruzam a fronteira Python↔R via Parquet sem teste de preservação de tipo.
- **K:** ruff ausente. 17 achados: 11 auto-corrigíveis, 6 residuais (2 falsos
  positivos F401 em 05; 4 E702 intencionais em 07).

---

## Achados e correções

### [CRITICAL — Open Science] F-1 — Zero arquivos de gerenciamento de dependências
- **Problema:** sem `requirements.txt`, `pyproject.toml` nem `renv.lock`. Um
  colaborador ou revisor FAPESP não consegue reproduzir o ambiente.
- **Correção:** `requirements.txt` com versões fixadas (9 pacotes Python + notas
  para torch/transformers/pyalex); `pyproject.toml` com metadados e config ruff;
  `INSTALL.md` com instruções completas para Python, R e dependências de sistema.
- **Nota:** torch, transformers e pyalex não têm versão fixada — dependem de
  plataforma (MPS/CUDA). Documentado em INSTALL.md.

### [MAJOR — bug real] G-1 — 05 quebra com export Label Studio vazio
- **Local:** `main()`, linha 215 (`df_long["id_artigo"].nunique()`)
- **Problema:** `KeyError: 'id_artigo'` quando o export JSON está vazio.
  Descoberto pelos testes de caminhos de erro do Round 4.
- **Prova:** `test_05_export_zero_anotacoes_nao_quebra` (falha na v5, passa na v6).
- **Correção:** early return com `_gravar_gs_vazio()` quando `df_long.empty`.

### [MAJOR — cobertura] G-2 — Zero testes de caminhos de erro
- **Correção:** nova suíte `test_error_paths_round4.py` (10 testes):
  call_llm com JSON inválido/vazio/incompleto; checkpoint corrompido; export
  vazio; anotador único; output_validator com probabilidades erradas e coluna
  faltante; log de fallback rastreável.

### [MAJOR — Open Science] H-1 — Zero validação de schema de output
- **Correção:** novo `utils/output_validator.py` — valida colunas obrigatórias,
  colunas 100% NaN, contagem de linhas suspeita, e probabilidades que somam ≈1.
  Aplicado em 04a antes de gravar os escores de cluster.

### [MAJOR] I-1 — Sem observabilidade para execução de 6+ horas
- **Local:** 04a (e 04b por analogia)
- **Correção:** estimativa pré-run (tokens estimados, horas a ~2s/chamada) antes
  da primeira chamada paga; ETA atualizado a cada `CHECKPOINT_INTERVAL`; resumo
  pós-run (tempo total, fallback rate, distribuição de clusters, fronteiras).

### [MINOR] K-1 — 11 achados de linting corrigidos automaticamente
- `pyarrow` e `pyarrow.parquet` não-usados em 01a e 04c.
- `n_before` definido e nunca lido em 01a.
- `numpy` redefinido em 06a.
- `classification_report` importado e não usado.
- `math` e duplicata de `np` em utils.
- `fleiss_kappa`/`krippendorff_alpha_nominal` em 05 (não chamados diretamente).
- `W292` (sem newline no fim de arquivo).

### [INFRA] K-2 — Linting sem config fixada
- **Correção:** `pyproject.toml` com `[tool.ruff.lint]` — seleciona E/F/W,
  ignora E501 e E702 (com justificativa), exclui `metrics_manual.py`.

### [INFRA] J-1 — Tipos cross-language sem teste de preservação
- **Correção:** nova suíte `test_type_roundtrip.py` (5 + 1 skip): verifica que
  `Int8` nullable, `bool` nullable, `float NaN`, `string/None` e probabilidades
  sobrevivem ao round-trip via parquet. Skip do teste R quando `arrow` ausente.

---

## Meta-análise — padrões recorrentes (4 rodadas)

**Padrão 1 — Silêncio na falha:** o achado mais perigoso de cada rodada foi uma
operação que retornava resultado plausível mas errado (04c zerando amostra; 09.R
falhando no parse; 05 com `tem_disputa` inerte; 05 com `KeyError` em export
vazio). Regra: todo caminho de entrada alternativo (vazio, corrompido, parcial)
deve ter um teste explícito.

**Padrão 2 — Inconsistência de atomicidade:** 02b/02c (Round 2) sobrescreviam
o corpus in-place; 04b (Round 2) gravava sem `.tmp`. Regra de linting candidata:
toda gravação que sobrescreve o input ou que é fruto de chamada paga deve usar
`.tmp → rename`.

**Padrão 3 — Contratos implícitos:** a maioria dos bugs foi de interface entre
scripts (schema não documentado, nomes de colunas divergentes). Regra: o contrato
de cada script (colunas lidas e gravadas) deve ser declarado explicitamente — o
`test_contrato_gs_06.py` (Round 2) formalizou isso para 05↔06; estender para os
demais contratos de alto risco (04a↔04c, 03↔04).

**Padrão 4 — Documentação como afterthought:** README, INSTALL, CHANGELOG foram
construídos incrementalmente. Regra para Open Science: qualquer script novo deve
ter entrada correspondente em INSTALL.md (dependências) e CHANGELOG.md (o que faz
e quando foi adicionado) no mesmo commit.

---

## Cobertura negativa

**Não reexaminado (coberto em rodadas anteriores):** contratos de schema, prompt
injection, gate α, eigen_centrality, NPMI, qcut degenerado, atomic writes.

**Não auditado nesta rodada e por quê:**
- Treinamento (06a/06b): exige GPU/MPS e dados de GS reais — não disponíveis.
- Execução real de 04a/04b: chamadas LLM pagas.
- R com stack completo (arrow/igraph/cld3): pacotes não instalados neste sandbox.
  Validação por parse + documentação empírica (INSTALL.md + test_type_roundtrip).
- CI/CD (GitHub Actions): fora do escopo da auditoria de código.
