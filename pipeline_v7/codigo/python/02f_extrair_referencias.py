"""
02f_extrair_referencias.py — Extração de referências citadas
============================================================
Output Manual §3.4bis (NOVO em v14): a partir do corpus limpo, produz uma
edge-list de citações que serve de base para análises de co-citação,
acoplamento bibliográfico, e PageRank do corpus.

Input:
    dados/intermediarios/corpus_limpo.parquet
    (colunas usadas: id, referencias, ano)

Output:
    dados/redes/edges_citacoes.csv (ou .parquet via --formato parquet)

Codebook v2.1 (a atualizar):
    edges_citacoes.csv:
        id_citante         str    OpenAlex Work ID do artigo que cita
        id_citada          str    OpenAlex Work ID da obra citada
        ano_citante        int    Ano do artigo citante (denormalizado)
        eh_interna         bool   TRUE se a obra citada também está no corpus

Notas operacionais:
    - Tabela cresce ~O(n_artigos × média_refs_por_artigo). Para corpus
      de 21k artigos com ~30 refs/artigo médio: ~630k linhas, ~30MB em CSV.
      Para Parquet com Snappy: ~5-8MB. Recomenda-se --formato parquet em
      uso operacional; CSV apenas para inspeção rápida.
    - Citações internas (eh_interna=TRUE) são as que ficarão na rede de
      co-citação intra-corpus. Citações externas viram input para BERTopic
      de referências (§7.5 do Manual) e para análise de filiação intelectual.

Robustez:
    - referencias ausente, vazio, ou não-list → artigo pulado
    - elementos não-str ou vazios → pulados individualmente
    - logs de stats descritivos para o relatório de qualidade §3.4bis

Autor: Fernando Leite | FAPESP | Refatoração v2 — 22/maio/2026
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

INPUT_DEFAULT = Path("dados/intermediarios/corpus_limpo.parquet")
OUT_DEFAULT   = Path("dados/redes/edges_citacoes.csv")

log = logging.getLogger("02f_extrair_referencias")


def main(input_path: Path, out_path: Path, fmt: str) -> None:
    log.info("Lendo %s ...", input_path)
    df = pd.read_parquet(input_path, columns=["id", "referencias", "ano"])
    log.info("  %d artigos carregados", len(df))

    corpus_ids: set[str] = set(df["id"].dropna().astype(str))

    # === Extração ===
    rows: list[tuple] = []
    n_sem_refs = 0
    for art_id, refs, ano in zip(df["id"], df["referencias"], df["ano"]):
        if refs is None or not isinstance(refs, (list, tuple)) or len(refs) == 0:
            n_sem_refs += 1
            continue

        ano_int = int(ano) if pd.notna(ano) else None
        for ref in refs:
            if not isinstance(ref, str) or not ref:
                continue
            rows.append((art_id, ref, ano_int, ref in corpus_ids))

    log.info("  %d citações extraídas (%d artigos sem refs válidas)",
             len(rows), n_sem_refs)

    if not rows:
        log.error("Nenhuma citação extraída. Abortando.")
        return

    out = pd.DataFrame(rows, columns=["id_citante", "id_citada", "ano_citante", "eh_interna"])

    # === Stats descritivos (vão no relatório de qualidade §3.4bis) ===
    n_citante_unique = out["id_citante"].nunique()
    n_citada_unique  = out["id_citada"].nunique()
    n_interna        = int(out["eh_interna"].sum())
    media_refs       = out.groupby("id_citante").size().mean()
    mediana_refs     = out.groupby("id_citante").size().median()

    log.info("Stats:")
    log.info("  Artigos com refs:      %d / %d (%.1f%%)",
             n_citante_unique, len(df), 100 * n_citante_unique / len(df))
    log.info("  Refs únicas:           %d", n_citada_unique)
    log.info("  Citações internas:    %d (%.1f%% das citações)",
             n_interna, 100 * n_interna / len(out))
    log.info("  Média refs/artigo:    %.1f", media_refs)
    log.info("  Mediana refs/artigo:  %.0f", mediana_refs)

    # === Gravar ===
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "parquet":
        out_path = out_path.with_suffix(".parquet")
        out.to_parquet(out_path, index=False, compression="snappy")
    else:
        out.to_csv(out_path, index=False, encoding="utf-8")
    log.info("Gravado: %s", out_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    parser = argparse.ArgumentParser(description="Extrai edge-list de citações do corpus limpo.")
    parser.add_argument("--input",   type=Path, default=INPUT_DEFAULT)
    parser.add_argument("--output",  type=Path, default=OUT_DEFAULT)
    parser.add_argument("--formato", choices=["csv", "parquet"], default="csv")
    args = parser.parse_args()
    main(args.input, args.output, args.formato)
