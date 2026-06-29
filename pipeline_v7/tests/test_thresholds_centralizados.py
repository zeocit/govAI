"""
tests/test_thresholds_centralizados.py — Trava a centralização dos limiares
============================================================================
Round 3 / decisão metodológica: os limiares de concordância passaram a viver
em utils/thresholds.py (single source of truth). Este teste impede que números
soltos (0.67, 0.55, 0.50, 0.60) reapareçam em 05 e que o gate deixe de ser o
Krippendorff alpha canônico.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent / "codigo" / "python"


def test_valores_canonicos():
    import sys
    sys.path.insert(0, str(ROOT))
    from utils.thresholds import ALPHA_GATE, KAPPA_REF, faixa_krippendorff
    assert ALPHA_GATE == 0.667, "ALPHA_GATE deve ser 0.667 (piso de Krippendorff)"
    assert KAPPA_REF == 0.61, "KAPPA_REF deve ser 0.61 (Landis & Koch substantial)"
    # Faixas de Krippendorff
    assert faixa_krippendorff(0.85) == "confiavel"
    assert faixa_krippendorff(0.70) == "tentativo"
    assert faixa_krippendorff(0.50) == "insuficiente"
    assert faixa_krippendorff(0.667) == "tentativo"   # limiar inclusivo
    assert faixa_krippendorff(0.666) == "insuficiente"


def test_05_usa_thresholds_centralizados():
    src = (ROOT / "05_processar_anotacoes.py").read_text(encoding="utf-8")
    assert "from utils.thresholds import" in src or "thresholds import" in src, \
        "05 não importa utils.thresholds"
    assert "ALPHA_GATE" in src and "KAPPA_REF" in src, \
        "05 não usa as constantes centralizadas"


def test_05_sem_limiares_soltos():
    """Nenhum literal de limiar antigo em código executável de 05."""
    src = (ROOT / "05_processar_anotacoes.py").read_text(encoding="utf-8")
    # Remover comentários e docstrings triviais antes de procurar literais soltos
    linhas_codigo = []
    for ln in src.splitlines():
        s = ln.split("#", 1)[0]  # descarta comentário inline
        linhas_codigo.append(s)
    codigo = "\n".join(linhas_codigo)
    # Os antigos gates soltos não podem mais aparecer como comparações numéricas
    for proibido in [">= 0.67", ">= 0.55", ">= 0.60", ">= 0.50",
                     ">=0.67", ">=0.55", ">=0.60", ">=0.50"]:
        assert proibido not in codigo, \
            f"Limiar solto '{proibido}' reapareceu em 05 — use utils.thresholds"


def test_gate_e_somente_alpha():
    """O gate de aceitação não pode voltar a depender de kappa.

    Verifica as CHAVES do bloco status_gate (não o texto bruto, que contém
    comentários mencionando 'kappa' legitimamente). Toda chave de gate deve
    referir-se a alpha.
    """
    src = (ROOT / "05_processar_anotacoes.py").read_text(encoding="utf-8")
    # Capturar o bloco status_gate equilibrando chaves (regex simples não basta)
    inicio = src.find('"status_gate"')
    assert inicio != -1, "bloco status_gate não encontrado em 05"
    abre = src.find("{", inicio)
    profundidade, i = 0, abre
    while i < len(src):
        if src[i] == "{":
            profundidade += 1
        elif src[i] == "}":
            profundidade -= 1
            if profundidade == 0:
                break
        i += 1
    bloco = src[abre + 1:i]
    # Extrair as chaves "..." : do bloco (linhas de código, sem comentários)
    chaves = []
    for ln in bloco.splitlines():
        codigo = ln.split("#", 1)[0]
        m = re.search(r'"([a-z_]+)"\s*:', codigo)
        if m:
            chaves.append(m.group(1))
    assert chaves, "nenhuma chave extraída de status_gate"
    for k in chaves:
        assert "alpha" in k or k == "gate_global_ok", \
            f"chave de gate '{k}' não é baseada em alpha — kappa não pode ser gate"


if __name__ == "__main__":
    tests = [test_valores_canonicos, test_05_usa_thresholds_centralizados,
             test_05_sem_limiares_soltos, test_gate_e_somente_alpha]
    falhas = []
    for t in tests:
        try:
            t(); print(f"  ✓ {t.__name__}")
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}"); falhas.append(t.__name__)
    if falhas:
        raise SystemExit(f"\n✗ {len(falhas)} falha(s): {falhas}")
    print(f"\n✓ Centralização de limiares íntegra ({len(tests)} testes).")
