"""
derive_orientacao.py

Fonte unica da derivacao deterministica da orientacao epistemologica a partir
dos tres marcadores canonicos. Substitui as regras divergentes que circulavam
no pipeline (prioridade fixa, DN-domina, argmax sobre escores continuos).

Decisao de design (Codebook v4.0, DA-08/DA-09; Guia de Anotacao V4):
  Dois eixos ortogonais.
    Eixo 1, orientacao epistemologica empirica:
      epi_positivista (EE), epi_interpretativa (IC).
    Eixo 2, registro doutrinario-normativo:
      epi_doutrinario_normativa (DN).
  orientacao_proeminente e o rotulo do eixo 1, funcao APENAS de EE e IC,
    sem regra de prioridade e sem escores continuos. DN nunca entra nela.
    Valores: positivista, interpretativa, mixed, nenhuma.
  A segunda camada ("orientacao doutrinario-normativa") e a propria flag
    epi_doutrinario_normativa, lida da sua coluna.
  inconclusiva = 1 apenas quando os tres marcadores sao 0.

Nao ha thresholds nesta derivacao: ela e puramente logica.
"""

from __future__ import annotations

VALORES_PROEMINENTE = ("positivista", "interpretativa", "mixed", "nenhuma")
_DN_TAGS = ("dn:modo", "dn:norm", "dn:ambos")


def _bin(x) -> int:
    """Coage para 0/1; aceita 0/1, 0.0/1.0, True/False. Erra fora disso."""
    v = int(round(float(x)))
    if v not in (0, 1):
        raise ValueError(f"marcador deve ser 0 ou 1, recebido {x!r}")
    return v


def orientacao_proeminente(epi_positivista, epi_interpretativa) -> str:
    """Rotulo do eixo 1, funcao apenas de EE e IC. DN nao participa."""
    ee, ic = _bin(epi_positivista), _bin(epi_interpretativa)
    if ee and ic:
        return "mixed"
    if ee:
        return "positivista"
    if ic:
        return "interpretativa"
    return "nenhuma"


def configuracao(epi_positivista, epi_interpretativa, epi_doutrinario_normativa) -> str:
    """Configuracao das tres flags, p.ex. 'EE+DN', 'IC', 'all_zero'."""
    ee = _bin(epi_positivista)
    ic = _bin(epi_interpretativa)
    dn = _bin(epi_doutrinario_normativa)
    partes = [nome for nome, v in (("EE", ee), ("IC", ic), ("DN", dn)) if v]
    return "+".join(partes) if partes else "all_zero"


def derive(epi_positivista, epi_interpretativa, epi_doutrinario_normativa) -> dict:
    """
    Deriva, a partir dos tres marcadores canonicos, todas as variaveis
    deterministicas a jusante. Use em qualquer ponto que tenha as tres flags
    (pre-classificacao LLM, gold standard, aplicacao do modelo).
    """
    ee = _bin(epi_positivista)
    ic = _bin(epi_interpretativa)
    dn = _bin(epi_doutrinario_normativa)
    return {
        "orientacao_proeminente": orientacao_proeminente(ee, ic),
        "epi_doutrinario_normativa": dn,          # segunda camada (registro)
        "inconclusiva": int(ee == 0 and ic == 0 and dn == 0),
        "configuracao": configuracao(ee, ic, dn),
    }


def derive_dataframe(df, prefixo: str = ""):
    """
    Aplica derive() a um DataFrame com as colunas canonicas e devolve uma copia
    com as colunas derivadas acrescentadas. Nao reescreve as flags. R consome
    estas colunas; nao deve re-derivar (fonte unica de verdade aqui).
    Colunas esperadas: epi_positivista, epi_interpretativa, epi_doutrinario_normativa.
    """
    import pandas as pd  # import local: o core nao depende de pandas
    cols = ["epi_positivista", "epi_interpretativa", "epi_doutrinario_normativa"]
    faltando = [c for c in cols if c not in df.columns]
    if faltando:
        raise KeyError(f"colunas ausentes: {faltando}")
    derivado = df[cols].apply(
        lambda r: pd.Series(derive(r[cols[0]], r[cols[1]], r[cols[2]])), axis=1
    )
    out = df.copy()
    for c in derivado.columns:
        if c == "epi_doutrinario_normativa":
            continue  # ja existe; nao duplicar
        out[prefixo + c] = derivado[c]
    return out


def validar_linha(epi_positivista, epi_interpretativa, epi_doutrinario_normativa,
                  confianca, notas) -> list:
    """
    Valida uma linha de anotacao humana contra as regras do Guia V4.
    Devolve a lista de violacoes (vazia se a linha e valida).

    confianca e o ordinal humano 1-3 (Codebook v4.0), NAO a entropia/conf_llm
    continua do pre-classificador.
    """
    problemas = []
    try:
        ee = _bin(epi_positivista)
        ic = _bin(epi_interpretativa)
        dn = _bin(epi_doutrinario_normativa)
    except ValueError as e:
        return [str(e)]

    try:
        c = int(round(float(confianca)))
    except (TypeError, ValueError):
        return [f"confianca ausente ou nao numerica: {confianca!r}"]
    if c not in (1, 2, 3):
        problemas.append(f"confianca fora de 1-3: {c}")

    nota = "" if notas is None else str(notas).strip()
    if nota.lower() in ("", "nan", "none"):
        nota = ""

    if c <= 1:
        if not nota:
            problemas.append("confianca <= 1 exige notas nomeando o marcador em duvida")
        elif not any(t in nota.upper() for t in ("EE", "IC", "DN")):
            problemas.append("confianca <= 1: notas deve nomear EE, IC ou DN")

    if dn == 1 and not any(tag in nota.lower() for tag in _DN_TAGS):
        problemas.append("DN = 1 exige etiqueta dn:modo, dn:norm ou dn:ambos em notas")

    if ee == 0 and ic == 0 and dn == 0 and c > 1:
        problemas.append("all-zero (inconclusiva) deve vir com confianca <= 1 e justificativa")

    return problemas


if __name__ == "__main__":
    # Tabela-verdade: confirma a recodificacao (sem prioridade, DN fora do eixo 1).
    casos = [
        (1, 0, 0, "positivista", 0),
        (0, 1, 0, "interpretativa", 0),
        (1, 1, 0, "mixed", 0),
        (0, 0, 1, "nenhuma", 0),
        (1, 0, 1, "positivista", 0),
        (0, 1, 1, "interpretativa", 0),
        (1, 1, 1, "mixed", 0),
        (0, 0, 0, "nenhuma", 1),
    ]
    falhas = 0
    for ee, ic, dn, esp_prom, esp_inc in casos:
        d = derive(ee, ic, dn)
        ok = d["orientacao_proeminente"] == esp_prom and d["inconclusiva"] == esp_inc
        falhas += 0 if ok else 1
        print(f"{'OK  ' if ok else 'FALHA'} ({ee},{ic},{dn}) -> "
              f"proeminente={d['orientacao_proeminente']:<14} "
              f"dn={d['epi_doutrinario_normativa']} "
              f"inconclusiva={d['inconclusiva']} config={d['configuracao']}")
    print(f"\n{len(casos) - falhas}/{len(casos)} casos corretos")
