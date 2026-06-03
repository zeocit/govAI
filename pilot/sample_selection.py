"""Seleção dos artigos para calibração de concordância inter-anotador.
Estratifica por cluster_origem; separa subpopulação jurídica em subsample próprio.
Entrada: corpus.csv com, no mínimo, doc_id, cluster_origem e subpopulacao_juridica.
Uso:
  python sample_selection.py corpus.csv \
      --strata cluster_origem \
      --n_prev 25 --n_boost 0 \
      --seed 42
Saída: sample_calib.csv (doc_id, subsample, stratum) — salvo no mesmo diretório do corpus.
"""
import argparse, os
import pandas as pd


def main(argv=None):
    """argv=None → lê sys.argv[1:] (CLI / !python no Colab).
    argv=[...] → usa lista explícita (chamada direta de célula de notebook)."""
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("--strata", nargs="+", default=["cluster_origem"])
    ap.add_argument("--n_prev",  type=int, default=25,
                    help="artigos da subamostra geral de calibração (default: 25)")
    ap.add_argument("--n_boost", type=int, default=0,
                    help="artigos adicionais da subpopulação jurídica (default: 0)")
    ap.add_argument("--juridica_col", default="subpopulacao_juridica",
                    help="coluna binária que identifica artigos jurídicos (default: subpopulacao_juridica)")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args(argv)

    df = pd.read_csv(a.corpus)
    assert "doc_id" in df.columns, "corpus.csv precisa de coluna doc_id"
    for col in a.strata:
        assert col in df.columns, f"corpus.csv não tem coluna de estrato: {col}"

    # --- Separar pool geral do pool jurídico ---
    if a.juridica_col in df.columns:
        mask_juridica = df[a.juridica_col].astype(int) == 1
    else:
        mask_juridica = pd.Series(False, index=df.index)
        print(f"[aviso] coluna '{a.juridica_col}' não encontrada; todos os artigos vão para calibracao.")

    df_geral    = df[~mask_juridica].copy()
    df_juridica = df[mask_juridica].copy()

    assert len(df_geral) > 0, "Pool geral vazio — verifique --juridica_col."

    # --- Subamostra geral: estratificada por cluster ---
    df_geral["_stratum"] = df_geral[a.strata].astype(str).agg(" | ".join, axis=1)
    frac = a.n_prev / len(df_geral)
    calib = pd.concat([
        g.sample(max(1, round(len(g) * frac)), random_state=a.seed)
        for _, g in df_geral.groupby("_stratum")
    ])
    calib = calib.sample(min(a.n_prev, len(calib)), random_state=a.seed)
    calib_ids = set(calib.doc_id)

    # --- Subamostra jurídica (boost) ---
    boost = pd.DataFrame(columns=df.columns)
    if a.n_boost > 0:
        assert len(df_juridica) > 0, "Pool jurídico vazio — verifique --juridica_col."
        pool = df_juridica[~df_juridica.doc_id.isin(calib_ids)]
        boost = pool.sample(min(a.n_boost, len(pool)), random_state=a.seed)

    # --- Saída ---
    frames = [calib.assign(subsample="calibracao")]
    if len(boost) > 0:
        frames.append(boost.assign(subsample="calibracao_juridica"))

    out = pd.concat(frames)[["doc_id", "subsample", "_stratum"]].rename(
        columns={"_stratum": "stratum"}
    )
    # artigos jurídicos que vieram da subamostra geral: corrigir stratum
    if "_stratum" not in boost.columns and len(boost) > 0:
        out.loc[out.subsample == "calibracao_juridica", "stratum"] = (
            boost[a.strata].astype(str).agg(" | ".join, axis=1).values
        )

    out_path = os.path.join(
        os.path.dirname(os.path.abspath(a.corpus)), "sample_calib.csv"
    )
    out.to_csv(out_path, index=False)

    n_calib   = (out.subsample == "calibracao").sum()
    n_juridica = (out.subsample == "calibracao_juridica").sum()
    print(f"sample_calib.csv → {out_path}")
    print(f"Total: {n_calib} calibracao + {n_juridica} calibracao_juridica = {len(out)} artigos")
    print(out.groupby(["subsample", "stratum"]).size().to_string())


if __name__ == "__main__":
    main()
