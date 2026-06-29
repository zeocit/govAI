"""
metrics_manual.py — Implementação manual de referência (LEGADO)
================================================================
Mantida como bateria de testes de regressão contra utils/metrics.py
(que usa irrCAC como fonte canônica per DA-06 do Codebook v2.2).

NÃO usar em produção. Usar apenas em tests/test_metrics_crossvalidation.py.

Origem: 05_processar_anotacoes.py pipeline_v3 (linhas 184-271).
Auditoria QA identificou variável `n_e` morta e uso de max() para
n_anotadores em vez de constante. Não corrompem resultados típicos.

Autor original: Fernando Leite | FAPESP
"""
from __future__ import annotations

from collections import Counter


def fleiss_kappa(ratings_matrix: list[list[int]], n_categories: int) -> float:
    """
    Kappa de Fleiss para N anotadores e K categorias.
    ratings_matrix: lista de listas, shape (n_artigos, n_anotadores).
    Retorna Kappa [-1, 1].
    """
    n_artigos = len(ratings_matrix)
    if n_artigos == 0:
        return float("nan")

    # Contar votos por categoria
    n_anotadores = max(len(r) for r in ratings_matrix)
    if n_anotadores < 2:
        return float("nan")

    p_j = [0.0] * n_categories
    P_i_list = []
    N = n_artigos * n_anotadores

    for row in ratings_matrix:
        n_j = [0] * n_categories
        for v in row:
            if 0 <= v < n_categories:
                n_j[v] += 1
        n_i = sum(n_j)
        if n_i < 2:
            P_i_list.append(0.0)
        else:
            P_i = sum(n * (n - 1) for n in n_j) / (n_i * (n_i - 1))
            P_i_list.append(P_i)
        for j in range(n_categories):
            p_j[j] += n_j[j] / N

    P_bar = sum(P_i_list) / n_artigos
    P_e   = sum(p * p for p in p_j)
    if abs(1 - P_e) < 1e-10:
        return float("nan")
    return (P_bar - P_e) / (1 - P_e)


def krippendorff_alpha_nominal(ratings_dict: dict[str, list]) -> float:
    """
    Krippendorff α para escala nominal.
    ratings_dict: {item_id: [val_anotador_1, val_anotador_2, ...]}
    Retorna α [-inf, 1].
    """
    items = list(ratings_dict.items())
    # Contagem geral de valores
    all_vals = [v for _, vals in items for v in vals if v is not None]
    if not all_vals:
        return float("nan")
    n_unicos = len(set(all_vals))
    if n_unicos < 2:
        return 1.0

    # D_o (diferença observada) e D_e (esperada)
    D_o = 0.0
    n_o = 0
    D_e = 0.0
    n_e = 0

    val_counts: Counter = Counter(all_vals)
    n_total = len(all_vals)

    for _, vals in items:
        valid = [v for v in vals if v is not None]
        m = len(valid)
        if m < 2:
            continue
        for i in range(len(valid)):
            for j in range(i + 1, len(valid)):
                d = 0 if valid[i] == valid[j] else 1
                D_o += d
                n_o += 1

    for val_a, count_a in val_counts.items():
        for val_b, count_b in val_counts.items():
            d = 0 if val_a == val_b else 1
            D_e += d * count_a * count_b
            n_e += 1

    if n_o == 0 or n_e == 0:
        return float("nan")
    D_o_norm = D_o / n_o
    D_e_norm = D_e / (n_total * (n_total - 1))
    if abs(D_e_norm) < 1e-10:
        return float("nan")
    return 1.0 - D_o_norm / D_e_norm
