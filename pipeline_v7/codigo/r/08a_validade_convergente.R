# 08a_validade_convergente.R — Validade convergente BERTopic × Quadro Integrado
# ==============================================================================
# Protocolo de Anotação §7.6.1, Manual §V.5bis (validade externa).
#
# Para cada cluster, mede a sobreposição lexical entre os top-N termos de cada
# tópico BERTopic (rodado sobre o subconjunto de artigos atribuídos ao cluster
# como cluster_primario) e o léxico de referência do cluster (extraído do
# Quadro Integrado, Apêndice M do Protocolo).
#
# Métricas:
#   - Jaccard:   |T ∩ L| / |T ∪ L|
#   - Cobertura: |T ∩ L| / |T|
#
# Critério de validade convergente (Protocolo §7.6.1):
#   - >= 80% tópicos com Jaccard máximo no cluster de origem: validade confirmada
#   - 60-80%: validade parcial — inspecionar divergentes (fronteira potencial)
#   - <  60%: alerta — auditoria do GS do cluster
#
# Input:
#   dados/intermediarios/bertopic_topics_por_cluster.parquet
#     Colunas mínimas: cluster_origem, topic_id, top_terms (lista ou string)
#   protocolo/lexico_clusters.csv
#     Colunas: cluster, lemma
#
# Output:
#   dados/intermediarios/validade_convergente.parquet
#   relatorios/validade_convergente_resumo.csv
#
# Autor: Fernando Leite | FAPESP | v3 — 28/maio/2026
#   Refatoração após auditoria QA: removida metaprogramação frágil
#   (bquote + !!!setNames), mapeamento de cluster_max_jaccard tornado
#   imune a ordem de colunas, atomic write, contrato de schema robusto a
#   top_terms vindo como lista/vetor/string única, validação explícita
#   de léxicos faltantes.

suppressPackageStartupMessages({
  library(arrow)
  library(dplyr)
  library(readr)
  library(stringr)
})

# ── Configuração ──────────────────────────────────────────────────────────────
INPUT_TOPICS   <- "dados/intermediarios/bertopic_topics_por_cluster.parquet"
INPUT_LEXICO   <- "protocolo/lexico_clusters.csv"
OUTPUT_DETALHE <- "dados/intermediarios/validade_convergente.parquet"
OUTPUT_RESUMO  <- "relatorios/validade_convergente_resumo.csv"

CLUSTERS          <- c("si", "ps", "sts", "law", "pa", "bcs")
N_TOP_TERMS       <- 30
LIMIAR_CONFIRMADA <- 0.80
LIMIAR_PARCIAL    <- 0.60

# ── Funções ───────────────────────────────────────────────────────────────────
normalizar_termo <- function(termo) {
  # Inclui ñ e diacríticos europeus comuns; preserva underscore (termos
  # compostos do tipo machine_learning); colapsa espaços/hífens múltiplos.
  termo |>
    str_to_lower() |>
    str_trim() |>
    str_replace_all("[^a-zñáàâãäéèêëíîïóôõöúûüç_/ -]", "") |>
    str_squish()
}

jaccard <- function(set_a, set_b) {
  if (length(set_a) == 0 && length(set_b) == 0) return(0)
  u <- length(union(set_a, set_b))
  if (u == 0) return(0)
  length(intersect(set_a, set_b)) / u
}

cobertura <- function(set_a, set_b) {
  if (length(set_a) == 0) return(0)
  length(intersect(set_a, set_b)) / length(set_a)
}

# Escrita atômica: .tmp → rename. Protege contra arquivos truncados em caso
# de crash durante a gravação.
write_parquet_atomic <- function(df, path) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  tmp <- paste0(path, ".tmp")
  write_parquet(df, tmp)
  if (!file.rename(tmp, path)) {
    stop("Falha no rename atômico de ", tmp, " → ", path)
  }
}

# ── Léxicos ───────────────────────────────────────────────────────────────────
message("Lendo léxico do Quadro Integrado: ", INPUT_LEXICO)
lexico_df <- read_csv(INPUT_LEXICO, show_col_types = FALSE) |>
  mutate(lemma = normalizar_termo(lemma)) |>
  filter(nchar(lemma) > 0, cluster %in% CLUSTERS)

lexicos <- split(lexico_df$lemma, lexico_df$cluster) |>
  lapply(unique)

# Aviso explícito sobre clusters sem léxico (silenciosamente zerado na versão original)
faltantes <- setdiff(CLUSTERS, names(lexicos))
if (length(faltantes) > 0) {
  warning("Léxico vazio para cluster(s): ", paste(faltantes, collapse = ", "),
          " — validade convergente desses clusters será zero por construção.")
  for (c in faltantes) lexicos[[c]] <- character(0)
}

