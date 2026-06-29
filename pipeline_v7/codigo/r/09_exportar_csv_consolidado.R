# ======================================================================
# 09_exportar_csv_consolidado.R — Export consolidado para Zenodo
# ======================================================================
# Manual §9.bis (v14): consolida todos os CSVs e JSONs de resultado em
# um arquivo ZIP versionado, acompanhado de um manifesto SHA256.
# Pronto para depósito no Zenodo.
#
# Input (todos opcionais — inclui os que existirem):
#   dados/redes/nodes_autores.csv
#   dados/redes/edges_autores_artigos.csv
#   dados/redes/nodes_instituicoes.csv
#   dados/redes/edges_autores_instituicoes.csv
#   dados/redes/edges_citacoes.csv  (ou .parquet)
#   dados/redes/nodes_termos.csv
#   dados/redes/edges_coautoria.csv
#   dados/redes/nodes_coautoria_metricas.csv
#   dados/redes/edges_cocitacao.csv
#   dados/redes/nodes_cocitacao_metricas.csv
#   dados/redes/edges_bib_coupling.csv
#   dados/redes/edges_cooccurrencia.csv
#   dados/resultados/predicoes_corpus.parquet → convertido para CSV
#   dados/resultados/relatorio_metricas_redes.csv
#   dados/resultados/relatorio_metricas_redes.json
#   dados/intermediarios/relatorio_limpeza.json
#   dados/gold_standard/gold_standard_final.parquet → convertido para CSV
#   dados/gold_standard/relatorio_concordancia.json
#
# Output:
#   dados/exports/{tag_git}_{data}_minerados.zip
#   dados/exports/{tag_git}_{data}_manifesto.json  (SHA256 + metadados)
#
# Manifesto contém:
#   - versão do repositório (git tag ou hash)
#   - data de geração
#   - hash SHA256 de cada arquivo incluído
#   - descrição de cada arquivo (campo "descricao")
#   - referência ao Codebook v4.0 para schema de cada arquivo
#
# Dependências:
#   install.packages(c("arrow", "data.table", "digest", "zip", "jsonlite"))
#   Opcional: system("git describe --tags --always") para versionamento
#
# Como executar:
#   Rscript 09_exportar_csv_consolidado.R
#   Rscript 09_exportar_csv_consolidado.R --tag v2.0-paper-metodologico
#
# Autor: Fernando Leite | FAPESP | Refatoração v2, 22/maio/2026
# Atualização v4.0 (23/jun/2026): alinhamento à orientação epistemológica em dois eixos;
#   postura epi / postura_dominante -> orientacao_proeminente + inconclusiva; refs Codebook v4.0.
# ======================================================================

suppressPackageStartupMessages({
  library(arrow)
  library(data.table)
  library(digest)
  library(zip)
  library(jsonlite)
})

# ---- Configuração -------------------------------------------------------
EXPORT_DIR <- "dados/exports"

