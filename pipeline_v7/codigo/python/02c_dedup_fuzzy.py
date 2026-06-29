"""
02c_dedup_fuzzy.py — Deduplicação fuzzy por título
===================================================
Manual §3.3.2 (v14): identifica artigos sem DOI (ou com DOI mal registrado)
que na prática são o mesmo artigo, via similaridade fuzzy de título.

A deduplicação exata por DOI já foi feita em 02_limpeza_estrutural.py.
Este script trata o caso residual: artigos sem DOI ou com DOIs divergentes
que são de fato o mesmo trabalho (e.g., versão preprint vs. publicada,
erro tipográfico no DOI, artigos de conferência vs. periódico).

Estratégia:
    1. Separar artigos com e sem DOI.
    2. Para artigos sem DOI: comparar título dentro de blocos (mesmo ano ± 1)
       usando Jaro-Winkler via rapidfuzz (vetorizado com process.cdist).
    3. Para artigos com DOI diferente: idem, mas opcional (via --incluir-doi).
    4. Arestas de similaridade ≥ threshold → grafo de duplicatas →
       componentes conexos → manter 1 representante por componente.
    5. Marcar os demais com dedup_grupo (id do representante) e dedup_motivo.

Otimização:
    - Bloco por ano (±1): reduz comparações de O(n²) para O(n_bloco²).
    - rapidfuzz.process.cdist: vetorizado em C, muito mais rápido que loop Python.
    - Limiar conservador (≥ 0.92): evita falsos positivos em títulos curtos.

Input:
    dados/intermediarios/corpus_limpo.parquet

Output:
    dados/intermediarios/corpus_limpo.parquet  (sobrescreve, com dedup_grupo e dedup_motivo)
    dados/intermediarios/relatorio_dedup_fuzzy.json

Autor: Fernando Leite | FAPESP | Refatoração v2 — 22/maio/2026
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import unicodedata
from pathlib import Path

import pandas as pd

try:
    from rapidfuzz import process as rp, distance as rdist
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

INPUT_PATH     = Path("dados/intermediarios/corpus_limpo.parquet")
RELATORIO_PATH = Path("dados/intermediarios/relatorio_dedup_fuzzy.json")

THRESHOLD     = 0.92    # Jaro-Winkler ≥ 0.92 → considerar duplicatas
ANO_JANELA    = 1       # comparar dentro de ±1 ano

log = logging.getLogger("02c_dedup_fuzzy")


def _gravar_atomico(df, path: Path) -> None:
    """Sobrescreve o parquet de forma atômica (.tmp → rename).
    02c sobrescreve o único corpus limpo in-place; sem atomicidade um crash
    durante a escrita o corromperia.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_parquet(tmp, index=False, compression="snappy")
    tmp.replace(path)


def normalizar_titulo(t: str | None) -> str:
    """Normaliza título para comparação: caixa baixa, sem pontuação extra, NFC."""
    if not t or not isinstance(t, str):
        return ""
    t = unicodedata.normalize("NFC", t).lower()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def encontrar_pares_duplicatas(df_bloco: pd.DataFrame, threshold: float) -> list[tuple[str, str]]:
    """
    Dado um bloco (DataFrame com colunas id, titulo_norm), retorna pares (id_A, id_B)
    com similaridade Jaro-Winkler ≥ threshold.
    Usa rapidfuzz.process.cdist para comparação vetorizada.
    """
    if len(df_bloco) < 2 or not HAS_RAPIDFUZZ:
        return []

    ids    = df_bloco["id"].tolist()
    titulos = df_bloco["titulo_norm"].tolist()

    # Matriz de similaridade (NxN), dtype float32 para economia de memória
    sim_matrix = rp.cdist(
        titulos, titulos,
        scorer=rdist.JaroWinkler.normalized_similarity,
        dtype="float32"
    )

    pares = []
    n = len(ids)
    for i in range(n):
        for j in range(i + 1, n):
            if sim_matrix[i, j] >= threshold:
                pares.append((ids[i], ids[j], float(sim_matrix[i, j])))

    return pares


def resolver_componente(df: pd.DataFrame, ids_comp: list[str]) -> str:
    """
    Escolhe o representante de um componente de duplicatas.
    Critério: maior cited_by_count; em caso de empate, mais antigo (menor ano).
    """
    sub = df[df["id"].isin(ids_comp)].copy()
    sub = sub.sort_values(["citacoes", "ano"], ascending=[False, True])
    return sub.iloc[0]["id"]


