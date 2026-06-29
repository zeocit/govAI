"""
04c_amostrar_para_label_studio.py — Amostragem estratificada para Gold Standard
==============================================================================
Manual §4.1 (v14) + Pré-registro OSF §3.4: seleciona N artigos para anotação
no Label Studio, com estratificação proporcional + reserva de fronteira.

Composição (DA-05):
    250 representativos: estratificação por
        (ano × idioma × periódico × quartil_citações × cluster_provável_LLM)
    250 fronteira: artigos com alta incerteza LLM
        (gap top1-top2 < 0,15 OR top1 < 0,55), ordenados por entropia decrescente

Sementes fixas (DA-05): 42, 123, 2026.

Input:
    dados/intermediarios/escores_llm_clusters.parquet
    dados/intermediarios/corpus_limpo.parquet
Output:
    dados/anotacoes/amostra_gs_seed{42|123|2026}.json (formato Label Studio)
    dados/anotacoes/amostra_gs_seed{...}_metadados.parquet

Autor: Fernando Leite | FAPESP | v2 — refatoração 22/maio/2026
"""

from __future__ import annotations

import argparse
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import orjson
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit

# ── Configuração ─────────────────────────────────────────────────────────────
ESCORES_LLM_PATH = Path("dados/intermediarios/escores_llm_clusters.parquet")
CORPUS_PATH      = Path("dados/intermediarios/corpus_limpo_textual.parquet")
OUTPUT_DIR       = Path("dados/anotacoes")
SNAPSHOT_PATH    = Path("dados/intermediarios/snapshot.json")

N_REPRESENTATIVOS = 250
N_FRONTEIRA       = 250
SEMENTES_PROJETO  = [42, 123, 2026]   # DA-05

# Critérios de fronteira (Manual §4.2bis.4)
GAP_FRONTEIRA  = 0.15
CONF_FRONTEIRA = 0.55

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("04c_amostrar_para_label_studio")


def carregar_dados() -> pd.DataFrame:
    """Carrega escores LLM + corpus textual, faz merge por id."""
    log.info("Lendo escores LLM: %s", ESCORES_LLM_PATH)
    escores = pd.read_parquet(ESCORES_LLM_PATH)
    log.info("  %d artigos com escores LLM", len(escores))

    log.info("Lendo corpus textual: %s", CORPUS_PATH)
    corpus = pd.read_parquet(CORPUS_PATH, columns=[
        "id", "titulo_limpo", "abstract_limpo", "ano", "idioma_detectado",
        "periodico_source_id", "citacoes",
    ])
    log.info("  %d artigos no corpus", len(corpus))

    df = escores.merge(corpus, on="id", how="inner")
    log.info("  %d após merge", len(df))
    if len(df) == 0:
        raise RuntimeError("Merge resultou em zero artigos. Verifique chaves de id.")
    return df


