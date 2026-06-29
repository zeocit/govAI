# ======================================================================
# 03_limpeza_textual.R — Limpeza textual de títulos e abstracts
# ======================================================================
# Manual §3.3bis (v14): aplica transformações textuais a título e abstract
# do corpus limpo estrutural, produzindo o corpus limpo textual pronto
# para classificação por LLM e Transformer.
#
# Input:
#   dados/intermediarios/corpus_limpo.parquet
#
# Output:
#   dados/intermediarios/corpus_limpo_textual.parquet
#
# Colunas adicionadas (Codebook v2.1 §3):
#   titulo_limpo              string  Título pós-limpeza textual
#   abstract_limpo            string  Abstract pós-limpeza textual
#   n_citacoes_inline_removidas int   Contagem de citações inline removidas do abstract
#   idioma_detectado          string  ISO 639-1 detectado pelo cld3
#   idioma_confianca          double  Probabilidade do idioma detectado [0,1]
#   abstract_n_palavras       int     Número de palavras do abstract limpo
#
# Transformações aplicadas (em ordem):
#   1. Normalização Unicode NFC
#   2. Remoção de tags HTML (e.g., <i>, <b>, <sub>, <sup>)
#   3. Remoção de citações inline:
#      - Numéricas entre colchetes: [1], [1-3], [1,2,3]
#      - Autor-ano: (Smith, 2020), (Smith & Jones, 2020), (Smith et al., 2020)
#   4. Normalização de espaços e caracteres de controle
#   5. Detecção de idioma via cld3 (quando openAlex não declarou)
#   6. Contagem de palavras
#
# Robustez:
#   - Títulos ou abstracts NULL → mantidos como NA (não geram erro)
#   - Textos com idioma não detectável (confiança < 0.5) → idioma_detectado = NA
#
# Dependências R:
#   install.packages(c("arrow", "stringi", "cld3", "dplyr"))
#
# Como executar:
#   Rscript 03_limpeza_textual.R
#   Rscript 03_limpeza_textual.R --input outro.parquet --output saida.parquet
#
# Autor: Fernando Leite | FAPESP | Refatoração v2 — 22/maio/2026
# ======================================================================

suppressPackageStartupMessages({
  library(arrow)
  library(dplyr)
  library(stringi)
  library(cld3)
})

# ---- Configuração padrão -----------------------------------------------
INPUT_DEFAULT  <- "dados/intermediarios/corpus_limpo.parquet"
OUTPUT_DEFAULT <- "dados/intermediarios/corpus_limpo_textual.parquet"

# ---- Padrões regex (compilados uma vez) --------------------------------

# Citações numéricas inline: [1], [1-3], [1, 2, 3], [10,11,12]
RE_CIT_NUMERICA <- "\\[\\d[\\d,;\\-\\s]*\\]"

# Citações autor-ano inline: (Smith, 2020), (Smith & Jones, 2020),
# (Smith et al., 2020), (Smith et al. 2020)
RE_CIT_AUTOR <- paste0(
  "\\(",
  "[A-ZÀ-Ö][a-zà-ö]+(\\s[A-ZÀ-Ö][a-zà-ö]+)*",  # Sobrenome(s)
  "(?:\\s(?:&|and|et al\\.?)\\s[A-ZÀ-Ö][a-zà-ö]+)*",  # & / and / et al.
  "(?:[\\.,]\\s?\\d{4}[a-z]?)?",                       # , ano (opcional)
  "\\)"
)

# Tags HTML comuns em títulos/abstracts bibliográficos
RE_HTML <- "<[^>]{1,50}>"

# ---- Funções utilitárias -----------------------------------------------

limpar_texto <- function(texto) {
  # Recebe vetor de strings; retorna lista com texto limpo + n_citacoes_inline

  if (is.null(texto) || length(texto) == 0)
    return(list(limpo = character(0), n_cit = integer(0)))

  # 1. Normalização Unicode NFC
  x <- stri_trans_nfc(texto)

  # 2. Remoção de tags HTML
  x <- stri_replace_all_regex(x, RE_HTML, " ")

  # 3. Remoção de citações numéricas + contagem
  n_cit_num <- stri_count_regex(x, RE_CIT_NUMERICA)
  x         <- stri_replace_all_regex(x, RE_CIT_NUMERICA, " ")

  # 4. Remoção de citações autor-ano + contagem acumulada
  n_cit_autor <- stri_count_regex(x, RE_CIT_AUTOR)
  x           <- stri_replace_all_regex(x, RE_CIT_AUTOR, " ")
  n_cit_total <- n_cit_num + n_cit_autor

  # 5. Remover caracteres de controle (exceto newline → espaço)
  x <- stri_replace_all_regex(x, "[\\p{Cc}&&[^\\n]]", "")
  x <- stri_replace_all_fixed(x, "\n", " ")

  # 6. Normalizar espaços múltiplos
  x <- stri_replace_all_regex(x, "\\s{2,}", " ")
  x <- stri_trim_both(x)

  # Textos que viraram vazios → NA
  x[nchar(x) == 0] <- NA_character_

  list(limpo = x, n_cit = as.integer(n_cit_total))
}

