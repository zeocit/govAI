# Piloto — seleção de artigos e obtenção dos abstracts

## 1. Selecionar os artigos (sample_selection.py)
Precisa de um `corpus.csv` com `doc_id` e colunas de estrato (ex.: `cluster`, `area` PA/IS, `region` BR/intl).
Esse é o seu quadro amostral — a lista de candidatos do corpus piloto, com metadados.

- **Subamostra representativa (≈150):** sorteio estratificado proporcional → estima a prevalência de misto sem viés.
- **Reforço de DN (≈50):** sobreamostra do estrato onde DN se concentra (ex.: `cluster==Law`) → garante casos positivos de DN para a separabilidade. Analisada à parte; **não** entra na estimativa de prevalência.

```
python sample_selection.py corpus.csv --strata cluster area region \
    --n_prev 150 --n_boost 50 --dn_filter "cluster==Law" --seed 42
```
Gera `sample.csv` (doc_id, subsample, stratum). `--seed` fixa a reprodutibilidade (registre-o).

## 2. Baixar os abstracts (download_abstracts.py)
Fonte recomendada: **OpenAlex** — gratuito, sem chave, abstracts via inverted index. Roda na sua máquina / Claude Code / Colab (a sandbox do chat não alcança a API).

- **Por DOIs** (se o corpus tem DOIs): `dois.csv` com colunas `doi[,doc_id]`.
  ```
  python download_abstracts.py --dois dois.csv --mailto voce@fgv.br
  ```
- **Por filtro OpenAlex** (ex.: todos os trabalhos de um periódico a partir de 2010):
  ```
  python download_abstracts.py --filter "primary_location.source.id:S137773608,from_publication_date:2010-01-01" --mailto voce@fgv.br
  ```
  (Ache o `source.id` do periódico buscando o título em https://api.openalex.org/sources?search=NOME)

Gera `abstracts.csv` (doc_id, abstract). Junte com `sample.csv` pelo `doc_id`.

**Periódicos brasileiros** com cobertura fraca no OpenAlex: complemente via **SciELO** (artigos têm DOI Crossref; dá para usar a API do Crossref `https://api.crossref.org/works/{doi}` e o campo `abstract`, quando presente) ou exportação direta do SciELO/Scopus/Web of Science se tiver acesso institucional pela FGV.

## 3. Ordem geral
1. `sample_selection.py corpus.csv …` → `sample.csv`
2. `download_abstracts.py …` → `abstracts.csv` (filtrar pelos doc_id de `sample.csv`)
3. (opcional, exploratório) `python llm_prepass.py abstracts.csv` → leitura provisória
4. Anotação humana dupla (guia V2, duas chaves) → `annotations.csv`
5. `python run_labels.py annotations.csv` → prevalência + α_DN
6. `python embeddings.py abstracts.csv` (Claude Code/Colab) → `embeddings.npy`
7. `python run_analysis.py annotations.csv` → separabilidade + probe + regra de decisão
