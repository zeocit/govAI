"""
utils/thresholds.py | Fonte unica dos limiares de concordancia do projeto
=========================================================================
Centraliza os limiares de confiabilidade entre anotadores (Krippendorff alpha)
e parametros de treino sensiveis a desbalanceamento. Importado por 05
(consolidacao do Gold Standard), 06b (treino epi) e pelo notebook de calibracao.

Gates de ACEITACAO do Gold Standard (OSF Pre-registro v2.0, secao 6):
    ALPHA_GATE_CLUSTER = 0.67   camada disciplinar (mono-rotulo)
    ALPHA_GATE_EPI     = 0.55   cada flag da camada epistemologica

Piso de VIABILIDADE da fase de calibracao (anterior ao Gold Standard):
    ALPHA_CALIB_DN_FLOOR = 0.667

    NOTA (mudanca registrada como desvio no Addendum 2): este piso foi elevado
    de 0.40 para 0.667 (limiar de Krippendorff para conclusoes tentativas).
    Consequencia: o piso de calibracao de DN (0.667) agora EXCEDE o gate de
    aceitacao epi do Gold Standard (0.55). A pre-checagem de calibracao de DN
    passa a ser mais estrita que a aceitacao final. Isto e deliberado
    (calibracao como filtro de qualidade do instrumento antes de escalar), mas
    inverte a relacao usual piso <= gate. O nome 'FLOOR' e mantido por
    compatibilidade de import; apos a mudanca, conceitualmente e um piso acima
    do gate. Ver Addendum 2 (secao de desvios) e exige assinatura da supervisora.

Referencia diagnostica (NAO e gate):
    KAPPA_REF = 0.61   limite inferior da faixa 'substancial' de Landis & Koch,
                       usado so para leitura do kappa de Fleiss (diagnostico).

Treino (06b):
    POS_WEIGHT_CAP = 10.0   teto do pos_weight (n_neg/n_pos) por flag na
                            BCEWithLogitsLoss; PROVISORIO, confirmar apos a
                            calibracao com a prevalencia empirica de DN.

Estes sao limiares de CONCORDANCIA (Krippendorff alpha). Limiares de DECISAO
(binarizacao score->flag em 0.5; banda de fronteira 0.15; confianca de cluster
0.55 em 04c) sao semanticamente distintos e vivem nos seus proprios scripts.
"""
from __future__ import annotations

# Gates de aceitacao do Gold Standard (OSF v2.0 secao 6) ----------------------
ALPHA_GATE_CLUSTER: float = 0.67
ALPHA_GATE_EPI:     float = 0.55

# Piso de viabilidade da calibracao para DN (Addendum 2: 0.40 -> 0.667) -------
ALPHA_CALIB_DN_FLOOR: float = 0.667

# Diagnostico (nao e gate) ----------------------------------------------------
KAPPA_REF: float = 0.61

# Treino epi (06b) ------------------------------------------------------------
POS_WEIGHT_CAP: float = 10.0

# Benchmarks de Krippendorff (2004): 0.667 tentativo, 0.80 firme.
_ALPHA_TENTATIVO: float = 0.667
_ALPHA_FIRME:     float = 0.80


def faixa_krippendorff(alpha: float) -> str:
    """Classifica um alpha de Krippendorff na faixa interpretativa padrao.

    < 0.667        -> 'insuficiente'
    [0.667, 0.80)  -> 'tentativo'
    >= 0.80        -> 'firme'
    NaN/None       -> 'indefinido'
    """
    if alpha is None or alpha != alpha:  # NaN
        return "indefinido"
    if alpha >= _ALPHA_FIRME:
        return "firme"
    if alpha >= _ALPHA_TENTATIVO:
        return "tentativo"
    return "insuficiente"


if __name__ == "__main__":
    print("Limiares de concordancia (fonte unica):")
    print(f"  ALPHA_GATE_CLUSTER    = {ALPHA_GATE_CLUSTER}")
    print(f"  ALPHA_GATE_EPI        = {ALPHA_GATE_EPI}")
    print(f"  ALPHA_CALIB_DN_FLOOR  = {ALPHA_CALIB_DN_FLOOR}  (era 0.40; Addendum 2)")
    print(f"  KAPPA_REF             = {KAPPA_REF}  (diagnostico)")
    print(f"  POS_WEIGHT_CAP        = {POS_WEIGHT_CAP}  (provisorio)")
    assert ALPHA_CALIB_DN_FLOOR > ALPHA_GATE_EPI, "inversao esperada apos a mudanca"
    for a in (0.30, 0.55, 0.667, 0.72, 0.85, float("nan")):
        print(f"  faixa({a}) = {faixa_krippendorff(a)}")
