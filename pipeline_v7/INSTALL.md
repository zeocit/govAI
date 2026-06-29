# INSTALL.md — govAI pipeline_v5

Instruções de instalação para reprodutibilidade do ambiente.
Testado em macOS Apple Silicon (M5 Max, Python 3.10+).

## Pré-requisitos do sistema

- Python ≥ 3.10
- R ≥ 4.3 (para os scripts `codigo/r/`)
- Git

## Python

```bash
# 1. Criar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# 2. Instalar dependências fixadas
pip install -r requirements.txt

# 3. Instalar torch (depende da plataforma):
# macOS Apple Silicon (MPS):
pip install torch torchvision

# Linux/Windows com CUDA 12.x:
# pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# CPU only (sem GPU):
# pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# 4. Instalar transformers e pyalex (não têm versão fixada por deps de plataforma)
pip install "transformers>=4.35" pyalex

# 5. Verificar instalação
python3 -m py_compile codigo/python/04a_classificar_clusters_llm.py && echo "OK"
```

## Variáveis de ambiente

```bash
# Copiar o template e preencher com suas credenciais
cp .env.example .env
# Editar .env e adicionar:
# OPENROUTER_API_KEY=sk-or-...
# OPENALEX_EMAIL=seu_email@instituicao.br
```

O arquivo `.env` está no `.gitignore` — nunca commitar credenciais.

## R

Os scripts R (`codigo/r/`) dependem dos seguintes pacotes:

```r
install.packages(c(
  "arrow",      # leitura/escrita de Parquet
  "data.table", # manipulação eficiente de dados
  "igraph",     # análise de redes
  "Matrix",     # matrizes esparsas (co-ocorrência)
  "stringi",    # limpeza de texto
  "cld3",       # detecção de idioma (requer libprotobuf)
  "udpipe",     # lematização
  "jsonlite",   # I/O JSON
  "readr",      # I/O CSV
  "dplyr",      # manipulação de dados
  "digest",     # hashing
  "zip"         # compactação de outputs
))
```

**Dependência de sistema para cld3** (macOS):
```bash
brew install protobuf
```

**Dependência de sistema para cld3** (Ubuntu/Debian):
```bash
apt-get install libprotobuf-dev protobuf-compiler
```

### renv (reprodutibilidade R)

Para fixar as versões dos pacotes R:
```r
install.packages("renv")
renv::init()
renv::snapshot()
```
O arquivo `renv.lock` gerado deve ser versionado no repositório.

## Verificação do ambiente

```bash
# Python: compilar todos os scripts
for f in codigo/python/*.py codigo/python/utils/*.py; do
  python3 -m py_compile "$f" && echo "✓ $f"
done

# Python: rodar testes
python3 -m pytest tests/ -v

# R: verificar sintaxe
for f in codigo/r/*.R; do
  Rscript -e "parse(file='$f')" 2>/dev/null && echo "✓ $f"
done

# Linting
ruff check codigo/python/ --select E,F,W --ignore E501,E702
```

## Estrutura de diretórios de dados

Os dados **não** estão versionados no repositório. Crie a estrutura antes de rodar:

```
dados/
├── brutos/           # output de 01a (corpus OpenAlex)
├── intermediarios/   # outputs de 02, 02b-02f, 03, 04a, 04b, 04c
├── anotacoes/        # outputs de 04c (JSON Label Studio) e imports do 05
├── gold_standard/    # output de 05
├── resultados/       # modelos treinados (06a, 06b) e predições (07)
└── redes/            # outputs de 07c-07g, 08, 09
```

## Notas de compatibilidade

- `TrainingArguments` (transformers): a construção é robusta a `eval_strategy`
  (≥4.46) vs `evaluation_strategy` (<4.46) via inspeção de assinatura em runtime.
- Apple Silicon (MPS): `fp16=False`, `bf16=False`, `dataloader_num_workers=0`.
  Variação de F1 entre rodadas de ≈0.5% é normal (MPS não é totalmente determinístico).
- Parquet cross-language: colunas `Int8` nullable (pandas) chegam como `integer`
  no R via arrow. `float('nan')` chega como `NA_real_`. Ver `tests/test_type_roundtrip.py`.
