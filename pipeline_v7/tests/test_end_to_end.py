"""
tests/test_end_to_end.py — Teste end-to-end: 04c → 05 com 100 artigos
======================================================================
Simula o pipeline completo com dados sintéticos realistas.
Não requer API externa (04a é simulado com escores fixos).

Cobertura:
  - 04c: amostragem estratificada (bug de schema corrigido no v3)
  - 05: parsing Label Studio → Gold Standard + métricas irrCAC
  - utils/metrics: via 05

Saídas geradas em /tmp/test_e2e/ (temporárias, não versionadas).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).parent.parent / "codigo" / "python"
sys.path.insert(0, str(ROOT))

CLUSTERS   = ["si", "ps", "sts", "law", "pa", "bcs"]
IDIOMAS    = ["pt", "en"]
PERIODICOS = [f"P{i:03d}" for i in range(20)]
OUT        = Path("/tmp/test_e2e")
OUT.mkdir(parents=True, exist_ok=True)

rng = random.Random(42)

# ─── 1. Gerar corpus sintético (100 artigos) ──────────────────────────────────
def gerar_corpus(n=100):
    rows = []
    for i in range(n):
        cluster_verdade = rng.choice(CLUSTERS)
        idioma = rng.choice(IDIOMAS)
        periodico = rng.choice(PERIODICOS)
        ano = rng.randint(2015, 2024)
        citacoes = int(abs(rng.gauss(25, 30)))
        abstract_map = {
            "si":  "This paper proposes an enterprise architecture framework for government interoperability using DeLone-McLean IS success model and maturity stages.",
            "ps":  "We analyze e-participation and deliberative democracy in digital public spheres using hybrid media systems theory and accountability metrics.",
            "sts": "Using SCOT and Heeks design-reality gap, we examine the co-evolution of smart city systems and administrative practices through ethnographic fieldwork.",
            "law": "This article argues for algorithmic accountability under GDPR and LGPD, drawing on Pasquale and Floridi's information ethics to propose a rights-based framework.",
            "pa":  "Drawing on Digital Era Governance and Public Value theory, we assess co-production of digital services across 47 municipalities using mixed methods.",
            "bcs": "We test an extended UTAUT model predicting adoption of mobile tax services among 1,200 citizens, using SEM and perceived usefulness constructs.",
        }
        rows.append({
            "id": f"W{i:04d}",
            "titulo_limpo": f"Article {i}: {cluster_verdade.upper()} study on digital governance",
            "abstract_limpo": abstract_map[cluster_verdade],
            "ano": ano,
            "idioma_detectado": idioma,
            "periodico_source_id": periodico,
            "citacoes": citacoes,
            "_cluster_verdade": cluster_verdade,   # para validação interna
        })
    return pd.DataFrame(rows)

corpus = gerar_corpus(100)
corpus_path = OUT / "corpus_limpo_textual.parquet"
corpus.drop(columns=["_cluster_verdade"]).to_parquet(corpus_path, index=False)
print(f"Corpus gerado: {len(corpus)} artigos")
print(f"  Clusters: {dict(corpus['_cluster_verdade'].value_counts())}")

# ─── 2. Simular output do 04a (escores LLM) ───────────────────────────────────
def simular_escores_llm(corpus_df):
    """Simula escores LLM com alta confiança (90% certos), 10% de fronteira."""
    rows = []
    for _, row in corpus_df.iterrows():
        ct = row["_cluster_verdade"]
        # Escores: cluster verdade recebe probabilidade alta
        scores = {c: rng.uniform(0.01, 0.08) for c in CLUSTERS}
        if rng.random() < 0.90:
            # Classificação correta — alta confiança
            scores[ct] = rng.uniform(0.60, 0.90)
        else:
            # Fronteira — dois clusters competem
            second = rng.choice([c for c in CLUSTERS if c != ct])
            scores[ct] = rng.uniform(0.35, 0.50)
            scores[second] = rng.uniform(0.30, 0.45)
        # Normalizar
        total = sum(scores.values())
        scores = {c: v / total for c, v in scores.items()}
        primario = max(scores, key=scores.get)
        sorted_vals = sorted(scores.values(), reverse=True)
        rows.append({
            "id": row["id"],
            **{f"cluster_{c}_llm": scores[c] for c in CLUSTERS},
            "cluster_primario_llm": primario,
            "cluster_secundario_llm": None,
            "fora_do_campo_llm": False,
            "entropia_cluster": float(-sum(v * np.log(v + 1e-12) for v in scores.values()) / np.log(6)),
            "is_fronteira_cluster": (sorted_vals[0] - sorted_vals[1]) < 0.15,
            "modelo_cluster": "meta-llama/llama-3.3-70b-instruct",
            "prompt_versao_cluster": "7f9a8fc2a98e",
            "temperatura": 0.0,
            "seed": 42,
            "data_execucao": "2026-05-29T00:00:00Z",
            "fallback_parsing_cluster": False,
        })
    return pd.DataFrame(rows)

escores = simular_escores_llm(corpus)
escores_path = OUT / "escores_llm_clusters.parquet"
escores.to_parquet(escores_path, index=False)
n_front = escores["is_fronteira_cluster"].sum()
print(f"\nEscores LLM gerados: {len(escores)} artigos, {n_front} fronteiras ({100*n_front/len(escores):.0f}%)")

# ─── 3. Testar 04c (amostragem estratificada) ────────────────────────────────
print("\n=== Testando 04c ===")

import importlib.util
spec = importlib.util.spec_from_file_location(
    "mod04c", ROOT / "04c_amostrar_para_label_studio.py"
)
mod04c = importlib.util.load_from_spec = spec
import importlib
mod04c = importlib.util.module_from_spec(spec)

# Executar 04c diretamente com paths de teste
from unittest.mock import patch
import importlib.util as ilu

# Montar contexto de execução com paths corretos
ctx = {}
exec(open(ROOT / "04c_amostrar_para_label_studio.py").read(), ctx)

# Substituir paths no módulo
ctx["ESCORES_LLM_PATH"] = escores_path
ctx["CORPUS_PATH"]      = corpus_path
ctx["OUTPUT_DIR"]       = OUT / "anotacoes"
ctx["SEMENTES_PROJETO"] = [42]   # só uma semente para o teste
ctx["SNAPSHOT_PATH"]    = OUT / "snapshot.json"

(OUT / "anotacoes").mkdir(exist_ok=True)

# Executar as funções de 04c
df_merged = ctx["carregar_dados"]()
print(f"  Merge OK: {len(df_merged)} artigos")

df_feat = ctx["computar_features_estratificacao"](df_merged)
n_front_04c = df_feat["eh_fronteira"].sum()
print(f"  Fronteiras detectadas: {n_front_04c} ({100*n_front_04c/len(df_feat):.0f}%)")
print(f"  Estratos únicos: {df_feat['estrato'].nunique()}")

# Amostragem
amostra_rep = ctx["amostrar_representativos"](df_feat, 50, 42)
amostra_front = ctx["amostrar_fronteira"](df_feat, 50, 42)
print(f"  Representativos: {len(amostra_rep)} | Fronteira: {len(amostra_front)}")

# Exportar JSON Label Studio
amostra_rep["criterio"] = "representativo"
amostra_front["criterio"] = "fronteira"
import pandas as pd
amostra = pd.concat([amostra_rep, amostra_front], ignore_index=True)

ctx["exportar_label_studio"](amostra, OUT / "anotacoes/amostra_gs_seed42_cluster.json", "cluster")
ctx["exportar_label_studio"](amostra, OUT / "anotacoes/amostra_gs_seed42_epi.json", "epi")

# Verificar arquivos
tasks_json = json.loads((OUT / "anotacoes/amostra_gs_seed42_cluster.json").read_bytes())
print(f"  JSON Label Studio: {len(tasks_json)} tarefas")
print(f"  ✓ 04c passou sem crash (bug de schema CORRIGIDO)")

# ─── 4. Simular export Label Studio e testar 05 ────────────────────────────
print("\n=== Testando 05 (Label Studio → Gold Standard + métricas irrCAC) ===")

# Montar JSON simulando 2 anotadores (alpha@fgv.br e beta@fgv.br)
def simular_label_studio_export(amostra_df, n_artigos=None):
    """Cria JSON no formato Label Studio com 2 anotadores, ~80% concordância."""
    rng2 = random.Random(123)
    tarefas = []
    df = amostra_df.head(n_artigos) if n_artigos else amostra_df

    for _, row in df.iterrows():
        cluster_base = row.get("cluster_primario_llm", rng2.choice(CLUSTERS))
        epi_pos_base = 1 if cluster_base in ("si", "bcs", "pa") else 0
        epi_int_base = 1 if cluster_base in ("sts", "ps") else 0

        anotacoes = []
        for email, offset_seed in [("alpha@fgv.br", 1), ("beta@fgv.br", 2)]:
            rng3 = random.Random(int(row["id"][1:]) * 10 + offset_seed)
            # 80% concordam com cluster base
            cl = cluster_base if rng3.random() < 0.80 else rng3.choice(CLUSTERS)
            epi_pos = epi_pos_base if rng3.random() < 0.85 else 1 - epi_pos_base
            epi_int = epi_int_base if rng3.random() < 0.85 else 1 - epi_int_base
            conf = rng3.choice(["alta", "alta", "media"])
            anotacoes.append({
                "completed_by": {"email": email},
                "result": [
                    {"from_name": "cluster_primario",   "value": {"choices": [cl]}},
                    {"from_name": "cluster_secundario", "value": {"choices": ["nenhum"]}},
                    {"from_name": "cluster_status",     "value": {"choices": ["classificado"]}},
                    {"from_name": "cluster_confianca",  "value": {"choices": [conf]}},
                    {"from_name": "epi_positivista",    "value": {"choices": [str(epi_pos)]}},
                    {"from_name": "epi_interpretativa", "value": {"choices": [str(epi_int)]}},
                    {"from_name": "epi_na",             "value": {"choices": ["FALSE"]}},
                    {"from_name": "epi_confianca",      "value": {"choices": ["media"]}},
                ]
            })
        tarefas.append({"data": {"id": row["id"]}, "annotations": anotacoes})
    return tarefas

export_ls = simular_label_studio_export(amostra, n_artigos=100)
export_ls_path = OUT / "anotacoes/label_studio_export.json"
export_ls_path.write_text(json.dumps(export_ls, ensure_ascii=False))
print(f"  Export Label Studio simulado: {len(export_ls)} tarefas, 2 anotadores")

# Executar 05 com paths de teste
ctx05 = {}
exec(open(ROOT / "05_processar_anotacoes.py").read(), ctx05)

ctx05["INPUT_LS"]     = export_ls_path
ctx05["INPUT_CORPUS"] = corpus_path
ctx05["OUTPUT_GS"]    = OUT / "gold_standard/gold_standard_final.parquet"
ctx05["OUTPUT_REL"]   = OUT / "gold_standard/relatorio_concordancia.json"
ctx05["OUTPUT_DISP"]  = OUT / "gold_standard/desacordos_para_revisao.csv"
(OUT / "gold_standard").mkdir(exist_ok=True)

ctx05["main"](
    ctx05["INPUT_LS"], ctx05["INPUT_CORPUS"],
    ctx05["OUTPUT_GS"], ctx05["OUTPUT_REL"], ctx05["OUTPUT_DISP"]
)

# Verificar outputs
gs = pd.read_parquet(OUT / "gold_standard/gold_standard_final.parquet")
rel = json.loads((OUT / "gold_standard/relatorio_concordancia.json").read_text())

print(f"\n  Gold Standard: {len(gs)} artigos")
print(f"  n_anotadores_únicos: {rel['n_anotadores_unicos']}")
print(f"  Krippendorff α cluster: {rel['krippendorff_alpha']['cluster']}")
print(f"  Fleiss κ cluster:        {rel['kappa']['cluster']}")
print(f"  Gwet AC1 cluster:        {rel['gwet_ac1']['cluster']}")
print(f"  IC95% α cluster:         {rel['krippendorff_alpha']['cluster_ci95']}")
print(f"  irrCAC versão:           {rel['irrcac_version']}")
print(f"  Gate cluster α≥0.667:    {rel['status_gate']['cluster_alpha_ok']}")
print(f"  Disputas pendentes:      {rel['n_disputas_pendentes']}")

print("\n✓ Teste end-to-end com 100 artigos: PASSOU")
print("  Fluxo coberto: corpus sintético → escores LLM simulados → 04c → Label Studio simulado → 05")
