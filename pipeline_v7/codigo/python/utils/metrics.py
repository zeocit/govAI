"""
metrics.py — Métricas de concordância via irrCAC (DA-06)
=========================================================
Wrapper fino sobre irrCAC.raw.CAC que:

  1. Mantém a API externa idêntica às funções manuais substituídas
     em 05_processar_anotacoes.py (retorno float, mesma assinatura).
  2. Devolve opcionalmente um dict enriquecido com IC95%, p-valor e
     Gwet's AC1 — novo campo `metricas_completas()`.
  3. Expõe a versão do pacote para rastreabilidade no snapshot.json.

Por que irrCAC:
  - Implementação de referência do próprio Gwet (2014), mesmo autor
    do pacote R canônico declarado em DA-06 do Codebook v2.2.
  - Lida nativamente com missings (NaN) — comum em sessões parciais.
  - Retorna IC95% e p-valor nativos — Protocolo Apêndice B exige bootstrap;
    o CI interno do irrCAC usa fórmula assintótica (mais rápido, mesma
    interpretação para N ≥ 50).
  - Inclui Gwet's AC1 como diagnóstico do paradoxo de Kappa — descrito no
    Apêndice C do Protocolo de Anotação.

Compatibilidade com implementação manual:
  A implementação anterior (utils/metrics_manual.py) é mantida como
  bateria de testes de regressão. Ver tests/test_metrics_crossvalidation.py.

Autor: Fernando Leite | FAPESP | v4 — 28/maio/2026
"""
from __future__ import annotations

import logging
from importlib.metadata import version, PackageNotFoundError
from typing import NamedTuple

import pandas as pd
from irrCAC.raw import CAC

log = logging.getLogger(__name__)

# Versão pinada para rastreabilidade em snapshot.json
try:
    IRRCAC_VERSION = version("irrCAC")
except PackageNotFoundError:
    IRRCAC_VERSION = "desconhecida"

# Peso canônico para escala nominal (sem penalização diferencial entre categorias)
NOMINAL_WEIGHT = "identity"


class MetricasCompletas(NamedTuple):
    """Estrutura enriquecida retornada por metricas_completas()."""
    # Métricas principais (Protocolo §8.1)
    krippendorff_alpha: float
    fleiss_kappa: float
    # IC95% assintótico
    alpha_ci_lower: float
    alpha_ci_upper: float
    kappa_ci_lower: float
    kappa_ci_upper: float
    # p-valores (Ho: concordância = 0)
    alpha_pvalue: float
    kappa_pvalue: float
    # Diagnóstico do paradoxo de Kappa (Apêndice C do Protocolo)
    gwet_ac1: float
    # Metadados
    n_artigos: int
    n_anotadores: int
    irrcac_version: str


def _build_cac(ratings: dict[str, list] | list[list]) -> CAC:
    """Constrói objeto CAC a partir de ratings_dict ou ratings_matrix."""
    if isinstance(ratings, dict):
        items = list(ratings.values())
        max_r = max(len(v) for v in items)
        matrix = [
            list(vals) + [None] * (max_r - len(vals))
            for vals in items
        ]
        df = pd.DataFrame(matrix)
    else:
        df = pd.DataFrame(ratings)
    return CAC(df, weights=NOMINAL_WEIGHT)


def krippendorff_alpha_nominal(ratings_dict: dict[str, list]) -> float:
    """Krippendorff α nominal via irrCAC.

    Drop-in replacement para a função homônima anterior.
    Aceita missings nativamente (None/NaN em qualquer posição).

    Args:
        ratings_dict: {item_id: [val_anotador_1, val_anotador_2, ...]}

    Returns:
        α ∈ [-∞, 1]; nan se dados insuficientes.
    """
    if not ratings_dict:
        return float("nan")
    try:
        cac = _build_cac(ratings_dict)
        return cac.krippendorff()["est"]["coefficient_value"]
    except Exception as exc:
        log.warning("irrCAC.krippendorff falhou (%s); retornando nan", exc)
        return float("nan")


def fleiss_kappa(
    ratings_matrix: list[list],
    n_categories: int,  # aceito mas ignorado — irrCAC infere automaticamente
) -> float:
    """Kappa de Fleiss via irrCAC.

    Drop-in replacement para a função homônima anterior.
    O parâmetro n_categories é mantido por compatibilidade de assinatura
    mas não é usado — irrCAC infere as categorias dos dados.

    Args:
        ratings_matrix: lista de listas (n_artigos × n_anotadores).
        n_categories: ignorado (mantido por compatibilidade).

    Returns:
        κ ∈ [-1, 1]; nan se dados insuficientes.
    """
    if not ratings_matrix:
        return float("nan")
    try:
        cac = _build_cac(ratings_matrix)
        return cac.fleiss()["est"]["coefficient_value"]
    except Exception as exc:
        log.warning("irrCAC.fleiss falhou (%s); retornando nan", exc)
        return float("nan")


def metricas_completas(ratings_dict: dict[str, list]) -> MetricasCompletas:
    """Calcula todas as métricas de concordância em uma única passagem.

    Mais eficiente que chamar as funções individuais separadamente:
    constrói o objeto CAC uma única vez e extrai todos os coeficientes.

    Returns:
        MetricasCompletas com α, κ, AC1, IC95%, p-valores e metadados.
        Em caso de erro, retorna nan em todos os campos numéricos.
    """
    def _nan_mc() -> MetricasCompletas:
        return MetricasCompletas(
            krippendorff_alpha=float("nan"),
            fleiss_kappa=float("nan"),
            alpha_ci_lower=float("nan"), alpha_ci_upper=float("nan"),
            kappa_ci_lower=float("nan"), kappa_ci_upper=float("nan"),
            alpha_pvalue=float("nan"),   kappa_pvalue=float("nan"),
            gwet_ac1=float("nan"),
            n_artigos=0, n_anotadores=0,
            irrcac_version=IRRCAC_VERSION,
        )

    if not ratings_dict:
        return _nan_mc()

    try:
        cac = _build_cac(ratings_dict)
        df  = cac.ratings  # DataFrame interno já convertido

        res_alpha  = cac.krippendorff()["est"]
        res_fleiss = cac.fleiss()["est"]
        res_gwet   = cac.gwet()["est"]

        alpha_ci = res_alpha["confidence_interval"]
        kappa_ci = res_fleiss["confidence_interval"]

        return MetricasCompletas(
            krippendorff_alpha = res_alpha["coefficient_value"],
            fleiss_kappa       = res_fleiss["coefficient_value"],
            alpha_ci_lower     = alpha_ci[0],
            alpha_ci_upper     = alpha_ci[1],
            kappa_ci_lower     = kappa_ci[0],
            kappa_ci_upper     = kappa_ci[1],
            alpha_pvalue       = res_alpha["p_value"],
            kappa_pvalue       = res_fleiss["p_value"],
            gwet_ac1           = res_gwet["coefficient_value"],
            n_artigos          = len(df),
            n_anotadores       = df.shape[1],
            irrcac_version     = IRRCAC_VERSION,
        )

    except Exception as exc:
        log.warning("metricas_completas falhou (%s); retornando nan", exc)
        return _nan_mc()
