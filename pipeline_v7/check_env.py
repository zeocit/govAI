#!/usr/bin/env python3
"""
check_env.py — Verifica se o ambiente está pronto para rodar o pipeline
=======================================================================
Executar antes da primeira execução real:
    python3 check_env.py

Saída: lista de PASSOU / FALHOU por dependência, com instrução de correção.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

OK = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m!\033[0m"

checks: list[tuple[bool, str, str]] = []  # (passou, label, instrução)


def chk(passou: bool, label: str, instrucao: str = "") -> bool:
    checks.append((passou, label, instrucao))
    status = OK if passou else FAIL
    print(f"  {status}  {label}")
    if not passou and instrucao:
        print(f"       → {instrucao}")
    return passou


# ── Python ────────────────────────────────────────────────────────────────────
print("\n=== Python ===")
chk(sys.version_info >= (3, 10),
    f"Python ≥ 3.10 (atual: {sys.version.split()[0]})",
    "Instale Python 3.10+ em python.org")

for pkg, install_hint in [
    ("irrCAC",      "pip install irrCAC==0.4.4"),
    ("openai",      "pip install openai==2.38.0"),
    ("pandas",      "pip install pandas==2.3.3"),
    ("numpy",       "pip install numpy==1.26.4"),
    ("pyarrow",     "pip install pyarrow==24.0.0"),
    ("sklearn",     "pip install scikit-learn==1.8.0"),
    ("tqdm",        "pip install tqdm==4.67.3"),
    ("orjson",      "pip install orjson==3.11.9"),
    ("rapidfuzz",   "pip install rapidfuzz==3.14.5"),
    ("torch",       "Ver INSTALL.md — depende de plataforma (MPS/CUDA/CPU)"),
    ("transformers","pip install 'transformers>=4.35'"),
    ("pyalex",      "pip install pyalex"),
]:
    chk(importlib.util.find_spec(pkg) is not None,
        f"  {pkg}",
        f"pip install {pkg}" if "pip install" not in install_hint else install_hint)

# ── Variáveis de ambiente ─────────────────────────────────────────────────────
print("\n=== Variáveis de ambiente ===")
chk(bool(os.getenv("OPENROUTER_API_KEY")),
    "OPENROUTER_API_KEY",
    "Adicione ao seu .env ou exporte no shell")
chk(bool(os.getenv("OPENALEX_EMAIL")),
    "OPENALEX_EMAIL",
    "Adicione ao seu .env (sem isto, rate limit mais restritivo no OpenAlex)")

# ── R ─────────────────────────────────────────────────────────────────────────
print("\n=== R ===")
r_ok = subprocess.run(["Rscript", "--version"], capture_output=True).returncode == 0
chk(r_ok, "R instalado", "Instale R ≥ 4.3 em r-project.org")

if r_ok:
    for pkg in ["arrow", "data.table", "igraph", "Matrix",
                "stringi", "cld3", "udpipe", "jsonlite"]:
        ok = subprocess.run(
            ["Rscript", "-e", f"library({pkg})"], capture_output=True
        ).returncode == 0
        chk(ok, f"  R: {pkg}", f'install.packages("{pkg}")')

# ── Scripts compilam ─────────────────────────────────────────────────────────
print("\n=== Compilação dos scripts ===")
from pathlib import Path
root = Path(__file__).parent
n_ok = n_fail = 0
for f in sorted((root / "codigo" / "python").glob("**/*.py")):
    r = subprocess.run([sys.executable, "-m", "py_compile", str(f)],
                       capture_output=True)
    if r.returncode == 0:
        n_ok += 1
    else:
        n_fail += 1
        print(f"  {FAIL}  {f.relative_to(root)}")
chk(n_fail == 0, f"Python scripts compilam ({n_ok}/{n_ok+n_fail})")

# ── Sumário ───────────────────────────────────────────────────────────────────
n_passou = sum(1 for p, _, _ in checks if p)
n_total  = len(checks)
n_falhou = n_total - n_passou

print(f"\n{'='*50}")
if n_falhou == 0:
    print(f"{OK} Ambiente pronto — {n_passou}/{n_total} verificações passaram.")
else:
    print(f"{FAIL} {n_falhou} verificação(ões) falharam. Corrija antes de rodar.")
    sys.exit(1)
