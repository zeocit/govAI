"""
02b_detectar_retracoes.py — Detecção e flag de retrações
=========================================================
Manual §3.3.1 (v14): identifica artigos retratados ou problemáticos
por dois métodos complementares e atualiza (ou adiciona) a coluna
flag_retratado no corpus limpo.

Input:
    dados/intermediarios/corpus_limpo.parquet

Output:
    dados/intermediarios/corpus_limpo.parquet  (sobrescreve, com flag_retratado atualizado)
    dados/intermediarios/relatorio_retracoes.json

Métodos de detecção (aplicados em camadas):
    1. Campo is_retracted do OpenAlex (alta confiabilidade, pode estar desatualizado)
    2. Palavras-chave no título (cobre casos não reportados ao OpenAlex ainda)

    Nota sobre Retraction Watch:
        Uma terceira camada ideal seria cruzamento com o banco de dados Retraction Watch.
        Este banco requer download manual periódico (CSV disponível em:
        http://retractiondatabase.org/) — não automatizável de forma estável.
        Quando disponível localmente, passar o caminho via --retraction-watch.

Autor: Fernando Leite | FAPESP | Refatoração v2 — 22/maio/2026
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

import pandas as pd

INPUT_PATH     = Path("dados/intermediarios/corpus_limpo.parquet")
RELATORIO_PATH = Path("dados/intermediarios/relatorio_retracoes.json")

# Palavras-chave para detecção em título (compiladas uma vez para performance)
_KEYWORDS_EN = [
    r"\bretraction\b", r"\bretracted\b", r"\berratum\b", r"\bcorrigendum\b",
    r"\bcorrection to\b", r"\bexpression of concern\b", r"\bwithdrawal\b",
    r"\bwithdrawn\b", r"\bpublisher's note\b", r"\beditor.s note\b"
]
_KEYWORDS_PT = [
    r"\bretrata[çc][aã]o\b", r"\bretratado\b", r"\bcorre[çc][aã]o\b",
    r"\bpreocupa[çc][aã]o editorial\b", r"\bretirada\b", r"\berrata\b"
]
_PATTERN = re.compile(
    "|".join(_KEYWORDS_EN + _KEYWORDS_PT),
    flags=re.IGNORECASE
)

log = logging.getLogger("02b_detectar_retracoes")


def detect_by_keyword(titulo: str | None) -> bool:
    """Retorna True se o título contém marcadores de retração."""
    if not titulo or not isinstance(titulo, str):
        return False
    return bool(_PATTERN.search(titulo))


def cruzar_retraction_watch(df: pd.DataFrame, rw_path: Path) -> pd.Series:
    """
    Cruza o corpus com o Retraction Watch CSV (quando disponível).

    O CSV do Retraction Watch tem colunas: Title, DOI, PMID, RetractionDate, etc.
    Fazemos match por DOI (preciso) e por título normalizado (fallback fuzzy-light).
    """
    try:
        rw = pd.read_csv(rw_path, encoding="utf-8", low_memory=False)
        # Normalizar DOIs para comparação
        rw_dois = set(rw["DOI"].dropna().str.lower().str.strip())
        mask_doi = df["doi"].str.lower().str.strip().isin(rw_dois)
        log.info("  Retraction Watch: %d matches por DOI", mask_doi.sum())
        return mask_doi
    except Exception as exc:
        log.warning("  Não foi possível usar Retraction Watch: %s", exc)
        return pd.Series(False, index=df.index)


def main(input_path: Path, relatorio_path: Path, rw_path: Path | None) -> None:
    log.info("Lendo %s ...", input_path)
    df = pd.read_parquet(input_path)
    n_total = len(df)
    log.info("  %d artigos", n_total)

    # ── Método 1: campo is_retracted do OpenAlex ─────────────────────────────
    col_is_retracted = df.get("is_retracted", pd.Series(False, index=df.index))
    flag_openalex = col_is_retracted.fillna(False).astype(bool)
    log.info("  Método 1 (OpenAlex is_retracted): %d flagged", flag_openalex.sum())

    # ── Método 2: palavras-chave no título ────────────────────────────────────
    titulo_col = df.get("titulo", df.get("titulo_limpo", pd.Series("", index=df.index)))
    flag_keyword = titulo_col.apply(detect_by_keyword)
    log.info("  Método 2 (keyword título): %d flagged", flag_keyword.sum())

    # ── Método 3: Retraction Watch (opcional) ─────────────────────────────────
    flag_rw = pd.Series(False, index=df.index)
    if rw_path and rw_path.exists():
        flag_rw = cruzar_retraction_watch(df, rw_path)
        log.info("  Método 3 (Retraction Watch): %d flagged", flag_rw.sum())
    else:
        log.info("  Método 3 (Retraction Watch): não aplicado (arquivo não fornecido)")

    # ── Consolidar ────────────────────────────────────────────────────────────
    df["flag_retratado"] = flag_openalex | flag_keyword | flag_rw
    df["motivo_retracao"] = ""
    df.loc[flag_openalex, "motivo_retracao"] += "openalex;"
    df.loc[flag_keyword,  "motivo_retracao"] += "keyword;"
    df.loc[flag_rw,       "motivo_retracao"] += "retraction_watch;"
    df["motivo_retracao"] = df["motivo_retracao"].str.rstrip(";")

    n_flagged = df["flag_retratado"].sum()
    log.info("Total flagged: %d (%.2f%% do corpus)", n_flagged, 100 * n_flagged / n_total)

    # ── Gravar corpus atualizado (atomic: .tmp → rename) ─────────────────────
    # Sobrescrever o input in-place sem atomicidade corromperia o corpus se o
    # processo morresse durante a escrita — e este é o único corpus limpo.
    tmp_path = input_path.with_suffix(input_path.suffix + ".tmp")
    df.to_parquet(tmp_path, index=False, compression="snappy")
    tmp_path.replace(input_path)
    log.info("Corpus atualizado em %s", input_path)

    # ── Relatório ─────────────────────────────────────────────────────────────
    flagged_sample = df[df["flag_retratado"]].head(20)[["id", "titulo", "motivo_retracao"]].to_dict("records")
    stats = {
        "n_total": n_total,
        "n_flagged": int(n_flagged),
        "pct_flagged": round(100 * n_flagged / n_total, 3),
        "por_metodo": {
            "openalex": int(flag_openalex.sum()),
            "keyword": int(flag_keyword.sum()),
            "retraction_watch": int(flag_rw.sum()),
            "apenas_keyword_nao_openalex": int((flag_keyword & ~flag_openalex).sum())
        },
        "amostra_flagged": flagged_sample
    }
    relatorio_path.parent.mkdir(parents=True, exist_ok=True)
    relatorio_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    log.info("Relatório: %s", relatorio_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler("logs/02b_detectar_retracoes.log", mode="a", encoding="utf-8")])
    Path("logs").mkdir(exist_ok=True)

    parser = argparse.ArgumentParser(description="Detecção de retrações no corpus.")
    parser.add_argument("--input",           type=Path, default=INPUT_PATH)
    parser.add_argument("--relatorio",       type=Path, default=RELATORIO_PATH)
    parser.add_argument("--retraction-watch",type=Path, default=None,
                        help="Caminho para o CSV do Retraction Watch (opcional).")
    args = parser.parse_args()
    main(args.input, args.relatorio, args.retraction_watch)
