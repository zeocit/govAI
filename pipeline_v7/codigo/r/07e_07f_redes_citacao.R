# ======================================================================
# 07e_rede_cocitacao.R — Rede de co-citação
# 07f_rede_coupling.R  — Rede de acoplamento bibliográfico (bibliographic coupling)
# ======================================================================
# Ambas as redes derivam de edges_citacoes.csv (produzido por 02f).
# São implementadas no mesmo arquivo para reaproveitar a carga de dados.
#
# ── Co-citação (07e) ────────────────────────────────────────────────────
# Definição: dois artigos (ref_A, ref_B) são co-citados quando ao menos
# um artigo do corpus os cita juntos. Peso = nº de artigos citantes.
# Este é um rede de REFERÊNCIAS (não de artigos do corpus).
# Útil para: identificar núcleos intelectuais, tradições teóricas.
#
# ── Acoplamento bibliográfico (07f) ─────────────────────────────────────
# Definição: dois artigos do corpus (art_A, art_B) compartilham referências.
# Peso = nº de referências compartilhadas.
# Útil para: clustering temático, similaridade entre artigos.
#
# Input:
#   dados/redes/edges_citacoes.csv (ou .parquet)
#   dados/redes/nodes_autores.csv  (para enriquecer nodes de co-citação)
#
# Outputs:
#   dados/redes/edges_cocitacao.csv         — rede de co-citação
#   dados/redes/nodes_cocitacao_metricas.csv
#   dados/redes/edges_bib_coupling.csv      — rede de coupling
#   dados/redes/nodes_coupling_metricas.csv
#
# Schema (Codebook v2.1):
#   edges_cocitacao.csv:
#       ref_A, ref_B (OpenAlex IDs), weight (nº co-artigos)
#   edges_bib_coupling.csv:
#       artigo_A, artigo_B (OpenAlex IDs), weight (nº refs comuns)
#
# Dependências:
#   install.packages(c("data.table", "igraph"))
#
# Como executar:
#   Rscript 07e_rede_cocitacao.R         # só co-citação
#   Rscript 07f_rede_coupling.R          # só coupling
#   Rscript 07e_rede_cocitacao.R --ambas # ambas em sequência
#
# Filtros de qualidade:
#   COCIT_MIN  — mínimo de co-artigos para uma aresta de co-citação (default: 3)
#   COUPLING_MIN — mínimo de refs compartilhadas para aresta de coupling (default: 5)
#
# Autor: Fernando Leite | FAPESP | Refatoração v2 — 22/maio/2026
# ======================================================================

suppressPackageStartupMessages({
  library(data.table)
  library(igraph)
})

# ---- Configuração -------------------------------------------------------
EDGES_CIT_PATH      <- "dados/redes/edges_citacoes.csv"
EDGES_CIT_PARQUET   <- "dados/redes/edges_citacoes.parquet"

OUT_COCIT_EDGES     <- "dados/redes/edges_cocitacao.csv"
OUT_COCIT_NODES     <- "dados/redes/nodes_cocitacao_metricas.csv"
OUT_COUPLING_EDGES  <- "dados/redes/edges_bib_coupling.csv"
OUT_COUPLING_NODES  <- "dados/redes/nodes_coupling_metricas.csv"

COCIT_MIN    <- 3L    # mínimo de co-citações para incluir aresta
COUPLING_MIN <- 5L    # mínimo de refs compartilhadas para incluir aresta


# ---- Carga de dados ----------------------------------------------------

carregar_citacoes <- function() {
  # Prefere Parquet (mais compacto) se existir
  if (file.exists(EDGES_CIT_PARQUET)) {
    message("[07e/f] Lendo ", EDGES_CIT_PARQUET)
    library(arrow, warn.conflicts = FALSE)
    dt <- as.data.table(arrow::read_parquet(EDGES_CIT_PARQUET))
  } else if (file.exists(EDGES_CIT_PATH)) {
    message("[07e/f] Lendo ", EDGES_CIT_PATH)
    dt <- fread(EDGES_CIT_PATH, select = c("id_citante", "id_citada",
                                           "ano_citante", "eh_interna"))
  } else {
    stop("Arquivo de citações não encontrado. Execute 02f_extrair_referencias.py primeiro.")
  }
  message("  ", format(nrow(dt), big.mark = "."), " citações")
  dt
}


