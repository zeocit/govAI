# ======================================================================
# 08_metricas_redes.R — Métricas descritivas de todas as 4 redes
# ======================================================================
# Manual §7.5 (v14): calcula métricas estruturais descritivas para as
# quatro redes geradas (coautoria, co-citação, coupling, co-ocorrência).
#
# Para cada rede, calcula:
#   - n_nodes, n_edges, density
#   - avg_degree, max_degree, gini_degree (desigualdade)
#   - transitivity (clustering coefficient global)
#   - avg_path_length_lcc (componente maior)
#   - diameter_lcc
#   - n_componentes, lcc_size (tamanho da maior componente)
#   - modularity_louvain
#   - assortativity_degree
#
# Input:
#   dados/redes/edges_coautoria.csv
#   dados/redes/edges_cocitacao.csv
#   dados/redes/edges_bib_coupling.csv
#   dados/redes/edges_cooccurrencia.csv
#
# Output:
#   dados/resultados/relatorio_metricas_redes.csv  — uma linha por rede
#   dados/resultados/relatorio_metricas_redes.json — idem em JSON (para pipeline)
#
# Dependências:
#   install.packages(c("data.table", "igraph"))
#
# Como executar:
#   Rscript 08_metricas_redes.R
#
# Autor: Fernando Leite | FAPESP | Refatoração v2 — 22/maio/2026
# ======================================================================

suppressPackageStartupMessages({
  library(data.table)
  library(igraph)
})

# ---- Configuração padrão -----------------------------------------------
REDES <- list(
  list(nome = "coautoria",    arquivo = "dados/redes/edges_coautoria.csv",    col_A = "author_A",  col_B = "author_B"),
  list(nome = "cocitacao",    arquivo = "dados/redes/edges_cocitacao.csv",    col_A = "ref_A",     col_B = "ref_B"),
  list(nome = "bib_coupling", arquivo = "dados/redes/edges_bib_coupling.csv", col_A = "artigo_A",  col_B = "artigo_B"),
  list(nome = "coocorrencia", arquivo = "dados/redes/edges_cooccurrencia.csv",col_A = "termo_A",   col_B = "termo_B")
)

OUTPUT_CSV  <- "dados/resultados/relatorio_metricas_redes.csv"
OUTPUT_JSON <- "dados/resultados/relatorio_metricas_redes.json"


# ---- Índice de Gini (desigualdade de grau) ─────────────────────────────

gini <- function(x) {
  x <- sort(x[x >= 0])
  n <- length(x)
  if (n == 0 || sum(x) == 0) return(NA_real_)
  2 * sum(seq_len(n) * x) / (n * sum(x)) - (n + 1) / n
}


# ---- Calcular métricas de uma rede ─────────────────────────────────────

