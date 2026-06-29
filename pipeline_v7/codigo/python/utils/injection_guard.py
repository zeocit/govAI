"""
utils/injection_guard.py — Detector de prompt injection em texto de entrada
============================================================================
Round 3, frente D (decisão: sinalizar + revisar antes de classificar).

Título e abstract são texto não-confiável inserido no prompt do LLM (04a/04b).
A delimitação <<<ARTICLE_BEGIN/END>>> + instrução de fronteira no system prompt
é a primeira linha de defesa. Este módulo é a segunda: detecta heurísticamente
abstracts com padrões típicos de injeção e os SEGREGA para revisão humana, em
vez de classificá-los automaticamente.

Não usa LLM — é regex/heurística, barato o suficiente para varrer o corpus
inteiro antes da primeira chamada paga. O objetivo é triagem, não bloqueio
perfeito: falsos positivos são aceitáveis (vão para revisão); o custo de um
falso negativo é apenas voltar ao nível de defesa da delimitação.
"""
from __future__ import annotations

import re

# Padrões de injeção conhecidos (PT + EN). Conservador: prioriza recall.
# Cada padrão é uma frase/estrutura atípica de um abstract acadêmico genuíno.
_PADROES = [
    r"ignore\s+(?:all\s+)?(?:previous|prior|above|the)\s+instructions?",
    r"ignore\s+(?:as\s+)?instru[çc][õo]es\s+(?:anteriores|acima|pr[ée]vias)",
    r"disregard\s+(?:all\s+)?(?:previous|prior|the)\s+",
    r"desconsidere\s+(?:as\s+)?instru[çc][õo]es",
    r"(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be)\b",
    r"(?:system|assistant|user)\s*:\s*",          # tentativa de forjar turno
    r"</?(?:system|instructions?|prompt)>",        # tags de papel
    r"set\s+(?:cluster_\w+|epi_\w+|\w+)\s+to\s+\d",  # forçar saída
    r"classify\s+(?:this\s+)?as\s+\w+",
    r"classifique\s+(?:isto\s+)?como\s+\w+",
    r"output\s+(?:only|exactly|the\s+following)",
    r"responda\s+(?:apenas|exatamente|somente)\s+com",
    r"<<<\s*article_(?:begin|end)\s*>>>",          # tentativa de forjar marcador
    r"new\s+instructions?\s*:",
    r"novas?\s+instru[çc][õo]es\s*:",
]

_REGEX = re.compile("|".join(_PADROES), re.IGNORECASE)


def detectar_injecao(titulo: str, abstract: str) -> tuple[bool, str]:
    """Retorna (suspeito, motivo). motivo = padrões casados, separados por '; '.

    suspeito=True → o item deve ser SEGREGADO para revisão humana, não
    classificado automaticamente.
    """
    texto = f"{titulo or ''}\n{abstract or ''}"
    achados = sorted({m.group(0).strip().lower() for m in _REGEX.finditer(texto)})
    if achados:
        return True, "; ".join(achados[:5])  # limita o motivo a 5 trechos
    return False, ""
