"""Seleção dos artigos do piloto (ponto 3).
Sorteio estratificado da subamostra representativa + reforço de DN.
Entrada: corpus.csv com, no mínimo, doc_id e colunas de estrato.
Uso:
  python sample_selection.py corpus.csv \
      --strata cluster_origem \
      --n_prev 150 --n_boost 50 \
      --dn_filter "cluster_origem==Law" \
      --seed 42
Saída: sample.csv (doc_id, subsample, stratum) — salvo no mesmo diretório de corpus.csv.
"""
import argparse, os
import pandas as pd


def main(argv=None):
    """argv=None  → lê sys.argv[1:] (chamada via CLI / !python no Colab).
    argv=[...]  → usa lista explícita (chamada direta de célula de notebook)."""
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("--strata", nargs="+", default=["cluster"])
    ap.add_argument("--n_prev", type=int, default=150)
    ap.add_argument("--n_boost", type=int, default=50)
    ap.add_argument("--dn_filter", default=None,
        help="filtro col==valor para o estrato de sobreamostragem (ex.: cluster_origem==Law)")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args(argv)

    df = pd.read_csv(a.corpus)
    assert "doc_id" in df.columns, "corpus.csv precisa de coluna doc_id"

    # --- Separar pool de prevalência (não-DN) do pool de reforço (DN) ---
    # BUG FIX 1: Law deve ser excluída do sorteio proporcional dos 150.
    if a.dn_filter and "==" in a.dn_filter:
        col_dn, val_dn = a.dn_filter.split("==", 1)
        mask_dn = df[col_dn].astype(str) == val_dn
    else:
        mask_dn = pd.Series(False, index=df.index)

    df_prev_pool  = df[~mask_dn].copy()
    df_boost_pool = df[mask_dn].copy()

    assert len(df_prev_pool)  > 0, "Pool de prevalência vazio — verifique --dn_filter."
    assert len(df_boost_pool) > 0, "Pool de reforço DN vazio — verifique --dn_filter."

    # --- Coluna de estrato (calculada sobre cada pool separadamente) ---
    df_prev_pool["_stratum"]  = df_prev_pool[a.strata].astype(str).agg(" | ".join, axis=1)
    df_boost_pool["_stratum"] = df_boost_pool[a.strata].astype(str).agg(" | ".join, axis=1)

    # --- Subamostra representativa: proporcional por estrato ---
    # BUG FIX 2: denominador = pool sem Law (5.640), não corpus completo (6.000).
    frac = a.n_prev / len(df_prev_pool)

    # FIX AVISO: list comprehension evita FutureWarning de groupby().apply() no pandas >= 2.2
    prev = pd.concat([
        g.sample(max(1, round(len(g) * frac)), random_state=a.seed)
        for _, g in df_prev_pool.groupby("_stratum")
    ])
    prev = prev.sample(min(a.n_prev, len(prev)), random_state=a.seed)
    prev_ids = set(prev.doc_id)

    # --- Reforço de DN: sobreamostra do pool DN, sem repetir IDs de prev ---
    boost_pool = df_boost_pool[~df_boost_pool.doc_id.isin(prev_ids)]
    boost = boost_pool.sample(min(a.n_boost, len(boost_pool)), random_state=a.seed)

    # --- Saída ---
    out = pd.concat([
        prev.assign(subsample="prevalence"),
        boost.assign(subsample="dn_boost"),
    ])[["doc_id", "subsample", "_stratum"]].rename(columns={"_stratum": "stratum"})

    # BUG FIX 3: salvar no diretório do corpus, não no cwd do Colab.
    out_path = os.path.join(os.path.dirname(os.path.abspath(a.corpus)), "sample.csv")
    out.to_csv(out_path, index=False)

    print(f"sample.csv → {out_path}")
    print(f"Total: {len(prev)} prevalence + {len(boost)} dn_boost = {len(out)} artigos")
    print(out.groupby(["subsample", "stratum"]).size().to_string())


if __name__ == "__main__":
    main()
