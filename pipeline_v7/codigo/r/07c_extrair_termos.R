# ======================================================================
# 07c_extrair_termos.R — Extração de termos e TF-IDF do abstract
# ======================================================================
# Manual §6.5 (v14): extrai n-gramas (1-3) dos abstracts limpos,
# calcula TF-IDF por termo, e (opcionalmente) distribui frequência
# por cluster disciplinar.
#
# Input:
#   dados/intermediarios/corpus_limpo_textual.parquet
#   dados/resultados/predicoes_corpus.parquet   (opcional — para freq por cluster)
#
# Output:
#   dados/redes/nodes_termos.csv
#
# Schema (Codebook v2.1):
#   termo            string   n-grama limpo
#   freq_global      int      nº total de ocorrências no corpus (soma TF)
#   df               int      document frequency (nº de artigos que contêm o termo)
#   idf              double   log(N / df) onde N = total de artigos
#   tf_idf_medio     double   média de TF-IDF por artigo onde o termo ocorre
#   freq_por_cluster string   "si:42;ps:13;..." (vazio se predicoes_corpus ausente)
#
# Estratégia de extração (sem udpipe — tokenização simples + stopwords):
#   1. Tokenizar abstract por espaço (após limpeza textual)
#   2. Filtrar stopwords (PT + EN) e tokens curtos (< 3 chars)
#   3. Extrair unigramas, bigramas e trigramas por deslizamento de janela
#   4. Filtrar por frequência mínima (DF_MIN artigos)
#   5. Calcular TF-IDF
#
# Nota — udpipe (lematização + POS filtering):
#   Para maior qualidade linguística, ver função opcional anotar_com_udpipe()
#   abaixo. Instalar: install.packages("udpipe")
#   Baixar modelos (uma vez):
#     library(udpipe)
#     udpipe_download_model("portuguese-bosque")
#     udpipe_download_model("english-ewt")
#
# Implementação vetorizada (Gemini sugeriu, refinada por auditoria FL):
#   - Passa vetor completo de textos para udpipe_annotate (otimização C++)
#   - parser="none" (não precisamos de análise sintática)
#   - Flag opcional incluir_verbos: VERB carrega sinal para camada epi
#     ("modelamos"=positivista, "interpretamos"=interpretativa).
#     Default TRUE para compatibilidade com análises da camada epi.
#
# Dependências:
#   install.packages(c("arrow", "data.table", "stringi"))
#
# Como executar:
#   Rscript 07c_extrair_termos.R
#   Rscript 07c_extrair_termos.R --n-max 2 --df-min 10  # só uni e bigramas, min 10 docs
#
# Autor: Fernando Leite | FAPESP | Refatoração v2 — 22/maio/2026
# ======================================================================

suppressPackageStartupMessages({
  library(arrow)
  library(data.table)
  library(stringi)
})

# ---- Configuração padrão -----------------------------------------------
CORPUS_PATH   <- "dados/intermediarios/corpus_limpo_textual.parquet"
PRED_PATH     <- "dados/resultados/predicoes_corpus.parquet"
OUTPUT_PATH   <- "dados/redes/nodes_termos.csv"

N_MAX   <- 3L      # tamanho máximo do n-grama
DF_MIN  <- 5L      # mínimo de documentos para um termo ser incluído
CLUSTERS <- c("si", "ps", "sts", "law", "pa", "bcs")

# ---- Stopwords (PT + EN) -----------------------------------------------
STOPWORDS <- c(
  # PT
  "de","da","do","das","dos","em","na","no","nas","nos","com","por","para",
  "que","se","um","uma","uns","umas","os","as","ao","aos","à","às","ou","e",
  "mas","não","este","esta","estes","estas","esse","essa","isso","isto",
  "ele","ela","eles","elas","seu","sua","seus","suas","meu","minha","nos",
  "foi","são","mais","como","bem","muito","também","já","quando","ainda",
  # EN
  "the","a","an","and","or","but","in","on","at","to","for","of","with",
  "is","are","was","were","be","been","has","have","had","that","this",
  "these","those","it","its","by","from","as","at","we","our","their",
  "which","who","how","what","where","when","while","than","can","will",
  "may","not","no","also","such","both","each","more","most","there","been",
  "using","used","use","based","study","paper","results","data","analysis",
  "research","approach","method","model","framework","between","across"
)

