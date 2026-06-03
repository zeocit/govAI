"""Parâmetros e limiares pré-registrados para a fase de calibração.
Fixados ANTES de observar resultados (integridade científica).
Referência: Codebook v2.2 §DA-06; OSF pre-registration v2 §6.
"""

# --- Limiares de calibração (fase pré-Gold Standard) ---
CALIB_ALPHA_DN_FLOOR     = 0.40   # Krippendorff α mínimo para epi_doutrinario_normativa
                                   # nas 25 anotações de calibração. Abaixo → revisar guia.
ALL_ZERO_RECONSIDER_RATE = 0.15   # > 15 % de artigos com (0,0,0) → reconsiderar esquema.

# --- Limiares do Gold Standard (entrada na fase de anotação completa) ---
GS_ALPHA_GATE_EPI     = 0.55   # Krippendorff α global — postura epistemológica
GS_ALPHA_GATE_CLUSTER = 0.67   # Krippendorff α global — cluster disciplinar

# --- Modelo de embeddings (BERTimbau) ---
MODEL_NAME = "neuralmind/bert-base-portuguese-cased"

# --- Esquema de anotação (uma linha por (doc_id, annotator)) ---
#   doc_id                    : identificador do artigo
#   subsample                 : 'calibracao' | 'calibracao_juridica'
#   annotator                 : 'ann1', 'ann2', ... ou 'gold' (rótulo adjudicado)
#   epi_positivista           : 0/1 — postura empírico-explicativa presente
#   epi_interpretativa        : 0/1 — postura interpretativo-compreensiva presente
#   epi_doutrinario_normativa : 0/1 — postura doutrinário-normativa presente
#   Três flags independentes; qualquer combinação é válida; (0,0,0) = inconclusivo.
ANN_COLS = [
    "doc_id", "subsample", "annotator",
    "epi_positivista", "epi_interpretativa", "epi_doutrinario_normativa",
]