message("  Tamanho dos léxicos:")
for (c in CLUSTERS) {
  message("    ", c, ": ", length(lexicos[[c]]), " lemas")
}

# ── Tópicos BERTopic ──────────────────────────────────────────────────────────
if (!file.exists(INPUT_TOPICS)) {
  stop("Arquivo de tópicos não encontrado: ", INPUT_TOPICS,
       "\n(Esperado: produzido pelo pipeline BERTopic — Parte VI do Manual)")
}

message("Lendo tópicos BERTopic: ", INPUT_TOPICS)
topics_df <- read_parquet(INPUT_TOPICS)
required <- c("cluster_origem", "topic_id", "top_terms")
missing  <- setdiff(required, names(topics_df))
if (length(missing) > 0) {
  stop("Colunas ausentes no arquivo de tópicos: ", paste(missing, collapse = ", "))
}
message("  ", nrow(topics_df), " tópicos | ",
        length(unique(topics_df$cluster_origem)), " clusters cobertos")

# Normalização robusta a top_terms ser lista, vetor, ou string única
# delimitada por vírgula/ponto-e-vírgula/pipe
top_terms_norm <- lapply(topics_df$top_terms, function(x) {
  termos <- if (is.list(x)) {
    unlist(x)
  } else if (is.character(x) && length(x) == 1) {
    strsplit(x, "[,;|]\\s*")[[1]]
  } else {
    as.character(x)
  }
  unique(normalizar_termo(head(termos, N_TOP_TERMS)))
})

# ── Cálculo das métricas ──────────────────────────────────────────────────────
# Forma idiomática direta — uma coluna por cluster, gerada explicitamente.
# Substitui o bloco bquote(...) + !!!setNames(...) da versão anterior, que
# dependia de propriedades não-documentadas de tidyeval dentro de rowwise().
resultados <- topics_df
resultados$top_terms_norm <- top_terms_norm

for (c in CLUSTERS) {
  resultados[[paste0("jaccard_", c)]] <- vapply(
    top_terms_norm,
    \(tt) jaccard(tt, lexicos[[c]]),
    numeric(1)
  )
  resultados[[paste0("cobertura_", c)]] <- vapply(
    top_terms_norm,
    \(tt) cobertura(tt, lexicos[[c]]),
    numeric(1)
  )
}

# Mapeamento de cluster vencedor — explícito por nome de coluna.
# A versão anterior usava CLUSTERS[max.col(across(starts_with("jaccard_")))],
# que assumia que across() preservasse a ordem de criação das colunas —
# propriedade não-documentada e quebrável em versões futuras do dplyr.
jaccard_cols <- paste0("jaccard_", CLUSTERS)
mat_j <- as.matrix(resultados[, jaccard_cols, drop = FALSE])
resultados$cluster_max_jaccard <- CLUSTERS[max.col(mat_j, ties.method = "first")]
resultados$valida <- resultados$cluster_max_jaccard == resultados$cluster_origem

# ── Resumo por cluster ────────────────────────────────────────────────────────
resumo <- resultados |>
  group_by(cluster_origem) |>
  summarise(
    n_topicos   = n(),
    n_validos   = sum(valida),
    pct_validos = n_validos / n_topicos,
    .groups = "drop"
  ) |>
  mutate(
    status = case_when(
      pct_validos >= LIMIAR_CONFIRMADA ~ "confirmada",
      pct_validos >= LIMIAR_PARCIAL    ~ "parcial",
      TRUE                             ~ "alerta"
    )
  )

# ── Gravar outputs (atomicamente) ─────────────────────────────────────────────
# Remove top_terms_norm (list-column) do parquet final para manter schema
# planos e compatível com leitura cross-language.
write_parquet_atomic(
  resultados |> select(-top_terms_norm),
  OUTPUT_DETALHE
)

dir.create(dirname(OUTPUT_RESUMO), recursive = TRUE, showWarnings = FALSE)
tmp_resumo <- paste0(OUTPUT_RESUMO, ".tmp")
write_csv(resumo, tmp_resumo)
file.rename(tmp_resumo, OUTPUT_RESUMO)

message("\n=== Resumo da validade convergente ===")
print(resumo)
message("\nDetalhamento gravado em: ", OUTPUT_DETALHE)
message("Resumo gravado em:        ", OUTPUT_RESUMO)

# ── Alertas explícitos ────────────────────────────────────────────────────────
alertas <- resumo |> filter(status == "alerta")
if (nrow(alertas) > 0) {
  message("\n⚠ ALERTA: os seguintes clusters falharam o critério de validade convergente:")
  print(alertas)
  message("Ação recomendada: auditoria do Gold Standard desses clusters (Protocolo §7.6.1).")
}
