"""
06a_treinar_clusters.py — Fine-tuning: clusters disciplinares
=============================================================
Manual §5.6 (v14): treina um classificador Transformer para a camada
disciplinar (6 clusters, mono-rótulo primário) em 9 células × 3 seeds
= 27 rodadas. Otimizado para Apple Silicon M5 Max via PyTorch MPS.

Células (3 encoders × 3 configurações de corpus):
    bertimbau × pt    — BERTimbau, artigos em português
    bertimbau × en    — BERTimbau, artigos em inglês
    bertimbau × bi    — BERTimbau, todos os artigos
    scibert × pt      — SciBERT, artigos em português
    scibert × en      — SciBERT, artigos em inglês
    scibert × bi      — SciBERT, todos
    xlmr × pt         — XLM-R, artigos em português
    xlmr × en         — XLM-R, artigos em inglês
    xlmr × bi         — XLM-R, todos

Input:
    dados/gold_standard/gold_standard_final.parquet
    dados/intermediarios/corpus_limpo_textual.parquet  (para texto)

Outputs:
    modelos/clusters/{celula}_seed{semente}/  — modelos HuggingFace salvos
    dados/resultados/predicoes_long_clusters.parquet    — métricas long-format
    dados/resultados/metricas_clusters.json  — sumário de todas as rodadas

Dependências:
    pip install transformers datasets torch scikit-learn pandas pyarrow
    (PyTorch deve ser instalado com suporte MPS — já incluso no pip do macOS)

Como executar:
    # Rodar todas as 27 células (lento, ~12-24h no M5 Max):
    python 06a_treinar_clusters.py

    # Rodar só uma célula (útil para teste):
    python 06a_treinar_clusters.py --celula bertimbau_pt --semente 42

    # Rodar só as sementes de uma célula específica:
    python 06a_treinar_clusters.py --celula scibert_en

Configuração de hardware (M5 Max 40 núcleos GPU):
    PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0  (deixa PyTorch usar toda a memória unificada)
    batch_size=32 para BERT-base com seq_len=256 no M5 Max
    batch_size=16 para seq_len=512

Autor: Fernando Leite | FAPESP | Refatoração v2 — 22/maio/2026
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

# ── Silenciar warnings de tokenização e paralelismo ────────────────────────
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.0")

# ── Configuração ────────────────────────────────────────────────────────────
GS_PATH      = Path("dados/gold_standard/gold_standard_final.parquet")
CORPUS_PATH  = Path("dados/intermediarios/corpus_limpo_textual.parquet")
MODELOS_DIR  = Path("modelos/clusters")
RESULTS_DIR  = Path("dados/resultados")

CLUSTERS = ["si", "ps", "sts", "law", "pa", "bcs"]
CLUSTER_TO_INT = {c: i for i, c in enumerate(CLUSTERS)}
INT_TO_CLUSTER = {i: c for c, i in CLUSTER_TO_INT.items()}

ENCODER_HUB = {
    "bertimbau": "neuralmind/bert-base-portuguese-cased",
    "scibert":   "allenai/scibert_scivocab_uncased",
    "xlmr":      "xlm-roberta-base"
}
SEEDS = [42, 123, 2026]
MAX_LENGTH = 512
BATCH_TRAIN = 16    # conservador para seq_len=512; aumentar para 32 se memória permitir
BATCH_EVAL  = 32
LEARNING_RATE   = 2e-5
WEIGHT_DECAY    = 0.01
N_EPOCHS        = 15   # early stopping evita overfitting
WARMUP_RATIO    = 0.1
PATIENCE        = 3    # early stopping patience

TEST_SIZE  = 0.15
VAL_SIZE   = 0.15   # do conjunto treino+val original

log = logging.getLogger("06a_treinar_clusters")


# ── Detecção de dispositivo (MPS → CUDA → CPU) ───────────────────────────────

def detectar_device() -> str:
    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        log.info("Dispositivo: MPS (Apple Silicon M5 Max)")
        return "mps"
    elif torch.cuda.is_available():
        log.info("Dispositivo: CUDA (%s)", torch.cuda.get_device_name(0))
        return "cuda"
    else:
        log.warning("Dispositivo: CPU (treinamento será lento)")
        return "cpu"


# ── Dataset PyTorch ──────────────────────────────────────────────────────────

class ClusterDataset(Dataset):
    """Dataset para classificação de cluster primário (mono-rótulo)."""

    def __init__(self, titulos: list[str], abstracts: list[str],
                 labels: list[int], tokenizer, max_length: int = MAX_LENGTH):
        self.encodings = tokenizer(
            titulos,
            abstracts,
            max_length=max_length,
            truncation=True,
            padding="max_length",
            return_token_type_ids=True
        )
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {k: torch.tensor(v[idx]) for k, v in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item


# ── Métricas ────────────────────────────────────────────────────────────────

def compute_metrics(pred):
    """Métricas para classificação cluster (mono-rótulo, 6 classes).

    Reportar para Manual §A.8 e artigo metodológico:
    - f1_macro (primária, otimização do early stopping)
    - f1 por classe (diagnóstico)
    - accuracy (sanity check)
    - f1_weighted (sensível a desbalanceamento)
    - ECE (Expected Calibration Error) — se > 0,10 acionar calibração isotônica
    - Brier score multi-classe — calibração probabilística
    """
    from sklearn.metrics import accuracy_score
    from scipy.special import softmax

    labels    = pred.label_ids
    preds     = pred.predictions.argmax(-1)
    probs     = softmax(pred.predictions, axis=-1)

    f1_macro    = f1_score(labels, preds, average="macro", zero_division=0)
    f1_weighted = f1_score(labels, preds, average="weighted", zero_division=0)
    f1_per_cl   = f1_score(labels, preds, average=None, zero_division=0,
                           labels=list(range(len(CLUSTERS))))
    acc         = accuracy_score(labels, preds)

    # ECE com 10 bins (padrão Guo et al. 2017)
    n_bins = 10
    bin_edges = np.linspace(0, 1, n_bins + 1)
    confidences = probs.max(axis=-1)
    accuracies = (preds == labels).astype(float)
    ece = 0.0
    for b in range(n_bins):
        mask = (confidences > bin_edges[b]) & (confidences <= bin_edges[b + 1])
        if mask.sum() > 0:
            avg_conf = confidences[mask].mean()
            avg_acc  = accuracies[mask].mean()
            ece += (mask.sum() / len(labels)) * abs(avg_conf - avg_acc)

    # Brier multi-classe: média do erro quadrático com rótulo one-hot
    onehot = np.zeros_like(probs)
    onehot[np.arange(len(labels)), labels] = 1
    brier = float(((probs - onehot) ** 2).sum(axis=-1).mean())

    result = {
        "f1_macro":    float(f1_macro),
        "f1_weighted": float(f1_weighted),
        "accuracy":    float(acc),
        "ece":         float(ece),
        "brier":       brier,
    }
    for i, cl in enumerate(CLUSTERS):
        result[f"f1_{cl}"] = float(f1_per_cl[i]) if i < len(f1_per_cl) else 0.0
    return result


# ── Carga e preparação dos dados ─────────────────────────────────────────────

def carregar_dados(idioma_filtro: str | None) -> pd.DataFrame:
    """
    Carrega Gold Standard e mescla com corpus textual.
    idioma_filtro: 'pt' | 'en' | None (= todos = bi)
    """
    gs = pd.read_parquet(GS_PATH)

    # ── Contrato com 05_processar_anotacoes.py (auditoria Round 2) ────────────
    # gs.get("col", escalar) num DataFrame devolve a Series se a coluna existe,
    # mas o ESCALAR se não existe — e um escalar booleano em gs[mask] quebra de
    # forma confusa. Validamos o contrato explicitamente: se 05 mudar de schema,
    # falhamos aqui com mensagem clara em vez de produzir uma máscara degenerada.
    cols_obrigatorias = {"id", "cluster_primario", "cluster_status", "concordancia_cluster"}
    faltantes = cols_obrigatorias - set(gs.columns)
    if faltantes:
        raise KeyError(
            f"Gold Standard sem colunas esperadas de 05: {sorted(faltantes)}. "
            f"Colunas presentes: {sorted(gs.columns)}"
        )

    # ── Filtros coerentes com o schema escrito por 05_processar_anotacoes.py ─
    # AUDITORIA QA: a versão anterior tentava filtrar por `tem_disputa`,
    # coluna que nunca foi escrita por 05 (05 escreve `concordancia_cluster`
    # com valor "disputa_pendente"). Resultado: gs.get("tem_disputa", False)
    # retornava o escalar False, e ~False vinha como True, tornando o filtro
    # silenciosamente inerte. Artigos sem cluster_primario resolvido
    # vazavam para o treino com label NaN, derrubando F1.
    eh_classificado    = gs["cluster_status"] == "classificado"
    sem_disputa        = gs["concordancia_cluster"] != "disputa_pendente"
    cluster_resolvido  = gs["cluster_primario"].notna()

    gs = gs[eh_classificado & sem_disputa & cluster_resolvido].copy()
    log.info("  Após filtros: %d artigos classificados e resolvidos", len(gs))

    corpus = pd.read_parquet(CORPUS_PATH, columns=["id", "titulo_limpo",
                                                    "abstract_limpo", "idioma_detectado"])
    df = gs.merge(corpus, on="id", how="inner")

    if idioma_filtro in ("pt", "en"):
        col_idioma = df.get("idioma_detectado", df.get("idioma", pd.Series(dtype=str)))
        df = df[col_idioma.fillna("").str.lower() == idioma_filtro]
        log.info("  Filtro idioma '%s': %d artigos", idioma_filtro, len(df))

    # Remover artigos sem cluster_primario válido
    df = df[df["cluster_primario"].isin(CLUSTERS)].copy()
    df["label"] = df["cluster_primario"].map(CLUSTER_TO_INT)
    df = df.dropna(subset=["label", "titulo_limpo", "abstract_limpo"])
    df["titulo_limpo"]   = df["titulo_limpo"].fillna("").astype(str)
    df["abstract_limpo"] = df["abstract_limpo"].fillna("").astype(str)
    log.info("  Dataset final: %d artigos", len(df))
    return df


def split_dados(df: pd.DataFrame, semente: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Divide em treino/val/teste estratificado por cluster_primario."""
    # Separar teste primeiro (estratificado)
    df_trainval, df_test = train_test_split(
        df, test_size=TEST_SIZE, random_state=semente,
        stratify=df["cluster_primario"]
    )
    # Separar validação do trainval
    df_train, df_val = train_test_split(
        df_trainval,
        test_size=VAL_SIZE / (1 - TEST_SIZE),
        random_state=semente,
        stratify=df_trainval["cluster_primario"]
    )
    log.info("  Split: treino=%d val=%d teste=%d", len(df_train), len(df_val), len(df_test))
    return df_train, df_val, df_test


