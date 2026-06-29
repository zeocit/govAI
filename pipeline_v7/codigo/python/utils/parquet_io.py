"""
parquet_io.py — I/O Parquet com schema explícito + snapshot atômico
====================================================================
Camada fina sobre safe_io.py com responsabilidades específicas:

- Gravação Parquet com schema pyarrow explícito para interop R↔Python
- Hash SHA-256 chunked do arquivo gerado
- Registro de auditoria em snapshot.json sob lock (concorrência-seguro)

Autor: Fernando Leite | FAPESP | v3 — 28/maio/2026
    Refatorado para delegar atomicidade e locking a safe_io.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import orjson
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

try:
    from .safe_io import atomic_write_json, file_lock, sha256_file
except ImportError:
    # Permite execução de scripts em árvore plana (sem pacote)
    from safe_io import atomic_write_json, file_lock, sha256_file  # type: ignore

SNAPSHOT_PATH = Path("dados/intermediarios/snapshot.json")
SNAPSHOT_LOCK = SNAPSHOT_PATH.with_suffix(".lock")
log = logging.getLogger(__name__)


def write_parquet_atomic(
    df: pd.DataFrame,
    output_path: Path,
    schema: pa.Schema | None = None,
    script: str | None = None,
    compression: str = "snappy",
) -> str:
    """Grava parquet de forma atômica e registra hash em snapshot.

    Args:
        df: DataFrame a gravar
        output_path: caminho final do .parquet
        schema: schema pyarrow opcional (recomendado para interop R/arrow)
        script: nome do script gerador (para entrada em snapshot.json)
        compression: codec (snappy, zstd, gzip)

    Returns:
        SHA-256 hex do arquivo gravado.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")

    if schema is not None:
        table = pa.Table.from_pandas(df, schema=schema, preserve_index=False)
        pq.write_table(table, tmp_path, compression=compression)
    else:
        df.to_parquet(tmp_path, index=False, compression=compression)

    # fsync explícito antes do rename garante persistência em filesystems
    # com cache agressivo. Critério para inclusão: a auditoria QA detectou
    # que sem isso o pipeline pode perder horas de chamadas LLM pagas.
    with tmp_path.open("rb") as f:
        os.fsync(f.fileno())
    tmp_path.replace(output_path)

    sha256 = sha256_file(output_path)  # chunked, escala para arquivos grandes
    if script is not None:
        registrar_snapshot(output_path, sha256, len(df), script)

    log.info(
        "Gravado: %s | %d linhas | %.2f MB | sha256=%s",
        output_path, len(df),
        output_path.stat().st_size / 1e6, sha256[:16]
    )
    return sha256


def registrar_snapshot(
    output_path: Path,
    sha256: str,
    n_rows: int,
    script: str,
    extras: dict | None = None,
) -> None:
    """Adiciona/atualiza entrada em snapshot.json sob lock — seguro
    para execução paralela de scripts (DA-04: 04a + 04b independentes).
    """
    with file_lock(SNAPSHOT_LOCK):
        snapshot: dict = {}
        if SNAPSHOT_PATH.exists():
            try:
                snapshot = orjson.loads(SNAPSHOT_PATH.read_bytes())
            except Exception as exc:
                # Preservar arquivo corrompido para diagnóstico antes de
                # recriar — comportamento anterior perdia a história
                # inteira silenciosamente.
                backup = SNAPSHOT_PATH.with_suffix(".corrupt.bak")
                try:
                    SNAPSHOT_PATH.rename(backup)
                    log.warning(
                        "Snapshot corrompido salvo em %s (%s); recriando",
                        backup, exc
                    )
                except OSError:
                    log.warning("Snapshot corrompido (%s); recriando", exc)
                snapshot = {}

        entrada = {
            "sha256": sha256,
            "size_bytes": output_path.stat().st_size,
            "n_rows": n_rows,
            "data_processamento": datetime.now(timezone.utc).isoformat(),
            "script": script,
        }
        if extras:
            entrada.update(extras)
        snapshot[str(output_path)] = entrada

        atomic_write_json(SNAPSHOT_PATH, snapshot, sort_keys=True)


def validar_schema(df: pd.DataFrame, schema: pa.Schema) -> list[str]:
    """Valida que o DataFrame é compatível com o schema esperado.

    Returns:
        Lista de mensagens de erro (vazia se OK).
    """
    erros = []
    for field in schema:
        if field.name not in df.columns:
            erros.append(f"Coluna ausente: {field.name}")
            continue
        try:
            pa.array(df[field.name], type=field.type)
        except (pa.ArrowTypeError, pa.ArrowInvalid) as e:
            erros.append(
                f"Tipo incompatível em '{field.name}': "
                f"esperado {field.type}, erro: {e}"
            )
    return erros
