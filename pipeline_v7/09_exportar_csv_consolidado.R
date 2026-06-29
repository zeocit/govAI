# 09_exportar_csv_consolidado.R | Exportacao consolidada para deposito Zenodo
# ===========================================================================
# Junta predicoes finais (07_aplicar_modelo.py) com metadados do corpus e
# gera dois artefatos:
#   1. corpus_govai_classificado.csv  -- dados para deposito
#   2. zenodo_dicionario_variaveis.csv -- manifesto de variaveis (Zenodo)
#
# Codebook de referencia: v4.0
# Esquema epistemologico: dois eixos ortogonais
#   Eixo 1: orientacao_proeminente (funcao de epi_positivista + epi_interpretativa)
#   Eixo 2: epi_doutrinario_normativa (flag independente)
#   inconclusiva = 1 sse os tres flags sao 0
#
# Autor: Fernando Leite | FAPESP 2023/13163-7
# ===========================================================================

suppressPackageStartupMessages({
  library(arrow)         # parquet I/O
  library(data.table)    # manipulacao rapida
  library(glue)          # strings interpoladas
})

CODEBOOK_VERSION <- "v4.0"
PREDICOES_PATH   <- "dados/resultados/predicoes_corpus.parquet"
CORPUS_PATH      <- "dados/intermediarios/corpus_limpo_textual.parquet"
OUT_DIR          <- "dados/resultados"
OUT_CSV          <- file.path(OUT_DIR, "corpus_govai_classificado.csv")
OUT_DICT         <- file.path(OUT_DIR, "zenodo_dicionario_variaveis.csv")

# --------------------------------------------------------------------------
# 1. Leitura
# --------------------------------------------------------------------------
cat("Lendo predicoes...\n")
pred  <- as.data.table(read_parquet(PREDICOES_PATH))
cat(glue("  {nrow(pred)} artigos, {ncol(pred)} colunas\n\n"))

cat("Lendo corpus...\n")
meta <- as.data.table(read_parquet(CORPUS_PATH))
cat(glue("  {nrow(meta)} artigos, {ncol(meta)} colunas\n\n"))

# --------------------------------------------------------------------------
# 2. Harmonizacao de chave (id vs doc_id)
# --------------------------------------------------------------------------
# O pipeline interno usa a coluna "id"; o corpus pode expor "doc_id" ou ambas.
# Renomeia para "id" se necessario para o join.
if ("doc_id" %in% names(meta) && !"id" %in% names(meta)) {
  setnames(meta, "doc_id", "id")
}
if (!"id" %in% names(pred)) {
  stop("Coluna 'id' ausente em predicoes_corpus.parquet.")
}
if (!"id" %in% names(meta)) {
  stop("Coluna 'id' (ou 'doc_id') ausente em corpus_limpo_textual.parquet.")
}

# --------------------------------------------------------------------------
# 3. Selecao de colunas de metadados para exportacao
# --------------------------------------------------------------------------
META_COLS <- intersect(
  c("id", "doi", "titulo", "titulo_limpo", "nome_periodico", "ano",
    "cluster_origem", "subpopulacao_juridica", "disciplina_juridica"),
  names(meta)
)
meta_sel <- meta[, ..META_COLS]

# --------------------------------------------------------------------------
# 4. Join e ordenacao de colunas
# --------------------------------------------------------------------------
df <- merge(pred, meta_sel, by = "id", all.x = TRUE)
setorder(df, id)

