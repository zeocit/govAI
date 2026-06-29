"""
02_limpeza_estrutural.py — Limpeza estrutural do corpus bruto
=============================================================
Manual §3.3 (v14): aplica filtros estruturais ao corpus bruto produzido
pelo script 01a, gerando o corpus limpo estrutural para etapas seguintes.

Input:
    dados/brutos/corpus_openalex.parquet

Output:
    dados/intermediarios/corpus_limpo.parquet
    dados/intermediarios/relatorio_limpeza.json   (estatísticas)

Transformações aplicadas:
    1. Filtro de tipo de obra: mantém 'article' e 'review' apenas
    2. Filtro de ano: 2000 <= ano <= 2024
    3. Filtro de idioma: mantém 'en' e 'pt' (e ausentes — detectados em 03)
    4. Remoção de abstract ausente (article sem abstract é inútil para classificação)
    5. Remoção de DOI duplicado exacto (mantém o registro com maior cited_by_count)
    6. Normalização de campos: garantir tipos pandas corretos
    7. Desserialização de colunas JSON (autores, referencias, concepts)
       para object (list/dict) — facilita scripts subsequentes

    Nota: deduplicação fuzzy (02c) e detecção de retração (02b) são executados
    APÓS este script, pois dependem de limpeza prévia.

Autor: Fernando Leite | FAPESP | Refatoração v2 — 22/maio/2026
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd
import orjson

INPUT_PATH       = Path("dados/brutos/corpus_openalex.parquet")
OUTPUT_PATH      = Path("dados/intermediarios/corpus_limpo.parquet")
RELATORIO_PATH   = Path("dados/intermediarios/relatorio_limpeza.json")

TIPOS_VALIDOS    = {"article", "review"}
ANO_MIN, ANO_MAX = 2000, 2024
IDIOMAS_VALIDOS  = {"en", "pt"}   # None/NaN: passa (detectado em 03_limpeza_textual.R)

log = logging.getLogger("02_limpeza_estrutural")


def desserializar_json_col(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Converte coluna de string JSON para object (list/dict).
    Linhas com JSON inválido recebem lista vazia.

    Otimização v2: usa orjson (parser C, 3–10x mais rápido que json builtin)
    + list comprehension (evita overhead do .apply do pandas).
    Idempotente: se a coluna já vem desserializada (parquet via pyarrow),
    retorna sem alteração.
    """
    if len(df) == 0:
        return df

    # Guard de contexto: se já é objeto Python (parquet com nested types), no-op
    sample = df[col].dropna().head(1)
    if len(sample) > 0 and isinstance(sample.iloc[0], (list, dict)):
        return df

    def fast_parse(v):
        if v is None or pd.isna(v):
            return []
        if isinstance(v, (list, dict)):
            return v
        if not isinstance(v, str):
            return []
        try:
            return orjson.loads(v)
        except (orjson.JSONDecodeError, ValueError, TypeError):
            return []

    df[col] = [fast_parse(x) for x in df[col]]
    return df