def computar_features_estratificacao(df: pd.DataFrame) -> pd.DataFrame:
    """Cria a chave de estrato e o flag de fronteira."""
    df = df.copy()

    # Quartis de citações (4 níveis). qcut com duplicates="drop" NÃO levanta erro
    # quando todas as citações são iguais (ex.: corpus pequeno todo com citacoes=0):
    # devolve TODA a coluna como NaN, silenciosamente. Isso degradaria a chave de
    # estrato (campo de quartil idêntico para todos) sem aviso. Detectamos o
    # colapso e caímos para um único quartil explícito, registrando em log.
    cit = df["citacoes"].astype("float64")
    quartis = pd.qcut(cit, q=4, labels=False, duplicates="drop")
    if quartis.isna().all():
        log.warning(
            "  Citações sem variância suficiente para quartis (%d valores distintos). "
            "Usando quartil único (0) — estratificação por citação desativada.",
            cit.nunique(dropna=True),
        )
        df["quartil_citacoes"] = pd.Series(0, index=df.index, dtype="Int8")
    else:
        df["quartil_citacoes"] = quartis.astype("Int8")

    # Chave composta — Manual §4.1
    df["estrato"] = (
        df["ano"].astype(str) + "|" +
        df["idioma_detectado"].fillna("NA").astype(str) + "|" +
        df["periodico_source_id"].astype(str) + "|" +
        df["quartil_citacoes"].astype(str) + "|" +
        df["cluster_primario_llm"].astype(str)
    )

    # ── Detecção do schema dos escores LLM (suporta 04a v2/v3 e legado) ─────
    # 04a v2/v3 escreve cluster_<c>_llm; convenção legada usava score_<c>.
    # Tenta cada padrão; se nenhum estiver completo, falha com mensagem clara.
    CLUSTERS_OK = ("si", "ps", "sts", "law", "pa", "bcs")
    candidatos = [
        [f"cluster_{c}_llm" for c in CLUSTERS_OK],   # convenção 04a v2/v3
        [f"score_{c}"       for c in CLUSTERS_OK],   # convenção legada
    ]
    score_cols: list[str] | None = None
    for grupo in candidatos:
        if all(col in df.columns for col in grupo):
            score_cols = grupo
            break
    if score_cols is None:
        relevantes = sorted(c for c in df.columns
                            if "cluster" in c or c.startswith("score_"))
        raise RuntimeError(
            "Colunas de escore LLM não encontradas. Esperado um dos prefixos: "
            "cluster_<c>_llm (04a v2+) ou score_<c> (legado). "
            f"Colunas presentes relacionadas: {relevantes}"
        )

    # Garantir ordem canônica das colunas para consistência cross-pipeline
    scores_mat = df[score_cols].to_numpy(dtype=np.float64)
    if scores_mat.size == 0:
        raise RuntimeError("Matriz de escores vazia após seleção de colunas.")

    sorted_scores = np.sort(scores_mat, axis=1)[:, ::-1]  # decrescente
    top1 = sorted_scores[:, 0]
    top2 = sorted_scores[:, 1] if sorted_scores.shape[1] > 1 else np.zeros_like(top1)

    df["confianca_cluster"] = top1
    df["gap_top1_top2"]     = top1 - top2
    df["eh_fronteira"]      = (df["gap_top1_top2"] < GAP_FRONTEIRA) | (top1 < CONF_FRONTEIRA)

    # Entropia LLM (calibração e estratificação de fronteira)
    # Re-normaliza para tratar escores que não somam exatamente 1 (clipping prévio)
    p = np.clip(scores_mat, 1e-12, None)
    p = p / p.sum(axis=1, keepdims=True)
    df["entropia_llm"] = -(p * np.log(p)).sum(axis=1)

    return df


