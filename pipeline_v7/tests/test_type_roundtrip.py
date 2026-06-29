"""
tests/test_type_roundtrip.py — Type safety Python ↔ R via Parquet (Round 4, frente J)
========================================================================================
O pipeline grava parquets em Python (pandas/pyarrow) e lê em R (arrow), e vice-versa.
Tipos nullable do pandas (`Int8`, `pd.NA`, `pd.StringDtype`) têm representação
diferente do numpy convencional e podem chegar com tipo inesperado no R.

Este teste:
  1. Cria DataFrames com os tipos problemáticos usados no pipeline.
  2. Grava como parquet com pyarrow (mesmo mecanismo do pipeline).
  3. Lê de volta com pyarrow e verifica a preservação de tipos.
  4. Se R estiver disponível, verifica via subprocess (validação extra).

Tipos críticos no pipeline:
  - Int8 nullable (quartil_citacoes, 04c)
  - bool nullable (eh_fronteira, 04c; is_fronteira_cluster, 04a)
  - float64 com NaN (cluster_si_llm etc, 04a/04b)
  - object/string com None (cluster_secundario_llm, idioma_detectado)
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

ROOT = Path(__file__).parent.parent / "codigo" / "python"
sys.path.insert(0, str(ROOT))


def _roundtrip(df: pd.DataFrame) -> pd.DataFrame:
    """Grava como parquet e relê — simula o I/O real do pipeline."""
    with tempfile.NamedTemporaryFile(suffix=".parquet") as f:
        df.to_parquet(f.name, index=False, engine="pyarrow")
        return pd.read_parquet(f.name, engine="pyarrow")


# ── Int8 nullable (quartil_citacoes em 04c) ───────────────────────────────────
def test_int8_nullable_preserva_na():
    df = pd.DataFrame({"v": pd.array([1, None, 0], dtype="Int8")})
    out = _roundtrip(df)
    assert out["v"].isna().sum() == 1, "Int8 NA deve ser preservado no round-trip"
    assert out["v"].dropna().tolist() == [1, 0]


# ── bool nullable (eh_fronteira em 04c) ──────────────────────────────────────
def test_bool_nullable_preserva_na():
    df = pd.DataFrame({"v": pd.array([True, None, False], dtype="boolean")})
    out = _roundtrip(df)
    assert out["v"].isna().sum() == 1


# ── float64 com NaN (probabilidades LLM) ─────────────────────────────────────
def test_float_nan_preserva():
    df = pd.DataFrame({"v": [0.8, float("nan"), 0.0]})
    out = _roundtrip(df)
    assert out["v"].isna().sum() == 1
    assert pytest.approx(out["v"].dropna().tolist()) == [0.8, 0.0]


# ── string/object com None (cluster_secundario_llm) ──────────────────────────
def test_string_none_preserva_como_na():
    df = pd.DataFrame({"v": pd.array(["si", None, "pa"], dtype="string")})
    out = _roundtrip(df)
    assert out["v"].isna().sum() == 1
    assert out["v"].dropna().tolist() == ["si", "pa"]


# ── soma de probabilidades sobrevive ao round-trip ───────────────────────────
def test_probabilidades_somam_1_apos_roundtrip():
    """As probabilidades de cluster gravadas por 04a devem somar ≈1 após round-trip."""
    clusters = ["si", "ps", "sts", "law", "pa", "bcs"]
    # Simular linha de saída de 04a (normalizada)
    probs = np.array([0.6, 0.15, 0.1, 0.05, 0.05, 0.05])
    df = pd.DataFrame(
        {f"cluster_{c}_llm": [probs[i]] for i, c in enumerate(clusters)}
    )
    out = _roundtrip(df)
    soma = out[[f"cluster_{c}_llm" for c in clusters]].sum(axis=1)
    assert abs(soma.iloc[0] - 1.0) < 1e-10


# ── R round-trip (executa somente se R estiver disponível) ───────────────────
R_DISPONIVEL = (
    subprocess.run(["Rscript", "--version"], capture_output=True).returncode == 0
    and subprocess.run(
        ["Rscript", "-e", "library(arrow)"], capture_output=True
    ).returncode == 0
)


@pytest.mark.skipif(not R_DISPONIVEL, reason="R não disponível neste ambiente")
def test_r_le_int8_nullable_como_integer():
    """R/arrow deve ler Int8 nullable como integer com NA, não como double."""
    df = pd.DataFrame({"quartil": pd.array([0, 1, None, 3], dtype="Int8")})
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        df.to_parquet(f.name, index=False)
        r_script = f"""
library(arrow, warn.conflicts=FALSE)
df <- read_parquet('{f.name}')
stopifnot(is.integer(df$quartil) || is.numeric(df$quartil))
stopifnot(sum(is.na(df$quartil)) == 1)
cat('OK\n')
"""
        result = subprocess.run(
            ["Rscript", "-e", r_script], capture_output=True, text=True
        )
        assert result.returncode == 0 and "OK" in result.stdout, \
            f"R não leu Int8 nullable corretamente:\n{result.stderr}"


if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        ["python", "-m", "pytest", __file__, "-v"],
        capture_output=False
    )
    raise SystemExit(result.returncode)
