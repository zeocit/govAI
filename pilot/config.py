"""Pré-registro do piloto de tipologia epistemológica — parâmetros e limiares.
Fixados ANTES de observar resultados (integridade). Calibráveis com a supervisora,
mas registrados a priori (ver protocolo_piloto_tipologia.docx, §5)."""

# Limiares de decisão pré-registrados
MISTO_THRESHOLD = 0.10      # misto < 10% => "raro"
ALPHA_DN_MIN    = 0.50      # concordância humana mínima para DN ser "coeso"
PROBE_MARGIN    = 0.02      # margem de F1 considerada relevante (senão, empate)

# Modelo de embeddings (BERTimbau). Requer rede até huggingface.co (Claude Code/Colab).
MODEL_NAME = "neuralmind/bert-base-portuguese-cased"

# Esquema esperado do CSV de anotações (uma linha por (doc_id, annotator)):
#   doc_id      : id do artigo
#   subsample   : 'prevalence' (amostra representativa) | 'dn_boost' (reforço de DN)
#   annotator   : 'ann1','ann2',... ou 'gold' (rótulo adjudicado)
#   A_pos,A_int : Chave A — binários independentes (0/1); misto = ambos 1
#   B_label     : Chave B — 'EE'|'IC'|'DN' (rótulo único mutuamente exclusivo)
#   B_forcing   : 1..3 — custo de supressão (3 = forçamento forte)
# Abstracts (para embeddings) em CSV separado: doc_id, abstract.
ANN_COLS = ["doc_id", "subsample", "annotator", "A_pos", "A_int", "B_label", "B_forcing"]
