# =====================================================================
# 07d_rede_coautoria.R — Construção da rede de coautoria
# =====================================================================
# Manual §7.2 (refatorado em v14): a partir de edges_autores_artigos.csv,
# constrói a rede de coautoria (autor-autor com peso = nº de artigos
# compartilhados) e calcula métricas estruturais por nó.
#
# Input:
#   dados/redes/edges_autores_artigos.csv
#   dados/redes/nodes_autores.csv   (opcional — para mesclar metadados nos nodes_metrics)
#
# Outputs:
#   dados/redes/edges_coautoria.csv          — uma linha por par de coautores
#   dados/redes/nodes_coautoria_metricas.csv — métricas estruturais por autor
#
# Codebook v2.1 (a atualizar):
#
#   edges_coautoria.csv:
#       author_A           str    OpenAlex Author ID (lexicograficamente menor)
#       author_B           str    OpenAlex Author ID (lexicograficamente maior)
#       weight             int    Número de artigos compartilhados
#
#   nodes_coautoria_metricas.csv:
#       author_id          str
#       degree             int    Número de coautores distintos
#       strength           num    Soma dos pesos das arestas incidentes
#       betweenness_norm   num    Centralidade de intermediação normalizada [0,1]
#       eigen_centrality   num    Centralidade de autovetor
#       closeness          num    Centralidade de proximidade (componente)
#       louvain_community  int    ID da comunidade Louvain (modularidade)
#       core_number        int    k-core do nó
#
# Otimização:
#   - data.table self-join (cartesian intra-id_artigo) — mais rápido que loop
#   - filtro lexicográfico (author_A < author_B) evita arestas duplicadas
#   - métricas calculadas no maior componente conexo (Louvain exige conectividade)
#     OU sobre o grafo inteiro com louvain por subgrafo (escolha documentada abaixo)
#
# Robustez:
#   - aborta com mensagem clara se input estiver vazio ou malformado
#   - lida com autores sem coautores (artigos solo) — entram no node table
#     com degree=0 e métricas NA
#
# Autor: Fernando Leite | FAPESP | Refatoração v2 — 22/maio/2026
# =====================================================================

suppressPackageStartupMessages({
  library(data.table)
  library(igraph)
})

# ---- Configuração padrão (sobrepondável via args) ----------------------
INPUT_EDGES_DEFAULT <- "dados/redes/edges_autores_artigos.csv"
INPUT_NODES_DEFAULT <- "dados/redes/nodes_autores.csv"
OUT_EDGES_DEFAULT   <- "dados/redes/edges_coautoria.csv"
OUT_NODES_DEFAULT   <- "dados/redes/nodes_coautoria_metricas.csv"


# ---- Funções utilitárias ----------------------------------------------

construir_arestas_coautoria <- function(edges_autor_artigo) {
  # Estratégia: para cada artigo, gera todas as combinações 2-a-2 de autores.
  # Implementação via self-join em data.table (cartesian dentro de id_artigo),
  # depois filtra para A < B lexicograficamente (evita pares duplicados e
  # auto-laços).

  setkey(edges_autor_artigo, id_artigo)
  pares <- edges_autor_artigo[
    edges_autor_artigo,
    on = "id_artigo",
    allow.cartesian = TRUE,
    nomatch = 0L
  ]
  # Após self-join: colunas author_id (lado esquerdo) e i.author_id (lado direito)
  pares <- pares[author_id < i.author_id]
  setnames(pares, c("author_id", "i.author_id"), c("author_A", "author_B"))

  # Peso = nº de artigos compartilhados (distinct count para robustez)
  edges <- pares[, .(weight = uniqueN(id_artigo)),
                 by = .(author_A, author_B)]
  setorder(edges, -weight, author_A, author_B)
  edges
}

