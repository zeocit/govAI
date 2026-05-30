# Piloto de decisão — tipologia epistemológica (EE / IC / DN)

Mede as duas grandezas que decidem entre **manter o multi-rótulo (EE/IC + DN derivado)**,
adotar **primário+secundário (3-B)** ou a **ternária pura**. Critérios pré-registrados em `config.py`
(e em `protocolo_piloto_tipologia.docx`, §5).

## O que precisa de humano (irredutível)
- **Prevalência de misto** e **α_DN** (concordância humana sobre DN) exigem anotação humana.
- α exige **≥ 2 anotadores**. Nenhum script substitui isso; rótulos não devem ser fabricados.

## Restrição de rede
- `embeddings.py` (BERTimbau) precisa de **huggingface.co** → rodar no **Claude Code / Colab / máquina local**,
  não na sandbox do chat.
- `run_labels.py` e `run_analysis.py --tfidf` rodam **em qualquer lugar** (só pandas/sklearn).
- `llm_prepass.py` usa a **API da Anthropic** (precisa de `ANTHROPIC_API_KEY`).

## Esquema de dados
- `annotations.csv`: uma linha por (doc_id, annotator). Colunas: doc_id, subsample
  {prevalence|dn_boost}, annotator {ann1,ann2,...,gold}, A_pos, A_int, B_label {EE|IC|DN}, B_forcing {1..3}.
- `abstracts.csv`: doc_id, abstract.

## Ordem de execução
1. `python llm_prepass.py abstracts.csv`  → triagem provisória (NÃO é padrão-ouro), escopo do piloto.
2. Anotação humana dupla → `annotations.csv` (≥2 anotadores + adjudicação 'gold').
3. `python run_labels.py annotations.csv`  → prevalência de misto + α_DN.
4. `python embeddings.py abstracts.csv`  (Claude Code/Colab) → `embeddings.npy`.
5. `python run_analysis.py annotations.csv`  → separabilidade + probe + regra de decisão.
   (Sem BERTimbau: `python run_analysis.py annotations.csv --tfidf abstracts.csv`.)

Dependências: `pip install pandas scikit-learn krippendorff` (+ `transformers torch` para o passo 4).
