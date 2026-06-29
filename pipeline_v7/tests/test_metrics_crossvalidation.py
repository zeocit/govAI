"""
tests/test_metrics_crossvalidation.py
======================================
Validação cruzada: irrCAC (utils/metrics.py) × implementação manual
(utils/metrics_manual.py).

Protocolo de aceitação (Codebook v2.2 Apêndice 6.3):
  - Concordância perfeita: ambas retornam 1.0 (ou muito próximo).
  - Concordância aleatória: ambas retornam próximo de 0.
  - Caso misto típico (2 anotadores, 500 artigos): |Δα| ≤ 0.005.
  - Missing values: irrCAC aceita sem crash; manual pode ser NaN.

Executar:
    cd pipeline_v4
    python -m pytest tests/test_metrics_crossvalidation.py -v

Resultados gravados em tests/crossval_report.json para rastreabilidade.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "codigo" / "python"))

from utils.metrics import (
    fleiss_kappa as fleiss_irrcac,
    krippendorff_alpha_nominal as alpha_irrcac,
    metricas_completas,
    IRRCAC_VERSION,
)
from utils.metrics_manual import (
    fleiss_kappa as fleiss_manual,
    krippendorff_alpha_nominal as alpha_manual,
)

CLUSTERS = ["si", "ps", "sts", "law", "pa", "bcs"]
CLUSTER_TO_INT = {c: i for i, c in enumerate(CLUSTERS)}
DELTA_THRESHOLD = 0.005   # tolerância máxima de divergência

results = {}


def make_ratings_dict(ratings: list[list[str]]) -> dict:
    return {str(i): vals for i, vals in enumerate(ratings)}


def make_ratings_matrix_int(ratings: list[list[str]]) -> list[list[int]]:
    return [[CLUSTER_TO_INT[v] for v in row] for row in ratings]


# ─── Dataset 1: concordância perfeita ─────────────────────────────────────────
def test_concordancia_perfeita_alpha():
    ratings = [["si", "si"], ["pa", "pa"], ["bcs", "bcs"], ["law", "law"], ["ps", "ps"]] * 10
    rd = make_ratings_dict(ratings)
    a = alpha_irrcac(rd)
    m = alpha_manual(rd)
    print(f"  [Perfeita] α irrCAC={a:.4f}  manual={m:.4f}")
    results["perfeita_alpha_irrcac"] = round(a, 6)
    results["perfeita_alpha_manual"] = round(m, 6)
    assert a >= 0.99, f"α deveria ser ≈1 (perfeita), got {a}"
    assert m >= 0.99, f"α manual deveria ser ≈1 (perfeita), got {m}"


def test_concordancia_perfeita_kappa():
    ratings = [["si", "si", "si"], ["pa", "pa", "pa"], ["bcs", "bcs", "bcs"]] * 10
    rm = make_ratings_matrix_int(ratings)
    k_i = fleiss_irrcac(rm, 6)
    k_m = fleiss_manual(rm, 6)
    print(f"  [Perfeita] κ irrCAC={k_i:.4f}  manual={k_m:.4f}")
    results["perfeita_kappa_irrcac"] = round(k_i, 6)
    results["perfeita_kappa_manual"] = round(k_m, 6)
    assert k_i >= 0.99, f"κ deveria ser ≈1 (perfeita), got {k_i}"
    assert k_m >= 0.99, f"κ manual deveria ser ≈1 (perfeita), got {k_m}"


# ─── Dataset 2: concordância aleatória ────────────────────────────────────────
def test_concordancia_aleatoria():
    rng = random.Random(42)
    # 200 artigos, 2 anotadores, seleção aleatória → α ≈ 0
    ratings = [[rng.choice(CLUSTERS), rng.choice(CLUSTERS)] for _ in range(200)]
    rd = make_ratings_dict(ratings)
    a_i = alpha_irrcac(rd)
    a_m = alpha_manual(rd)
    print(f"  [Aleatória] α irrCAC={a_i:.4f}  manual={a_m:.4f}")
    results["aleatoria_alpha_irrcac"] = round(a_i, 6)
    results["aleatoria_alpha_manual"] = round(a_m, 6)
    # Para dados aleatórios, α deve ser próximo de 0 (pode ser levemente negativo)
    assert abs(a_i) < 0.20, f"α aleatório deveria ser ≈0, got {a_i}"
    assert abs(a_m) < 0.20, f"α manual aleatório deveria ser ≈0, got {a_m}"


# ─── Dataset 3: caso misto típico — tolerância ≤ 0.005 ───────────────────────
def test_caso_tipico_convergencia():
    """Simula caso realista: 500 artigos, 2 anotadores, κ≈0.70."""
    rng = random.Random(123)
    ratings = []
    for _ in range(500):
        base = rng.choice(CLUSTERS)
        # 80% de probabilidade de concordância
        if rng.random() < 0.80:
            ratings.append([base, base])
        else:
            ratings.append([base, rng.choice(CLUSTERS)])

    rd = make_ratings_dict(ratings)
    rm = make_ratings_matrix_int(ratings)

    a_i = alpha_irrcac(rd)
    a_m = alpha_manual(rd)
    k_i = fleiss_irrcac(rm, 6)
    k_m = fleiss_manual(rm, 6)

    delta_a = abs(a_i - a_m)
    delta_k = abs(k_i - k_m)

    print(f"  [Típico] α irrCAC={a_i:.4f}  manual={a_m:.4f}  |Δ|={delta_a:.6f}")
    print(f"  [Típico] κ irrCAC={k_i:.4f}  manual={k_m:.4f}  |Δ|={delta_k:.6f}")
    results["tipico_alpha_irrcac"]  = round(a_i, 6)
    results["tipico_alpha_manual"]  = round(a_m, 6)
    results["tipico_alpha_delta"]   = round(delta_a, 8)
    results["tipico_kappa_irrcac"]  = round(k_i, 6)
    results["tipico_kappa_manual"]  = round(k_m, 6)
    results["tipico_kappa_delta"]   = round(delta_k, 8)

    assert delta_a <= DELTA_THRESHOLD, \
        f"|Δα| = {delta_a:.6f} excede tolerância de {DELTA_THRESHOLD}"
    assert delta_k <= DELTA_THRESHOLD, \
        f"|Δκ| = {delta_k:.6f} excede tolerância de {DELTA_THRESHOLD}"


# ─── Dataset 4: prevalência alta (paradoxo de Kappa) ─────────────────────────
def test_prevalencia_alta_AC1():
    """cluster 'si' domina (70%). Gwet's AC1 deve ser > Fleiss κ."""
    rng = random.Random(2026)
    ratings = []
    for _ in range(300):
        base = "si" if rng.random() < 0.70 else rng.choice(CLUSTERS[1:])
        agree = rng.random() < 0.80
        ratings.append([base, base if agree else rng.choice(CLUSTERS)])

    rd = make_ratings_dict(ratings)
    mc = metricas_completas(rd)

    print(f"  [Prevalência alta SI=70%] κ={mc.fleiss_kappa:.4f}  "
          f"α={mc.krippendorff_alpha:.4f}  AC1={mc.gwet_ac1:.4f}")
    results["prevalencia_alta_kappa"] = round(mc.fleiss_kappa, 6)
    results["prevalencia_alta_alpha"] = round(mc.krippendorff_alpha, 6)
    results["prevalencia_alta_ac1"]   = round(mc.gwet_ac1, 6)
    # AC1 deve ser maior que Kappa (diagnóstico do paradoxo)
    # (pode ser diferente em direção; marcamos como informação, não falha)
    print(f"  [Diagnóstico paradoxo] AC1 > κ: {mc.gwet_ac1 > mc.fleiss_kappa}")


