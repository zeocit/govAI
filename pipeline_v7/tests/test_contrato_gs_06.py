"""
tests/test_contrato_gs_06.py — Teste de contrato entre 05 e 06a/06b
====================================================================
Auditoria Round 2 (cross-script contract): os bugs mais perigosos do
pipeline viviam ENTRE scripts, não dentro deles (ex.: 05 escrevia
`concordancia_cluster`, mas 06 filtrava por `tem_disputa`, inexistente).

Este teste fixa o contrato de colunas do Gold Standard: as colunas que
06a e 06b exigem DEVEM ser exatamente as que 05 escreve. Se alguém alterar
o schema de 05 sem atualizar 06 (ou vice-versa), este teste falha cedo,
antes de um treino de horas produzir rótulos degenerados.

Executar:
    cd pipeline_v4   (ou pipeline_v5)
    python -m pytest tests/test_contrato_gs_06.py -v
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent / "codigo" / "python"

# Colunas que 05 escreve em cada registro do Gold Standard (gs_rows.append({...})).
# Mantido como fonte de verdade do contrato; derivado por leitura do AST de 05.
GS_COLS_ESCRITAS = {
    "id", "cluster_primario", "cluster_secundario", "cluster_status",
    "cluster_confianca", "concordancia_cluster", "epi_positivista",
    "epi_interpretativa", "epi_na", "epi_misto", "epi_status",
    "epi_confianca", "concordancia_epi_pos", "concordancia_epi_int",
    "n_anotadores", "anotadores", "tem_disputa",
}

# Colunas que 06a e 06b exigem explicitamente (cols_obrigatorias / acessos diretos).
COLS_EXIGIDAS_06A = {"id", "cluster_primario", "cluster_status", "concordancia_cluster"}
COLS_EXIGIDAS_06B = {"id", "cluster_status", "concordancia_cluster",
                     "epi_positivista", "epi_interpretativa"}


def _cols_escritas_por_05() -> set[str]:
    """Extrai do AST de 05 as chaves do dict passado a gs_rows.append(...)."""
    src = (ROOT / "05_processar_anotacoes.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    chaves: set[str] = set()
    for node in ast.walk(tree):
        # procurar gs_rows.append({ ... })
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "append"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "gs_rows"
                and node.args
                and isinstance(node.args[0], ast.Dict)):
            for k in node.args[0].keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    chaves.add(k.value)
    return chaves


def test_05_escreve_colunas_declaradas():
    """O dict real de 05 deve conter exatamente o contrato GS_COLS_ESCRITAS."""
    reais = _cols_escritas_por_05()
    assert reais, "Não foi possível extrair as colunas escritas por 05 (mudou o nome de gs_rows?)."
    faltando = GS_COLS_ESCRITAS - reais
    sobrando = reais - GS_COLS_ESCRITAS
    assert not faltando, f"05 deixou de escrever colunas do contrato: {sorted(faltando)}"
    assert not sobrando, (
        f"05 escreve colunas fora do contrato declarado neste teste: {sorted(sobrando)}. "
        f"Atualize GS_COLS_ESCRITAS se a mudança for intencional."
    )


def test_06a_exige_apenas_o_que_05_escreve():
    faltando = COLS_EXIGIDAS_06A - _cols_escritas_por_05()
    assert not faltando, (
        f"06a exige colunas que 05 não escreve: {sorted(faltando)} — contrato quebrado."
    )


def test_06b_exige_apenas_o_que_05_escreve():
    faltando = COLS_EXIGIDAS_06B - _cols_escritas_por_05()
    assert not faltando, (
        f"06b exige colunas que 05 não escreve: {sorted(faltando)} — contrato quebrado."
    )


def test_06_tem_validacao_explicita_de_schema():
    """06a/06b devem validar o schema do GS (raise KeyError), não usar gs.get(escalar)."""
    for nome in ["06a_treinar_clusters.py", "06b_treinar_epi.py"]:
        src = (ROOT / nome).read_text(encoding="utf-8")
        assert "cols_obrigatorias" in src and "raise KeyError" in src, (
            f"{nome} não valida explicitamente as colunas do GS — "
            f"regressão do contrato Round 2."
        )
        # gs.get("cluster_status", "classificado") era o padrão frágil removido
        assert not re.search(r'gs\.get\(\s*"cluster_status"', src), (
            f"{nome} voltou a usar gs.get(\"cluster_status\", escalar) — padrão frágil."
        )


if __name__ == "__main__":
    tests = [
        test_05_escreve_colunas_declaradas,
        test_06a_exige_apenas_o_que_05_escreve,
        test_06b_exige_apenas_o_que_05_escreve,
        test_06_tem_validacao_explicita_de_schema,
    ]
    falhas = []
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}")
            falhas.append(t.__name__)
    if falhas:
        raise SystemExit(f"\n✗ {len(falhas)} falha(s) de contrato: {falhas}")
    print(f"\n✓ Contrato GS↔06 íntegro ({len(tests)} testes).")
