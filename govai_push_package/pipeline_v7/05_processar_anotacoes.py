"""
05_processar_anotacoes.py | Parse de anotacoes Label Studio -> Gold Standard
============================================================================
Migracao dois eixos: tres flags POSITIVOS independentes na camada epi
(epi_positivista, epi_interpretativa, epi_doutrinario_normativa). Sem campo
'epi_na'. orientacao_proeminente derivada das flags (DA-09); inconclusiva e
dn_subtag emitidas. Alpha de Krippendorff para os TRES flags. Gates (OSF secao
6): cluster 0.67, epi 0.55; piso de calibracao DN 0.667 (era 0.40, Addendum 2).

Campos do template Label Studio (Apendice G):
    cluster_primario              radio: si | ps | sts | law | pa | bcs
    cluster_secundario            dropdown: nenhum | si | ps | sts | law | pa | bcs
    cluster_status                radio: classificado | fora_do_campo
    cluster_confianca             radio: alta | media | baixa
    epi_positivista               checkbox: 1 | 0
    epi_interpretativa            checkbox: 1 | 0
    epi_doutrinario_normativa     checkbox: 1 | 0
    epi_confianca                 radio: alta | media | baixa
    notas                         textarea

Saida GS (derivadas): orientacao_proeminente, inconclusiva, dn_subtag (de notas).

Autor: Fernando Leite | FAPESP | Refatoracao v4 (dois eixos, derivacao deterministica) - 25/jun/2026
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

try:
    from utils.metrics import metricas_completas, IRRCAC_VERSION
except ImportError:
    from .utils.metrics import metricas_completas, IRRCAC_VERSION  # type: ignore

try:
    from utils.thresholds import (
        ALPHA_GATE_CLUSTER, ALPHA_GATE_EPI, ALPHA_CALIB_DN_FLOOR,
        KAPPA_REF, faixa_krippendorff,
    )
except ImportError:
    from .utils.thresholds import (  # type: ignore
        ALPHA_GATE_CLUSTER, ALPHA_GATE_EPI, ALPHA_CALIB_DN_FLOOR,
        KAPPA_REF, faixa_krippendorff,
    )

try:
    from utils.derive_orientacao import derive   # fonte unica da derivacao (DA-09)
except ImportError:
    from .utils.derive_orientacao import derive  # type: ignore

INPUT_LS     = Path("dados/anotacoes/label_studio_export.json")
INPUT_CORPUS = Path("dados/intermediarios/corpus_limpo_textual.parquet")
OUTPUT_GS    = Path("dados/gold_standard/gold_standard_final.parquet")
OUTPUT_REL   = Path("dados/gold_standard/relatorio_concordancia.json")
OUTPUT_DISP  = Path("dados/gold_standard/desacordos_para_revisao.csv")

CLUSTERS  = ["si", "ps", "sts", "law", "pa", "bcs"]
EPI_FLAGS = ["epi_positivista", "epi_interpretativa", "epi_doutrinario_normativa"]

log = logging.getLogger("05_processar_anotacoes")

_TRUEY = {"1", "True", "true", "sim"}


# Sintese: orientacao_proeminente e derivada das flags por utils/derive_orientacao.py
# (DA-09: sem prioridade, sem DN-domina). dn_subtag consolida a etiqueta dn: das
# notas dos anotadores (DA-08), apenas quando DN=1.
def _dn_subtag(notas) -> str | None:
    t = str(notas or "").lower()
    for tag in ("dn:ambos", "dn:modo", "dn:norm"):
        if tag in t:
            return tag.split(":")[1]
    return None


def consolidar_dn_subtag(grupo: pd.DataFrame, dn_resolvido: int) -> str | None:
    """Subtag dn: modal entre anotadores que marcaram DN=1; None se DN!=1."""
    if dn_resolvido != 1:
        return None
    subtags = [
        _dn_subtag(n)
        for n, dn in zip(grupo["notas"].tolist(),
                         grupo["epi_doutrinario_normativa"].tolist())
        if int(dn) == 1
    ]
    subtags = [s for s in subtags if s]
    if not subtags:
        return None
    return Counter(subtags).most_common(1)[0][0]


# Parsing do JSON do Label Studio ---------------------------------------------
def extrair_campo(result_items: list[dict], from_name: str) -> str | None:
    for item in result_items:
        if item.get("from_name") == from_name:
            val = item.get("value", {})
            choices = val.get("choices", [])
            if choices:
                return str(choices[0])
            text = val.get("text", [])
            if text:
                return str(text[0]) if isinstance(text, list) else str(text)
    return None


def parse_anotacao(ann: dict, art_id: str) -> dict | None:
    result = ann.get("result", [])
    if not result:
        return None

    anotador          = ann.get("completed_by", {}).get("email", "desconhecido")
    cluster_primario  = extrair_campo(result, "cluster_primario")
    cluster_secundario = extrair_campo(result, "cluster_secundario")
    cluster_status    = extrair_campo(result, "cluster_status") or "classificado"
    cluster_confianca = extrair_campo(result, "cluster_confianca") or "media"
    epi_confianca     = extrair_campo(result, "epi_confianca") or "media"
    notas             = extrair_campo(result, "notas")

    flags = {}
    for f in EPI_FLAGS:
        raw = extrair_campo(result, f)
        flags[f] = 1 if str(raw).strip() in _TRUEY else 0

    return {
        "id_artigo":           art_id,
        "anotador":            anotador,
        "cluster_primario":    cluster_primario,
        "cluster_secundario":  cluster_secundario if cluster_secundario not in {None, "nenhum"} else None,
        "cluster_status":      cluster_status,
        "cluster_confianca":   cluster_confianca,
        "epi_positivista":           flags["epi_positivista"],
        "epi_interpretativa":        flags["epi_interpretativa"],
        "epi_doutrinario_normativa": flags["epi_doutrinario_normativa"],
        "epi_confianca":       epi_confianca,
        "notas":               notas,
    }


def parse_tasks(tasks: list[dict]) -> pd.DataFrame:
    rows = []
    for task in tasks:
        art_id = task.get("data", {}).get("id") or str(task.get("id", ""))
        for ann in task.get("annotations", []):
            parsed = parse_anotacao(ann, art_id)
            if parsed:
                rows.append(parsed)
    return pd.DataFrame(rows)


# Resolucao de concordancia ---------------------------------------------------
def resolver_campo_categorico(vals: list[str]) -> tuple[str | None, str]:
    if not vals:
        return None, "sem_dados"
    contagem = Counter(v for v in vals if v is not None)
    if not contagem:
        return None, "sem_dados"
    modal, n_modal = contagem.most_common(1)[0]
    n_total = len(vals)
    if n_modal == n_total:
        return modal, "unanime"
    elif n_modal > n_total / 2:
        return modal, "2_de_3"
    return None, "disputa_pendente"


def resolver_campo_binario(vals: list[int]) -> tuple[int | None, str]:
    if not vals:
        return None, "sem_dados"
    contagem = Counter(vals)
    modal, n_modal = contagem.most_common(1)[0]
    n_total = len(vals)
    if n_modal == n_total:
        return int(modal), "unanime"
    elif n_modal > n_total / 2:
        return int(modal), "2_de_3"
    return None, "disputa_pendente"


def _gravar_gs_vazio(output_gs: Path, output_rel: Path,
                     output_disp: Path) -> None:
    for path in [output_gs, output_rel, output_disp]:
        path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame().to_parquet(output_gs, index=False)
    output_rel.write_text(
        json.dumps({"status": "sem_anotacoes", "n_anotadores_unicos": 0,
                    "status_gate": {"gate_global_ok": False}}, indent=2),
        encoding="utf-8",
    )
    pd.DataFrame().to_csv(output_disp, index=False)


def main(input_ls: Path, input_corpus: Path, output_gs: Path,
         output_rel: Path, output_disp: Path) -> None:

    log.info("Lendo Label Studio export: %s", input_ls)
    with input_ls.open(encoding="utf-8") as f:
        tasks = json.load(f)
    log.info("  %d tarefas", len(tasks))

    df_long = parse_tasks(tasks)
    if df_long.empty:
        log.warning("  Export sem anotacoes. Gold Standard vazio.")
        _gravar_gs_vazio(output_gs, output_rel, output_disp)
        return

    log.info("  %d anotacoes totais (%d artigos unicos)",
             len(df_long), df_long["id_artigo"].nunique())

    gs_rows  = []
    disputas = []

    for art_id, grupo in df_long.groupby("id_artigo"):
        anotadores = grupo["anotador"].tolist()
        n_ann      = len(anotadores)

        cluster_vals      = grupo["cluster_primario"].tolist()
        cluster_resolvido, conc_cluster = resolver_campo_categorico(cluster_vals)
        if n_ann < 2 and conc_cluster == "unanime":
            conc_cluster = "anotacao_unica"

        cluster_sec_vals = grupo["cluster_secundario"].tolist()
        cluster_sec, _   = resolver_campo_categorico(
            [v for v in cluster_sec_vals if v])
        cluster_status_vals = grupo["cluster_status"].tolist()
        cluster_status, _   = resolver_campo_categorico(cluster_status_vals)

        flag_res  = {}
        flag_conc = {}
        for f in EPI_FLAGS:
            vals = [int(v) if pd.notna(v) else 0 for v in grupo[f].tolist()]
            res, conc = resolver_campo_binario(vals)
            flag_res[f]  = res if res is not None else 0
            flag_conc[f] = conc

        d = derive(
            flag_res["epi_positivista"],
            flag_res["epi_interpretativa"],
            flag_res["epi_doutrinario_normativa"],
        )
        dn_subtag = consolidar_dn_subtag(
            grupo, flag_res["epi_doutrinario_normativa"])

        conf_cluster = Counter(grupo["cluster_confianca"].dropna()).most_common(1)
        conf_cluster = conf_cluster[0][0] if conf_cluster else "media"
        conf_epi     = Counter(grupo["epi_confianca"].dropna()).most_common(1)
        conf_epi     = conf_epi[0][0] if conf_epi else "media"

        tem_disputa = (conc_cluster == "disputa_pendente") or any(
            c == "disputa_pendente" for c in flag_conc.values()
        )
        if tem_disputa:
            disputas.append({
                "id_artigo":    art_id,
                "n_anotadores": n_ann,
                "cluster_primario_vals": "|".join(str(v) for v in cluster_vals),
                "conc_cluster":          conc_cluster,
                **{f"{f}_vals": "|".join(str(v) for v in grupo[f].tolist())
                   for f in EPI_FLAGS},
                **{f"conc_{f}": flag_conc[f] for f in EPI_FLAGS},
            })

        gs_rows.append({
            "id":                                 art_id,
            "cluster_primario":                   cluster_resolvido,
            "cluster_secundario":                 cluster_sec,
            "cluster_status":                     cluster_status or "classificado",
            "cluster_confianca":                  conf_cluster,
            "concordancia_cluster":               conc_cluster,
            "epi_positivista":                    flag_res["epi_positivista"],
            "epi_interpretativa":                 flag_res["epi_interpretativa"],
            "epi_doutrinario_normativa":          flag_res["epi_doutrinario_normativa"],
            "orientacao_proeminente":             d["orientacao_proeminente"],
            "inconclusiva":                       d["inconclusiva"],
            "dn_subtag":                          dn_subtag,
            "epi_confianca":                      conf_epi,
            "concordancia_epi_positivista":              flag_conc["epi_positivista"],
            "concordancia_epi_interpretativa":           flag_conc["epi_interpretativa"],
            "concordancia_epi_doutrinario_normativa":    flag_conc["epi_doutrinario_normativa"],
            "n_anotadores":  n_ann,
            "anotadores":    ";".join(sorted(set(anotadores))),
            "tem_disputa":   tem_disputa,
        })

    gs = pd.DataFrame(gs_rows)
    log.info("Gold Standard: %d artigos", len(gs))

    # Mesclar metadados do corpus (filtro defensivo: so colunas presentes)
    if input_corpus.exists():
        schema_corpus  = pq.read_schema(input_corpus)
        cols_desejadas = ["id", "titulo_limpo", "abstract_limpo", "ano",
                          "periodico_nome", "periodico_source_id"]
        cols_presentes = [c for c in cols_desejadas if c in schema_corpus.names]
        if "id" not in cols_presentes:
            log.warning("  Corpus sem coluna 'id'; metadados nao mesclados.")
        else:
            corpus = pd.read_parquet(input_corpus, columns=cols_presentes)
            gs = gs.merge(corpus, on="id", how="left")
            log.info("  Metadados mesclados (%s)",
                     ", ".join(c for c in cols_presentes if c != "id"))

    # Kappa e alpha por camada (irrCAC; DA-06) --------------------------------
    cluster_to_int        = {c: i for i, c in enumerate(CLUSTERS)}
    ratings_alpha_cluster = defaultdict(list)
    ratings_epi           = {f: {} for f in EPI_FLAGS}

    for art_id, grupo in df_long.groupby("id_artigo"):
        rc = [cluster_to_int.get(v) for v in grupo["cluster_primario"].tolist()
              if v in cluster_to_int]
        if rc:
            ratings_alpha_cluster[art_id] = rc
        for f in EPI_FLAGS:
            ratings_epi[f][str(art_id)] = [
                int(v) if pd.notna(v) else 0 for v in grupo[f].tolist()
            ]

    mc_cluster    = metricas_completas(ratings_alpha_cluster)
    kappa_cluster = mc_cluster.fleiss_kappa
    alpha_cluster = mc_cluster.krippendorff_alpha

    mc_epi    = {f: metricas_completas(ratings_epi[f]) for f in EPI_FLAGS}
    alpha_epi = {f: mc_epi[f].krippendorff_alpha for f in EPI_FLAGS}
    kappa_epi = {f: mc_epi[f].fleiss_kappa       for f in EPI_FLAGS}

    log.info("Kappa cluster:   %.3f (ref. >= %.2f, diagnostico)  [AC1=%.3f]",
             kappa_cluster, KAPPA_REF, mc_cluster.gwet_ac1)
    log.info("Krippendorff alpha cluster: %.3f "
             "(GATE >= %.3f -> %s)  IC95%%=(%.3f, %.3f)",
             alpha_cluster, ALPHA_GATE_CLUSTER,
             faixa_krippendorff(alpha_cluster),
             mc_cluster.alpha_ci_lower, mc_cluster.alpha_ci_upper)
    # Todos os flags epi sao julgados contra o mesmo gate de aceitacao do GS
    # (ALPHA_GATE_EPI = 0.55), inclusive DN (decisao Etapa 2). O piso de
    # calibracao (0.667) e da fase de calibracao; abaixo, so como diagnostico.
    for f in EPI_FLAGS:
        a = alpha_epi[f]
        log.info("Krippendorff alpha %s: %.3f "
                 "(gate_epi >= %.3f -> %s) [kappa=%.3f]",
                 f, a, ALPHA_GATE_EPI, faixa_krippendorff(a), kappa_epi[f])
    a_dn = alpha_epi["epi_doutrinario_normativa"]
    log.info("Diagnostico DN: alpha %.3f vs piso de calibracao %.3f -> %s "
             "(gate de aceitacao do GS para DN e %.3f, nao o piso)",
             a_dn, ALPHA_CALIB_DN_FLOOR,
             "clarou" if a_dn >= ALPHA_CALIB_DN_FLOOR else "abaixo",
             ALPHA_GATE_EPI)
    if mc_cluster.gwet_ac1 - kappa_cluster > 0.15:
        log.warning(
            "  Paradoxo de prevalencia provavel "
            "(AC1 %.3f >> kappa %.3f): interprete kappa com cautela.",
            mc_cluster.gwet_ac1, kappa_cluster)
    log.info("Disputas pendentes: %d (%.1f%%)", len(disputas),
             100 * len(disputas) / max(len(gs), 1))

    for path in [output_gs, output_rel, output_disp]:
        path.parent.mkdir(parents=True, exist_ok=True)
    gs.to_parquet(output_gs, index=False, compression="snappy")
    log.info("Gold Standard gravado: %s", output_gs)

    # Gate de aceitacao por camada
    epi_pos_ok        = bool(alpha_epi["epi_positivista"]           >= ALPHA_GATE_EPI)
    epi_int_ok        = bool(alpha_epi["epi_interpretativa"]        >= ALPHA_GATE_EPI)
    epi_dn_ok         = bool(alpha_epi["epi_doutrinario_normativa"] >= ALPHA_GATE_EPI)
    dn_calib_floor_ok = bool(alpha_epi["epi_doutrinario_normativa"] >= ALPHA_CALIB_DN_FLOOR)
    cluster_ok        = bool(alpha_cluster >= ALPHA_GATE_CLUSTER)

    stats = {
        "n_tarefas":           len(tasks),
        "n_anotacoes":         len(df_long),
        "n_artigos_gs":        len(gs),
        "n_anotadores_unicos": df_long["anotador"].nunique(),
        "krippendorff_alpha": {
            "cluster":      round(alpha_cluster, 4),
            "cluster_ci95": [round(mc_cluster.alpha_ci_lower, 4),
                             round(mc_cluster.alpha_ci_upper, 4)],
            "epi_positivista":           round(alpha_epi["epi_positivista"], 4),
            "epi_interpretativa":        round(alpha_epi["epi_interpretativa"], 4),
            "epi_doutrinario_normativa": round(alpha_epi["epi_doutrinario_normativa"], 4),
        },
        "kappa_diagnostico": {
            "cluster":                   round(kappa_cluster, 4),
            "epi_positivista":           round(kappa_epi["epi_positivista"], 4),
            "epi_interpretativa":        round(kappa_epi["epi_interpretativa"], 4),
            "epi_doutrinario_normativa": round(kappa_epi["epi_doutrinario_normativa"], 4),
            "paradoxo_prevalencia_provavel": bool(
                mc_cluster.gwet_ac1 - kappa_cluster > 0.15),
        },
        "gwet_ac1":      {"cluster": round(mc_cluster.gwet_ac1, 4)},
        "irrcac_version": IRRCAC_VERSION,
        "limiares": {
            "alpha_gate_cluster":     ALPHA_GATE_CLUSTER,
            "alpha_gate_epi":         ALPHA_GATE_EPI,
            "alpha_calib_dn_floor":   ALPHA_CALIB_DN_FLOOR,
            "kappa_ref_diagnostico":  KAPPA_REF,
        },
        "faixa_krippendorff": {
            "cluster":                   faixa_krippendorff(alpha_cluster),
            "epi_positivista":           faixa_krippendorff(alpha_epi["epi_positivista"]),
            "epi_interpretativa":        faixa_krippendorff(alpha_epi["epi_interpretativa"]),
            "epi_doutrinario_normativa": faixa_krippendorff(alpha_epi["epi_doutrinario_normativa"]),
        },
        "status_gate": {
            "cluster_alpha_ok":     cluster_ok,
            "epi_pos_alpha_ok":     epi_pos_ok,
            "epi_int_alpha_ok":     epi_int_ok,
            "epi_dn_alpha_ok":      epi_dn_ok,
            "epi_dn_calib_floor_ok": dn_calib_floor_ok,
            "gate_global_ok": bool(
                cluster_ok and epi_pos_ok and epi_int_ok and epi_dn_ok),
        },
        "n_disputas_pendentes": len(disputas),
    }
    output_rel.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    if disputas:
        pd.DataFrame(disputas).to_csv(output_disp, index=False,
                                      encoding="utf-8")
        log.info("Disputas para revisao: %s (%d artigos)",
                 output_disp, len(disputas))

    log.info("Concluido.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/05_processar_anotacoes.log",
                                mode="a", encoding="utf-8"),
        ],
    )
    Path("logs").mkdir(exist_ok=True)
    parser = argparse.ArgumentParser(
        description="Converte export Label Studio em Gold Standard (ternario).")
    parser.add_argument("--input-ls",     type=Path, default=INPUT_LS)
    parser.add_argument("--input-corpus", type=Path, default=INPUT_CORPUS)
    parser.add_argument("--output-gs",    type=Path, default=OUTPUT_GS)
    parser.add_argument("--output-rel",   type=Path, default=OUTPUT_REL)
    parser.add_argument("--output-disp",  type=Path, default=OUTPUT_DISP)
    args = parser.parse_args()
    main(args.input_ls, args.input_corpus, args.output_gs,
         args.output_rel, args.output_disp)
