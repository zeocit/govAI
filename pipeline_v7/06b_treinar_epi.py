"""
06b_treinar_epi.py | Fine-tuning: orientacao epistemologica
===========================================================
Migracao dois eixos: tres flags POSITIVOS independentes
(positivista, interpretativa, doutrinario_normativa). num_labels=3,
problem_type='multi_label_classification', BCEWithLogitsLoss com pos_weight
por flag computado de y_train (n_neg/n_pos), limitado por POS_WEIGHT_CAP.

Decisao arquitetural DA-03: classificadores independentes (nao multi-task).
Este script faz fine-tuning de um modelo separado para a camada epi, sem
compartilhar parametros com o classificador de cluster.

Input:
    dados/gold_standard/gold_standard_final.parquet
    dados/intermediarios/corpus_limpo_textual.parquet

Outputs:
    modelos/epi/{arquitetura}_seed{semente}/
    dados/resultados/predicoes_long_epi.parquet
    dados/resultados/metricas_epi.json

Autor: Fernando Leite | FAPESP | Refatoracao v4 (dois eixos, derivacao deterministica) - 25/jun/2026
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
    set_seed,
)

try:
    from utils.thresholds import POS_WEIGHT_CAP
except ImportError:
    from .utils.thresholds import POS_WEIGHT_CAP  # type: ignore

try:
    from utils.derive_orientacao import derive   # fonte unica da derivacao (DA-09)
except ImportError:
    from .utils.derive_orientacao import derive  # type: ignore

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.0")

GS_PATH     = Path("dados/gold_standard/gold_standard_final.parquet")
CORPUS_PATH = Path("dados/intermediarios/corpus_limpo_textual.parquet")
MODELOS_DIR = Path("modelos/epi")
RESULTS_DIR = Path("dados/resultados")

ENCODER_HUB = {
    "bertimbau": "neuralmind/bert-base-portuguese-cased",
    "scibert":   "allenai/scibert_scivocab_uncased",
    "xlmr":      "xlm-roberta-base",
}
EPI_CATS      = ["positivista", "interpretativa", "doutrinario_normativa"]
EPI_FLAGS     = [f"epi_{c}" for c in EPI_CATS]
SEEDS         = [42, 123, 2026]
MAX_LENGTH    = 512
BATCH_TRAIN   = 16
BATCH_EVAL    = 32
LEARNING_RATE = 2e-5
WEIGHT_DECAY  = 0.01
N_EPOCHS      = 15
WARMUP_RATIO  = 0.1
PATIENCE      = 3
TEST_SIZE     = 0.15
VAL_SIZE      = 0.15

log = logging.getLogger("06b_treinar_epi")


def detectar_device() -> str:
    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        log.info("Dispositivo: MPS (Apple Silicon)")
        return "mps"
    elif torch.cuda.is_available():
        return "cuda"
    return "cpu"


# A chave de estratificacao do split e construida em carregar_dados_epi a partir
# das flags via utils/derive_orientacao.py (eixo 1) combinada com a flag DN, para
# preservar a representacao de DN nos splits sem reintroduzir a regra 'DN domina'.


# Dataset ---------------------------------------------------------------------
class EpiDataset(Dataset):
    """Multi-label: labels = [epi_positivista, epi_interpretativa, epi_doutrinario_normativa]."""

    def __init__(self, titulos, abstracts, labels_matrix, tokenizer,
                 max_length=MAX_LENGTH):
        self.encodings = tokenizer(
            titulos, abstracts,
            max_length=max_length, truncation=True,
            padding="max_length", return_token_type_ids=True,
        )
        self.labels = labels_matrix

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {k: torch.tensor(v[idx]) for k, v in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx], dtype=torch.float)
        return item


# Trainer com pos_weight ------------------------------------------------------
class WeightedTrainer(Trainer):
    """BCEWithLogitsLoss(pos_weight=...) por flag.

    Sobrescreve compute_loss para aplicar peso por classe, mitigando o
    desbalanceamento da dimensao doutrinario_normativa. pos_weight vem de
    y_train (n_neg/n_pos por flag), com clamp em POS_WEIGHT_CAP.

    O AutoModel multi_label usa BCE sem pos_weight internamente; ao remover
    'labels' de inputs antes de model(**inputs), o modelo nao calcula loss
    interna e evita dupla contagem.
    """

    def __init__(self, *args, pos_weight: torch.Tensor | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._pos_weight = pos_weight

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels  = inputs.pop("labels")
        outputs = model(**inputs)
        logits  = outputs.logits
        pw      = (self._pos_weight.to(logits.device)
                   if self._pos_weight is not None else None)
        loss_fct = torch.nn.BCEWithLogitsLoss(pos_weight=pw)
        loss = loss_fct(logits, labels.float())
        return (loss, outputs) if return_outputs else loss


def compute_pos_weight(labels_matrix: list[list[float]],
                       cap: float) -> torch.Tensor:
    """pos_weight por flag = n_neg / n_pos, com clamp em cap."""
    y   = np.asarray(labels_matrix, dtype=float)
    n   = y.shape[0]
    pos = y.sum(axis=0)
    neg = n - pos
    with np.errstate(divide="ignore", invalid="ignore"):
        w = np.where(pos > 0, neg / pos, 1.0)
    w = np.minimum(w, cap)
    log.info("  pos_weight por flag %s: %s (cap=%.1f)",
             EPI_CATS, np.round(w, 3).tolist(), cap)
    return torch.tensor(w, dtype=torch.float)


# Metricas --------------------------------------------------------------------
def compute_metrics_epi(pred):
    from sklearn.metrics import hamming_loss, jaccard_score

    logits = pred.predictions
    labels = pred.label_ids
    probs  = 1 / (1 + np.exp(-logits))
    preds  = (probs >= 0.5).astype(int)

    result = {}
    for i, cat in enumerate(EPI_CATS):
        f1 = f1_score(labels[:, i], preds[:, i],
                      average="binary", zero_division=0)
        result[f"f1_{cat}"]    = float(f1)
        result[f"brier_{cat}"] = float(
            ((probs[:, i] - labels[:, i]) ** 2).mean())
    result["f1_macro"]        = float(
        np.mean([result[f"f1_{c}"] for c in EPI_CATS]))
    result["hamming_loss"]    = float(hamming_loss(labels, preds))
    result["jaccard_samples"] = float(
        jaccard_score(labels, preds, average="samples", zero_division=0))
    return result


# Dados -----------------------------------------------------------------------
def carregar_dados_epi(idioma_filtro: str | None) -> pd.DataFrame:
    gs = pd.read_parquet(GS_PATH)

    cols_obrigatorias = {"id", "cluster_status", "concordancia_cluster",
                         *EPI_FLAGS}
    faltantes = cols_obrigatorias - set(gs.columns)
    if faltantes:
        raise KeyError(
            f"Gold Standard sem colunas epi esperadas de 05: {sorted(faltantes)}. "
            f"Colunas presentes: {sorted(gs.columns)}"
        )

    eh_classificado = gs["cluster_status"] == "classificado"
    sem_disputa     = gs["concordancia_cluster"] != "disputa_pendente"
    gs = gs[eh_classificado & sem_disputa].copy()

    corpus = pd.read_parquet(
        CORPUS_PATH,
        columns=["id", "titulo_limpo", "abstract_limpo", "idioma_detectado"],
    )
    df = gs.merge(corpus, on="id", how="inner")

    if idioma_filtro in ("pt", "en"):
        col = df.get("idioma_detectado",
                     df.get("idioma", pd.Series(dtype=str)))
        df  = df[col.fillna("").str.lower() == idioma_filtro]

    df = df.dropna(subset=["titulo_limpo", "abstract_limpo"])
    df["titulo_limpo"]   = df["titulo_limpo"].fillna("").astype(str)
    df["abstract_limpo"] = df["abstract_limpo"].fillna("").astype(str)
    for f in EPI_FLAGS:
        df[f] = df[f].fillna(0).astype(float)
    # Chave de estratificacao: rotulo do eixo 1 (derive) + flag DN. Combinar com
    # DN preserva a propriedade que a antiga regra 'DN domina' garantia (DN
    # representado em treino/val/teste), sem usar DN como valor de rotulo.
    df["strat_key"] = df.apply(
        lambda r: derive(
            int(r["epi_positivista"]),
            int(r["epi_interpretativa"]),
            int(r["epi_doutrinario_normativa"]),
        )["orientacao_proeminente"] + f"__dn{int(r['epi_doutrinario_normativa'])}",
        axis=1,
    )
    log.info("  Dataset epi: %d artigos", len(df))
    return df


def split_dados_epi(df: pd.DataFrame, semente: int):
    """Split estratificado por strat_key (eixo 1 + DN); fallback aleatorio."""
    strat_col = df["strat_key"]
    try:
        df_tv, df_test = train_test_split(
            df, test_size=TEST_SIZE, random_state=semente, stratify=strat_col)
        df_train, df_val = train_test_split(
            df_tv, test_size=VAL_SIZE / (1 - TEST_SIZE),
            random_state=semente, stratify=strat_col[df_tv.index])
    except ValueError:
        log.warning("  Estratificacao falhou. Split aleatorio.")
        df_tv, df_test = train_test_split(
            df, test_size=TEST_SIZE, random_state=semente)
        df_train, df_val = train_test_split(
            df_tv, test_size=VAL_SIZE / (1 - TEST_SIZE), random_state=semente)
    log.info("  Split epi: treino=%d val=%d teste=%d",
             len(df_train), len(df_val), len(df_test))
    return df_train, df_val, df_test


def labels_matrix(df: pd.DataFrame) -> list[list[float]]:
    return df[EPI_FLAGS].values.tolist()


# Treino ----------------------------------------------------------------------
def treinar_epi_semente(encoder_nome: str, idioma_filtro: str | None,
                        semente: int, device: str) -> tuple[dict, list]:
    celula_nome = f"{encoder_nome}_{idioma_filtro or 'bi'}"
    run_nome    = f"{celula_nome}_seed{semente}"
    model_dir   = MODELOS_DIR / run_nome
    log.info("=== Epi rodada: %s ===", run_nome)

    df = carregar_dados_epi(idioma_filtro)
    if len(df) < 20:
        log.warning("  Dados insuficientes (%d). Pulando.", len(df))
        return {"run": run_nome, "status": "dados_insuficientes"}, []

    df_train, df_val, df_test = split_dados_epi(df, semente)

    # Reprodutibilidade: fixar RNGs antes de instanciar o modelo.
    set_seed(semente)

    hub_name  = ENCODER_HUB[encoder_nome]
    tokenizer = AutoTokenizer.from_pretrained(hub_name)
    model     = AutoModelForSequenceClassification.from_pretrained(
        hub_name,
        num_labels=len(EPI_CATS),
        problem_type="multi_label_classification",
    )

    y_train    = labels_matrix(df_train)
    pos_weight = compute_pos_weight(y_train, POS_WEIGHT_CAP)

    ds_train = EpiDataset(df_train["titulo_limpo"].tolist(),
                          df_train["abstract_limpo"].tolist(),
                          y_train, tokenizer)
    ds_val   = EpiDataset(df_val["titulo_limpo"].tolist(),
                          df_val["abstract_limpo"].tolist(),
                          labels_matrix(df_val), tokenizer)
    ds_test  = EpiDataset(df_test["titulo_limpo"].tolist(),
                          df_test["abstract_limpo"].tolist(),
                          labels_matrix(df_test), tokenizer)

    import inspect
    _ta_params = set(inspect.signature(TrainingArguments.__init__).parameters)
    targs_kwargs = dict(
        output_dir=str(model_dir), num_train_epochs=N_EPOCHS,
        per_device_train_batch_size=BATCH_TRAIN,
        per_device_eval_batch_size=BATCH_EVAL,
        learning_rate=LEARNING_RATE, weight_decay=WEIGHT_DECAY,
        warmup_ratio=WARMUP_RATIO,
        save_strategy="epoch", metric_for_best_model="f1_macro",
        greater_is_better=True, load_best_model_at_end=True,
        save_total_limit=1, seed=semente, data_seed=semente,
        report_to="none", logging_steps=10,
        fp16=False, bf16=False,
        dataloader_num_workers=0, dataloader_pin_memory=False,
        full_determinism=False,
    )
    if "eval_strategy" in _ta_params:
        targs_kwargs["eval_strategy"] = "epoch"
    else:
        targs_kwargs["evaluation_strategy"] = "epoch"
    if "use_mps_device" in _ta_params:
        targs_kwargs["use_mps_device"] = (device == "mps")
    if "no_cuda" in _ta_params:
        targs_kwargs["no_cuda"] = (device not in ("cuda",))

    training_args = TrainingArguments(**targs_kwargs)

    trainer = WeightedTrainer(
        model=model, args=training_args,
        train_dataset=ds_train, eval_dataset=ds_val,
        compute_metrics=compute_metrics_epi,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=PATIENCE)],
        pos_weight=pos_weight,
    )

    trainer.train()
    test_results = trainer.evaluate(ds_test)
    log.info("  F1-macro epi teste: %.4f",
             test_results.get("eval_f1_macro", float("nan")))
    for c in EPI_CATS:
        log.info("    F1 %s: %.4f", c,
                 test_results.get(f"eval_f1_{c}", float("nan")))

    model_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(model_dir))
    tokenizer.save_pretrained(str(model_dir))

    pred_output = trainer.predict(ds_test)
    logits      = pred_output.predictions
    probs       = 1 / (1 + np.exp(-logits))
    preds       = (probs >= 0.5).astype(int)
    labels_arr  = pred_output.label_ids.astype(int)
    ids_test    = df_test["id"].tolist()

    long_rows = []
    for i, art_id in enumerate(ids_test):
        for j, cat in enumerate(EPI_CATS):
            long_rows.append({
                "id":                art_id,
                "celula":            celula_nome,
                "corpus_treino":     idioma_filtro or "bi",
                "modelo":            encoder_nome,
                "semente":           semente,
                "particao":          "teste",
                "camada":            "epi",
                "dimensao":          cat,
                "prob":              float(probs[i, j]),
                "pred":              int(preds[i, j]),
                "rotulo_verdadeiro": int(labels_arr[i, j]),
                "acerto":            int(preds[i, j]) == int(labels_arr[i, j]),
            })

    metricas = {
        "run":            run_nome,
        "encoder":        encoder_nome,
        "idioma_filtro":  idioma_filtro or "bi",
        "semente":        semente,
        "n_treino":       len(df_train),
        "n_val":          len(df_val),
        "n_teste":        len(df_test),
        "f1_macro_teste": float(test_results.get("eval_f1_macro", float("nan"))),
        "f1_por_cat":     {c: float(test_results.get(f"eval_f1_{c}", float("nan")))
                           for c in EPI_CATS},
        "pos_weight":     pos_weight.tolist(),
        "status":         "ok",
        "model_dir":      str(model_dir),
    }
    return metricas, long_rows


# Main ------------------------------------------------------------------------
def main(arquitetura: str, semente_filtro: int | None) -> None:
    partes        = arquitetura.lower().split("_")
    encoder_nome  = partes[0]
    idioma_raw    = partes[1] if len(partes) > 1 else "bi"
    idioma_filtro = None if idioma_raw == "bi" else idioma_raw

    if encoder_nome not in ENCODER_HUB:
        raise SystemExit(
            f"Encoder desconhecido: {encoder_nome}. "
            f"Escolha: {list(ENCODER_HUB)}")

    device = detectar_device()
    MODELOS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    long_path     = RESULTS_DIR / "predicoes_long_epi.parquet"
    metricas_path = RESULTS_DIR / "metricas_epi.json"

    runs_done = set()
    if long_path.exists():
        df_prev   = pd.read_parquet(long_path)
        runs_done = set(
            df_prev["celula"].str.cat(
                df_prev["semente"].astype(str), sep="_seed"))
        log.info("Rodadas epi ja completas: %d", len(runs_done))

    todas_metricas, todos_long_rows = [], []
    for semente in SEEDS:
        if semente_filtro and semente != semente_filtro:
            continue
        celula_nome = f"{encoder_nome}_{idioma_filtro or 'bi'}"
        run_key     = f"{celula_nome}_seed{semente}"
        if run_key in runs_done:
            log.info("Pulando rodada ja completa: %s", run_key)
            continue
        resultado, long_rows = treinar_epi_semente(
            encoder_nome, idioma_filtro, semente, device)
        todas_metricas.append(resultado)
        todos_long_rows.extend(long_rows)

    if todos_long_rows:
        df_new = pd.DataFrame(todos_long_rows)
        if long_path.exists():
            df_all = pd.concat([pd.read_parquet(long_path), df_new],
                               ignore_index=True)
        else:
            df_all = df_new
        df_all.to_parquet(long_path, index=False, compression="snappy")
        log.info("predicoes_long_epi.parquet: %d linhas", len(df_all))

    existing = (json.load(metricas_path.open())
                if metricas_path.exists() else [])
    if todas_metricas:
        metricas_path.write_text(
            json.dumps(existing + todas_metricas, indent=2,
                       ensure_ascii=False, default=str)
        )
    ok = [m for m in existing + todas_metricas if m.get("status") == "ok"]
    if ok:
        df_m = pd.DataFrame(ok)
        log.info("\nResultados epi:\n%s",
                 df_m[["run", "f1_macro_teste"]]
                 .sort_values("f1_macro_teste", ascending=False)
                 .to_string(index=False))
    log.info("Concluido.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/06b_treinar_epi.log",
                                mode="a", encoding="utf-8"),
        ],
    )
    Path("logs").mkdir(exist_ok=True)
    parser = argparse.ArgumentParser(
        description="Fine-tuning: orientacao epistemologica (dois eixos).")
    parser.add_argument("--arquitetura", required=True,
                        help="Arquitetura vencedora de 06a (ex: xlmr_bi).")
    parser.add_argument("--semente", type=int, default=None)
    args = parser.parse_args()
    main(args.arquitetura, args.semente)