# Catálogo de arquivos a exportar
CATALOGO <- list(
  list(
    arquivo   = "dados/redes/nodes_autores.csv",
    nome_zip  = "nodes_autores.csv",
    descricao = "Nós da rede de coautoria: um por autor único no corpus. Colunas: author_id, display_name, n_artigos, n_first_author, n_last_author, n_corresponding, n_instituicoes, instituicoes_ids, n_paises, paises_codes, is_brasileiro, primeiro_ano, ultimo_ano.",
    codebook  = "Codebook v4.0 §5.1"
  ),
  list(
    arquivo   = "dados/redes/edges_autores_artigos.csv",
    nome_zip  = "edges_autores_artigos.csv",
    descricao = "Arestas bipartitas autor × artigo. Colunas: id_artigo, author_id, ordem_autoria, is_first, is_last, is_corresponding.",
    codebook  = "Codebook v4.0 §5.1"
  ),
  list(
    arquivo   = "dados/redes/edges_coautoria.csv",
    nome_zip  = "edges_coautoria.csv",
    descricao = "Arestas da rede de coautoria: pares de autores que compartilham artigos. Colunas: author_A, author_B, weight.",
    codebook  = "Codebook v4.0 §8 (derivado)"
  ),
  list(
    arquivo   = "dados/redes/nodes_coautoria_metricas.csv",
    nome_zip  = "nodes_coautoria_metricas.csv",
    descricao = "Métricas estruturais por nó na rede de coautoria: degree, strength, betweenness, eigen, closeness, Louvain community, k-core.",
    codebook  = "Codebook v4.0 §8 (derivado)"
  ),
  list(
    arquivo   = "dados/redes/nodes_termos.csv",
    nome_zip  = "nodes_termos.csv",
    descricao = "Termos (n-gramas 1-3) extraídos de abstracts com frequências e TF-IDF. Colunas: termo, freq_global, df, idf, tf_idf_medio, freq_por_cluster.",
    codebook  = "Codebook v4.0 §8 (derivado)"
  ),
  list(
    arquivo   = "dados/redes/edges_cocitacao.csv",
    nome_zip  = "edges_cocitacao.csv",
    descricao = "Arestas da rede de co-citação: pares de referências citadas pelo mesmo artigo. Colunas: ref_A, ref_B, weight.",
    codebook  = "Codebook v4.0 §8 (derivado)"
  ),
  list(
    arquivo   = "dados/redes/edges_bib_coupling.csv",
    nome_zip  = "edges_bib_coupling.csv",
    descricao = "Arestas da rede de acoplamento bibliográfico: pares de artigos do corpus que compartilham referências. Colunas: artigo_A, artigo_B, weight.",
    codebook  = "Codebook v4.0 §8 (derivado)"
  ),
  list(
    arquivo   = "dados/redes/edges_cooccurrencia.csv",
    nome_zip  = "edges_cooccurrencia.csv",
    descricao = "Arestas da rede de co-ocorrência de termos nos abstracts. Colunas: termo_A, termo_B, n_co_artigos, pmi, npmi.",
    codebook  = "Codebook v4.0 §8 (derivado)"
  ),
  list(
    arquivo   = "dados/resultados/relatorio_metricas_redes.csv",
    nome_zip  = "relatorio_metricas_redes.csv",
    descricao = "Métricas descritivas das 4 redes (coautoria, co-citação, coupling, co-ocorrência): density, avg_degree, transitivity, modularity_louvain, etc.",
    codebook  = "Manual v22 §7.5"
  ),
  list(
    arquivo   = "dados/resultados/relatorio_metricas_redes.json",
    nome_zip  = "relatorio_metricas_redes.json",
    descricao = "Mesmo conteúdo de relatorio_metricas_redes.csv em formato JSON estruturado.",
    codebook  = "Manual v22 §7.5"
  ),
  list(
    arquivo   = "dados/intermediarios/relatorio_limpeza.json",
    nome_zip  = "relatorio_limpeza.json",
    descricao = "Estatísticas de retenção do corpus após os filtros de limpeza estrutural (§3.3).",
    codebook  = "Manual v22 §3.3"
  ),
  list(
    arquivo   = "dados/gold_standard/relatorio_concordancia.json",
    nome_zip  = "relatorio_concordancia.json",
    descricao = "Métricas de acordo inter-anotador do Gold Standard: Kappa de Fleiss e Krippendorff α por camada.",
    codebook  = "Manual v22 §4.5; Protocolo v11 §8"
  )
)

# Arquivos Parquet a converter para CSV no export
PARQUETS_PARA_CSV <- list(
  list(
    arquivo   = "dados/resultados/predicoes_corpus.parquet",
    nome_zip  = "predicoes_corpus.csv",
    descricao = "Predições do classificador sobre o corpus completo (~21k artigos): probabilidades de cluster (6) e orientação epistemológica (3 marcadores: epi_positivista, epi_interpretativa, epi_doutrinario_normativa), cluster_primario_pred, orientacao_proeminente, inconclusiva.",
    codebook  = "Codebook v4.0 §8"
  ),
  list(
    arquivo   = "dados/gold_standard/gold_standard_final.parquet",
    nome_zip  = "gold_standard_final.csv",
    descricao = "Gold Standard anotado por humanos: 400-500 artigos com cluster_primario, os 3 marcadores epi, orientacao_proeminente, inconclusiva, métricas de concordância.",
    codebook  = "Codebook v4.0 §5"
  )
)


# ---- Utilitários -------------------------------------------------------

obter_tag_git <- function() {
  tag <- tryCatch(
    trimws(system("git describe --tags --always 2>/dev/null", intern = TRUE)),
    error   = function(e) "",
    warning = function(w) ""
  )
  if (length(tag) == 0 || nchar(tag) == 0) {
    hash <- tryCatch(
      trimws(system("git rev-parse --short HEAD 2>/dev/null", intern = TRUE)),
      error = function(e) "sem-git"
    )
    return(if (length(hash) > 0 && nchar(hash) > 0) hash else "sem-git")
  }
  tag
}

sha256_arquivo <- function(path) {
  tryCatch(digest(path, algo = "sha256", file = TRUE), error = function(e) NA_character_)
}


# ---- Main --------------------------------------------------------------