# ---- Métricas estruturais (reutilizável) --------------------------------

calcular_metricas_rede <- function(edges_dt, col_A, col_B, weight_col = "weight") {
  g <- graph_from_data_frame(
    edges_dt[, c(col_A, col_B, weight_col), with = FALSE],
    directed = FALSE
  )
  E(g)$weight <- edges_dt[[weight_col]]
  all_ids <- unique(c(edges_dt[[col_A]], edges_dt[[col_B]]))
  missing <- setdiff(all_ids, V(g)$name)
  if (length(missing)) g <- add_vertices(g, length(missing), name = missing)

  comp   <- components(g)
  metrics <- data.table(
    id               = V(g)$name,
    degree           = degree(g),
    strength         = strength(g, weights = E(g)$weight),
    betweenness_norm = betweenness(g, normalized = TRUE,
                                   weights = 1 / E(g)$weight),
    # PageRank (Round 3, 2a): centralidade de citação robusta a grafos
    # desconexos (o fator de teleporte a mantém bem definida em todos os
    # componentes, ao contrário do autovetor). Preferida ao eigenvector para
    # redes de citação. Peso = co-citações / referências compartilhadas.
    pagerank         = page_rank(g, weights = E(g)$weight)$vector,
    core_number      = coreness(g),
    componente       = comp$membership
  )

  # Louvain por componente
  louvain_vec <- rep(NA_integer_, length(V(g)))
  offset <- 0L
  for (k in seq_len(comp$no)) {
    vids <- which(comp$membership == k)
    if (length(vids) < 2L) next
    g_sub <- induced_subgraph(g, vids = vids)
    lv <- cluster_louvain(g_sub, weights = E(g_sub)$weight)
    louvain_vec[vids] <- lv$membership + offset
    offset <- offset + max(lv$membership)
  }
  metrics[, louvain_community := louvain_vec]
  metrics[, componente := NULL]

  list(g = g, metrics = metrics)
}


# ── 07e: Co-citação ─────────────────────────────────────────────────────────

construir_cocitacao <- function(dt, cocit_min) {
  message("[07e] Construindo rede de co-citação...")

  # Precisamos apenas das referências (não importa se interna ou externa)
  # Self-join por id_citante: cada par (ref_A, ref_B) citado pelo mesmo artigo
  setkey(dt, id_citante)
  pares <- dt[dt, on = "id_citante", allow.cartesian = TRUE, nomatch = 0L]
  pares <- pares[id_citada < i.id_citada]
  setnames(pares, c("id_citada", "i.id_citada"), c("ref_A", "ref_B"))

  # Peso = nº de artigos citantes que co-citam o par
  edges <- pares[, .(weight = uniqueN(id_citante)), by = .(ref_A, ref_B)]
  edges <- edges[weight >= cocit_min]
  setorder(edges, -weight)

  message("  ", nrow(edges), " arestas de co-citação (com peso >= ", cocit_min, ")")
  message("  ", uniqueN(c(edges$ref_A, edges$ref_B)), " referências únicas na rede")
  edges
}

rede_cocitacao <- function(dt, cocit_min, out_edges, out_nodes) {
  edges <- construir_cocitacao(dt, cocit_min)
  if (nrow(edges) == 0) { message("  Sem arestas. Pulando métricas."); return(invisible(NULL)) }

  res     <- calcular_metricas_rede(edges, "ref_A", "ref_B")
  metrics <- res$metrics
  g       <- res$g

  message("[07e] Stats:")
  message("  Densidade: ", round(edge_density(g), 6))
  message("  Grau médio: ", round(mean(metrics$degree), 2))
  message("  Top-5 por grau:")
  print(head(metrics[order(-degree), .(id, degree, strength)], 5))

  dir.create(dirname(out_edges), recursive = TRUE, showWarnings = FALSE)
  fwrite(edges, out_edges)
  fwrite(metrics, out_nodes)
  message("[07e] Gravados: ", out_edges, " | ", out_nodes)
}


# ── 07f: Acoplamento bibliográfico ───────────────────────────────────────────