# ── Treinamento de uma célula × semente ─────────────────────────────────────

def treinar_celula_semente(encoder_nome: str, idioma_filtro: str | None,
                            semente: int, device: str) -> dict:
    """
    Treina um classificador para uma célula específica.
    Retorna dicionário de métricas.
    """
    celula_nome = f"{encoder_nome}_{idioma_filtro or 'bi'}"
    run_nome    = f"{celula_nome}_seed{semente}"
    model_dir   = MODELOS_DIR / run_nome
    log.info("=== Rodada: %s ===", run_nome)

    # Dados
    df = carregar_dados(idioma_filtro)
    if len(df) < 30:
        log.warning("  Dados insuficientes (%d artigos). Pulando.", len(df))
        return {"run": run_nome, "status": "dados_insuficientes", "n": len(df)}

    df_train, df_val, df_test = split_dados(df, semente)

    # Reprodutibilidade: fixar todas as RNGs (Python, numpy, torch) ANTES de
    # instanciar o modelo. A cabeça de classificação de
    # AutoModelForSequenceClassification é inicializada aleatoriamente; sem
    # set_seed aqui, as 3 seeds não controlam essa inicialização e a variância
    # entre rodadas mistura ruído de inicialização com efeito real de semente.
    # TrainingArguments(seed=...) só afeta o estado APÓS a construção do modelo.
    set_seed(semente)

    # Tokenizer e modelo
    hub_name  = ENCODER_HUB[encoder_nome]
    tokenizer = AutoTokenizer.from_pretrained(hub_name)
    model     = AutoModelForSequenceClassification.from_pretrained(
        hub_name,
        num_labels=len(CLUSTERS),
        problem_type="single_label_classification"
    )

    # Datasets
    ds_train = ClusterDataset(df_train["titulo_limpo"].tolist(),
                               df_train["abstract_limpo"].tolist(),
                               df_train["label"].astype(int).tolist(), tokenizer)
    ds_val   = ClusterDataset(df_val["titulo_limpo"].tolist(),
                               df_val["abstract_limpo"].tolist(),
                               df_val["label"].astype(int).tolist(), tokenizer)
    ds_test  = ClusterDataset(df_test["titulo_limpo"].tolist(),
                               df_test["abstract_limpo"].tolist(),
                               df_test["label"].astype(int).tolist(), tokenizer)

    # TrainingArguments — compatíveis com MPS/CUDA/CPU.
    # Compatibilidade de versão: `evaluation_strategy` foi renomeado para
    # `eval_strategy` (transformers ≥ 4.46) e `use_mps_device`/`no_cuda` foram
    # depreciados em favor da auto-detecção de dispositivo. Em vez de fixar um
    # nome que quebra na versão errada, inspecionamos a assinatura em runtime e
    # montamos os kwargs com os nomes efetivamente aceitos.
    import inspect
    _ta_params = set(inspect.signature(TrainingArguments.__init__).parameters)

    targs_kwargs = dict(
        output_dir              = str(model_dir),
        num_train_epochs        = N_EPOCHS,
        per_device_train_batch_size = BATCH_TRAIN,
        per_device_eval_batch_size  = BATCH_EVAL,
        learning_rate           = LEARNING_RATE,
        weight_decay            = WEIGHT_DECAY,
        warmup_ratio            = WARMUP_RATIO,
        save_strategy           = "epoch",
        metric_for_best_model   = "f1_macro",
        greater_is_better       = True,
        load_best_model_at_end  = True,
        save_total_limit        = 1,
        seed                    = semente,
        data_seed               = semente,
        report_to               = "none",
        logging_steps           = 10,
        # MPS: fp16/bf16 produzem NaN em gradientes no PyTorch atual.
        fp16                    = False,
        bf16                    = False,
        # MPS não tolera múltiplos workers (perde handle GPU); pin_memory é
        # inócuo em memória unificada Apple Silicon.
        dataloader_num_workers  = 0,
        dataloader_pin_memory   = False,
        # MPS não tem determinismo completo (variação ~0,5% F1).
        full_determinism        = False,
    )
    # Estratégia de avaliação: nome varia por versão.
    if "eval_strategy" in _ta_params:
        targs_kwargs["eval_strategy"] = "epoch"
    else:  # transformers < 4.46
        targs_kwargs["evaluation_strategy"] = "epoch"
    # Seleção de dispositivo: só passa flags legadas se a versão as aceita.
    if "use_mps_device" in _ta_params:
        targs_kwargs["use_mps_device"] = (device == "mps")
    if "no_cuda" in _ta_params:
        targs_kwargs["no_cuda"] = (device not in ("cuda",))

    training_args = TrainingArguments(**targs_kwargs)

    trainer = Trainer(
        model           = model,
        args            = training_args,
        train_dataset   = ds_train,
        eval_dataset    = ds_val,
        compute_metrics = compute_metrics,
        callbacks       = [EarlyStoppingCallback(early_stopping_patience=PATIENCE)]
    )

    trainer.train()

    # Avaliar no conjunto de teste
    test_results = trainer.evaluate(ds_test)
    log.info("  F1-macro teste: %.4f", test_results.get("eval_f1_macro", float("nan")))

    # Salvar modelo final
    model_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(model_dir))
    tokenizer.save_pretrained(str(model_dir))

    # Gerar predições long-format para predicoes_long_clusters.parquet
    pred_output = trainer.predict(ds_test)
    probs       = torch.softmax(torch.tensor(pred_output.predictions), dim=-1).numpy()
    preds       = probs.argmax(axis=-1)
    ids_test    = df_test["id"].tolist()
    labels_test = df_test["label"].astype(int).tolist()

    long_rows = []
    for i, (art_id, prob_row, pred_i, label_i) in enumerate(
            zip(ids_test, probs, preds, labels_test)):
        for j, cluster in enumerate(CLUSTERS):
            long_rows.append({
                "id": art_id,
                "celula": celula_nome,
                "corpus_treino": idioma_filtro or "bi",
                "modelo": encoder_nome,
                "semente": semente,
                "particao": "teste",
                "camada": "cluster",
                "dimensao": cluster,
                "prob": float(prob_row[j]),
                "pred": 1 if pred_i == j else 0,
                "rotulo_verdadeiro": 1 if label_i == j else 0,
                "acerto": (pred_i == j) == (label_i == j)
            })

    metricas = {
        "run": run_nome,
        "encoder": encoder_nome,
        "idioma_filtro": idioma_filtro or "bi",
        "semente": semente,
        "n_treino": len(df_train),
        "n_val": len(df_val),
        "n_teste": len(df_test),
        "f1_macro_teste": float(test_results.get("eval_f1_macro", float("nan"))),
        "f1_por_cluster": {
            cl: float(test_results.get(f"eval_f1_{cl}", float("nan")))
            for cl in CLUSTERS
        },
        "status": "ok",
        "model_dir": str(model_dir)
    }
    return metricas, long_rows