# Colunas de exportacao (ordem legivel para deposito)
EXPORT_COLS <- c(
  # Identificacao
  "id", "doi", "nome_periodico", "ano",
  # Cluster
  "cluster_primario_pred", "cluster_certeza", "cluster_secundario_pred",
  paste0("cluster_", c("si", "ps", "sts", "law", "pa", "bcs"), "_prob"),
  # Epi -- tres flags independentes (Eixo 1 + Eixo 2)
  "epi_positivista_pred", "epi_interpretativa_pred", "epi_doutrinario_normativa_pred",
  # Epi -- derivadas
  "orientacao_proeminente", "inconclusiva", "epi_certeza",
  # Probabilidades epi (suporte a limiares alternativos)
  "epi_positivista_prob", "epi_interpretativa_prob", "epi_doutrinario_normativa_prob",
  # Estratos e flags contextuais
  "cluster_origem", "subpopulacao_juridica", "disciplina_juridica",
  # Rastreabilidade
  "modelo_final_cluster", "modelo_final_epi", "data_predicao"
)
EXPORT_COLS <- intersect(EXPORT_COLS, names(df))
df_out <- df[, ..EXPORT_COLS]

cat(glue("Colunas exportadas: {ncol(df_out)}\n"))
cat(glue("Artigos: {nrow(df_out)}\n\n"))

# --------------------------------------------------------------------------
# 5. Gravacao do CSV consolidado
# --------------------------------------------------------------------------
dir.create(OUT_DIR, recursive = TRUE, showWarnings = FALSE)
fwrite(df_out, OUT_CSV, bom = FALSE, encoding = "UTF-8")
cat(glue("CSV gravado: {OUT_CSV}\n"))
cat(glue("Tamanho: {round(file.size(OUT_CSV)/1e6, 2)} MB\n\n"))

# --------------------------------------------------------------------------
# 6. Dicionario de variaveis (manifesto Zenodo)
# --------------------------------------------------------------------------
# Descricoes alinhadas ao Codebook v4.0 e ao esquema epistemologico dois eixos.

dicionario <- data.table(
  coluna = character(),
  tipo   = character(),
  valores_possiveis = character(),
  descricao = character()
)

adicionar <- function(coluna, tipo, valores, descricao) {
  dicionario <<- rbind(dicionario, data.table(
    coluna = coluna, tipo = tipo,
    valores_possiveis = valores, descricao = descricao
  ))
}

# Identificacao
adicionar("id",             "string",  "ex: W2123456789",
  "Identificador unico do artigo (OpenAlex Work ID).")
adicionar("doi",            "string",  "ex: 10.1080/...",
  "Digital Object Identifier do artigo. NA quando ausente.")
adicionar("nome_periodico", "string",  "livre",
  "Nome do periodico de publicacao, normalizado pelo pipeline de limpeza.")
adicionar("ano",            "integer", "1990-2024",
  "Ano de publicacao.")

# Cluster disciplinar
adicionar("cluster_primario_pred", "string",
  "si | ps | sts | law | pa | bcs",
  glue("Cluster disciplinar primario atribuido pelo classificador (BERTimbau fine-tuned). ",
       "Seis categorias: SI (Sistemas de Informacao), PS (Political Science), ",
       "STS (Science and Technology Studies), Law (Ciencias Juridicas), ",
       "PA (Public Administration), BCS (Behavioral and Cognitive Sciences). ",
       "Codebook {CODEBOOK_VERSION}."))
adicionar("cluster_certeza", "float", "[0,1]",
  "Probabilidade softmax do cluster primario. Indica confianca do modelo.")
adicionar("cluster_secundario_pred", "string",
  "si | ps | sts | law | pa | bcs | NA",
  glue("Cluster secundario quando a diferenca de probabilidade entre o ",
       "primario e o segundo colocado for inferior a 0.15. NA caso contrario."))
for (cl in c("si", "ps", "sts", "law", "pa", "bcs")) {
  adicionar(glue("cluster_{cl}_prob"), "float", "[0,1]",
    glue("Probabilidade softmax do cluster {toupper(cl)}."))
}

# Epi -- Eixo 1 (orientacao_proeminente)
adicionar("epi_positivista_pred", "integer", "0 | 1",
  glue("Flag Empirico-Explicativo (EE): 1 se o artigo adota postura epistemologica ",
       "positivista/empirico-explicativa. Flag binario independente. ",
       "Eixo 1 do esquema dois eixos (Codebook {CODEBOOK_VERSION})."))
