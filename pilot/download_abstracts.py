"""Baixa abstracts e gera abstracts.csv (doc_id, abstract) — ponto 4.
Fonte: OpenAlex (gratuito, sem chave; abstracts via inverted index).
RODA na sua máquina / Claude Code / Colab (a sandbox do chat não alcança api.openalex.org).
Modos:
  1) por lista de DOIs:   python download_abstracts.py --dois dois.csv   (coluna: doi[,doc_id])
  2) por filtro OpenAlex: python download_abstracts.py --filter "primary_location.source.id:Sxxxx,from_publication_date:2010-01-01"
Requisitos: requests, pandas. Use --mailto seu@email para o "polite pool".
Para periódicos brasileiros pouco cobertos pelo OpenAlex, complemente via SciELO/Crossref.
"""
import sys, time, argparse, requests, pandas as pd

API = "https://api.openalex.org/works"

def reconstruct(inv):
    if not inv: return ""
    pos = [(i, w) for w, idxs in inv.items() for i in idxs]
    return " ".join(w for _, w in sorted(pos))

def by_dois(path, mailto):
    df = pd.read_csv(path); rows = []
    for _, r in df.iterrows():
        doi = str(r["doi"]).strip()
        did = r["doc_id"] if "doc_id" in df.columns else doi
        try:
            w = requests.get(f"{API}/doi:{doi}", params={"mailto": mailto}, timeout=30).json()
            rows.append({"doc_id": did, "abstract": reconstruct(w.get("abstract_inverted_index"))})
        except Exception as e:
            rows.append({"doc_id": did, "abstract": ""})
        time.sleep(0.1)
    return pd.DataFrame(rows)

def by_filter(flt, mailto, max_n=2000):
    rows, cursor = [], "*"
    while cursor and len(rows) < max_n:
        j = requests.get(API, params={"filter": flt, "per-page": 200, "cursor": cursor,
            "select": "id,doi,abstract_inverted_index", "mailto": mailto}, timeout=60).json()
        for w in j.get("results", []):
            rows.append({"doc_id": w["id"].split("/")[-1],
                         "abstract": reconstruct(w.get("abstract_inverted_index"))})
        cursor = j.get("meta", {}).get("next_cursor")
        time.sleep(0.1)
    return pd.DataFrame(rows)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dois"); ap.add_argument("--filter")
    ap.add_argument("--mailto", default="you@example.com")
    a = ap.parse_args()
    df = by_dois(a.dois, a.mailto) if a.dois else by_filter(a.filter, a.mailto)
    df = df[df.abstract.str.len() > 0]
    df.to_csv("abstracts.csv", index=False)
    print(f"abstracts.csv: {len(df)} abstracts não-vazios")

if __name__ == "__main__":
    main()
