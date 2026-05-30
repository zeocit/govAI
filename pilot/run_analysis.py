"""Q-c (Sondas 2 e 3) + decisão pré-registrada.
Sonda 2: separabilidade (silhouette por rótulo, KMeans(3) vs rótulos).
Sonda 3: probe em CV — B1 (softmax 3 vias) vs B2 (2 sigmoides OvR + DN derivado).
Entradas: embeddings.npy + doc_ids.csv (de embeddings.py) OU --tfidf abstracts.csv
          e annotations.csv (rótulos 'gold').
Uso: python run_analysis.py annotations.csv [--tfidf abstracts.csv]
"""
import sys, numpy as np, pandas as pd
from sklearn.metrics import silhouette_score, adjusted_rand_score, f1_score
from sklearn.cluster import KMeans
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
import config as C

def load_X(args):
    if "--tfidf" in args:
        from sklearn.feature_extraction.text import TfidfVectorizer
        ab = pd.read_csv(args[args.index("--tfidf")+1]).dropna(subset=["abstract"])
        X = TfidfVectorizer(max_features=2000, ngram_range=(1,2)).fit_transform(ab.abstract).toarray()
        return X, ab.doc_id.tolist(), "TF-IDF (proxy, sem BERTimbau)"
    X = np.load("embeddings.npy"); ids = pd.read_csv("doc_ids.csv").doc_id.tolist()
    return X, ids, "BERTimbau"

def main(args):
    ann = pd.read_csv(args[0]); gold = ann[ann.annotator=="gold"].set_index("doc_id")
    X, ids, src = load_X(args)
    y = np.array([gold.loc[i,"B_label"] if i in gold.index else None for i in ids])
    keep = y != None; X, y = X[keep], y[keep].astype(str)
    print(f"== Q-c Separabilidade ({src}); n rotulado = {len(y)} ; classes = {dict(zip(*np.unique(y, return_counts=True)))} ==")

    # Sonda 2
    try:
        sil = silhouette_score(X, y)
        km = KMeans(3, n_init=10, random_state=0).fit_predict(X)
        ari = adjusted_rand_score(y, km)
        print(f"  silhouette por rótulo: {sil:.3f}   |  KMeans(3) ARI vs rótulos: {ari:.3f}")
        for cls in ["EE","IC","DN"]:
            m = y==cls
            if m.sum()>1: print(f"    silhouette só {cls}: {silhouette_score(X, m.astype(int)):.3f} (coesão DN é o foco)")
    except Exception as e:
        print("  [sonda 2 falhou]", e)

    # Sonda 3 — probe CV
    print("  -- Sonda 3: probe em validação cruzada (k=5) --")
    skf = StratifiedKFold(5, shuffle=True, random_state=0)
    f1_b1, f1_b2 = [], []
    yb = pd.Series(y)
    for tr, te in skf.split(X, y):
        # B1: softmax 3 vias
        clf = LogisticRegression(max_iter=1000, multi_class="multinomial").fit(X[tr], y[tr])
        f1_b1.append(f1_score(y[te], clf.predict(X[te]), labels=["DN"], average="macro", zero_division=0))
        # B2: duas sigmoides OvR (EE, IC) + DN derivado por exclusão
        pe = LogisticRegression(max_iter=1000).fit(X[tr], (y[tr]=="EE").astype(int)).predict(X[te])
        pi = LogisticRegression(max_iter=1000).fit(X[tr], (y[tr]=="IC").astype(int)).predict(X[te])
        pred = np.where((pe==0)&(pi==0), "DN", np.where(pe==1,"EE","IC"))
        f1_b2.append(f1_score(y[te], pred, labels=["DN"], average="macro", zero_division=0))
    import statistics as st
    b1, b2 = st.mean(f1_b1), st.mean(f1_b2)
    print(f"    F1_DN B1 (softmax)   : {b1:.3f} +/- {st.pstdev(f1_b1):.3f}")
    print(f"    F1_DN B2 (derivação) : {b2:.3f} +/- {st.pstdev(f1_b2):.3f}")

    # Decisão (lê alpha_DN do run_labels manualmente OU passe via env); aqui só sinaliza a regra
    print("\n== Regra de decisão (preencher misto% e alpha_DN de run_labels.py) ==")
    print(f"  ternária pura  SE  misto < {C.MISTO_THRESHOLD:.0%} E alpha_DN >= {C.ALPHA_DN_MIN} E F1_DN(B1) >= F1_DN(B2)")
    print(f"  3-B (prim+sec) SE  misto >= {C.MISTO_THRESHOLD:.0%} E alpha_DN >= {C.ALPHA_DN_MIN}")
    print(f"  3-A (resíduo)  SE  alpha_DN < {C.ALPHA_DN_MIN}  OU  F1_DN(B1) < F1_DN(B2) - {C.PROBE_MARGIN}")
    print(f"  [observado] F1_DN(B1)={b1:.3f} vs F1_DN(B2)={b2:.3f} -> "
          + ("B2 melhor (favorece 3-A)" if b2 > b1 + C.PROBE_MARGIN else "empate/B1 (não bloqueia ternária)"))

if __name__ == "__main__":
    main(sys.argv[1:])