def amostrar_representativos(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """Amostragem estratificada por chave 'estrato'.

    StratifiedShuffleSplit exige ≥2 artigos por estrato. A chave plena
    (ano × idioma × periódico × quartil × cluster) é muito granular: em
    corpora pequenos ou de teste, quase todo estrato vira singleton e a
    amostra representativa colapsa para zero — comportamento silenciosamente
    errado. Implementa-se um recuo progressivo de granularidade:

        1. estrato pleno (5 dimensões)         — ideal
        2. estrato reduzido (cluster × quartil) — preserva equilíbrio
                                                  disciplinar e de citações
        3. amostra aleatória estratificada por cluster — piso garantido

    O nível efetivamente usado é registrado em log para rastreabilidade
    (Pré-registro OSF §3.4 exige reportar desvios da estratificação plena).
    """
    rep = df[~df["eh_fronteira"]].copy()
    if len(rep) == 0:
        log.warning("  Nenhum artigo representativo (todos são fronteira).")
        return rep

    def _estratos_validos(col: str) -> pd.Index:
        contagem = rep[col].value_counts()
        return contagem[contagem >= 2].index

    # Nível 1: estrato pleno
    estratos_validos = _estratos_validos("estrato")
    cobertura_plena = rep["estrato"].isin(estratos_validos).mean()
    nivel = "pleno"
    col_estrato = "estrato"

    # Nível 2: se a chave plena cobre < 50% dos artigos, recuar para
    # cluster × quartil (preserva as duas dimensões metodologicamente
    # mais relevantes — DA-05).
    if cobertura_plena < 0.50:
        rep["estrato_reduzido"] = (
            rep["cluster_primario_llm"].astype(str) + "|" +
            rep["quartil_citacoes"].astype(str)
        )
        estratos_validos = _estratos_validos("estrato_reduzido")
        cobertura_reduzida = rep["estrato_reduzido"].isin(estratos_validos).mean()
        if cobertura_reduzida >= 0.50:
            nivel = "reduzido (cluster × quartil)"
            col_estrato = "estrato_reduzido"
        else:
            # Nível 3: piso — estratificar só por cluster
            rep["estrato_cluster"] = rep["cluster_primario_llm"].astype(str)
            estratos_validos = _estratos_validos("estrato_cluster")
            nivel = "mínimo (cluster)"
            col_estrato = "estrato_cluster"

    rep_filtrado = rep[rep[col_estrato].isin(estratos_validos)]
    descartados = len(rep) - len(rep_filtrado)
    log.info(
        "  Estratificação nível '%s': %d estratos válidos (≥2). "
        "%d artigos descartados de estratos singletons.",
        nivel, len(estratos_validos), descartados,
    )

    if len(rep_filtrado) <= n:
        log.warning(
            "  Apenas %d artigos representativos disponíveis (alvo %d). Usando todos.",
            len(rep_filtrado), n,
        )
        return rep_filtrado.drop(
            columns=[c for c in ("estrato_reduzido", "estrato_cluster")
                     if c in rep_filtrado.columns]
        )

    sss = StratifiedShuffleSplit(n_splits=1, train_size=n, random_state=seed)
    idx_train, _ = next(sss.split(rep_filtrado, rep_filtrado[col_estrato]))
    return rep_filtrado.iloc[idx_train].drop(
        columns=[c for c in ("estrato_reduzido", "estrato_cluster")
                 if c in rep_filtrado.columns]
    ).copy()


def amostrar_fronteira(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """Seleciona n artigos de fronteira ordenados por entropia decrescente.
    Em caso de empate, usa seed para desempate reprodutível.
    """
    fronteira = df[df["eh_fronteira"]].copy()
    if len(fronteira) <= n:
        log.warning(
            "  Apenas %d artigos de fronteira disponíveis (alvo %d). Usando todos.",
            len(fronteira), n,
        )
        return fronteira

    # Pequena perturbação determinística para desempate
    rng = np.random.default_rng(seed)
    fronteira["_jitter"] = rng.uniform(0, 1e-9, size=len(fronteira))
    fronteira["_score_ordenacao"] = fronteira["entropia_llm"] + fronteira["_jitter"]

    fronteira = fronteira.sort_values("_score_ordenacao", ascending=False)
    return fronteira.head(n).drop(columns=["_jitter", "_score_ordenacao"])


def exportar_label_studio(df_amostra: pd.DataFrame, arquivo_json: Path, projeto: str) -> None:
    """Exporta no formato Label Studio.
    projeto ∈ {'cluster', 'epi'} — campos exibidos diferem por projeto."""
    base_cols = ["id", "titulo_limpo", "abstract_limpo"]
    if projeto == "cluster":
        # Mostrar predição LLM como dica auxiliar (anotador decide independentemente)
        extra_cols = ["cluster_primario_llm", "confianca_cluster", "gap_top1_top2", "eh_fronteira"]
    else:
        extra_cols = ["eh_fronteira"]

    cols = [c for c in base_cols + extra_cols if c in df_amostra.columns]
    tasks = [
        {"data": {k: (v if pd.notna(v) else None) for k, v in rec.items()}}
        for rec in df_amostra[cols].to_dict(orient="records")
    ]

    # Atomic write via orjson
    arquivo_json.parent.mkdir(parents=True, exist_ok=True)
    tmp = arquivo_json.with_suffix(".json.tmp")
    tmp.write_bytes(orjson.dumps(tasks, option=orjson.OPT_INDENT_2))
    tmp.replace(arquivo_json)
    log.info("Gravado: %s (%d tarefas)", arquivo_json, len(tasks))


def registrar_snapshot(arquivos: list[Path], seed: int) -> None:
    """Hash SHA-256 + entrada em snapshot.json para reprodutibilidade."""
    snapshot = {}
    if SNAPSHOT_PATH.exists():
        snapshot = orjson.loads(SNAPSHOT_PATH.read_bytes())
    for arq in arquivos:
        if arq.exists():
            sha = hashlib.sha256(arq.read_bytes()).hexdigest()
            snapshot[str(arq)] = {
                "sha256": sha,
                "size_bytes": arq.stat().st_size,
                "seed": seed,
                "data_amostragem": datetime.now(timezone.utc).isoformat(),
                "script": "04c_amostrar_para_label_studio.py",
            }
    SNAPSHOT_PATH.write_bytes(orjson.dumps(snapshot, option=orjson.OPT_INDENT_2))


def main(seeds: list[int], n_rep: int, n_front: int) -> None:
    df = carregar_dados()
    df = computar_features_estratificacao(df)

    log.info("Estratos únicos: %d", df["estrato"].nunique())
    log.info("Artigos de fronteira: %d (%.1f%%)",
             df["eh_fronteira"].sum(), 100 * df["eh_fronteira"].mean())

    for seed in seeds:
        log.info("=== Amostragem com seed=%d ===", seed)
        amostra_rep   = amostrar_representativos(df, n_rep, seed)
        amostra_front = amostrar_fronteira(df, n_front, seed)
        amostra_rep["criterio"]   = "representativo"
        amostra_front["criterio"] = "fronteira"
        amostra = pd.concat([amostra_rep, amostra_front], ignore_index=True)

        log.info("  Total amostrado: %d (%d rep + %d front)",
                 len(amostra), len(amostra_rep), len(amostra_front))

        # Exportar JSON Label Studio (cluster e epi separados — DA-04)
        arquivo_cluster = OUTPUT_DIR / f"amostra_gs_seed{seed}_cluster.json"
        arquivo_epi     = OUTPUT_DIR / f"amostra_gs_seed{seed}_epi.json"
        exportar_label_studio(amostra, arquivo_cluster, projeto="cluster")
        exportar_label_studio(amostra, arquivo_epi,     projeto="epi")

        # Metadados em parquet para auditoria + cálculo de alpha_artigo downstream
        meta_path = OUTPUT_DIR / f"amostra_gs_seed{seed}_metadados.parquet"
        cols_meta = [
            "id", "criterio", "estrato", "ano", "idioma_detectado",
            "periodico_source_id", "quartil_citacoes", "citacoes",
            "cluster_primario_llm", "confianca_cluster", "gap_top1_top2",
            "entropia_llm", "eh_fronteira",
        ]
        cols_meta = [c for c in cols_meta if c in amostra.columns]
        tmp_meta = meta_path.with_suffix(".parquet.tmp")
        amostra[cols_meta].to_parquet(tmp_meta, index=False, compression="snappy")
        tmp_meta.replace(meta_path)

        registrar_snapshot([arquivo_cluster, arquivo_epi, meta_path], seed)
        log.info("  Snapshot atualizado.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amostragem estratificada para GS — Manual §4.1")
    parser.add_argument("--seeds", type=int, nargs="+", default=SEMENTES_PROJETO,
                        help="Sementes (default: 42 123 2026 conforme DA-05)")
    parser.add_argument("--n-rep", type=int, default=N_REPRESENTATIVOS)
    parser.add_argument("--n-front", type=int, default=N_FRONTEIRA)
    args = parser.parse_args()
    main(args.seeds, args.n_rep, args.n_front)
