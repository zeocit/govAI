"""
02d_extrair_autores.py — Extração de estrutura de autoria
==========================================================
Output Manual §3.4bis (NOVO em v14): a partir do corpus limpo, produz duas
tabelas (nodes + edges) que servirão de input para construção da rede de
coautoria e para análise descritiva de produtividade por autor.

Input:
    dados/intermediarios/corpus_limpo.parquet
    (colunas usadas: id, autores [estruturada], ano)

Outputs:
    dados/redes/nodes_autores.csv          — uma linha por autor único
    dados/redes/edges_autores_artigos.csv  — uma linha por par (autor, artigo)

Codebook v2.1 (a atualizar):

    nodes_autores.csv:
        author_id          str    OpenAlex Author ID
        display_name       str    Nome de exibição
        n_artigos          int    Total de artigos do autor no corpus
        n_first_author     int    Quantas vezes foi primeiro autor
        n_last_author      int    Quantas vezes foi último autor
        n_corresponding    int    Quantas vezes foi corresponding
        n_instituicoes     int    Número de instituições distintas (carreira no corpus)
        instituicoes_ids   str    IDs concatenadas por ";"
        n_paises           int    Número de países distintos
        paises_codes       str    Códigos ISO 3166-1 alpha-2 concatenados por ";"
        is_brasileiro      bool   TRUE se ao menos uma instituição é BR
        primeiro_ano       int    Ano da primeira publicação no corpus
        ultimo_ano         int    Ano da última publicação no corpus

    edges_autores_artigos.csv:
        id_artigo          str
        author_id          str
        ordem_autoria      int    Posição na lista de autores (1-indexed)
        is_first           bool
        is_last            bool
        is_corresponding   bool

Robustez implementada:
    - authorships ausente, vazio, ou não-list → artigo é pulado (com log)
    - elementos do authorship sem author.id → pulados individualmente
    - institutions ausente ou vazio → autor entra sem institutions
    - position ausente → infere por ordem (first/last/middle)

Otimização implementada:
    - groupby vetorizado para contagens por autor (vs. loop)
    - leitura seletiva de colunas (pandas read_parquet columns=)
    - set para acumular institutions/countries (O(1) dedup)

Autor: Fernando Leite | FAPESP | Refatoração v2 — 22/maio/2026
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

INPUT_DEFAULT     = Path("dados/intermediarios/corpus_limpo.parquet")
OUT_NODES_DEFAULT = Path("dados/redes/nodes_autores.csv")
OUT_EDGES_DEFAULT = Path("dados/redes/edges_autores_artigos.csv")

log = logging.getLogger("02d_extrair_autores")


def parse_authorship(item: dict) -> dict | None:
    """Normaliza um elemento da lista 'authorships' do OpenAlex.

    Lida com chaves ausentes, valores None, e variações de schema observadas
    em diferentes snapshots do OpenAlex (formatos novos vs. antigos).

    Returns:
        dict normalizado ou None se o registro não tem author_id (degenerado).
    """
    if not isinstance(item, dict):
        return None

    author_block = item.get("author") or {}
    author_id = author_block.get("id")
    if not author_id:
        return None

    institutions = item.get("institutions") or []
    inst_ids: list[str] = []
    inst_countries: list[str] = []
    for inst in institutions:
        if not isinstance(inst, dict):
            continue
        iid = inst.get("id")
        if iid:
            inst_ids.append(iid)
        cc = inst.get("country_code")
        if cc:
            inst_countries.append(cc)

    # Fallback: campo "countries" no nível do authorship (formato mais recente)
    if not inst_countries and item.get("countries"):
        inst_countries = [c for c in item["countries"] if isinstance(c, str)]

    return {
        "author_id": author_id,
        "display_name": author_block.get("display_name", "") or "",
        "institution_ids": inst_ids,
        "country_codes": inst_countries,
        "position": item.get("author_position", "middle"),
        "is_corresponding": bool(item.get("is_corresponding", False))
    }


def main(input_path: Path, out_nodes: Path, out_edges: Path) -> None:
    log.info("Lendo %s ...", input_path)
    df = pd.read_parquet(input_path, columns=["id", "autores", "ano"])
    log.info("  %d artigos carregados", len(df))

    # === Etapa 1: explode authorships ===
    edge_rows: list[dict] = []
    author_meta: dict[str, dict] = {}
    n_artigos_sem_authorship = 0

    for art_id, autores, ano in zip(df["id"], df["autores"], df["ano"]):
        if autores is None or not isinstance(autores, (list, tuple)) or len(autores) == 0:
            n_artigos_sem_authorship += 1
            continue

        n_aut = len(autores)
        for ordem_zero, raw in enumerate(autores):
            norm = parse_authorship(raw)
            if norm is None:
                continue

            position = norm["position"]
            is_first = (position == "first") or (ordem_zero == 0)
            is_last  = (position == "last")  or (ordem_zero == n_aut - 1)

            edge_rows.append({
                "id_artigo": art_id,
                "author_id": norm["author_id"],
                "ordem_autoria": ordem_zero + 1,
                "is_first": is_first,
                "is_last": is_last,
                "is_corresponding": norm["is_corresponding"]
            })

            aid = norm["author_id"]
            meta = author_meta.setdefault(aid, {
                "display_name": norm["display_name"],
                "institution_ids": set(),
                "country_codes": set(),
                "anos": []
            })
            meta["institution_ids"].update(norm["institution_ids"])
            meta["country_codes"].update(norm["country_codes"])
            if pd.notna(ano):
                try:
                    meta["anos"].append(int(ano))
                except (ValueError, TypeError):
                    pass
            # Manter display_name não-vazio se vier vazio em alguma ocorrência
            if not meta["display_name"] and norm["display_name"]:
                meta["display_name"] = norm["display_name"]

    if n_artigos_sem_authorship:
        log.warning("  %d artigos sem authorship válido (pulados)", n_artigos_sem_authorship)

    edges = pd.DataFrame(edge_rows)
    log.info("  %d arestas autor-artigo extraídas", len(edges))

    if edges.empty:
        log.error("Nenhuma aresta extraída. Abortando.")
        return

    # === Etapa 2: agregação vetorizada ===
    agg = edges.groupby("author_id", as_index=False).agg(
        n_artigos=("id_artigo", "nunique"),
        n_first_author=("is_first", "sum"),
        n_last_author=("is_last", "sum"),
        n_corresponding=("is_corresponding", "sum")
    )

    # Materializar metadados textuais via comprehension
    meta_rows = []
    for aid in agg["author_id"]:
        m = author_meta[aid]
        anos = m["anos"]
        countries = m["country_codes"]
        meta_rows.append({
            "display_name": m["display_name"],
            "n_instituicoes": len(m["institution_ids"]),
            "instituicoes_ids": ";".join(sorted(m["institution_ids"])),
            "n_paises": len(countries),
            "paises_codes": ";".join(sorted(countries)),
            "is_brasileiro": "BR" in countries,
            "primeiro_ano": min(anos) if anos else pd.NA,
            "ultimo_ano":   max(anos) if anos else pd.NA
        })

    meta_df = pd.DataFrame(meta_rows)
    nodes = pd.concat([agg.reset_index(drop=True), meta_df], axis=1)

    # Ordem canônica de colunas (interface estável — não mudar sem bump v2.x)
    col_order = [
        "author_id", "display_name", "n_artigos",
        "n_first_author", "n_last_author", "n_corresponding",
        "n_instituicoes", "instituicoes_ids",
        "n_paises", "paises_codes", "is_brasileiro",
        "primeiro_ano", "ultimo_ano"
    ]
    nodes = nodes[col_order]

    log.info("  %d autores únicos consolidados", len(nodes))
    log.info("    %d brasileiros (%.1f%%)",
             nodes["is_brasileiro"].sum(),
             100 * nodes["is_brasileiro"].mean())

    # === Etapa 3: gravar ===
    out_nodes.parent.mkdir(parents=True, exist_ok=True)
    out_edges.parent.mkdir(parents=True, exist_ok=True)
    nodes.to_csv(out_nodes, index=False, encoding="utf-8")
    edges.to_csv(out_edges, index=False, encoding="utf-8")
    log.info("Gravados: %s | %s", out_nodes, out_edges)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    parser = argparse.ArgumentParser(description="Extrai estrutura de autoria do corpus limpo.")
    parser.add_argument("--input",  type=Path, default=INPUT_DEFAULT)
    parser.add_argument("--nodes",  type=Path, default=OUT_NODES_DEFAULT)
    parser.add_argument("--edges",  type=Path, default=OUT_EDGES_DEFAULT)
    args = parser.parse_args()
    main(args.input, args.nodes, args.edges)
