#!/bin/sh
set -e

# Rode da raiz do clone govAI:
#   cd /caminho/para/govAI
#   sh /caminho/para/apply.sh

if [ ! -d ".git" ]; then
  echo "ERRO: rode da raiz do clone govAI (onde fica .git)"
  exit 1
fi

PKGDIR="$(cd "$(dirname "$0")" && pwd)"

git config user.email "fernando@cientometria2"
git config user.name "Fernando Leite"

echo "=== HEAD atual ==="
git log --oneline -3
echo ""

# -------------------------------------------------------
# COMMIT 1: renames (somente se ainda nao feitos)
# -------------------------------------------------------
if [ -d "Lab Notebook" ] && [ ! -d "lab-notebook" ]; then
  echo "--- commit 1: renomeando Lab Notebook -> lab-notebook e legacy -> archive/legacy ---"
  git mv "Lab Notebook" lab-notebook
  mkdir -p archive
  git mv legacy archive/legacy
  git add -A
  git commit -m "repo: realize layout documentado (lab-notebook/, archive/legacy/)"
  echo "commit 1 aplicado."
elif [ -d "lab-notebook" ]; then
  echo "commit 1: lab-notebook/ ja existe, pulando."
else
  echo "AVISO: nao encontrei 'Lab Notebook' nem 'lab-notebook'. Verifique a estrutura."
fi

echo ""

# -------------------------------------------------------
# COMMIT 2: pipeline_v7 + notebooks
# -------------------------------------------------------
if [ -d "pipeline_v7" ] && [ -f "pipeline_v7/04b_classificar_epi_llm.py" ]; then
  echo "commit 2: pipeline_v7/ ja existe com arquivos, pulando."
else
  echo "--- commit 2: adicionando pipeline_v7/ e notebooks/ ---"
  mkdir -p pipeline_v7/utils notebooks
  cp "$PKGDIR/pipeline_v7/04b_classificar_epi_llm.py"   pipeline_v7/
  cp "$PKGDIR/pipeline_v7/05_processar_anotacoes.py"     pipeline_v7/
  cp "$PKGDIR/pipeline_v7/06b_treinar_epi.py"            pipeline_v7/
  cp "$PKGDIR/pipeline_v7/07_aplicar_modelo.py"          pipeline_v7/
  cp "$PKGDIR/pipeline_v7/utils/thresholds.py"           pipeline_v7/utils/
  cp "$PKGDIR/pipeline_v7/utils/derive_orientacao.py"    pipeline_v7/utils/
  cp "$PKGDIR/notebooks/govai_calibracao_colab.ipynb"    notebooks/
  git add pipeline_v7 notebooks
  git commit -m "feat: pipeline_v7 camada epi dois eixos (04b 05 06b 07) + utils (thresholds, derive_orientacao) + notebook calibracao"
  echo "commit 2 aplicado."
fi

echo ""

# -------------------------------------------------------
# COMMIT 3: entrada do Lab Notebook
# -------------------------------------------------------
LABFILE="2026-06-29_confianca-1-3-and-two-axis-doc-reconciliation.md"
if [ -d "lab-notebook" ]; then
  LABDIR="lab-notebook"
else
  LABDIR="Lab Notebook"
fi

if [ -f "$LABDIR/$LABFILE" ]; then
  echo "commit 3: entrada do lab notebook ja existe, pulando."
else
  echo "--- commit 3: entrada do lab notebook ---"
  cp "$PKGDIR/lab-notebook/$LABFILE" "$LABDIR/"
  git add "$LABDIR/$LABFILE"
  git commit -m "lab: confianca 1-3 and two-axis doc reconciliation"
  echo "commit 3 aplicado."
fi

echo ""
echo "=== log final ==="
git log --oneline -7
echo ""
echo "Proximo passo: git push origin main"