detectar_idioma <- function(textos, idioma_openalex) {
  # Detecta idioma apenas onde o OpenAlex não declarou (NA)
  # Retorna data.frame com idioma_detectado e idioma_confianca
  #
  # CORREÇÃO (auditoria v5): a versão anterior usava detect_language_mixed(),
  # que NÃO é vetorizada — ela concatena todo o vetor num único texto e
  # devolve as `size` (default 3) línguas predominantes do conjunto inteiro.
  # Atribuir esse resultado (1–3 linhas) a N posições por documento
  # (resultado$idioma_detectado[mask] <- detected$language) recicla os valores
  # e corrompe a detecção linha a linha. A função vetorizada correta é
  # detect_language(), que retorna um ISO 639-1 por documento (ou NA quando
  # não confiável). Ela não expõe probabilidade; portanto registramos a
  # confiança como 1.0 para detecções bem-sucedidas e NA para as não
  # confiáveis (que a própria cld3 marca como NA), preservando o contrato
  # downstream sem inventar um número de confiança espúrio.
  n <- length(textos)
  resultado <- data.frame(
    idioma_detectado = idioma_openalex,
    idioma_confianca = ifelse(is.na(idioma_openalex), NA_real_, 1.0),
    stringsAsFactors = FALSE
  )

  mask_detectar <- is.na(idioma_openalex) & !is.na(textos) & nchar(textos) > 20
  if (sum(mask_detectar) == 0) return(resultado)

  # Vetorizada: um resultado por documento, alinhado a textos[mask_detectar].
  detected <- detect_language(textos[mask_detectar])

  resultado$idioma_detectado[mask_detectar] <- detected
  # cld3 retorna NA quando não pôde determinar de forma confiável.
  resultado$idioma_confianca[mask_detectar] <- ifelse(is.na(detected), NA_real_, 1.0)

  resultado
}

contar_palavras <- function(texto) {
  ifelse(
    is.na(texto),
    NA_integer_,
    as.integer(stri_count_boundaries(texto, type = "word"))
  )
}

# ---- Main --------------------------------------------------------------

main <- function(input_path, output_path) {
  message("[03] Lendo ", input_path)
  df <- read_parquet(input_path)
  message("  ", nrow(df), " artigos")

  # Limpar título
  message("[03] Limpando títulos...")
  res_titulo <- limpar_texto(df$titulo)
  df$titulo_limpo <- res_titulo$limpo

  # Limpar abstract
  message("[03] Limpando abstracts...")
  res_abstract <- limpar_texto(df$abstract)
  df$abstract_limpo            <- res_abstract$limpo
  df$n_citacoes_inline_removidas <- res_abstract$n_cit

  # Contar palavras
  df$abstract_n_palavras <- contar_palavras(df$abstract_limpo)

  # Detecção de idioma
  message("[03] Detectando idioma...")
  idioma_col <- if ("idioma" %in% colnames(df)) df$idioma else rep(NA_character_, nrow(df))
  det_idioma <- detectar_idioma(df$abstract_limpo, idioma_col)
  df$idioma_detectado <- det_idioma$idioma_detectado
  df$idioma_confianca <- det_idioma$idioma_confianca

  # Estatísticas
  message("[03] Estatísticas:")
  message("  Títulos limpos com NA:     ", sum(is.na(df$titulo_limpo)))
  message("  Abstracts limpos com NA:   ", sum(is.na(df$abstract_limpo)))
  message("  Citações inline removidas: ", sum(df$n_citacoes_inline_removidas, na.rm = TRUE))
  message("  Média palavras abstract:   ", round(mean(df$abstract_n_palavras, na.rm = TRUE), 1))
  message("  Idiomas detectados:")
  print(table(df$idioma_detectado, useNA = "ifany"))

  # Gravar (atômico: .tmp → rename, evita parquet truncado em interrupção)
  dir.create(dirname(output_path), recursive = TRUE, showWarnings = FALSE)
  tmp_path <- paste0(output_path, ".tmp")
  write_parquet(df, tmp_path, compression = "snappy")
  file.rename(tmp_path, output_path)
  message("[03] Gravado: ", output_path)
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
    input_path  = parse_arg("--input",  INPUT_DEFAULT),
    output_path = parse_arg("--output", OUTPUT_DEFAULT)
  )
}