metricas_rede <- function(nome, edges_dt, col_A, col_B) {
  if (nrow(edges_dt) == 0) {
    return(list(rede = nome, n_nodes = 0L, n_edges = 0L, status = "vazia"))
  }

  # Determinar coluna de peso. Preferência: "weight" (peso canônico — em
  # co-ocorrência é o NPMI>0 definido por 07g; Round 3, 2b), com fallback para
  # n_co_artigos (contagem bruta) e, por fim, peso unitário.
  peso_col <- intersect(c("weight", "npmi", "n_co_artigos"), colnames(edges_dt))
  peso <- if (length(peso_col) > 0) edges_dt[[peso_col[1]]] else rep(1L, nrow(edges_dt))

  g <- graph_from_data_frame(
    data.frame(from = edges_dt[[col_A]], to = edges_dt[[col_B]], weight = peso),
    directed = FALSE
  )

  n_nodes <- vcount(g)
  n_edges <- ecount(g)

  if (n_nodes == 0 || n_edges == 0) {
    return(list(rede = nome, n_nodes = n_nodes, n_edges = 0L, status = "sem_arestas"))
  }

  # Componentes
  comp      <- components(g)
  lcc_idx   <- which.max(comp$csize)
  lcc_size  <- comp$csize[lcc_idx]
  lcc_nodes <- which(comp$membership == lcc_idx)
  g_lcc     <- induced_subgraph(g, vids = lcc_nodes)

  # Métricas básicas
  deg      <- degree(g)
  avg_deg  <- mean(deg)
  max_deg  <- max(deg)
  gini_deg <- gini(deg)
  dens     <- edge_density(g)
  trans    <- transitivity(g, type = "global")
  assort   <- tryCatch(assortativity_degree(g, directed = FALSE), error = function(e) NA_real_)

  # Métricas na LCC (evitar problemas com grafo desconexo)
  avg_path <- tryCatch(
    mean_distance(g_lcc, weights = 1 / E(g_lcc)$weight, directed = FALSE),
    error = function(e) NA_real_
  )
  diam <- tryCatch(
    diameter(g_lcc, weights = 1 / E(g_lcc)$weight, directed = FALSE),
    error = function(e) NA_real_
  )

  # Modularidade Louvain
  lv <- tryCatch(cluster_louvain(g, weights = E(g)$weight), error = function(e) NULL)
  mod <- if (!is.null(lv)) modularity(lv) else NA_real_

  list(
    rede             = nome,
    n_nodes          = n_nodes,
    n_edges          = n_edges,
    density          = round(dens, 6),
    avg_degree       = round(avg_deg, 3),
    max_degree       = max_deg,
    gini_degree      = round(gini_deg, 4),
    transitivity     = round(trans, 4),
    avg_path_lcc     = round(avg_path, 4),
    diameter_lcc     = round(diam, 2),
    n_componentes    = comp$no,
    lcc_size_abs     = lcc_size,
    lcc_size_pct     = round(100 * lcc_size / n_nodes, 1),
    modularity_louvain = round(mod, 4),
    assortativity    = round(assort, 4),
    status           = "ok"
  )
}


# ---- Main --------------------------------------------------------------

main <- function() {
  message("[08] Calculando métricas de todas as redes...")

  resultados <- lapply(REDES, function(r) {
    if (!file.exists(r$arquivo)) {
      message("  ", r$nome, ": arquivo não encontrado (", r$arquivo, ")")
      return(list(rede = r$nome, status = "arquivo_ausente"))
    }
    message("  ", r$nome, ": lendo ", r$arquivo, "...")
    edges <- fread(r$arquivo)
    message("    ", nrow(edges), " arestas")
    metricas_rede(r$nome, edges, r$col_A, r$col_B)
  })

  # Imprimir sumário
  message("\n[08] Sumário de métricas:\n")
  for (r in resultados) {
    message("  --- ", toupper(r$rede), " ---")
    message("  Nós: ", r$n_nodes, " | Arestas: ", r$n_edges,
            " | Densidade: ", r$density)
    message("  Grau médio: ", r$avg_degree, " | Grau máximo: ", r$max_degree)
    message("  Clustering: ", r$transitivity,
            " | Modularidade Louvain: ", r$modularity_louvain)
    message("  LCC: ", r$lcc_size_abs, " nós (", r$lcc_size_pct, "%)",
            " | Path médio LCC: ", r$avg_path_lcc)
    message("")
  }

  # Gravar CSV
  df_out <- rbindlist(lapply(resultados, as.data.table), fill = TRUE)
  dir.create(dirname(OUTPUT_CSV), recursive = TRUE, showWarnings = FALSE)
  fwrite(df_out, OUTPUT_CSV)
  message("[08] CSV gravado: ", OUTPUT_CSV)

  # Gravar JSON
  library(jsonlite, warn.conflicts = FALSE)
  writeLines(toJSON(resultados, auto_unbox = TRUE, pretty = TRUE), OUTPUT_JSON)
  message("[08] JSON gravado: ", OUTPUT_JSON)
}

if (sys.nframe() == 0) main()