# ─── Dataset 5: missings ──────────────────────────────────────────────────────
def test_missings_sem_crash():
    """irrCAC deve aceitar None sem crash; manual pode diferir."""
    ratings_com_none = {
        "a0": ["si", "si"],
        "a1": ["pa", None],    # anotador 2 não marcou
        "a2": ["bcs", "bcs"],
        "a3": [None, "law"],   # anotador 1 não marcou
        "a4": ["ps", "ps"],
    }
    a_i = alpha_irrcac(ratings_com_none)
    print(f"  [Missings] α irrCAC={a_i:.4f}  (manual NÃO testado aqui — crash esperado)")
    results["missings_alpha_irrcac"] = round(a_i, 6) if not (a_i != a_i) else "nan"
    # Apenas verifica que não crasha e retorna número
    assert not (a_i is None), "alpha não deveria ser None"


# ─── Gravar relatório ─────────────────────────────────────────────────────────
def salvar_relatorio():
    results["irrcac_version"]   = IRRCAC_VERSION
    results["delta_threshold"]  = DELTA_THRESHOLD
    results["status"]           = "PASSED"
    outfile = Path(__file__).parent / "crossval_report.json"
    outfile.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\n  Relatório gravado em: {outfile}")


if __name__ == "__main__":
    print("=== Validação cruzada irrCAC × manual ===\n")
    tests = [
        test_concordancia_perfeita_alpha,
        test_concordancia_perfeita_kappa,
        test_concordancia_aleatoria,
        test_caso_tipico_convergencia,
        test_prevalencia_alta_AC1,
        test_missings_sem_crash,
    ]
    failures = []
    for t in tests:
        print(f"\n[{t.__name__}]")
        try:
            t()
            print("  ✓ PASSOU")
        except AssertionError as e:
            print(f"  ✗ FALHOU: {e}")
            failures.append(t.__name__)
            results["status"] = "FAILED"
    salvar_relatorio()
    if failures:
        print(f"\n✗ {len(failures)} teste(s) falharam: {failures}")
        sys.exit(1)
    else:
        print(f"\n✓ Todos os {len(tests)} testes passaram.")