main <- function(tag_manual = NULL) {
  data_str <- format(Sys.Date(), "%Y%m%d")
  tag_git  <- if (!is.null(tag_manual)) tag_manual else obter_tag_git()
  nome_base <- paste0(tag_git, "_", data_str)

  dir.create(EXPORT_DIR, recursive = TRUE, showWarnings = FALSE)

  zip_path  <- file.path(EXPORT_DIR, paste0(nome_base, "_minerados.zip"))
  man_path  <- file.path(EXPORT_DIR, paste0(nome_base, "_manifesto.json"))

  tmp_dir <- file.path(tempdir(), "export_minerados")
  unlink(tmp_dir, recursive = TRUE)
  dir.create(tmp_dir, recursive = TRUE)

  manifesto <- list(
    versao_git   = tag_git,
    data_geracao = format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC"),
    codebook     = "https://doi.org/10.5281/zenodo.XXXXXXX",  # Atualizar após depósito
    arquivos     = list()
  )

  message("[09] Copiando arquivos CSV existentes...")
  n_incluidos <- 0L
  for (item in CATALOGO) {
    if (!file.exists(item$arquivo)) {
      message("  AUSENTE: ", item$arquivo)
      next
    }
    dest <- file.path(tmp_dir, item$nome_zip)
    file.copy(item$arquivo, dest, overwrite = TRUE)
    hash <- sha256_arquivo(dest)
    manifesto$arquivos[[length(manifesto$arquivos) + 1]] <- list(
      nome      = item$nome_zip,
      origem    = item$arquivo,
      sha256    = hash,
      descricao = item$descricao,
      codebook  = item$codebook
    )
    message("  ✅ ", item$nome_zip, " (SHA256: ", substr(hash, 1, 12), "...)")
    n_incluidos <- n_incluidos + 1L
  }

  message("[09] Convertendo Parquet → CSV...")
  for (item in PARQUETS_PARA_CSV) {
    if (!file.exists(item$arquivo)) {
      message("  AUSENTE: ", item$arquivo)
      next
    }
    df <- as.data.table(read_parquet(item$arquivo))
    dest <- file.path(tmp_dir, item$nome_zip)
    fwrite(df, dest)
    hash <- sha256_arquivo(dest)
    manifesto$arquivos[[length(manifesto$arquivos) + 1]] <- list(
      nome      = item$nome_zip,
      origem    = item$arquivo,
      sha256    = hash,
      descricao = item$descricao,
      codebook  = item$codebook
    )
    message("  ✅ ", item$nome_zip, " (", nrow(df), " linhas, SHA256: ",
            substr(hash, 1, 12), "...)")
    n_incluidos <- n_incluidos + 1L
  }

  # Incluir o próprio manifesto no ZIP
  manifesto_tmp <- file.path(tmp_dir, "manifesto.json")
  writeLines(toJSON(manifesto, auto_unbox = TRUE, pretty = TRUE), manifesto_tmp)

  message("[09] Criando ZIP: ", zip_path, " (", n_incluidos, " arquivos)...")
  arquivos_zip <- list.files(tmp_dir, full.names = TRUE)
  zip(zip_path, files = arquivos_zip, mode = "cherry-pick")

  # Copiar manifesto para fora do ZIP também
  file.copy(manifesto_tmp, man_path, overwrite = TRUE)

  message("[09] ✅ Export concluído:")
  message("  ZIP:      ", zip_path, " (", round(file.size(zip_path) / 1e6, 1), " MB)")
  message("  Manifesto:", man_path)
  message("  Arquivos incluídos: ", n_incluidos)
  message("")
  message("  Para depositar no Zenodo:")
  message("  1. Acesse https://zenodo.org/deposit/new")
  message("  2. Upload do ZIP: ", basename(zip_path))
  message("  3. Upload do manifesto: ", basename(man_path))
  message("  4. Atualizar DOI no Codebook v4.0 §Anexo C após publicação.")

  unlink(tmp_dir, recursive = TRUE)
}


# ---- CLI ---------------------------------------------------------------
if (sys.nframe() == 0) {
  args     <- commandArgs(trailingOnly = TRUE)
  idx_tag  <- which(args == "--tag")
  tag_arg  <- if (length(idx_tag) > 0 && idx_tag < length(args)) args[idx_tag + 1L] else NULL
  main(tag_manual = tag_arg)
}



# ====================================================================
# NOTA (auditoria v5): o apêndice abaixo era texto livre NÃO comentado,
# o que tornava o script inválido em R (falha ao rodar via Rscript).
# Comentado integralmente; conteúdo preservado como referência.
# ====================================================================
# Apêndice — Dependências completas
# Python
# Instalar todas as dependências Python do pipeline:
# pip install pyalex tqdm pyarrow pandas openai rapidfuzz
#
# R
# Instalar todas as dependências R do pipeline:
# install.packages(c(
#   'arrow',       # leitura/escrita de Parquet em R
#   'data.table',  # manipulação de dados rápida
#   'igraph',      # construção e análise de redes
#   'stringi',     # limpeza textual Unicode
#   'cld3',        # detecção de idioma
#   'stringr',     # regex e manipulação de strings
#   'purrr',       # programação funcional
#   'udpipe',      # lematização e PoS (07c)
#   'icr',         # Krippendorff alpha (05, análise de concordância)
#   'irr',         # Kappa de Fleiss (05, análise de concordância)
#   'boot',        # Bootstrap para IC (05)
#   'vcd',         # V de Cramér (gate de colinearidade)
#   'infotheo'     # MI normalizada (gate de colinearidade)
# ))
#
# Variáveis de ambiente
# Obrigatórias antes de rodar os scripts 04a/04b:
# export OPENROUTER_API_KEY='sk-or-...'
#
# Recomendado (evita warnings do pyalex):
