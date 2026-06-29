"""
01a_coleta_openalex.py — Coleta sistemática via OpenAlex
=========================================================
Manual §3.2.5 (v14): coleta todos os artigos e reviews dos periódicos
definidos no universo de fontes (protocolo/periodicos_source_ids.txt),
para o período 2000-2024, via pyalex.

Nota sobre a biblioteca:
    openalexR é o pacote R; em Python o equivalente oficial é `pyalex`.
    Instalar: pip install pyalex tqdm pyarrow pandas

Input:
    protocolo/periodicos_source_ids.txt — um OpenAlex Source ID por linha
    (formato: S1234567890, sem URL completa)

Output:
    dados/brutos/corpus_openalex.parquet

Schema de saída (Codebook v2.1 §2):
    id, doi, titulo, abstract_raw, abstract, ano, data_publicacao,
    periodico_nome, periodico_source_id, periodico_issn_l, idioma,
    citacoes, tipo_obra, is_retracted, autores, referencias, concepts,
    data_coleta

Operação:
    - Paginação cursor-based via pyalex (.paginate())
    - Checkpoint automático: salva progresso a cada CHUNK_SIZE periódicos
      em dados/brutos/.checkpoint_coleta.parquet (permite retomar)
    - Exponential backoff em erros de rede
    - Logging completo para auditoria

Reprodutibilidade:
    - A data de coleta é gravada em cada linha (data_coleta)
    - O arquivo de saída é versionado via tag git (não gerenciado aqui)
    - Para reproduzir exatamente: usar o mesmo protocolo/periodicos_source_ids.txt

Autor: Fernando Leite | FAPESP | Refatoração v2 — 22/maio/2026
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyalex
from pyalex import Works
from tqdm import tqdm

# ── Configuração ────────────────────────────────────────────────────────────
SOURCES_FILE   = Path("protocolo/periodicos_source_ids.txt")
OUTPUT_PATH    = Path("dados/brutos/corpus_openalex.parquet")
CHECKPOINT_PATH = Path("dados/brutos/.checkpoint_coleta.parquet")

ANO_INICIO = 2000
ANO_FIM    = 2024
TIPOS_OBRA = ["article", "review"]
IDIOMAS    = ["en", "pt"]          # None = não filtrar por idioma na API

# Configurações de paginação e retry
PER_PAGE        = 200              # máximo permitido pela API
CHUNK_SIZE      = 5               # salvar checkpoint a cada N source_ids
RETRY_MAX       = 5
RETRY_BASE_WAIT = 2.0             # segundos (backoff exponencial)

# Email para polite pool da API (aumenta rate limit)
OPENALEX_EMAIL  = "seu_email@instituicao.br"  # ALTERAR antes de rodar

log = logging.getLogger("01a_coleta_openalex")


# ── Helpers ──────────────────────────────────────────────────────────────────

# Circuit breaker: abstracts típicos têm ≤500 tokens; >10k é índice corrompido do OpenAlex
MAX_TOKEN_POSITION = 10_000


def reconstruct_abstract(
    inverted_index: dict | None,
    logger_anomalia: logging.Logger | None = None,
) -> str:
    """Reconstrói o texto do abstract a partir do inverted_index do OpenAlex.

    Refatorado para usar dicionário esparso em vez de lista contígua —
    blinda contra OOM se um registro corrompido devolver índice anômalo
    (e.g. position=99999999), e contra strings vazias intermediárias.
    """
    if not inverted_index or not isinstance(inverted_index, dict):
        return ""
    try:
        word_dict: dict[int, str] = {}
        max_pos = -1
        for word, positions in inverted_index.items():
            for pos in positions:
                if not isinstance(pos, int) or pos < 0:
                    continue
                if pos > MAX_TOKEN_POSITION:
                    if logger_anomalia is not None:
                        logger_anomalia.warning(
                            "Posição anômala %d descartada (limite %d)",
                            pos, MAX_TOKEN_POSITION,
                        )
                    return ""  # Aborto explícito, não silencioso
                word_dict[pos] = word
                if pos > max_pos:
                    max_pos = pos
        if max_pos < 0:
            return ""
        return " ".join(word_dict.get(i, "") for i in range(max_pos + 1)).strip()
    except (ValueError, TypeError) as e:
        if logger_anomalia is not None:
            logger_anomalia.warning("Falha na reconstrução do abstract: %s", e)
        return ""


def parse_work(work: dict, data_coleta: str) -> dict:
    """Normaliza um registro OpenAlex para o schema do Codebook v2.1."""
    loc    = work.get("primary_location") or {}
    source = loc.get("source") or {}

    return {
        "id":                 work.get("id", ""),
        "doi":                work.get("doi"),
        "titulo":             work.get("display_name", ""),
        "abstract_raw":       json.dumps(work.get("abstract_inverted_index"), ensure_ascii=False)
                              if work.get("abstract_inverted_index") else None,
        "abstract":           reconstruct_abstract(work.get("abstract_inverted_index"), logging.getLogger(__name__)),
        "ano":                work.get("publication_year"),
        "data_publicacao":    work.get("publication_date"),
        "periodico_nome":     source.get("display_name"),
        "periodico_source_id": source.get("id"),
        "periodico_issn_l":   source.get("issn_l"),
        "idioma":             work.get("language"),
        "citacoes":           work.get("cited_by_count", 0),
        "tipo_obra":          work.get("type"),
        "is_retracted":       bool(work.get("is_retracted", False)),
        "autores":            json.dumps(work.get("authorships", []), ensure_ascii=False),
        "referencias":        json.dumps(work.get("referenced_works", []), ensure_ascii=False),
        "concepts":           json.dumps(work.get("concepts", []), ensure_ascii=False),
        "data_coleta":        data_coleta,
    }


def fetch_source_with_retry(source_id: str, data_coleta: str) -> list[dict]:
    """Coleta todos os artigos de um source_id com retry exponencial."""
    # NOTA (auditoria v5): IDIOMAS é intencionalmente NÃO aplicado na API.
    # 02_limpeza_estrutural mantém artigos sem idioma declarado (idioma.isna())
    # para detecção posterior em 03_limpeza_textual.R; filtrar por language aqui
    # descartaria esses registros na origem, contradizendo essa decisão. O filtro
    # de idioma permanece como responsabilidade de 02. Mantido como variável de
    # configuração documentada, mas deliberadamente inerte na query.
    query = (
        Works()
        .filter(
            primary_location={"source": {"id": source_id}},
            publication_year=f"{ANO_INICIO}-{ANO_FIM}",
            type="|".join(TIPOS_OBRA),
        )
        .select([
            "id", "doi", "display_name", "publication_year", "publication_date",
            "language", "type", "cited_by_count", "is_retracted",
            "abstract_inverted_index", "authorships", "referenced_works",
            "concepts", "primary_location"
        ])
    )

    records: list[dict] = []
    attempt = 0

    while attempt < RETRY_MAX:
        try:
            for page in query.paginate(per_page=PER_PAGE):
                for work in page:
                    records.append(parse_work(work, data_coleta))
            return records

        except Exception as exc:
            attempt += 1
            wait = RETRY_BASE_WAIT * (2 ** attempt)
            log.warning("Erro em %s (tentativa %d/%d): %s — aguardando %.0fs",
                        source_id, attempt, RETRY_MAX, exc, wait)
            if attempt >= RETRY_MAX:
                log.error("Falhou definitivamente para %s. Pulando.", source_id)
                return records
            time.sleep(wait)

    return records


def load_checkpoint() -> tuple[set[str], list[dict]]:
    """Carrega checkpoint de execução anterior (source_ids já coletados + registros)."""
    if not CHECKPOINT_PATH.exists():
        return set(), []

    try:
        df = pd.read_parquet(CHECKPOINT_PATH)
        source_ids_done = set(df["periodico_source_id"].dropna().unique())
        records = df.to_dict("records")
        log.info("Checkpoint: %d artigos de %d fontes já coletados",
                 len(records), len(source_ids_done))
        return source_ids_done, records
    except Exception as exc:
        log.warning("Não foi possível carregar checkpoint: %s. Iniciando do zero.", exc)
        return set(), []


def save_checkpoint(records: list[dict]) -> None:
    """Salva checkpoint intermediário."""
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_parquet(CHECKPOINT_PATH, index=False, compression="snappy")


# ── Main ─────────────────────────────────────────────────────────────────────

def main(sources_file: Path, output_path: Path) -> None:
    # Configurar polite pool
    pyalex.config.email = OPENALEX_EMAIL

    # Carregar lista de fontes
    if not sources_file.exists():
        raise FileNotFoundError(
            f"Arquivo de fontes não encontrado: {sources_file}\n"
            "Crie o arquivo com um OpenAlex Source ID por linha (ex.: S205292342)."
        )
    source_ids = [
        line.strip()
        for line in sources_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    log.info("%d fontes carregadas de %s", len(source_ids), sources_file)

    # Carregar checkpoint
    source_ids_done, all_records = load_checkpoint()
    source_ids_pending = [s for s in source_ids if s not in source_ids_done]
    log.info("%d fontes já coletadas; %d pendentes", len(source_ids_done), len(source_ids_pending))

    data_coleta = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Coleta
    with tqdm(source_ids_pending, desc="Coletando fontes", unit="source") as pbar:
        for chunk_start in range(0, len(source_ids_pending), CHUNK_SIZE):
            chunk = source_ids_pending[chunk_start : chunk_start + CHUNK_SIZE]
            for source_id in chunk:
                len(all_records)
                records = fetch_source_with_retry(source_id, data_coleta)
                all_records.extend(records)
                log.info("  %s: %d artigos coletados (total acumulado: %d)",
                         source_id, len(records), len(all_records))
                pbar.update(1)

            # Salvar checkpoint após cada chunk
            save_checkpoint(all_records)
            log.info("Checkpoint salvo (%d artigos até agora)", len(all_records))

    # Output final
    if not all_records:
        log.warning("Nenhum artigo coletado. Verifique os source_ids e o filtro de anos.")
        return

    df = pd.DataFrame(all_records)
    log.info("Total final: %d artigos", len(df))
    log.info("Distribuição por tipo: %s", df["tipo_obra"].value_counts().to_dict())
    log.info("Distribuição por idioma: %s", df["idioma"].value_counts().to_dict())
    log.info("Período: %s – %s", df["ano"].min(), df["ano"].max())

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Gravação atômica: escrever em .tmp e renomear (evita arquivo corrupto se interrompido)
    tmp_path = output_path.with_suffix(".parquet.tmp")
    df.to_parquet(tmp_path, index=False, compression="snappy")
    tmp_path.replace(output_path)

    # Hash SHA-256 + entrada em snapshot.json para auditoria de reprodutibilidade
    import hashlib
    sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()
    snapshot_path = Path("dados/intermediarios/snapshot.json")
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {}
    if snapshot_path.exists():
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot[str(output_path)] = {
        "sha256": sha256,
        "size_bytes": output_path.stat().st_size,
        "n_rows": len(df),
        "data_coleta": datetime.now(timezone.utc).isoformat(),
        "script": "01a_coleta_openalex.py",
    }
    snapshot_path.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info("Gravado: %s (%.1f MB) | sha256=%s",
             output_path, output_path.stat().st_size / 1e6, sha256[:16])

    # Remover checkpoint após sucesso completo
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()
        log.info("Checkpoint removido.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/01a_coleta_openalex.log", mode="a", encoding="utf-8")
        ]
    )
    Path("logs").mkdir(exist_ok=True)

    parser = argparse.ArgumentParser(description="Coleta sistemática via OpenAlex (pyalex).")
    parser.add_argument("--sources", type=Path, default=SOURCES_FILE)
    parser.add_argument("--output",  type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    main(args.sources, args.output)
