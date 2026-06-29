# ======================================================================
# parallel_safe.R — Paralelismo seguro em macOS / Apple Silicon
# ======================================================================
# Auditoria: mclapply usa fork() em UNIX (zero-copy via copy-on-write),
# mas pode causar deadlock se a BLAS estiver multi-threaded (Accelerate
# em macOS, OpenBLAS em Linux). Este helper aplica as guardas necessárias
# antes de chamar mclapply.
#
# Uso:
#   source("utils/parallel_safe.R")
#   resultados <- mclapply_safe(lista, function(x) processar(x), n_cores = 8)
# ======================================================================

#' mclapply com guardas de segurança contra BLAS-fork deadlock
#'
#' @param X         Lista, vetor ou data.table de entrada
#' @param FUN       Função a aplicar a cada elemento
#' @param n_cores   Número de cores; NULL = detectCores() - 1 (Linux) ou 8 (macOS M-series)
#' @param prescheduling FALSE para trabalhos heterogêneos (recomendado)
#' @param ...       Argumentos extras passados a FUN
#' @return Lista com resultados, na ordem original de X
mclapply_safe <- function(X, FUN, n_cores = NULL, prescheduling = FALSE, ...) {
  # 1. Guarda BLAS-fork deadlock (CRÍTICO em macOS Accelerate)
  old_omp     <- Sys.getenv("OMP_NUM_THREADS", unset = NA)
  old_openblas <- Sys.getenv("OPENBLAS_NUM_THREADS", unset = NA)
  Sys.setenv(OMP_NUM_THREADS = "1")
  Sys.setenv(OPENBLAS_NUM_THREADS = "1")
  if (requireNamespace("RcppParallel", quietly = TRUE)) {
    RcppParallel::setThreadOptions(numThreads = 1)
  }

  on.exit({
    # Restaurar configuração anterior
    if (is.na(old_omp))      Sys.unsetenv("OMP_NUM_THREADS")
    else                     Sys.setenv(OMP_NUM_THREADS = old_omp)
    if (is.na(old_openblas)) Sys.unsetenv("OPENBLAS_NUM_THREADS")
    else                     Sys.setenv(OPENBLAS_NUM_THREADS = old_openblas)
  }, add = TRUE)

  # 2. Detectar plataforma e definir n_cores
  if (is.null(n_cores)) {
    if (Sys.info()["sysname"] == "Darwin") {
      # M-series: usar apenas performance cores (8 em M5 Max)
      n_cores <- 8L
    } else {
      n_cores <- max(1L, parallel::detectCores() - 1L)
    }
  }

  # 3. Executar com mclapply
  resultados <- parallel::mclapply(
    X = X,
    FUN = FUN,
    mc.cores = n_cores,
    mc.preschedule = prescheduling,
    ...
  )

  # 4. Verificar falhas (mclapply silenciosamente retorna try-error em falhas)
  erros <- which(sapply(resultados, inherits, "try-error"))
  if (length(erros) > 0) {
    warning(sprintf(
      "%d/%d iterações falharam (índices: %s). Verifique resultados[idx]$messages.",
      length(erros), length(resultados),
      paste(head(erros, 10), collapse = ", ")
    ))
  }

  return(resultados)
}


#' Detectar se o ambiente é RStudio (mclapply pode ter comportamento inesperado)
em_rstudio <- function() {
  identical(Sys.getenv("RSTUDIO"), "1")
}


# Aviso ao carregar em RStudio
if (em_rstudio()) {
  warning(
    "Você está no RStudio. mclapply pode ter comportamento inesperado. ",
    "Para paralelismo confiável, rode via terminal: Rscript meu_script.R"
  )
}