# ---- Anotação opcional com udpipe (vetorizada) -------------------------
# Função para uso opcional quando se deseja lematização + POS filtering.
# Substituir a chamada de tokenize_simples() pela saída desta função.
anotar_com_udpipe <- function(dt_docs, modelo_pt = NULL, modelo_en = NULL,
                                incluir_verbos = TRUE) {
  if (!requireNamespace("udpipe", quietly = TRUE)) {
    stop("Pacote 'udpipe' não instalado. install.packages('udpipe')")
  }
  library(udpipe)

  # Tags de POS a manter
  # NOUN/ADJ/PROPN: termos de conteúdo (default da literatura cientométrica)
  # VERB: opcional, carrega sinal metodológico para a camada epi
  #   (e.g., "modelamos"=positivista, "interpretamos"=interpretativa)
  tags_validas <- if (incluir_verbos) {
    c("NOUN", "ADJ", "PROPN", "VERB")
  } else {
    c("NOUN", "ADJ", "PROPN")
  }

  # Separar por idioma e anotar com o modelo correto
  dt_pt <- dt_docs[idioma_detectado == "pt"]
  dt_en <- dt_docs[idioma_detectado == "en"]

  resultados <- list()

  if (nrow(dt_pt) > 0 && !is.null(modelo_pt)) {
    # OTIMIZAÇÃO: passar vetor completo de uma só vez (interno em C++)
    anot_pt <- udpipe_annotate(
      modelo_pt,
      x = dt_pt$texto,
      doc_id = dt_pt$id,
      parser = "none"   # Sem análise sintática (ganho 2x de velocidade)
    )
    resultados[["pt"]] <- as.data.table(anot_pt)
  }

  if (nrow(dt_en) > 0 && !is.null(modelo_en)) {
    anot_en <- udpipe_annotate(
      modelo_en,
      x = dt_en$texto,
      doc_id = dt_en$id,
      parser = "none"
    )
    resultados[["en"]] <- as.data.table(anot_en)
  }

  if (length(resultados) == 0) {
    stop("Nenhum modelo udpipe disponível para os idiomas presentes.")
  }

  dt_anotado <- rbindlist(resultados, use.names = TRUE, fill = TRUE)
  dt_filtrado <- dt_anotado[upos %in% tags_validas & !is.na(lemma)]
  dt_filtrado[, lemma_lower := stri_trans_tolower(lemma)]
  dt_filtrado[, lemma_lower := stri_trans_general(lemma_lower, "NFC")]
  setnames(dt_filtrado, "doc_id", "id")
  return(dt_filtrado[, .(id, token = lemma_lower, upos)])
}


# ---- Tokenização e extração de n-gramas --------------------------------

clean_tokens <- function(texto) {
  if (is.na(texto) || nchar(texto) < 10) return(character(0))
  # Lowercase e normalização
  x <- stri_trans_tolower(stri_trans_nfc(texto))
  # Remover caracteres não-alfanuméricos (manter espaços)
  x <- stri_replace_all_regex(x, "[^a-záéíóúâêîôûãõàèìòùüçñ0-9\\s]", " ")
  x <- stri_replace_all_regex(x, "\\s+", " ")
  x <- stri_trim_both(x)
  tokens <- stri_split_fixed(x, " ")[[1]]
  # Filtrar: stopwords, tokens curtos, tokens puramente numéricos
  tokens <- tokens[
    nchar(tokens) >= 3 &
    !tokens %in% STOPWORDS &
    !stri_detect_regex(tokens, "^[0-9]+$")
  ]
  tokens
}

extrair_ngramas <- function(tokens, n_max) {
  if (length(tokens) == 0) return(character(0))
  out <- tokens  # unigramas
  if (n_max >= 2 && length(tokens) >= 2) {
    bigrams <- paste(tokens[-length(tokens)], tokens[-1])
    out <- c(out, bigrams)
  }
  if (n_max >= 3 && length(tokens) >= 3) {
    trigrams <- paste(tokens[-c(length(tokens)-1, length(tokens))],
                      tokens[-c(1, length(tokens))],
                      tokens[-c(1:2)])
    out <- c(out, trigrams)
  }
  out
}

# ---- Cálculo de TF-IDF -------------------------------------------------

calcular_tfidf <- function(dt_long, n_docs) {
  # dt_long: data.table(id, termo, tf) — uma linha por (artigo, termo)
  # Calcular DF por termo
  df_por_termo <- dt_long[, .(df = .N, freq_global = sum(tf)), by = termo]
  df_por_termo[, idf := log(n_docs / df)]
  # TF-IDF médio por termo (sobre artigos que contêm o termo)
  tfidf_por_artigo <- dt_long[df_por_termo, on = "termo", nomatch = 0L]
  tfidf_por_artigo[, tf_idf := tf * idf]
  tfidf_medio <- tfidf_por_artigo[, .(tf_idf_medio = mean(tf_idf)), by = termo]
  resultado <- merge(df_por_termo, tfidf_medio, by = "termo")
  resultado
}

