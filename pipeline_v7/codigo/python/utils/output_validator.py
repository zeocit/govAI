"""
utils/output_validator.py — Validação leve de schema de output (Round 4, frente H)
====================================================================================
Nenhum script validava o que GRAVA antes desta rodada. Erros de schema nos
outputs são descobertos pelo próximo script — de forma obscura e sem contexto.
Este módulo adiciona verificações mínimas sem dependências extras.

Uso:
    from utils.output_validator import validar_output_parquet
    validar_output_parquet(df, cols_obrigatorias={...}, nome_script="04a")
"""
from __future__ import annotations

import logging
import warnings
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)


def validar_output_parquet(
    df: pd.DataFrame,
    cols_obrigatorias: dict[str, type | None],
    nome_script: str,
    n_input: int | None = None,
    prob_cols: list[str] | None = None,
    prob_tol: float = 1e-4,
) -> None:
    """Valida o DataFrame antes de gravar como Parquet.

    Args:
        df: DataFrame a validar.
        cols_obrigatorias: {nome_coluna: tipo_esperado | None}.
            tipo None = só presença, sem checagem de dtype.
        nome_script: nome do script chamador, para logs.
        n_input: tamanho do input, para detectar perda/explosão de linhas.
        prob_cols: colunas de probabilidade que devem somar ≈1.0 por linha.
        prob_tol: tolerância para a soma das probabilidades.

    Levanta:
        ValueError se houver colunas obrigatórias ausentes.
    Emite:
        warnings.warn para violações não-fatais (NaN, contagem suspeita).
    """
    erros: list[str] = []
    avisos: list[str] = []

    # 1. Colunas obrigatórias
    faltantes = [c for c in cols_obrigatorias if c not in df.columns]
    if faltantes:
        erros.append(f"[{nome_script}] Output sem colunas obrigatórias: {sorted(faltantes)}")

    # 2. Colunas totalmente NaN (silenciosamente errado)
    for col in cols_obrigatorias:
        if col in df.columns and df[col].isna().all():
            avisos.append(f"[{nome_script}] Coluna '{col}' é 100% NaN no output.")

    # 3. Contagem de linhas suspeita
    if n_input is not None and len(df) == 0:
        erros.append(f"[{nome_script}] Output com 0 linhas (input tinha {n_input}).")
    if n_input is not None and len(df) > 2 * n_input:
        avisos.append(
            f"[{nome_script}] Output tem {len(df)} linhas vs {n_input} de input "
            f"(> 2×). Verificar se há duplicatas."
        )

    # 4. Probabilidades somam ≈1.0 por linha
    if prob_cols:
        presentes = [c for c in prob_cols if c in df.columns]
        if len(presentes) < len(prob_cols):
            ausentes = set(prob_cols) - set(presentes)
            erros.append(
                f"[{nome_script}] Colunas de probabilidade ausentes: {sorted(ausentes)}"
            )
        elif len(presentes) > 0:
            soma = df[presentes].sum(axis=1)
            n_fora = (soma - 1.0).abs().gt(prob_tol).sum()
            if n_fora > 0:
                avisos.append(
                    f"[{nome_script}] {n_fora} linhas com probabilidades que não "
                    f"somam 1.0 (±{prob_tol}). Max desvio: {(soma - 1.0).abs().max():.6f}"
                )

    # Emit
    for e in erros:
        log.error(e)
    for a in avisos:
        log.warning(a)
        warnings.warn(a, stacklevel=3)

    if erros:
        raise ValueError(
            f"Output de '{nome_script}' falhou na validação de schema:\n"
            + "\n".join(erros)
        )

    if not erros and not avisos:
        log.debug("[%s] Validação de output OK (%d linhas).", nome_script, len(df))