adicionar("epi_interpretativa_pred", "integer", "0 | 1",
  glue("Flag Interpretativo-Compreensivo (IC): 1 se o artigo adota postura epistemologica ",
       "interpretativa/compreensiva. Flag binario independente. ",
       "Eixo 1 do esquema dois eixos (Codebook {CODEBOOK_VERSION})."))

# Epi -- Eixo 2 (independente)
adicionar("epi_doutrinario_normativa_pred", "integer", "0 | 1",
  glue("Flag Doutrinario-Normativo (DN): 1 se o artigo adota postura epistemologica ",
       "doutrinaria ou normativa (producao de normas, prescricao de modalidades de acao, ",
       "ou fundamentos normativos juridicos). Regra disjuntiva: dn:modo OR dn:norm. ",
       "Eixo 2 independente; nao entra em orientacao_proeminente. ",
       "Codebook {CODEBOOK_VERSION}."))

# Epi -- derivadas
adicionar("orientacao_proeminente", "string",
  "positivista | interpretativa | mixed | nenhuma",
  glue("Orientacao epistemologica proeminente derivada dos flags EE e IC (Eixo 1). ",
       "Valores: 'positivista' (EE=1, IC=0), 'interpretativa' (EE=0, IC=1), ",
       "'mixed' (EE=1, IC=1), 'nenhuma' (EE=0, IC=0). ",
       "DN nao entra neste eixo. Derivacao deterministica via utils/derive_orientacao.py ",
       "(DA-09). Codebook {CODEBOOK_VERSION}."))
adicionar("inconclusiva", "integer", "0 | 1",
  glue("Flag de artigo inconclusivo: 1 sse os tres flags epi sao 0 (EE=0, IC=0, DN=0). ",
       "Distinto de 'nenhuma' em orientacao_proeminente, que indica apenas EE=IC=0 ",
       "(um artigo DN-only tem orientacao_proeminente='nenhuma' mas inconclusiva=0). ",
       "Codebook {CODEBOOK_VERSION}."))
adicionar("epi_certeza", "float", "[0,1]",
  "Decisividade media do modelo epi: mean(2 * |prob - 0.5|) sobre os tres flags. Indica confianca do modelo.")

# Probabilidades epi
for (cat in c("positivista", "interpretativa", "doutrinario_normativa")) {
  adicionar(glue("epi_{cat}_prob"), "float", "[0,1]",
    glue("Probabilidade sigmoid do flag epi_{cat}. ",
         "Limiar de classificacao: 0.5 (pred=1 se prob>=0.5)."))
}

# Estratos e flags contextuais
adicionar("cluster_origem", "string",
  "si | ps | sts | law | pa | bcs | misto",
  "Cluster de origem do artigo na coleta (stratum de amostragem). Pode divergir do cluster_primario_pred.")
adicionar("subpopulacao_juridica", "integer", "0 | 1",
  "Flag heuristico legado: 1 se o artigo foi coletado no estrato juridico da busca inicial. Ver disciplina_juridica para o construto canonico.")
adicionar("disciplina_juridica", "integer", "0 | 1",
  "Flag canonico de disciplina juridica: 1 se o artigo pertence a um dos 59 periodicos juridicos verificados (whitelist curada). Variavel instrumental de H4.")

# Rastreabilidade
adicionar("modelo_final_cluster", "string", "nome do diretorio",
  "Nome do diretorio do modelo BERTimbau fine-tuned usado para a classificacao de clusters.")
adicionar("modelo_final_epi",     "string", "nome do diretorio",
  "Nome do diretorio do modelo BERTimbau fine-tuned usado para a classificacao epistemologica.")
adicionar("data_predicao",        "string", "ISO 8601 UTC",
  "Data e hora (UTC) em que as predicoes foram geradas.")

# Gravacao do dicionario
fwrite(dicionario, OUT_DICT, bom = FALSE, encoding = "UTF-8")
cat(glue("Dicionario gravado: {OUT_DICT} ({nrow(dicionario)} variaveis)\n"))
cat(glue("Codebook de referencia: {CODEBOOK_VERSION}\n"))
