"""
logging_setup.py — Configuração padrão de logging para todos os scripts
=========================================================================
Substitui prints por logging estruturado com timestamp, nível, módulo.
Grava em arquivo + console simultaneamente.

Uso:
    from utils.logging_setup import setup_logging
    log = setup_logging("01a_coleta_openalex")

Autor: Fernando Leite | FAPESP | v2 — 22/maio/2026
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logging(
    nome_script: str,
    log_dir: Path = Path("logs"),
    nivel: int = logging.INFO,
    rotacao: bool = True,
) -> logging.Logger:
    """Configura logging estruturado com console + arquivo.

    Args:
        nome_script: identificador do script (usado no nome do arquivo de log)
        log_dir: diretório de logs (criado se não existir)
        nivel: nível mínimo (default INFO)
        rotacao: se True, cria um arquivo por execução (timestamped); se False, append único

    Returns:
        Logger configurado pronto para uso.
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if rotacao:
        log_file = log_dir / f"{nome_script}_{timestamp}.log"
    else:
        log_file = log_dir / f"{nome_script}.log"

    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # Limpar handlers anteriores se já configurado
    logger = logging.getLogger(nome_script)
    logger.setLevel(nivel)
    logger.handlers.clear()
    logger.propagate = False

    # Console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    logger.addHandler(console_handler)

    # Arquivo
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    logger.addHandler(file_handler)

    logger.info("=" * 60)
    logger.info("Início da execução de %s", nome_script)
    logger.info("Log: %s", log_file)
    logger.info("=" * 60)

    return logger