# ---- Main --------------------------------------------------------------

main <- function(corpus_path, pred_path, output_path, n_max, df_min) {
  message("[07c] Lendo corpus...")
  df <- as.data.table(read_parquet(corpus_path, col_select = c("id", "abstract_limpo")))
  n_docs <- nrow(df)
  message("  ", n_docs, " artigos")

  message("[07c] Extraindo n-gramas (n_max=", n_max, ")...")
  # Para cada artigo, tokenizar e gerar n-gramas com TF
  resultado_list <- lapply(seq_len(nrow(df)), function(i) {
    tokens <- clean_tokens(df$abstract_limpo[i])
    ngramas <- extrair_ngramas(tokens, n_max)
    if (length(ngramas) == 0) return(NULL)
    # TF por termo no artigo (normalizado)
    tab <- table(ngramas)
    n_total <- sum(tab)
    data.table(
      id    = df$id[i],
      termo = names(tab),
      tf    = as.numeric(tab) / n_total
    )
  })
  dt_long <- rbindlist(resultado_list, use.names = TRUE)
  message("  ", format(nrow(dt_long), big.mark = "."), " pares (artigo, termo)")

  # Filtrar por DF mínimo (antes de calcular TF-IDF, para eficiência)
  df_counts <- dt_long[, .(df_check = .N), by = termo]
  termos_validos <- df_counts[df_check >= df_min, termo]
  dt_long <- dt_long[termo %in% termos_validos]
  message("  ", length(termos_validos), " termos com DF >= ", df_min)

  message("[07c] Calculando TF-IDF...")
  nodes_termos <- calcular_tfidf(dt_long, n_docs)
  setorder(nodes_termos, -freq_global)

  # ---- Frequência por cluster (opcional) --------------------------------
  nodes_termos[, freq_por_cluster := ""]
  if (file.exists(pred_path)) {
    message("[07c] Calculando freq por cluster (predicoes_corpus.parquet)...")
    pred <- as.data.table(read_parquet(pred_path,
                                       col_select = c("id", "cluster_primario_pred")))
    dt_com_cluster <- merge(dt_long, pred, by = "id", all.x = TRUE)
    freq_cluster <- dt_com_cluster[
      !is.na(cluster_primario_pred),
      .(n_artigos_cluster = .N),
      by = .(termo, cluster_primario_pred)
    ]
    # Para cada termo, concatenar "cluster:n_artigos"
    freq_cluster_str <- freq_cluster[, {
      partes <- paste(cluster_primario_pred, n_artigos_cluster, sep = ":")
      .(freq_por_cluster = paste(sort(partes), collapse = ";"))
    }, by = termo]
    nodes_termos <- merge(nodes_termos, freq_cluster_str, by = "termo", all.x = TRUE)
    nodes_termos[is.na(freq_por_cluster), freq_por_cluster := ""]
  } else {
    message("  predicoes_corpus.parquet não encontrado — freq_por_cluster vazio")
  }

  # Reordenar colunas canonicamente
  setcolorder(nodes_termos, c("termo", "freq_global", "df", "idf",
                               "tf_idf_medio", "freq_por_cluster"))

  # Estatísticas
  message("[07c] Estatísticas:")
  message("  Termos únicos:          ", nrow(nodes_termos))
  message("  Top-10 por freq_global:")
  print(head(nodes_termos[, .(termo, freq_global, df, idf)], 10))

  dir.create(dirname(output_path), recursive = TRUE, showWarnings = FALSE)
  fwrite(nodes_termos, output_path)
  message("[07c] Gravado: ", output_path)
}

# ---- CLI ---------------------------------------------------------------
if (sys.nframe() == 0) {
  args <- commandArgs(trailingOnly = TRUE)
  parse_arg <- function(key, default) {
    idx <- which(args == key)
    if (length(idx) == 0L || idx >= length(args)) return(default)
    args[idx + 1L]
  }
  main(
    corpus_path = parse_arg("--corpus", CORPUS_PATH),
    pred_path   = parse_arg("--predicoes", PRED_PATH),
    output_path = parse_arg("--output", OUTPUT_PATH),
    n_max       = as.integer(parse_arg("--n-max", N_MAX)),
    df_min      = as.integer(parse_arg("--df-min", DF_MIN))
  )
}
