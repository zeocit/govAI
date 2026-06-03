# Calibração — tipologia epistemológica ternária

Fase de calibração inter-anotador que antecede a construção do Gold Standard.
Critério de entrada na anotação completa: **α_doutrinario_normativa ≥ 0,40** (Krippendorff,
irrCAC/R). Limiares pré-registrados em `config.py` e OSF pre-registration v2 §6.

## Critério de entrada

| Gate | Limiar | Consequência se abaixo |
|------|--------|------------------------|
| `CALIB_ALPHA_DN_FLOOR` | 0,40 | Revisar Guia de Anotação v3 §3.3 e repetir |
| `ALL_ZERO_RECONSIDER_RATE` | > 15 % | Reconsiderar esquema de categorias |

Os limiares do Gold Standard (`GS_ALPHA_GATE_EPI = 0,55`; `GS_ALPHA_GATE_CLUSTER = 0,67`)
são aplicados na fase seguinte, após aprovação na calibração.

## O que requer humano (irredutível)

- α inter-anotador exige **≥ 2 anotadores independentes**.
- Nenhum script substitui anotação humana; rótulos fabricados invalidam o gate e o pré-registro OSF.

## Restrições de rede

- `embeddings.py` (BERTimbau) requer **huggingface.co** — rodar no Colab ou máquina local.
- `run_labels.py` e `sample_selection.py` rodam em qualquer ambiente (só pandas).
- `llm_prepass.py` requer `ANTHROPIC_API_KEY` no ambiente.

## Esquema de dados

`sample_calib.csv`: doc_id, subsample {calibracao|calibracao_juridica}, stratum.

`annotations.csv`: uma linha por (doc_id, annotator):

| Coluna | Tipo | Valores |
|--------|------|---------|
| doc_id | str | id do artigo |
| subsample | str | calibracao \| calibracao_juridica |
| annotator | str | ann1, ann2, … \| gold |
| epi_positivista | 0/1 | postura empírico-explicativa presente |
| epi_interpretativa | 0/1 | postura interpretativo-compreensiva presente |
| epi_doutrinario_normativa | 0/1 | postura doutrinário-normativa presente |

Três flags independentes; qualquer combinação é válida; (0,0,0) = inconclusivo (não deriva nenhuma postura).

## Ordem de execução

1. `python sample_selection.py corpus.csv` → `sample_calib.csv` (25 artigos, seed 42)
2. `python llm_prepass.py abstracts.csv` → triagem exploratória (NÃO é padrão-ouro)
3. Anotação humana dupla → `annotations.csv` (≥ 2 anotadores + adjudicação 'gold')
4. `python run_labels.py annotations.csv` → α por postura + veredicto do gate
5. *(opcional)* `python embeddings.py abstracts.csv` (Colab/local) → `embeddings.npy`

Dependências: `pip install pandas krippendorff` (+ `transformers torch` para o passo 5).
