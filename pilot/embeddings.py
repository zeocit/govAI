"""Extrai embeddings BERTimbau dos abstracts (Q-c, Sondas 2 e 3).
REQUER rede até huggingface.co -> rodar no Claude Code (sua máquina) ou Colab,
NÃO nesta sandbox. Salva embeddings.npy (alinhado a doc_ids.csv).
Uso: python embeddings.py abstracts.csv   (colunas: doc_id, abstract)
Requisitos: transformers, torch, pandas, numpy
"""
import sys, numpy as np, pandas as pd, torch
from transformers import AutoTokenizer, AutoModel
import config as C

def main(path):
    df = pd.read_csv(path).dropna(subset=["abstract"])
    tok = AutoTokenizer.from_pretrained(C.MODEL_NAME)
    mdl = AutoModel.from_pretrained(C.MODEL_NAME).eval()
    dev = "cuda" if torch.cuda.is_available() else "cpu"; mdl.to(dev)
    embs = []
    with torch.no_grad():
        for i in range(0, len(df), 16):
            batch = df.abstract.iloc[i:i+16].tolist()
            enc = tok(batch, padding=True, truncation=True, max_length=256, return_tensors="pt").to(dev)
            out = mdl(**enc).last_hidden_state            # mean-pooling mascarado
            mask = enc.attention_mask.unsqueeze(-1).float()
            pooled = (out*mask).sum(1)/mask.sum(1).clamp(min=1e-9)
            embs.append(pooled.cpu().numpy())
    X = np.vstack(embs)
    np.save("embeddings.npy", X)
    df[["doc_id"]].to_csv("doc_ids.csv", index=False)
    print(f"salvo embeddings.npy {X.shape} + doc_ids.csv")

if __name__ == "__main__":
    main(sys.argv[1])
