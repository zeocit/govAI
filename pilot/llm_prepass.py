"""PRÉ-CLASSIFICAÇÃO EXPLORATÓRIA por LLM (triagem provisória — NÃO é padrão-ouro).
Tipologia ternária multi-rótulo: epi_positivista, epi_interpretativa,
epi_doutrinario_normativa como flags positivos independentes.
Qualquer combinação é válida; três zeros não derivam nenhuma postura.
Saída: score_positivista, score_interpretativa, score_doutrinario_normativa,
       postura_dominante_llm, nota_epistemologica, entropia_llm_epi.
NÃO substitui anotação humana nem fornece alpha_DN (requer ≥2 humanos independentes).
Requer ANTHROPIC_API_KEY no ambiente. Uso: python llm_prepass.py abstracts.csv
Schema: Codebook DA-08 / pilot/config.py
"""
import sys, os, json, math, pandas as pd, urllib.request

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
    "\"postura_dominante_llm\":\"positivista|interpretativa|doutrinario_normativa|mixed\","
    "\"nota_epistemologica\":\"<1-2 frases>\"}\n\n"
    "score_x = confiança de que a postura x está presente. "
    "postura_dominante_llm = maior score; 'mixed' se duas ou mais >= 0.5; "
    "empate exato resolve a favor de positivista."
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
    dom = obj.get("postura_dominante_llm", "")
    if dom not in (*POSTURA_VALORES, "mixed"):
        pos = [k for k, v in scores.items() if v >= 0.5]
        if len(pos) >= 2:
            dom = "mixed"
        elif pos:
            dom = pos[0].replace("score_", "")
        else:
            dom = max(scores, key=scores.get).replace("score_", "")
    return {
        **scores,
        "postura_dominante_llm": dom,
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
                "postura_dominante_llm": None,
                "nota_epistemologica": str(e),
                "entropia_llm_epi": None,
            }
        rows.append({"doc_id": r.doc_id, "annotator": "llm_prepass", **c})
    out = pd.DataFrame(rows)
    out.to_csv("annotations_llm_prepass.csv", index=False)
    n = len(out)
    dn  = (out.postura_dominante_llm == "doutrinario_normativa").sum()
    mix = (out.postura_dominante_llm == "mixed").sum()
    az  = (
        (out.score_positivista.fillna(0) < 0.5) &
        (out.score_interpretativa.fillna(0) < 0.5) &
        (out.score_doutrinario_normativa.fillna(0) < 0.5)
    ).sum()
    print(
        f"[EXPLORATÓRIO — não é padrão-ouro] n={n} | "
        f"doutrinario_normativa dominante={dn} ({dn/n:.0%}) | "
        f"mixed={mix} ({mix/n:.0%}) | all-zero={az} ({az/n:.0%})"
    )
    print("Use para triagem/escopo; alpha_DN humano (irrCAC/R) continua necessário.")


if __name__ == "__main__":
    main(sys.argv[1])
