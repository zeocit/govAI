"""PRÉ-CLASSIFICAÇÃO EXPLORATÓRIA por LLM (triagem provisória — NÃO é padrão-ouro).
Tipologia ternária multi-rótulo: epi_ee, epi_ic, epi_dn como flags positivos independentes.
Qualquer combinação é válida; três zeros não derivam DN. Saída: score_ee, score_ic,
score_dn, postura_dominante_llm, nota_epistemologica, entropia_llm_epi.
NÃO substitui anotação humana nem fornece alpha_DN (requer >=2 humanos independentes).
Requer ANTHROPIC_API_KEY no ambiente. Uso: python llm_prepass.py abstracts.csv
Schema: Codebook DA-08 / 04b_prompt_update.md
"""
import sys, os, json, math, pandas as pd, urllib.request

CRITERIO = (
    "Você é um classificador de posturas epistemológicas de artigos acadêmicos sobre "
    "Governança Digital. Recebe título e abstract. Avalie TRÊS posturas, cada uma como "
    "marcador binário independente. Um artigo pode ter mais de uma. Não derive nenhuma "
    "por exclusão.\n\n"
    "EE — empírico-explicativa: há evidência empírica sistematizada e afirmação causal/"
    "explicativa (hipóteses, amostra, estatística, generalização).\n"
    "IC — interpretativo-compreensiva: há evidência com pretensão hermenêutica genuína "
    "(caso profundo, etnografia, sensemaking, processo situado).\n"
    "DN — doutrinário-normativa: há argumentação doutrinária, normativa ou principiológica "
    "própria (doutrina jurídica, ética principialista, filosofia da informação; tom "
    "prescritivo 'deve-se/ought to'). DN pode coexistir com EE ou IC.\n\n"
    "Regras:\n"
    "- Classifique pelo tipo de afirmação e método, nunca pelo tópico.\n"
    "- Qualidade fraca não muda a postura; empírico raso continua EE.\n"
    "- Se nenhuma das três se aplicar, retorne os três em 0 e explique em "
    "nota_epistemologica (NÃO marque DN por exclusão).\n"
    "- Responda SOMENTE com JSON, sem texto antes ou depois, sem markdown.\n\n"
    "Formato de saída:\n"
    "{\"score_ee\":<float 0..1>,\"score_ic\":<float 0..1>,\"score_dn\":<float 0..1>,"
    "\"postura_dominante_llm\":\"EE|IC|DN|mixed\","
    "\"nota_epistemologica\":\"<1-2 frases>\"}\n\n"
    "score_x = confiança de que a postura x está presente. postura_dominante_llm = maior "
    "score; 'mixed' se duas ou mais >= 0.5; empate exato resolve a favor de EE."
)

def _hbern(p):
    p = min(max(p, 1e-9), 1 - 1e-9)
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))

def parse_response(raw):
    txt = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    obj = json.loads(txt[txt.find("{"):txt.rfind("}")+1])
    scores = {k: float(obj.get(k, 0.0)) for k in ("score_ee", "score_ic", "score_dn")}
    entropia = sum(_hbern(v) for v in scores.values()) / 3.0
    dom = obj.get("postura_dominante_llm", "")
    if dom not in ("EE", "IC", "DN", "mixed"):
        pos = [k for k, v in scores.items() if v >= 0.5]
        if len(pos) >= 2:   dom = "mixed"
        elif pos:           dom = pos[0].split("_")[1].upper()
        else:               dom = max(scores, key=scores.get).split("_")[1].upper()
    return {**scores,
            "postura_dominante_llm": dom,
            "nota_epistemologica": str(obj.get("nota_epistemologica", ""))[:500],
            "entropia_llm_epi": round(entropia, 4)}

def classify(abstract, key):
    body = json.dumps({"model": "claude-sonnet-4-20250514", "max_tokens": 300,
        "messages": [{"role": "user", "content": CRITERIO + "\n\nABSTRACT:\n" + abstract}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    txt = "".join(b.get("text", "") for b in
                  json.load(urllib.request.urlopen(req)).get("content", [])
                  if b.get("type") == "text")
    return parse_response(txt)

def main(path):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key: sys.exit("defina ANTHROPIC_API_KEY")
    df = pd.read_csv(path).dropna(subset=["abstract"])
    rows = []
    for _, r in df.iterrows():
        try:
            c = classify(r.abstract, key)
        except Exception as e:
            c = {"score_ee": None, "score_ic": None, "score_dn": None,
                 "postura_dominante_llm": None, "nota_epistemologica": str(e),
                 "entropia_llm_epi": None}
        rows.append({"doc_id": r.doc_id, "annotator": "llm_prepass", **c})
    out = pd.DataFrame(rows)
    out.to_csv("annotations_llm_prepass.csv", index=False)
    n = len(out)
    dn  = (out.postura_dominante_llm == "DN").sum()
    mix = (out.postura_dominante_llm == "mixed").sum()
    az  = ((out.score_ee.fillna(0) < 0.5) &
           (out.score_ic.fillna(0) < 0.5) &
           (out.score_dn.fillna(0) < 0.5)).sum()
    print(f"[EXPLORATÓRIO — não é padrão-ouro] n={n} | DN dominante={dn} ({dn/n:.0%}) "
          f"| mixed={mix} ({mix/n:.0%}) | all-zero={az} ({az/n:.0%})")
    print("Use para triagem/escopo; alpha_DN humano (irrCAC/R) continua necessário.")

if __name__ == "__main__":
    main(sys.argv[1])