# ── Main ────────────────────────────────────────────────────────────────────

def main(celula_filtro: str | None, semente_filtro: int | None) -> None:
    device = detectar_device()
    MODELOS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    todas_metricas  = []
    todos_long_rows = []

    # Carregar resultados anteriores se existirem (permite retomar)
    long_path = RESULTS_DIR / "predicoes_long_clusters.parquet"
    metricas_path = RESULTS_DIR / "metricas_clusters.json"
    if long_path.exists():
        df_prev = pd.read_parquet(long_path)
        runs_done = set(df_prev["celula"].str.cat(df_prev["semente"].astype(str), sep="_seed"))
        log.info("Retomando: %d rodadas já completas", len(runs_done))
    else:
        runs_done = set()

    for encoder_nome in ENCODER_HUB:
        for idioma_config in ["pt", "en", None]:
            celula_nome = f"{encoder_nome}_{idioma_config or 'bi'}"
            if celula_filtro and not celula_nome.startswith(celula_filtro.replace("-", "_")):
                continue

            for semente in SEEDS:
                if semente_filtro and semente != semente_filtro:
                    continue
                run_key = f"{celula_nome}_seed{semente}"
                if run_key in runs_done:
                    log.info("Pulando rodada já completa: %s", run_key)
                    continue

                resultado = treinar_celula_semente(encoder_nome, idioma_config, semente, device)
                if isinstance(resultado, tuple):
                    metricas, long_rows = resultado
                    todas_metricas.append(metricas)
                    todos_long_rows.extend(long_rows)
                else:
                    todas_metricas.append(resultado)

    # Consolidar e gravar
    if todos_long_rows:
        df_new = pd.DataFrame(todos_long_rows)
        if long_path.exists():
            df_existing = pd.read_parquet(long_path)
            df_all = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df_all = df_new
        df_all.to_parquet(long_path, index=False, compression="snappy")
        log.info("predicoes_long_clusters.parquet: %d linhas", len(df_all))

    if todas_metricas:
        # Append a métricas existentes
        existing = []
        if metricas_path.exists():
            with metricas_path.open() as f:
                existing = json.load(f)
        all_metrics = existing + todas_metricas
        metricas_path.write_text(json.dumps(all_metrics, indent=2, ensure_ascii=False, default=str))

        # Sumarizar melhor resultado por célula
        ok = [m for m in all_metrics if m.get("status") == "ok"]
        if ok:
            df_m = pd.DataFrame(ok)
            melhor_por_celula = (
                df_m.sort_values("f1_macro_teste", ascending=False)
                    .groupby(["encoder", "idioma_filtro"])
                    .first()["f1_macro_teste"]
            )
            log.info("\nMelhor F1-macro por célula:\n%s", melhor_por_celula.to_string())

    log.info("Concluído.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/06a_treinar_clusters.log", mode="a", encoding="utf-8")
        ])
    Path("logs").mkdir(exist_ok=True)

    parser = argparse.ArgumentParser(description="Fine-tuning: clusters disciplinares.")
    parser.add_argument("--celula",  default=None,
                        help="Filtrar por célula (ex: bertimbau_pt, scibert_en).")
    parser.add_argument("--semente", type=int, default=None,
                        help="Rodar apenas esta semente (42, 123, ou 2026).")
    args = parser.parse_args()
    main(args.celula, args.semente)
