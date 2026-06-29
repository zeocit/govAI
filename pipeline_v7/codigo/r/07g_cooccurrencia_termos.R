# ======================================================================
# 07g_cooccurrencia_termos.R — Rede de co-ocorrência de termos
# ======================================================================
# Manual §7.4 (v14): constrói a rede de co-ocorrência de termos a partir
# do abstract. Dois termos co-ocorrem quando aparecem no mesmo abstract.
# Peso: PMI (pointwise mutual information).
#
# Input:
#   dados/intermediarios/corpus_limpo_textual.parquet
#   dados/redes/nodes_termos.csv   (lista de termos válidos, do 07c)
#
# Output:
#   dados/redes/edges_cooccurrencia.csv
#
# Schema (Codebook v2.1):
#   termo_A         string
#   termo_B         string
#   n_co_artigos    int    nº de artigos em que ambos aparecem
#   pmi             double pointwise mutual information
#   npmi            double normalized PMI [-1, 1]; 1 = sempre juntos, -1 = nunca
#
# Estratégia:
#   1. Construir matriz binária termo × artigo (esparsa, via Matrix)
#   2. Co-ocorrência = t(M) %*% M → matriz artigo × artigo (direto)
#      Ou mais eficiente: M %*% t(M) → matriz termo × termo (co-ocorrências)
#   3. PMI = log(P(A,B) / P(A)*P(B))  com N = nº artigos
#   4. Filtrar por PMI_MIN e N_CO_MIN para remover ruído
#
# Dependências:
#   install.packages(c("arrow", "data.table", "Matrix", "stringi"))
#
# Como executar:
#   Rscript 07g_cooccurrencia_termos.R
#   Rscript 07g_cooccurrencia_termos.R --n-co-min 10 --pmi-min 1.0
#
# Nota de escala:
#   Para corpus de 21k artigos e 5k termos: matriz M é 5k × 21k = 105M células,
#   mas esparsa (~1-5% não-zero). A multiplicação esparsa M %*% t(M) é
#   muito eficiente com a biblioteca Matrix. Esperar ~30-60s no M5 Max.
#
# Autor: Fernando Leite | FAPESP | Refatoração v2 — 22/maio/2026
# ======================================================================

suppressPackageStartupMessages({
  library(arrow)
  library(data.table)
  library(Matrix)
  library(stringi)
})

# ---- Configuração padrão -----------------------------------------------
CORPUS_PATH  <- "dados/intermediarios/corpus_limpo_textual.parquet"
TERMOS_PATH  <- "dados/redes/nodes_termos.csv"
OUTPUT_PATH  <- "dados/redes/edges_cooccurrencia.csv"

N_CO_MIN  <- 5L     # mínimo de artigos com co-ocorrência
PMI_MIN   <- 0.5    # mínimo de PMI para incluir aresta (filtro de ruído)
N_MAX     <- 3L     # max n-grama (deve ser igual ao usado em 07c)

# ---- Reutilizar extração de n-gramas do 07c ----------------------------

STOPWORDS <- c(
  "de","da","do","das","dos","em","na","no","nas","nos","com","por","para",
  "que","se","um","uma","uns","umas","os","as","ao","aos","à","às","ou","e",
  "mas","não","este","esta","estes","estas","esse","essa","isso","isto",
  "ele","ela","eles","elas","seu","sua","seus","suas","meu","minha",
  "foi","são","mais","como","bem","muito","também","já","quando","ainda",
  "the","a","an","and","or","but","in","on","at","to","for","of","with",
  "is","are","was","were","be","been","has","have","had","that","this",
  "these","those","it","its","by","from","as","we","our","their","which",
  "who","how","what","where","when","while","than","can","will","may",
  "not","no","also","such","both","each","more","most","there","using",
  "used","use","based","study","paper","results","data","analysis",
  "research","approach","method","model","framework","between","across"
)

clean_tokens_g <- function(texto) {
  if (is.na(texto) || nchar(texto) < 10) return(character(0))
  x <- stri_trans_tolower(stri_trans_nfc(texto))
  x <- stri_replace_all_regex(x, "[^a-záéíóúâêîôûãõàèìòùüçñ0-9\\s]", " ")
  x <- stri_replace_all_regex(x, "\\s+", " ")
  tokens <- stri_split_fixed(stri_trim_both(x), " ")[[1]]
  tokens[nchar(tokens) >= 3 & !tokens %in% STOPWORDS &
         !stri_detect_regex(tokens, "^[0-9]+$")]
}

extrair_ngramas_g <- function(tokens, n_max) {
  if (length(tokens) == 0) return(character(0))
  out <- tokens
  if (n_max >= 2 && length(tokens) >= 2)
    out <- c(out, paste(tokens[-length(tokens)], tokens[-1]))
  if (n_max >= 3 && length(tokens) >= 3)
    out <- c(out, paste(tokens[-c(length(tokens)-1, length(tokens))],
                        tokens[-c(1, length(tokens))],
                        tokens[-c(1:2)]))
  unique(out)    # binário por artigo (presença/ausência)
}


# ---- Construção da matriz esparsa ---------------------------------------

