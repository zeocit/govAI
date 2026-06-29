"""PRÉ-CLASSIFICAÇÃO EXPLORATÓRIA por LLM (triagem provisória — NÃO é padrão-ouro).
Tipologia ternária multi-rótulo: epi_positivista, epi_interpretativa,
epi_doutrinario_normativa como flags positivos independentes.
Qualquer combinação é válida; três zeros → inconclusiva.
Saída: score_positivista, score_interpretativa, score_doutrinario_normativa,
       orientacao_proeminente_llm, inconclusiva, nota_epistemologica, entropia_llm_epi.
Dois eixos ortogonais (DA-09):
  Eixo 1 — orientacao_proeminente_llm: derivado de EE e IC apenas (DN nunca entra).
  Eixo 2 — score_doutrinario_normativa: flag independente, lido diretamente.
NÃO substitui anotação humana nem fornece alpha_DN (requer ≥2 humanos independentes).
Requer ANTHROPIC_API_KEY no ambiente. Uso: python llm_prepass.py abstracts.csv
Schema: Codebook v4.0 DA-08/DA-09 / pilot/config.py
"""
import sys, os, json, math, pandas as pd, urllib.request

# Importação robusta de derive_orientacao: mesma pasta, ./utils ou ../utils.
# Falha alto se o módulo não for encontrado em nenhum dos layouts.
_AQUI = os.path.dirname(os.path.abspath(__file__))
for _cand in (
    _AQUI,
    os.path.normpath(os.path.join(_AQUI, "utils")),
    os.path.normpath(os.path.join(_AQUI, os.pardir, "utils")),
):
    if os.path.isfile(os.path.join(_cand, "derive_orientacao.py")) and _cand not in sys.path:
        sys.path.insert(0, _cand)
        break
try:
    from derive_orientacao import derive   # fonte única da derivação (DA-09)
except ModuleNotFoundError:
    sys.exit(
        "derive_orientacao.py não encontrado. Coloque-o na mesma pasta deste script, "
        "em utils/ ou em ../utils/."
    )

POSTURA_VALORES = ("positivista", "interpretativa", "doutrinario_normativa")

CRITERIO = (
    "Você é um classificador de posturas epistemológicas de artigos acadêmicos sobre "
    "Governança Digital. Recebe título e abstract. Avalie TRÊS posturas, cada uma como "
    "marcador binário independente. Um artigo pode ter mais de uma. Não derive nenhuma "
    "por exclusão.\n\n"
    "positivista — empírico-explicativa: há evidência empírica sistematizada e afirmação "
    "causal/explicativa (hipóteses, amostra, estatística, generalização).\n"
    "interpretativa — interpretativo-compreensiva: há evidência com pretensão hermenêutica "
    "genuína (caso profundo, etnografia, sensemaking, processo situado).\n"
    "doutrinario_normativa — doutrinário-normativa: há argumentação doutrinária, normativa "
    "ou principiológica própria (doutrina jurídica, ética principialista, filosofia da "
    "informação; tom prescritivo 'deve-se/ought to'). Pode coexistir com as demais.\n\n"
    "Regras:\n"
    "- Classifique pelo tipo de afirmação e método, nunca pelo tópico.\n"
    "- Qualidade fraca não muda a postura; empírico raso continua positivista.\n"
    "- Se nenhuma das três se aplicar, retorne os três scores em 0 e explique em "
    "nota_epistemologica (NÃO marque doutrinario_normativa por exclusão).\n"
    "- Responda SOMENTE com JSON, sem texto antes ou depois, sem markdown.\n\n"
    "Formato de saída:\n"
    "{\"score_positivista\":<float 0..1>,\"score_interpretativa\":<float 0..1>,"
    "\"score_doutrinario_normativa\":<float 0..1>,"
    "\"nota_epistemologica\":\"<1-2 frases>\"}\n\n"
    "score_x = confiança de que a postura x está presente (limiar de decisão = 0,5). "
    "Não derive nem retorne um rótulo de orientação proeminente: ele é computado localmente "
    "a partir dos scores de EE e IC (DA-09)."
)


def _hbern(p):
    p = min(max(p, 1e-9), 1 - 1e-9)
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def parse_response(raw):
    txt = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    obj = json.loads(txt[txt.find("{"):txt.rfind("}")+1])
    score_keys = ("score_positivista", "score_interpretativa", "score_doutrinario_normativa")
    scores = {k: float(obj.get(k, 0.0)) for k in score_keys}
    entropia = sum(_hbern(v) for v in scores.values()) / 3.0
    # Derivação dois eixos via DA-09: orientacao_proeminente_llm só de EE+IC (Eixo 1).
    # DN nunca entra no Eixo 1. inconclusiva = 1 sse os três flags são 0.
    ee = int(scores["score_positivista"] >= 0.5)
    ic = int(scores["score_interpretativa"] >= 0.5)
    dn = int(scores["score_doutrinario_normativa"] >= 0.5)
    deriv = derive(ee, ic, dn)
    return {
        **scores,
        "orientacao_proeminente_llm": deriv["orientacao_proeminente"],
        "inconclusiva": deriv["inconclusiva"],
        "nota_epistemologica": str(obj.get("nota_epistemologica", ""))[:500],
        "entropia_llm_epi": round(entropia, 4),
    }


def classify(abstract, key):
    body = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": CRITERIO + "\n\nABSTRACT:\n" + abstract}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"},
    )
    txt = "".join(
        b.get("text", "") for b in
        json.load(urllib.request.urlopen(req)).get("content", [])
        if b.get("type") == "text"
    )
    return parse_response(txt)


def main(path):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("defina ANTHROPIC_API_KEY")
    df = pd.read_csv(path).dropna(subset=["abstract"])
    rows = []
    for _, r in df.iterrows():
        try:
            c = classify(r.abstract, key)
        except Exception as e:
            c = {
                "score_positivista": None, "score_interpretativa": None,
                "score_doutrinario_normativa": None,
                "orientacao_proeminente_llm": None,
                "inconclusiva": None,
                "nota_epistemologica": str(e),
                "entropia_llm_epi": None,
            }
        rows.append({"doc_id": r.doc_id, "annotator": "llm_prepass", **c})
    out = pd.DataFrame(rows)
    out.to_csv("annotations_llm_prepass.csv", index=False)
    n = len(out)
    dn  = (out.score_doutrinario_normativa.fillna(0) >= 0.5).sum()
    mix = (out.orientacao_proeminente_llm == "mixed").sum()
    inc = out.inconclusiva.fillna(0).astype(int).sum()
    az  = (
        (out.score_positivista.fillna(0) < 0.5) &
        (out.score_interpretativa.fillna(0) < 0.5) &
        (out.score_doutrinario_normativa.fillna(0) < 0.5)
    ).sum()
    print(
        f"[EXPLORATÓRIO — não é padrão-ouro] n={n} | "
        f"DN (Eixo 2, score>=0.5)={dn} ({dn/n:.0%}) | "
        f"orientacao mixed (Eixo 1)={mix} ({mix/n:.0%}) | "
        f"inconclusiva={inc} ({inc/n:.0%}) | all-zero={az} ({az/n:.0%})"
    )
    print("Use para triagem/escopo; alpha_DN humano (irrCAC/R) continua necessário.")


if __name__ == "__main__":
    main(sys.argv[1])