def main(input_path: Path, output_path: Path, relatorio_path: Path) -> None:
    log.info("Lendo %s ...", input_path)
    df = pd.read_parquet(input_path)
    n_inicial = len(df)
    log.info("  %d artigos brutos", n_inicial)
    stats: dict = {"n_inicial": n_inicial, "filtros": {}}

    # ── 1. Filtro tipo de obra ────────────────────────────────────────────────
    df = df[df["tipo_obra"].isin(TIPOS_VALIDOS)]
    stats["filtros"]["tipo_obra"] = n_inicial - len(df)
    log.info("  Após filtro tipo (%s): %d (removidos: %d)",
             TIPOS_VALIDOS, len(df), stats["filtros"]["tipo_obra"])

    # ── 2. Filtro de ano ──────────────────────────────────────────────────────
    df["ano"] = pd.to_numeric(df["ano"], errors="coerce")
    n_antes = len(df)
    df = df[df["ano"].between(ANO_MIN, ANO_MAX, inclusive="both")]
    stats["filtros"]["ano"] = n_antes - len(df)
    log.info("  Após filtro ano (%d-%d): %d (removidos: %d)",
             ANO_MIN, ANO_MAX, len(df), stats["filtros"]["ano"])

    # ── 3. Filtro de idioma ───────────────────────────────────────────────────
    # Mantém idiomas válidos E artigos sem idioma declarado (serão detectados em 03)
    n_antes = len(df)
    mask_idioma = df["idioma"].isin(IDIOMAS_VALIDOS) | df["idioma"].isna()
    df = df[mask_idioma]
    stats["filtros"]["idioma"] = n_antes - len(df)
    log.info("  Após filtro idioma (%s + NA): %d (removidos: %d)",
             IDIOMAS_VALIDOS, len(df), stats["filtros"]["idioma"])

    # ── 4. Filtro abstract ausente ────────────────────────────────────────────
    n_antes = len(df)
    df = df[df["abstract"].notna() & (df["abstract"].str.strip() != "")]
    stats["filtros"]["abstract_ausente"] = n_antes - len(df)
    log.info("  Após filtro abstract ausente: %d (removidos: %d)",
             len(df), stats["filtros"]["abstract_ausente"])

    # ── 5. Deduplicação por DOI exacto ────────────────────────────────────────
    n_antes = len(df)
    df["doi"] = df["doi"].str.lower().str.strip()
    tem_doi = df[df["doi"].notna() & (df["doi"] != "")]
    sem_doi = df[df["doi"].isna() | (df["doi"] == "")]
    # Para artigos com DOI, manter apenas 1 por DOI (maior cited_by_count)
    tem_doi_dedup = (
        tem_doi.sort_values("citacoes", ascending=False)
               .drop_duplicates(subset=["doi"], keep="first")
    )
    df = pd.concat([tem_doi_dedup, sem_doi], ignore_index=True)
    stats["filtros"]["doi_duplicado"] = n_antes - len(df)
    log.info("  Após dedup DOI exacto: %d (removidos: %d)",
             len(df), stats["filtros"]["doi_duplicado"])

    # ── 6. Normalização de tipos ──────────────────────────────────────────────
    # Decisão arquitetural: MANTER Pandas nullable types (Int32) — pyarrow + R/arrow
    # lidam bem desde 2022. Converter para float64 (como sugerido por Gemini)
    # degrada o schema semântico (ano não pode ser 2023.5) e perde a distinção
    # entre citacoes=0 (nunca citado) e citacoes=NA (metadado ausente) — distinção
    # cientometricamente importante para IPC e normalizações por citação.
    df["ano"]      = df["ano"].astype("Int32")
    df["citacoes"] = pd.to_numeric(df["citacoes"], errors="coerce").astype("Int32")
    df["is_retracted"] = df["is_retracted"].fillna(False).astype(bool)

    # Sanity check: anos fora do intervalo do projeto são bug de extração
    fora_intervalo = df["ano"].between(2000, 2024, inclusive="both")
    assert (fora_intervalo | df["ano"].isna()).all(), (
        f"Anos fora de 2000-2024 detectados: "
        f"{df.loc[~fora_intervalo & df['ano'].notna(), 'ano'].unique()[:10]}"
    )

    # ── 7. Desserialização de colunas JSON ───────────────────────────────────
    for col in ["autores", "referencias", "concepts"]:
        if col in df.columns:
            df = desserializar_json_col(df, col)
            log.info("  Coluna '%s' desserializada", col)

    # ── Estatísticas finais ───────────────────────────────────────────────────
    stats["n_final"] = len(df)
    stats["retencao_pct"] = round(100 * len(df) / n_inicial, 1)
    stats["distribuicao_idioma"] = df["idioma"].fillna("NA").value_counts().to_dict()
    stats["distribuicao_tipo"]   = df["tipo_obra"].value_counts().to_dict()
    stats["distribuicao_ano"]    = df["ano"].value_counts().sort_index().to_dict()

    log.info("Corpus limpo: %d artigos (retenção: %.1f%%)", len(df), stats["retencao_pct"])

    # ── Gravar (atomic write + hash em snapshot) ──────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(".parquet.tmp")
    df.to_parquet(tmp_path, index=False, compression="snappy")
    tmp_path.replace(output_path)

    import hashlib
    from datetime import datetime, timezone
    sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()
    snapshot_path = Path("dados/intermediarios/snapshot.json")
    snapshot = {}
    if snapshot_path.exists():
        snapshot = orjson.loads(snapshot_path.read_bytes())
    snapshot[str(output_path)] = {
        "sha256": sha256,
        "size_bytes": output_path.stat().st_size,
        "n_rows": len(df),
        "data_processamento": datetime.now(timezone.utc).isoformat(),
        "script": "02_limpeza_estrutural.py",
    }
    snapshot_path.write_bytes(orjson.dumps(snapshot, option=orjson.OPT_INDENT_2))
    log.info("Gravado: %s | sha256=%s", output_path, sha256[:16])

    relatorio_path.parent.mkdir(parents=True, exist_ok=True)
    relatorio_path.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8"
    )
    log.info("Relatório: %s", relatorio_path)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/02_limpeza_estrutural.log", mode="a", encoding="utf-8")
        ]
    )
    Path("logs").mkdir(exist_ok=True)

    parser = argparse.ArgumentParser(description="Limpeza estrutural do corpus bruto.")
    parser.add_argument("--input",     type=Path, default=INPUT_PATH)
    parser.add_argument("--output",    type=Path, default=OUTPUT_PATH)
    parser.add_argument("--relatorio", type=Path, default=RELATORIO_PATH)
    args = parser.parse_args()
    main(args.input, args.output, args.relatorio)