construir_matriz_binaria <- function(df_corpus, termos_validos) {
  message("  Extraindo presença de termos por artigo...")
  n_docs  <- nrow(df_corpus)
  n_terms <- length(termos_validos)
  termos_idx <- setNames(seq_along(termos_validos), termos_validos)

  # Listas de índices para construção esparsa (i=termo, j=artigo)
  i_list <- integer(0)
  j_list <- integer(0)

  for (j in seq_len(n_docs)) {
    tokens  <- clean_tokens_g(df_corpus$abstract_limpo[j])
    ngramas <- extrair_ngramas_g(tokens, N_MAX)
    ngramas_validos <- ngramas[ngramas %in% termos_validos]
    if (length(ngramas_validos) == 0) next
    i_idx <- termos_idx[ngramas_validos]
    i_list <- c(i_list, i_idx)
    j_list <- c(j_list, rep(j, length(i_idx)))
  }

  M <- sparseMatrix(i = i_list, j = j_list,
                    x = 1, dims = c(n_terms, n_docs),
                    dimnames = list(termos_validos, df_corpus$id))
  message("  Matriz binária: ", n_terms, " × ", n_docs,
          " (", round(100 * nnzero(M) / (n_terms * n_docs), 2), "% não-zero)")
  M
}


# ---- PMI e NPMI --------------------------------------------------------

calcular_pmi <- function(M, n_co_min, pmi_min) {
  message("  Calculando co-ocorrências (produto matricial esparso)...")
  # Co-ocorrência = número de artigos em que termos i e j aparecem juntos
  # CoOc = M %*% t(M) → matrix n_terms × n_terms
  # Diagonal = df de cada termo
  CoOc <- tcrossprod(M)   # M %*% t(M), eficiente para esparso

  n_docs  <- ncol(M)
  df_vetor <- diag(CoOc)   # df de cada termo (ocorrências na diagonal)

  message("  Extraindo pares com co-ocorrência >= ", n_co_min, "...")
  # Converter para triplet (i, j, valor), apenas triângulo superior, excl diagonal
  CoOc_upper <- triu(CoOc, k = 1)
  cx <- summary(CoOc_upper)   # data.frame com (i, j, x)
  cx <- cx[cx$x >= n_co_min, ]
  setDT(cx)
  setnames(cx, c("idx_A", "idx_B", "n_co_artigos"))

  if (nrow(cx) == 0) return(data.table())

  termos_nomes <- rownames(CoOc)
  cx[, termo_A := termos_nomes[idx_A]]
  cx[, termo_B := termos_nomes[idx_B]]

  # PMI = log2(P(A,B) / (P(A) * P(B)))
  # P(A,B) = n_co / N; P(A) = df_A / N; P(B) = df_B / N
  df_A <- df_vetor[cx$idx_A]
  df_B <- df_vetor[cx$idx_B]
  p_ab <- cx$n_co_artigos / n_docs
  p_a  <- df_A / n_docs
  p_b  <- df_B / n_docs

  cx[, pmi  := log2(p_ab / (p_a * p_b))]
  # NPMI = PMI / (-log2(P(A,B)))  → [-1, 1]
  cx[, npmi := pmi / (-log2(pmax(p_ab, 1e-12)))]

  # Filtrar por PMI mínimo
  cx <- cx[pmi >= pmi_min]
  cx[, c("idx_A", "idx_B") := NULL]

  # Peso canônico de produção (Round 3, 2b): weight = NPMI, restrito a NPMI > 0
  # (associação acima do acaso). NPMI normaliza pela frequência marginal, ao
  # contrário da contagem bruta n_co_artigos — que fica preservada como coluna
  # para análise de sensibilidade na fase de escrita. Arestas com NPMI ≤ 0
  # (associação igual/abaixo do acaso) não entram na rede ponderada.
  cx <- cx[npmi > 0]
  cx[, weight := npmi]
  setcolorder(cx, c("termo_A", "termo_B", "weight", "npmi", "pmi", "n_co_artigos"))
  setorder(cx, -weight)
  cx
}


# ---- Main --------------------------------------------------------------

main <- function(corpus_path, termos_path, output_path, n_co_min, pmi_min) {
  message("[07g] Lendo corpus...")
  df <- as.data.table(read_parquet(corpus_path, col_select = c("id", "abstract_limpo")))
  message("  ", nrow(df), " artigos")

  if (!file.exists(termos_path)) {
    stop("nodes_termos.csv não encontrado. Execute 07c_extrair_termos.R primeiro.")
  }
  termos_validos <- fread(termos_path, select = "termo")$termo
  message("  ", length(termos_validos), " termos válidos de 07c")

  message("[07g] Construindo matriz binária termo × artigo...")
  M <- construir_matriz_binaria(df, termos_validos)

  message("[07g] Calculando PMI...")
  edges <- calcular_pmi(M, n_co_min, pmi_min)

  if (nrow(edges) == 0) {
    message("Nenhuma co-ocorrência com os filtros especificados.")
    return(invisible(NULL))
  }

  message("[07g] Estatísticas:")
  message("  Arestas de co-ocorrência: ", nrow(edges))
  message("  PMI médio: ", round(mean(edges$pmi), 3))
  message("  NPMI médio: ", round(mean(edges$npmi), 3))
  message("  Top-10 por NPMI:")
  print(head(edges[, .(termo_A, termo_B, n_co_artigos, pmi = round(pmi, 2),
                       npmi = round(npmi, 3))], 10))

  dir.create(dirname(output_path), recursive = TRUE, showWarnings = FALSE)
  fwrite(edges, output_path)
  message("[07g] Gravado: ", output_path)
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
    corpus_path = parse_arg("--corpus",    CORPUS_PATH),
    termos_path = parse_arg("--termos",    TERMOS_PATH),
    output_path = parse_arg("--output",    OUTPUT_PATH),
    n_co_min    = as.integer(parse_arg("--n-co-min", N_CO_MIN)),
    pmi_min     = as.numeric(parse_arg("--pmi-min",  PMI_MIN))
  )
}
