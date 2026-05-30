"""Seleção dos artigos do piloto (ponto 3).
Sorteio estratificado da subamostra representativa + reforço de DN.
Entrada: corpus.csv com, no mínimo, doc_id e colunas de estrato.
Uso:
  python sample_selection.py corpus.csv \
      --strata cluster area region \
      --n_prev 150 --n_boost 50 \
      --dn_filter "cluster==Law" \
      --seed 42
Saída: sample.csv (doc_id, subsample, stratum).
"""
import sys, argparse, pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("--strata", nargs="+", default=["cluster"])
    ap.add_argument("--n_prev", type=int, default=150)
    ap.add_argument("--n_boost", type=int, default=50)
    ap.add_argument("--dn_filter", default=None,
        help="filtro col==valor para o estrato com mais DN (ex.: cluster==Law)")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    df = pd.read_csv(a.corpus)
    assert "doc_id" in df.columns, "corpus.csv precisa de coluna doc_id"

    # --- subamostra representativa: proporcional por estrato ---
    df["_stratum"] = df[a.strata].astype(str).agg(" | ".join, axis=1)
    frac = a.n_prev / len(df)
    prev = (df.groupby("_stratum", group_keys=False)
              .apply(lambda g: g.sample(max(1, round(len(g)*frac)), random_state=a.seed)))
    prev = prev.sample(min(a.n_prev, len(prev)), random_state=a.seed)
    prev_ids = set(prev.doc_id)

    # --- reforço de DN: sobreamostra do estrato com mais DN, sem repetir ---
    pool = df[~df.doc_id.isin(prev_ids)]
    if a.dn_filter and "==" in a.dn_filter:
        col, val = a.dn_filter.split("==", 1)
        pool = pool[pool[col].astype(str) == val]
    boost = pool.sample(min(a.n_boost, len(pool)), random_state=a.seed)

    out = pd.concat([
        prev.assign(subsample="prevalence"),
        boost.assign(subsample="dn_boost"),
    ])[["doc_id", "subsample", "_stratum"]].rename(columns={"_stratum": "stratum"})
    out.to_csv("sample.csv", index=False)
    print(f"sample.csv: {len(prev)} prevalence + {len(boost)} dn_boost = {len(out)} artigos")
    print(out.groupby(["subsample"]).size().to_string())

if __name__ == "__main__":
    main()
