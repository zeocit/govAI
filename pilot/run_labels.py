"""Calibração de concordância inter-anotador — tipologia epistemológica ternária.
Calcula Krippendorff α por postura (epi_positivista, epi_interpretativa,
epi_doutrinario_normativa) e aplica os limiares pré-registrados em config.py.
Saída: α por postura, distribuição de padrões de consenso, alertas e veredicto do gate.
Uso: python run_labels.py annotations.csv
Requisitos: pandas, krippendorff  (pip install krippendorff)
"""
import sys, math, collections, pandas as pd
import config as C

EPI_COLS = ["epi_positivista", "epi_interpretativa", "epi_doutrinario_normativa"]


def kripp_alpha(matrix, level="interval"):
    """matrix: lista de listas (unidades × anotadores), None para faltante."""
    try:
        import krippendorff, numpy as np
        n_raters = max(len(r) for r in matrix)
        data = [[float("nan")] * len(matrix) for _ in range(n_raters)]
        for u, row in enumerate(matrix):
            for r, v in enumerate(row):
                if v is not None:
                    data[r][u] = float(v)
        return krippendorff.alpha(reliability_data=data, level_of_measurement=level)
    except Exception:
        return float("nan")


def build_matrix(pivot, units, raters, col):
    return [
        [
            pivot[(pivot.doc_id == u) & (pivot.annotator == r)][col].iloc[0]
            if not pivot[(pivot.doc_id == u) & (pivot.annotator == r)].empty
            else None
            for r in raters
        ]
        for u in units
    ]


def main(path):
    df = pd.read_csv(path)

    for col in EPI_COLS:
        if col not in df.columns:
            sys.exit(f"[erro] coluna ausente: {col}. Verifique ANN_COLS em config.py.")

    raters = sorted(r for r in df.annotator.unique() if r != "gold")
    if len(raters) < 2:
        sys.exit("[erro] calibração requer ≥ 2 anotadores humanos. Arquivo insuficiente.")

    pivot = df[df.annotator != "gold"]
    units = sorted(pivot.doc_id.unique())
    n = len(units)

    print(
        f"== Calibração inter-anotador  "
        f"(n={n} artigos, {len(raters)} anotadores: {', '.join(raters)}) ==\n"
    )

    # --- Krippendorff α por postura ---
    print("-- Krippendorff α por postura (intervalar) --")
    alphas = {}
    for col in EPI_COLS:
        mat = build_matrix(pivot, units, raters, col)
        a = kripp_alpha(mat, level="interval")
        alphas[col] = a
        suffix = ""
        if col == "epi_doutrinario_normativa":
            if math.isnan(a):
                suffix = "  ← [INCONCLUSIVO]"
            elif a < C.CALIB_ALPHA_DN_FLOOR:
                suffix = (
                    f"  ← [ABAIXO DO PISO {C.CALIB_ALPHA_DN_FLOOR:.2f}] "
                    f"— revisar Guia v3 §3.3"
                )
            else:
                suffix = f"  ← [OK ≥ {C.CALIB_ALPHA_DN_FLOOR:.2f}]"
        print(f"  {col:<34}: α = {a:.3f}{suffix}")

    # --- Distribuição de padrões de consenso ---
    ref = df[df.annotator == "gold"]
    ref_label = "gold"
    if ref.empty:
        ref = df[df.annotator == raters[0]]
        ref_label = f"{raters[0]} (provisório — sem gold)"
        print(f"\n[aviso] sem linhas 'gold'; usando '{raters[0]}' para padrões.")

    n_ref = len(ref)
    print(f"\n-- Distribuição de padrões ({ref_label}, n={n_ref}) --")
    pattern_counts = collections.Counter(
        tuple(int(row[c]) for c in EPI_COLS)
        for _, row in ref.iterrows()
    )
    all_zero_count = pattern_counts.get((0, 0, 0), 0)
    for pat, cnt in sorted(pattern_counts.items(), key=lambda x: -x[1]):
        label = " + ".join(
            short for short, v in zip(["pos", "int", "dn"], pat) if v
        ) or "all-zero"
        bar = "█" * round(cnt / n_ref * 20)
        print(f"  {pat}  {label:<18}  {cnt:>4}  {cnt/n_ref:>5.1%}  {bar}")

    # --- Alertas ---
    az_rate = all_zero_count / n_ref if n_ref > 0 else 0.0
    print("\n-- Alertas --")
    if az_rate > C.ALL_ZERO_RECONSIDER_RATE:
        print(
            f"  [ALERTA] all-zero = {az_rate:.1%} > {C.ALL_ZERO_RECONSIDER_RATE:.0%} "
            f"— reconsiderar esquema de categorias antes de prosseguir."
        )
    else:
        print(f"  all-zero = {az_rate:.1%}  [OK ≤ {C.ALL_ZERO_RECONSIDER_RATE:.0%}]")

    # --- Veredicto do gate ---
    a_dn = alphas["epi_doutrinario_normativa"]
    print("\n-- Veredicto do gate de calibração --")
    if math.isnan(a_dn):
        print("  INCONCLUSIVO — α_doutrinario_normativa indefinido. Verificar dados.")
    elif a_dn >= C.CALIB_ALPHA_DN_FLOOR:
        print(
            f"  APROVADO — α_doutrinario_normativa = {a_dn:.3f} ≥ {C.CALIB_ALPHA_DN_FLOOR:.2f}"
        )
        print(
            f"  → Prosseguir para Gold Standard "
            f"(gate GS: α_epi ≥ {C.GS_ALPHA_GATE_EPI:.2f}, α_cluster ≥ {C.GS_ALPHA_GATE_CLUSTER:.2f})."
        )
    else:
        print(
            f"  REPROVADO — α_doutrinario_normativa = {a_dn:.3f} < {C.CALIB_ALPHA_DN_FLOOR:.2f}"
        )
        print("  → Revisar Guia de Anotação v3 §3.3 e repetir calibração.")

    print(
        "\n[nota] Resultados exigem anotações humanas reais. "
        "Fabricar rótulos invalida o gate e compromete o pré-registro OSF."
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: python run_labels.py annotations.csv")
        sys.exit(1)
    main(sys.argv[1])
