"""PRÉ-CLASSIFICAÇÃO EXPLORATÓRIA por LLM (triagem provisória — NÃO é padrão-ouro).
Produz rótulos EE/IC/DN + flags A_pos/A_int provisórios para: (i) leitura provisória
da prevalência de misto e da distribuição de DN; (ii) viabilizar a separabilidade.
NÃO substitui anotação humana nem fornece alpha_DN (precisa de >=2 humanos).
Requer ANTHROPIC_API_KEY no ambiente. Uso: python llm_prepass.py abstracts.csv
"""
import sys, os, json, pandas as pd, urllib.request

CRITERIO = (
 "Classifique a POSTURA EPISTEMOLÓGICA do artigo a partir do abstract. "
 "Responda só JSON: {\"B_label\":\"EE|IC|DN\",\"A_pos\":0|1,\"A_int\":0|1,\"conf\":0-1}. "
 "EE=empírico-explicativa (hipótese/N/estatística; afirma o que É/causa). "
 "IC=interpretativo-compreensiva (caso profundo/etnografia/hermenêutica; significado situado). "
 "DN=doutrinário-normativa (sem dado empírico; argumento por princípio/norma; 'dever ser'). "
 "A_pos/A_int são os binários (podem ser ambos 1 = misto)."
)

def classify(abstract, key):
    body = json.dumps({"model":"claude-sonnet-4-20250514","max_tokens":200,
        "messages":[{"role":"user","content":CRITERIO+"\n\nABSTRACT:\n"+abstract}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type":"application/json","x-api-key":key,"anthropic-version":"2023-06-01"})
    txt = "".join(b.get("text","") for b in json.load(urllib.request.urlopen(req)).get("content",[]) if b.get("type")=="text")
    return json.loads(txt[txt.find("{"):txt.rfind("}")+1])

def main(path):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key: sys.exit("defina ANTHROPIC_API_KEY")
    df = pd.read_csv(path).dropna(subset=["abstract"]); rows=[]
    for _,r in df.iterrows():
        try: c = classify(r.abstract, key)
        except Exception as e: c = {"B_label":None,"A_pos":None,"A_int":None,"conf":0}
        rows.append({"doc_id":r.doc_id, "subsample":"prevalence", "annotator":"llm_prepass",
                     "A_pos":c.get("A_pos"),"A_int":c.get("A_int"),"B_label":c.get("B_label"),"B_forcing":1})
    out = pd.DataFrame(rows); out.to_csv("annotations_llm_prepass.csv", index=False)
    n=len(out); misto=((out.A_pos==1)&(out.A_int==1)).sum()
    print(f"[EXPLORATÓRIO — não é padrão-ouro] n={n} | misto provisório={misto}/{n} ({misto/n:.0%}) "
          f"| DN provisório={ (out.B_label=='DN').sum() }/{n}")
    print("Use para triagem/escopo; o alpha_DN humano continua necessário.")

if __name__ == "__main__":
    main(sys.argv[1])
