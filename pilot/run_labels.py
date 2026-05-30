"""Q-a (prevalência de misto) e parte de Q-c (concordância humana de DN).
NÃO precisa de Hugging Face — roda em qualquer ambiente com pandas/sklearn.
Uso: python run_labels.py annotations.csv
Requisitos: pandas, scikit-learn, krippendorff  (pip install krippendorff)
"""
import sys, math, pandas as pd
from sklearn.metrics import cohen_kappa_score
import config as C

def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"),)*3
    p = k/n; d = 1+z*z/n
    c = (p+z*z/(2*n))/d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return p, max(0,c-h), min(1,c+h)

def kripp_alpha(matrix):
    """matrix: lista de listas (unidades x avaliadores), valores nominais ou None."""
    try:
        import krippendorff, numpy as np
        # krippendorff espera avaliadores x unidades; usa np.nan para faltantes
        cats = sorted({v for row in matrix for v in row if v is not None})
        code = {c:i for i,c in enumerate(cats)}
        n_raters = max(len(r) for r in matrix)
        data = [[float("nan")]*len(matrix) for _ in range(n_raters)]
        for u,row in enumerate(matrix):
            for r,v in enumerate(row):
                data[r][u] = code[v] if v is not None else float("nan")
        return krippendorff.alpha(reliability_data=data, level_of_measurement="nominal")
    except Exception as e:
        return float("nan")

def main(path):
    df = pd.read_csv(path)
    raters = sorted(r for r in df.annotator.unique() if r != "gold")
    gold = df[df.annotator == "gold"]
    if gold.empty:
        print("[aviso] sem linhas 'gold'; usando", raters[0], "para prevalência (provisório).")
        gold = df[df.annotator == raters[0]]

    # ---- Q-a: prevalência de misto (subamostra representativa, adjudicada) ----
    prev = gold[gold.subsample == "prevalence"]
    n = len(prev)
    misto = int(((prev.A_pos == 1) & (prev.A_int == 1)).sum())
    p, lo, hi = wilson(misto, n)
    forcing = int((prev.B_forcing >= 2).sum())
    print(f"== Q-a Prevalência de misto (n={n}, subamostra representativa) ==")
    print(f"  misto (A_pos=1 & A_int=1): {misto}/{n} = {p:.1%}  IC95% [{lo:.1%}, {hi:.1%}]")
    print(f"  custo de supressão (B_forcing>=2): {forcing}/{n} = {forcing/n:.1%}" if n else "")

    # ---- Q-c (parte 1): concordância humana, com foco em DN ----
    print("\n== Q-c.1 Concordância inter-anotador ==")
    pivot = df[df.annotator != "gold"]
    units = sorted(pivot.doc_id.unique())
    def col_matrix(col, mapper=lambda x: x):
        m = []
        for u in units:
            sub = pivot[pivot.doc_id == u]
            m.append([mapper(sub[sub.annotator==r][col].iloc[0]) if not sub[sub.annotator==r].empty else None for r in raters])
        return m
    aA_pos = kripp_alpha(col_matrix("A_pos"))
    aA_int = kripp_alpha(col_matrix("A_int"))
    aB     = kripp_alpha(col_matrix("B_label"))
    aB_dn  = kripp_alpha(col_matrix("B_label", lambda x: "DN" if x=="DN" else "other"))
    print(f"  alpha (Chave A, A_pos)        : {aA_pos:.3f}")
    print(f"  alpha (Chave A, A_int)        : {aA_int:.3f}")
    print(f"  alpha (Chave B, EE/IC/DN)     : {aB:.3f}")
    print(f"  alpha (Chave B, DN vs. resto) : {aB_dn:.3f}   <-- limiar pré-registrado >= {C.ALPHA_DN_MIN}")
    if len(raters) == 2:
        a,b = raters
        k = cohen_kappa_score(*[ [df[(df.doc_id==u)&(df.annotator==r)].B_label.iloc[0] for u in units] for r in (a,b)])
        print(f"  kappa de Cohen (B_label, {a} vs {b}): {k:.3f}")

    print("\n[nota] Resultados exigem anotações humanas reais. Sem >=2 anotadores, alpha não é definido.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: python run_labels.py annotations.csv"); sys.exit(1)
    main(sys.argv[1])
