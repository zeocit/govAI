"""
07_aplicar_modelo.py | Aplicacao dos modelos finais ao corpus completo
======================================================================
Migracao dois eixos: 3 dims epi de saida (positivista, interpretativa,
doutrinario_normativa), flags independentes via sigmoid. orientacao_proeminente
derivada das flags (DA-09, sem prioridade); inconclusiva quando os 3 flags sao 0;
DN nao entra no eixo 1 (a flag binaria e usada diretamente para H4).

Schema epi de saida:
    epi_positivista_prob            float  [0,1]
    epi_interpretativa_prob         float  [0,1]
    epi_doutrinario_normativa_prob  float  [0,1]
    epi_positivista_pred            int    {0,1}
    epi_interpretativa_pred         int    {0,1}
    epi_doutrinario_normativa_pred  int    {0,1}
    orientacao_proeminente          str    {positivista, interpretativa, mixed, nenhuma}
    inconclusiva                    int    {0,1} (1 sse os 3 flags sao 0)
    epi_certeza                     float  decisividade media: mean(2*|prob-0.5|)

Autor: Fernando Leite | FAPESP | Refatoracao v4 (dois eixos, derivacao deterministica) - 24/jun/2026
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from tqdm import tqdm

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from utils.derive_orientacao import derive   # fonte unica da derivacao (DA-09)
except ImportError:
    from .utils.derive_orientacao import derive  # type: ignore

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.0")

CORPUS_PATH  = Path("dados/intermediarios/corpus_limpo_textual.parquet")
OUTPUT_PATH  = Path("dados/resultados/predicoes_corpus.parquet")
METRICAS_CL  = Path("dados/resultados/metricas_clusters.json")
METRICAS_EPI = Path("dados/resultados/metricas_epi.json")

CLUSTERS       = ["si", "ps", "sts", "law", "pa", "bcs"]
EPI_CATS       = ["positivista", "interpretativa", "doutrinario_normativa"]
MAX_LENGTH     = 512
BATCH_INF      = 32
SECUNDARIO_GAP = 0.15

log = logging.getLogger("07_aplicar_modelo")


def detectar_device() -> str:
    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        return "mps"
    elif torch.cuda.is_available():
        return "cuda"
    return "cpu"


# Dataset de inferencia -------------------------------------------------------
class InferenceDataset(Dataset):
    def __init__(self, titulos, abstracts, tokenizer, max_length=MAX_LENGTH):
        self.encodings = tokenizer(
            titulos, abstracts,
            max_length=max_length, truncation=True,
            padding="max_length", return_token_type_ids=True,
        )

    def __len__(self):
        return len(self.encodings["input_ids"])

    def __getitem__(self, idx):
        return {k: torch.tensor(v[idx]) for k, v in self.encodings.items()}


@torch.no_grad()
def inferir(model, dataloader, device: str) -> np.ndarray:
    model.eval()
    model.to(device)
    all_logits = []
    for batch in tqdm(dataloader, desc="Inferencia", leave=False):
        batch   = {k: v.to(device) for k, v in batch.items()}
        outputs = model(**batch)
        all_logits.append(outputs.logits.cpu().numpy())
    return np.concatenate(all_logits, axis=0)


def melhor_modelo_de_metricas(metricas_path: Path) -> str | None:
    if not metricas_path.exists():
        return None
    try:
        dados = json.load(metricas_path.open())
        ok    = [m for m in dados if m.get("status") == "ok"
                 and m.get("model_dir")]
        if not ok:
            return None
        return max(ok, key=lambda m: m.get("f1_macro_teste", 0))["model_dir"]
    except Exception as exc:
        log.warning("Nao foi possivel ler metricas: %s", exc)
        return None


# Sintese: orientacao_proeminente e derivada das flags por utils/derive_orientacao.py
# (DA-09: sem regra de prioridade, sem DN-domina; DN nao entra no eixo 1). A flag
# binaria epi_doutrinario_normativa_pred permanece para H4.


# Main ------------------------------------------------------------------------
def main(modelo_cluster_path: str | None, modelo_epi_path: str | None,
         auto_melhor: bool, output_path: Path = OUTPUT_PATH) -> None:
    device = detectar_device()
    log.info("Dispositivo: %s", device)

    if auto_melhor:
        modelo_cluster_path = melhor_modelo_de_metricas(METRICAS_CL)
        modelo_epi_path     = melhor_modelo_de_metricas(METRICAS_EPI)
        if not modelo_cluster_path:
            raise SystemExit(
                "Nao foi possivel identificar melhor modelo cluster.")
        if not modelo_epi_path:
            raise SystemExit(
                "Nao foi possivel identificar melhor modelo epi.")

    if not modelo_cluster_path or not Path(modelo_cluster_path).exists():
        raise SystemExit(
            f"Modelo cluster nao encontrado: {modelo_cluster_path}")
    if not modelo_epi_path or not Path(modelo_epi_path).exists():
        raise SystemExit(
            f"Modelo epi nao encontrado: {modelo_epi_path}")

    log.info("Modelo cluster: %s", modelo_cluster_path)
    log.info("Modelo epi:     %s", modelo_epi_path)

    corpus = pd.read_parquet(
        CORPUS_PATH, columns=["id", "titulo_limpo", "abstract_limpo"])
    corpus["titulo_limpo"]   = corpus["titulo_limpo"].fillna("").astype(str)
    corpus["abstract_limpo"] = corpus["abstract_limpo"].fillna("").astype(str)
    log.info("  %d artigos", len(corpus))

    titulos   = corpus["titulo_limpo"].tolist()
    abstracts = corpus["abstract_limpo"].tolist()

    # Inferencia cluster (softmax) --------------------------------------------
    tok_cl = AutoTokenizer.from_pretrained(modelo_cluster_path)
    mod_cl = AutoModelForSequenceClassification.from_pretrained(
        modelo_cluster_path)
    dl_cl  = DataLoader(
        InferenceDataset(titulos, abstracts, tok_cl),
        batch_size=BATCH_INF, shuffle=False)
    logits_cl = inferir(mod_cl, dl_cl, device)
    del mod_cl

    probs_cl  = np.exp(logits_cl - logits_cl.max(axis=1, keepdims=True))
    probs_cl /= probs_cl.sum(axis=1, keepdims=True)
    sorted_idx     = probs_cl.argsort(axis=1)[:, ::-1]
    primario_idx   = sorted_idx[:, 0]
    secundario_idx = sorted_idx[:, 1]
    gap = (probs_cl[np.arange(len(probs_cl)), primario_idx]
           - probs_cl[np.arange(len(probs_cl)), secundario_idx])
    tem_secundario = gap < SECUNDARIO_GAP

    # Inferencia epi (3 dims, sigmoid independente) ---------------------------
    tok_epi = AutoTokenizer.from_pretrained(modelo_epi_path)
    mod_epi = AutoModelForSequenceClassification.from_pretrained(
        modelo_epi_path)
    dl_epi  = DataLoader(
        InferenceDataset(titulos, abstracts, tok_epi),
        batch_size=BATCH_INF, shuffle=False)
    logits_epi = inferir(mod_epi, dl_epi, device)
    del mod_epi

    probs_epi = 1 / (1 + np.exp(-logits_epi))   # shape (n, 3); sigmoid independente
    preds_epi = (probs_epi >= 0.5).astype(int)

    log.info("Consolidando resultados...")
    data_pred = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n         = len(corpus)
    df_out    = pd.DataFrame({"id": corpus["id"].to_numpy()})

    # Cluster
    onehot_primario = np.zeros((n, len(CLUSTERS)), dtype=int)
    onehot_primario[np.arange(n), primario_idx] = 1
    clusters_arr = np.array(CLUSTERS)
    for j, cl in enumerate(CLUSTERS):
        df_out[f"cluster_{cl}_prob"] = probs_cl[:, j]
        df_out[f"cluster_{cl}_pred"] = onehot_primario[:, j]
    df_out["cluster_primario_pred"]   = clusters_arr[primario_idx]
    df_out["cluster_secundario_pred"] = np.where(
        tem_secundario, clusters_arr[secundario_idx], None)
    df_out["cluster_certeza"] = probs_cl[np.arange(n), primario_idx]

    # Epi (tres flags independentes)
    for j, cat in enumerate(EPI_CATS):
        df_out[f"epi_{cat}_prob"] = probs_epi[:, j]
        df_out[f"epi_{cat}_pred"] = preds_epi[:, j].astype(int)

    _deriv = [derive(int(p), int(i), int(d))
              for p, i, d in zip(preds_epi[:, 0], preds_epi[:, 1], preds_epi[:, 2])]
    df_out["orientacao_proeminente"] = [r["orientacao_proeminente"] for r in _deriv]
    df_out["inconclusiva"]           = [r["inconclusiva"] for r in _deriv]

    # epi_certeza: decisividade media = mean(2*|prob-0.5|), em [0,1]
    df_out["epi_certeza"] = (2.0 * np.abs(probs_epi - 0.5)).mean(axis=1)

    df_out["modelo_final_cluster"] = str(Path(modelo_cluster_path).name)
    df_out["modelo_final_epi"]     = str(Path(modelo_epi_path).name)
    df_out["data_predicao"]        = data_pred

    log.info("Distribuicao cluster_primario_pred:\n%s",
             df_out["cluster_primario_pred"].value_counts().to_string())
    log.info("Distribuicao orientacao_proeminente:\n%s",
             df_out["orientacao_proeminente"].value_counts().to_string())
    log.info("Certeza media cluster: %.3f",
             df_out["cluster_certeza"].mean())
    log.info("Certeza media epi:     %.3f",
             df_out["epi_certeza"].mean())

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = output_path.with_suffix(output_path.suffix + ".tmp")
    df_out.to_parquet(tmp_out, index=False, compression="snappy")
    tmp_out.replace(output_path)
    log.info("Gravado: %s (%d artigos, %.1f MB)",
             output_path, len(df_out),
             output_path.stat().st_size / 1e6)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/07_aplicar_modelo.log",
                                mode="a", encoding="utf-8"),
        ],
    )
    Path("logs").mkdir(exist_ok=True)
    parser = argparse.ArgumentParser(
        description="Aplica modelos finais ao corpus (epi ternario).")
    parser.add_argument("--modelo-cluster", type=str, default=None)
    parser.add_argument("--modelo-epi",     type=str, default=None)
    parser.add_argument("--auto-melhor", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    if not args.auto_melhor and (
            not args.modelo_cluster or not args.modelo_epi):
        parser.error(
            "Forneca --auto-melhor OU ambos "
            "--modelo-cluster e --modelo-epi.")
    main(args.modelo_cluster, args.modelo_epi,
         args.auto_melhor, args.output)