def main(input_path: Path, relatorio_path: Path, incluir_doi: bool) -> None:
    if not HAS_RAPIDFUZZ:
        raise SystemExit("rapidfuzz não está instalado. Execute: pip install rapidfuzz")

    log.info("Lendo %s ...", input_path)
    df = pd.read_parquet(input_path)
    n_total = len(df)
    log.info("  %d artigos", n_total)

    # Inicializar colunas (preservar existentes se já houver)
    if "dedup_grupo" not in df.columns:
        df["dedup_grupo"] = None
    if "dedup_motivo" not in df.columns:
        df["dedup_motivo"] = None

    # Normalizar títulos
    titulo_col = "titulo" if "titulo" in df.columns else "titulo_limpo"
    df["titulo_norm"] = df[titulo_col].apply(normalizar_titulo)

    # Filtrar artigos sem DOI (e opcionalmente com DOI)
    sem_doi = df["doi"].isna() | (df["doi"].str.strip() == "")
    if incluir_doi:
        candidatos = df.copy()
        log.info("  Comparando todos os %d artigos (--incluir-doi)", len(candidatos))
    else:
        candidatos = df[sem_doi].copy()
        log.info("  Comparando %d artigos sem DOI", len(candidatos))

    if len(candidatos) < 2:
        log.info("Artigos insuficientes para comparação. Nada a fazer.")
        df.drop(columns=["titulo_norm"], inplace=True)
        _gravar_atomico(df, input_path)
        return

    # Construir pares por bloco de ano ± ANO_JANELA
    todos_os_pares: list[tuple] = []
    anos_unicos = sorted(candidatos["ano"].dropna().astype(int).unique())

    for ano in anos_unicos:
        bloco = candidatos[
            candidatos["ano"].between(ano - ANO_JANELA, ano + ANO_JANELA, inclusive="both")
        ]
        if len(bloco) < 2:
            continue
        pares = encontrar_pares_duplicatas(bloco[["id", "titulo_norm"]], THRESHOLD)
        todos_os_pares.extend([(a, b, sim) for a, b, sim in pares])

    log.info("  %d pares de duplicatas encontrados", len(todos_os_pares))

    if not todos_os_pares:
        log.info("Nenhuma duplicata fuzzy detectada.")
        df.drop(columns=["titulo_norm"], inplace=True)
        _gravar_atomico(df, input_path)
        return

    # Deduplificar pares (múltiplos blocos podem gerar o mesmo par)
    pares_unicos = list({(min(a, b), max(a, b)): sim for a, b, sim in todos_os_pares}.items())

    # Construir grafo simples (union-find) para componentes conexos
    parent: dict[str, str] = {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for (a, b), _ in pares_unicos:
        union(a, b)

    # Agrupar por componente e escolher representante
    from collections import defaultdict
    componentes: dict[str, list[str]] = defaultdict(list)
    ids_em_pares = set()
    for (a, b), _ in pares_unicos:
        ids_em_pares.add(a)
        ids_em_pares.add(b)
    for aid in ids_em_pares:
        componentes[find(aid)].append(aid)

    n_grupos   = len([c for c in componentes.values() if len(c) > 1])
    n_removidos = sum(len(c) - 1 for c in componentes.values() if len(c) > 1)
    log.info("  %d grupos de duplicatas, %d artigos a marcar como duplicata", n_grupos, n_removidos)

    # Marcar duplicatas no df
    for raiz, ids_comp in componentes.items():
        if len(ids_comp) < 2:
            continue
        representante = resolver_componente(df, ids_comp)
        duplicatas    = [x for x in ids_comp if x != representante]
        df.loc[df["id"].isin(duplicatas), "dedup_grupo"]  = representante
        df.loc[df["id"].isin(duplicatas), "dedup_motivo"] = "titulo_fuzzy"

    df.drop(columns=["titulo_norm"], inplace=True)
    _gravar_atomico(df, input_path)
    log.info("Corpus atualizado em %s", input_path)

    # Relatório
    stats = {
        "n_total": n_total,
        "n_candidatos_comparados": len(candidatos),
        "n_pares_encontrados": len(pares_unicos),
        "n_grupos": n_grupos,
        "n_duplicatas_marcadas": n_removidos,
        "threshold_jaro_winkler": THRESHOLD,
        "janela_ano": ANO_JANELA,
        "amostra_pares": [(a, b, round(s, 4)) for (a, b), s in pares_unicos[:20]]
    }
    relatorio_path.parent.mkdir(parents=True, exist_ok=True)
    relatorio_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Relatório: %s", relatorio_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler("logs/02c_dedup_fuzzy.log", mode="a", encoding="utf-8")])
    Path("logs").mkdir(exist_ok=True)

    parser = argparse.ArgumentParser(description="Deduplicação fuzzy por título.")
    parser.add_argument("--input",       type=Path, default=INPUT_PATH)
    parser.add_argument("--relatorio",   type=Path, default=RELATORIO_PATH)
    parser.add_argument("--incluir-doi", action="store_true",
                        help="Comparar também artigos COM DOI (mais lento, mais conservador).")
    args = parser.parse_args()
    main(args.input, args.relatorio, args.incluir_doi)