calcular_metricas <- function(edges_coaut, all_author_ids) {
  # Constrói o grafo a partir de edges; adiciona nós isolados (autores solo)
  if (nrow(edges_coaut) == 0L) {
    return(data.table(
      author_id = all_author_ids,
      degree = 0L, strength = 0,
      betweenness_norm = NA_real_, eigen_centrality = NA_real_,
      closeness = NA_real_, louvain_community = NA_integer_,
      core_number = 0L
    ))
  }

  g <- graph_from_data_frame(
    d = edges_coaut[, .(author_A, author_B, weight)],
    directed = FALSE,
    vertices = data.frame(name = all_author_ids, stringsAsFactors = FALSE)
  )

  # Métricas estruturais — todas vetorizadas
  # NOTA (auditoria Round 3, 2a): eigen_centrality NÃO entra aqui. A centralidade
  # de autovetor só é bem definida (Perron-Frobenius) em grafo conexo; no grafo
  # inteiro desconexo, o igraph concentra a centralidade no maior componente e
  # zera os demais. Calculada abaixo, restrita ao componente gigante (LCG),
  # com NA fora dele — coerente com o tratamento de closeness/Louvain.
  metrics <- data.table(
    author_id        = V(g)$name,
    degree           = degree(g),
    strength         = strength(g, weights = E(g)$weight),
    betweenness_norm = betweenness(g, weights = 1 / E(g)$weight,
                                   normalized = TRUE),
    core_number      = coreness(g)
  )

  # Closeness e Louvain só fazem sentido em componentes conexos.
  # Estratégia: calcular por componente; nós isolados ficam NA.
  comp <- components(g)
  metrics[, componente := comp$membership]

  # Eigenvector centrality restrita ao componente gigante (LCG) — Round 3, 2a.
  # Fora do LCG fica NA: comparar autovetor entre componentes não tem sentido
  # (cada componente normaliza ao próprio máximo). Reportamos a centralidade de
  # autovetor apenas onde ela é bem definida.
  eigen_vec <- rep(NA_real_, length(V(g)))
  if (comp$no >= 1L) {
    lcc_k     <- which.max(comp$csize)
    nodes_lcc <- which(comp$membership == lcc_k)
    if (length(nodes_lcc) >= 2L) {
      g_lcc <- induced_subgraph(g, vids = nodes_lcc)
      eigen_vec[nodes_lcc] <- as.numeric(
        eigen_centrality(g_lcc, weights = E(g_lcc)$weight)$vector
      )
    }
  }
  metrics[, eigen_centrality := eigen_vec]

  # Closeness por componente (evita warnings sobre grafo desconexo)
  closeness_vec <- rep(NA_real_, length(V(g)))
  for (k in seq_len(comp$no)) {
    nodes_k <- which(comp$membership == k)
    if (length(nodes_k) < 2L) next
    g_sub <- induced_subgraph(g, vids = nodes_k)
    closeness_vec[nodes_k] <- closeness(g_sub, weights = 1 / E(g_sub)$weight)
  }
  metrics[, closeness := closeness_vec]

  # Louvain por componente (componentes < 2 nós ficam NA)
  louvain_vec <- rep(NA_integer_, length(V(g)))
  cluster_offset <- 0L
  for (k in seq_len(comp$no)) {
    nodes_k <- which(comp$membership == k)
    if (length(nodes_k) < 2L) {
      next
    }
    g_sub <- induced_subgraph(g, vids = nodes_k)
    lv <- cluster_louvain(g_sub, weights = E(g_sub)$weight)
    louvain_vec[nodes_k] <- lv$membership + cluster_offset
    cluster_offset <- cluster_offset + max(lv$membership)
  }
  metrics[, louvain_community := louvain_vec]

  metrics[, componente := NULL]
  metrics
}


# ---- Main -------------------------------------------------------------

main <- function(input_edges, input_nodes, out_edges, out_nodes) {
  message("[07d] Lendo ", input_edges)
  if (!file.exists(input_edges)) {
    stop("Input não encontrado: ", input_edges)
  }
  dt <- fread(input_edges, select = c("id_artigo", "author_id"))
  message("  ", nrow(dt), " arestas autor-artigo")

  if (nrow(dt) == 0L) {
    stop("Tabela de entrada vazia.")
  }

  all_author_ids <- unique(dt$author_id)
  message("  ", length(all_author_ids), " autores únicos")

  message("[07d] Construindo arestas de coautoria...")
  edges_coaut <- construir_arestas_coautoria(dt)
  message("  ", nrow(edges_coaut), " arestas de coautoria")

  message("[07d] Calculando métricas estruturais...")
  metrics <- calcular_metricas(edges_coaut, all_author_ids)

  # Anexar metadados do autor se disponíveis (display_name, is_brasileiro)
  if (file.exists(input_nodes)) {
    nodes_meta <- fread(input_nodes,
                        select = c("author_id", "display_name", "is_brasileiro", "n_artigos"))
    metrics <- merge(metrics, nodes_meta, by = "author_id", all.x = TRUE)
    setcolorder(metrics, c("author_id", "display_name", "n_artigos",
                           "is_brasileiro", "degree", "strength",
                           "betweenness_norm", "eigen_centrality",
                           "closeness", "louvain_community", "core_number"))
  } else {
    message("  (sem ", input_nodes, " — métricas sem metadados textuais)")
  }

  # Stats descritivas (vão no relatório §7.2)
  message("[07d] Stats descritivas:")
  message("  Densidade da rede: ", round(2 * nrow(edges_coaut) /
            (length(all_author_ids) * (length(all_author_ids) - 1)), 6))
  message("  Grau médio:         ", round(mean(metrics$degree), 2))
  message("  Grau máximo:        ", max(metrics$degree))
  message("  Autores isolados:   ", sum(metrics$degree == 0))

  # Gravar
  dir.create(dirname(out_edges), recursive = TRUE, showWarnings = FALSE)
  dir.create(dirname(out_nodes), recursive = TRUE, showWarnings = FALSE)
  fwrite(edges_coaut, out_edges)
  fwrite(metrics,     out_nodes)
  message("[07d] Gravados: ", out_edges, " | ", out_nodes)
}


# ---- CLI --------------------------------------------------------------
if (sys.nframe() == 0) {
  args <- commandArgs(trailingOnly = TRUE)
  parse_arg <- function(key, default) {
    idx <- which(args == key)
    if (length(idx) == 0L) return(default)
    args[idx + 1L]
  }

  main(
    input_edges = parse_arg("--input-edges", INPUT_EDGES_DEFAULT),
    input_nodes = parse_arg("--input-nodes", INPUT_NODES_DEFAULT),
    out_edges   = parse_arg("--out-edges",   OUT_EDGES_DEFAULT),
    out_nodes   = parse_arg("--out-nodes",   OUT_NODES_DEFAULT)
  )
}