construir_coupling <- function(dt, coupling_min) {
  message("[07f] Construindo rede de acoplamento bibliográfico...")

  # Usar apenas referências de artigos DO CORPUS (corpus_ids são id_citante)
  corpus_ids <- unique(dt$id_citante)

  # Filtrar apenas citações de artigos do corpus
  dt_corpus <- dt[id_citante %in% corpus_ids]

  # Self-join por id_citada: par de artigos que compartilha uma referência
  setkey(dt_corpus, id_citada)
  pares <- dt_corpus[dt_corpus, on = "id_citada", allow.cartesian = TRUE, nomatch = 0L]
  pares <- pares[id_citante < i.id_citante]
  setnames(pares, c("id_citante", "i.id_citante"), c("artigo_A", "artigo_B"))

  # Peso = nº de referências compartilhadas
  edges <- pares[, .(weight = uniqueN(id_citada)), by = .(artigo_A, artigo_B)]
  edges <- edges[weight >= coupling_min]
  setorder(edges, -weight)

  message("  ", nrow(edges), " arestas de coupling (peso >= ", coupling_min, ")")
  message("  ", uniqueN(c(edges$artigo_A, edges$artigo_B)), " artigos na rede")
  edges
}

rede_coupling <- function(dt, coupling_min, out_edges, out_nodes) {
  edges <- construir_coupling(dt, coupling_min)
  if (nrow(edges) == 0) { message("  Sem arestas. Pulando métricas."); return(invisible(NULL)) }

  res     <- calcular_metricas_rede(edges, "artigo_A", "artigo_B")
  metrics <- res$metrics
  g       <- res$g

  message("[07f] Stats:")
  message("  Densidade: ", round(edge_density(g), 6))
  message("  Grau médio: ", round(mean(metrics$degree), 2))
  message("  Top-5 por grau (artigos mais acoplados):")
  print(head(metrics[order(-degree), .(id, degree, strength)], 5))

  dir.create(dirname(out_edges), recursive = TRUE, showWarnings = FALSE)
  fwrite(edges, out_edges)
  fwrite(metrics, out_nodes)
  message("[07f] Gravados: ", out_edges, " | ", out_nodes)
}


# ---- Main --------------------------------------------------------------

main <- function(rodar_cocitacao = TRUE, rodar_coupling = TRUE,
                 cocit_min = COCIT_MIN, coupling_min = COUPLING_MIN) {
  dt <- carregar_citacoes()
  if (rodar_cocitacao) rede_cocitacao(dt, cocit_min, OUT_COCIT_EDGES, OUT_COCIT_NODES)
  if (rodar_coupling)  rede_coupling(dt,  coupling_min, OUT_COUPLING_EDGES, OUT_COUPLING_NODES)
  message("[07e/f] Concluído.")
}

# ---- CLI ---------------------------------------------------------------
if (sys.nframe() == 0) {
  args <- commandArgs(trailingOnly = TRUE)
  parse_arg <- function(key, default) {
    idx <- which(args == key)
    if (length(idx) == 0L || idx >= length(args)) return(default)
    args[idx + 1L]
  }
  # Detecção do nome do script sem depender de %||% (operador de rlang/purrr,
  # não carregados aqui — usá-lo dispara 'could not find function "%||%"' no
  # Rscript). ofile pode ser NULL quando rodado por outras vias; tratamos isso.
  ofile <- tryCatch(sys.frames()[[1]]$ofile, error = function(e) NULL)
  script_name <- if (is.null(ofile)) "07e_rede_cocitacao.R" else sub(".*[\\/]", "", ofile)
  ambas <- "--ambas" %in% args

  rodar_e <- ambas || grepl("07e", script_name)
  rodar_f <- ambas || grepl("07f", script_name)
  if (!rodar_e && !rodar_f) { rodar_e <- TRUE; rodar_f <- TRUE }  # fallback

  main(
    rodar_cocitacao = rodar_e,
    rodar_coupling  = rodar_f,
    cocit_min       = as.integer(parse_arg("--cocit-min",    COCIT_MIN)),
    coupling_min    = as.integer(parse_arg("--coupling-min", COUPLING_MIN))
  )
}
