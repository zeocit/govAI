"""
safe_io.py — Primitivas de I/O atômico e idempotente
=====================================================
Centraliza primitivas que aparecem reimplementadas em vários scripts:

- Escrita atômica para bytes e JSON (.tmp → fsync → rename)
- Lock de arquivo por OS-level (mitiga lost-update em snapshot.json
  quando 04a e 04b rodam em paralelo)
- Hash SHA-256 em chunks (escala para arquivos > 1 GB)

Razão para existir: na auditoria do pipeline_v2, parquet_io.py e
04c.py implementaram parcialmente estas primitivas com tratamento de
erro divergente. Este módulo é a fonte única; parquet_io.py importa
daqui, e scripts ad-hoc (04c) podem fazer o mesmo.

Autor: Fernando Leite | FAPESP | v3 — 28/maio/2026
"""
from __future__ import annotations

import errno
import hashlib
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import orjson

CHUNK_SIZE = 1 << 20  # 1 MiB


def sha256_file(path: Path) -> str:
    """Hash SHA-256 lendo em chunks (escala para arquivos grandes).

    Substitui o padrão Path.read_bytes() + hashlib.sha256(), que carrega
    o arquivo inteiro em memória — frágil para corpora > 1 GB.
    """
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Escreve bytes atomicamente: .tmp → fsync → rename.

    Garantia: o arquivo final ou está intacto, ou ainda contém a versão
    anterior. Nunca fica em estado truncado, mesmo com kill -9 entre
    write e rename.

    O fsync explícito antes do rename é necessário em filesystems com
    cache agressivo (NFS, ext4 com data=writeback): sem ele, o rename
    pode ser persistido antes do conteúdo, expondo um arquivo nominal
    mas com dados perdidos após reboot.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def atomic_write_json(path: Path, obj: dict, sort_keys: bool = True) -> None:
    """Atomic write de JSON via orjson (com OPT_INDENT_2 e OPT_SORT_KEYS)."""
    opts = orjson.OPT_INDENT_2
    if sort_keys:
        opts |= orjson.OPT_SORT_KEYS
    atomic_write_bytes(path, orjson.dumps(obj, option=opts))


@contextmanager
def file_lock(lockfile: Path, timeout_s: float = 30.0) -> Iterator[None]:
    """Lock de arquivo por fcntl (POSIX) ou msvcrt (Windows).

    Bloqueia até o lock ser obtido ou estourar o timeout. Necessário para
    evitar lost-update em snapshot.json quando dois scripts rodam em
    paralelo (04a + 04b é o caso real previsto em DA-04).

    Uso:
        with file_lock(Path("dados/.snapshot.lock")):
            # ler-modificar-escrever snapshot.json com segurança
            ...
    """
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lockfile), os.O_CREAT | os.O_RDWR)
    try:
        deadline = time.monotonic() + timeout_s
        while True:
            try:
                if os.name == "posix":
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    import msvcrt
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                break
            except (BlockingIOError, OSError) as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                if time.monotonic() > deadline:
                    raise TimeoutError(
                        f"Lock {lockfile} indisponível após {timeout_s}s"
                    )
                time.sleep(0.1)
        yield
    finally:
        try:
            if os.name == "posix":
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
