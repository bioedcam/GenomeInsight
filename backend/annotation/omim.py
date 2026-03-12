"""Optional OMIM enrichment for gene-phenotype associations.

Requires a user-provided OMIM API key (configured in setup wizard,
stored in ``config.toml``).  When available, enriches the
``gene_phenotype`` table with MIM numbers, OMIM-specific phenotype
text, and inheritance patterns from the OMIM genemap2 download.

No OMIM data is bundled (MIT license compliance).  MONDO/HPO is the
default open gene-phenotype source; OMIM is supplementary.

Usage::

    from backend.annotation.omim import (
        fetch_omim_genemap2,
        load_omim_enrichment,
        enrich_with_omim,
    )

    # Full pipeline (requires API key)
    stats = enrich_with_omim(reference_engine, api_key="...")
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
import sqlalchemy as sa
import structlog

from backend.db.tables import database_versions, gene_phenotype

logger = structlog.get_logger(__name__)

# ── OMIM API endpoint ────────────────────────────────────────────────────

OMIM_API_BASE = "https://data.omim.org"
OMIM_GENEMAP2_ENDPOINT = "/downloads/genemap2.txt"

# Batch size for inserts
BATCH_SIZE = 10_000


# ── Data classes ─────────────────────────────────────────────────────────


@dataclass
class OMIMRecord:
    """A single parsed OMIM genemap2 record."""

    gene_symbol: str
    mim_number: str
    phenotype_text: str
    phenotype_mim: str | None = None
    inheritance: str | None = None
    mapping_key: int | None = None


@dataclass
class OMIMLoadStats:
    """Statistics from an OMIM enrichment operation."""

    total_lines: int = 0
    records_loaded: int = 0
    skipped_no_gene: int = 0
    skipped_no_phenotype: int = 0
    skipped_comments: int = 0
    genes_enriched: int = 0


# ── Inheritance pattern parsing ──────────────────────────────────────────

_OMIM_INHERITANCE_ABBREVS = {
    "AD": "Autosomal dominant",
    "AR": "Autosomal recessive",
    "XL": "X-linked",
    "XLR": "X-linked recessive",
    "XLD": "X-linked dominant",
    "YL": "Y-linked",
    "Mi": "Mitochondrial",
    "Mu": "Multifactorial",
    "IC": "Isolated cases",
    "SMo": "Somatic mosaicism",
    "Smu": "Somatic mutation",
    "DD": "Digenic dominant",
    "DR": "Digenic recessive",
    "?AD": "Autosomal dominant",
    "?AR": "Autosomal recessive",
}


def _parse_inheritance(inheritance_raw: str) -> str | None:
    """Parse OMIM inheritance field into a standardized pattern.

    The genemap2 inheritance column may contain abbreviations like
    ``AD``, ``AR``, ``XLR``, or full text. Returns the first
    recognized pattern.
    """
    if not inheritance_raw:
        return None

    # Try direct lookup of common abbreviations
    stripped = inheritance_raw.strip()
    if stripped in _OMIM_INHERITANCE_ABBREVS:
        return _OMIM_INHERITANCE_ABBREVS[stripped]

    # Split on common delimiters and try each token
    for token in stripped.replace(";", ",").split(","):
        token = token.strip()
        if token in _OMIM_INHERITANCE_ABBREVS:
            return _OMIM_INHERITANCE_ABBREVS[token]

    # Try matching against full text patterns
    lower = stripped.lower()
    if "autosomal dominant" in lower:
        return "Autosomal dominant"
    if "autosomal recessive" in lower:
        return "Autosomal recessive"
    if "x-linked recessive" in lower:
        return "X-linked recessive"
    if "x-linked dominant" in lower:
        return "X-linked dominant"
    if "x-linked" in lower:
        return "X-linked"

    return None


# ── Genemap2 parsing ─────────────────────────────────────────────────────


def parse_genemap2_text(text: str) -> tuple[list[OMIMRecord], OMIMLoadStats]:
    """Parse OMIM genemap2 text content into records.

    The genemap2 file is tab-separated with ``#``-prefixed comments.
    Key columns (0-indexed):
    - 5: Gene/Locus
    - 8: Gene Symbols (pipe-separated)
    - 12: Phenotypes (semicolon-separated phenotype entries)

    Each phenotype entry has the format:
    ``Phenotype description, MIM_number (mapping_key), Inheritance``

    Args:
        text: Full genemap2 file content.

    Returns:
        Tuple of (list of OMIMRecord, OMIMLoadStats).
    """
    stats = OMIMLoadStats()
    records: list[OMIMRecord] = []

    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            stats.skipped_comments += 1
            continue

        stats.total_lines += 1
        fields = line.split("\t")

        if len(fields) < 13:
            continue

        # Gene symbols column (index 8) — may be pipe-separated
        gene_symbols_raw = fields[8].strip() if len(fields) > 8 else ""
        if not gene_symbols_raw:
            # Fallback to Gene/Locus (index 5)
            gene_symbols_raw = fields[5].strip() if len(fields) > 5 else ""

        if not gene_symbols_raw:
            stats.skipped_no_gene += 1
            continue

        # Use the first gene symbol
        gene_symbol = gene_symbols_raw.split(",")[0].strip()
        if not gene_symbol:
            stats.skipped_no_gene += 1
            continue

        # MIM number (index 5)
        mim_number = fields[5].strip() if len(fields) > 5 else ""

        # Phenotypes column (index 12)
        phenotypes_raw = fields[12].strip() if len(fields) > 12 else ""
        if not phenotypes_raw:
            stats.skipped_no_phenotype += 1
            continue

        # Parse individual phenotype entries (semicolon-separated)
        for pheno_entry in phenotypes_raw.split(";"):
            pheno_entry = pheno_entry.strip()
            if not pheno_entry:
                continue

            record = _parse_phenotype_entry(pheno_entry, gene_symbol, mim_number)
            if record:
                records.append(record)

    stats.records_loaded = len(records)
    return records, stats


def _parse_phenotype_entry(entry: str, gene_symbol: str, mim_number: str) -> OMIMRecord | None:
    """Parse a single OMIM phenotype entry string.

    Format: ``Phenotype text, MIM_number (mapping_key), Inheritance``
    or just: ``Phenotype text``
    """
    if not entry.strip():
        return None

    # Extract phenotype MIM and mapping key if present
    phenotype_mim: str | None = None
    mapping_key: int | None = None
    inheritance: str | None = None
    phenotype_text = entry.strip()

    # Try to find MIM number pattern: 6-digit number
    # and mapping key pattern: (N) where N is 1-4
    parts = entry.rsplit(",", 2)

    if len(parts) >= 2:
        # Last part might be inheritance
        last = parts[-1].strip()
        remaining = parts[:-1]

        # Check if last part looks like inheritance
        if _parse_inheritance(last):
            inheritance = _parse_inheritance(last)
            # Rejoin the rest as phenotype text
            phenotype_text = ",".join(remaining).strip()

            # Check if the new last part has MIM and mapping key
            if len(remaining) >= 2:
                second_last = remaining[-1].strip()
                _try_extract_mim_and_key(second_last, phenotype_text, gene_symbol)
        else:
            phenotype_text = entry.strip()

    # Try to extract MIM number from the entry
    # Pattern: number at end after comma, possibly with (N)
    import re

    mim_match = re.search(r"\b(\d{6})\s*\((\d)\)\s*$", phenotype_text)
    if mim_match:
        phenotype_mim = mim_match.group(1)
        try:
            mapping_key = int(mim_match.group(2))
        except ValueError:
            pass
        phenotype_text = phenotype_text[: mim_match.start()].rstrip(", ")

    # Clean up leading special characters
    phenotype_text = phenotype_text.lstrip("?{[]} ")

    if not phenotype_text:
        return None

    return OMIMRecord(
        gene_symbol=gene_symbol,
        mim_number=mim_number,
        phenotype_text=phenotype_text,
        phenotype_mim=phenotype_mim,
        inheritance=inheritance,
        mapping_key=mapping_key,
    )


def _try_extract_mim_and_key(
    text: str, phenotype_text: str, gene_symbol: str
) -> tuple[str | None, int | None]:
    """Try to extract MIM number and mapping key from a text fragment."""
    import re

    match = re.search(r"(\d{6})\s*\((\d)\)", text)
    if match:
        return match.group(1), int(match.group(2))
    return None, None


# ── OMIM API interaction ─────────────────────────────────────────────────


def fetch_omim_genemap2(
    api_key: str,
    *,
    timeout: float = 120.0,
) -> str:
    """Fetch the genemap2 file from the OMIM API.

    Args:
        api_key: OMIM API key.
        timeout: HTTP timeout seconds.

    Returns:
        Raw text content of genemap2.

    Raises:
        httpx.HTTPStatusError: On non-2xx response.
        ValueError: If API key is empty.
    """
    if not api_key:
        raise ValueError("OMIM API key is required")

    url = f"{OMIM_API_BASE}{OMIM_GENEMAP2_ENDPOINT}"

    logger.info("omim_fetch_start")

    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(timeout, connect=30.0),
    ) as client:
        response = client.get(
            url,
            headers={"ApiKey": api_key},
        )
        response.raise_for_status()

    logger.info(
        "omim_fetch_complete",
        size_bytes=len(response.text),
    )
    return response.text


# ── Load into DB ─────────────────────────────────────────────────────────


def _records_to_rows(records: list[OMIMRecord]) -> list[dict]:
    """Convert OMIM records to insert-ready row dicts."""
    rows: list[dict] = []
    for rec in records:
        disease_id = f"OMIM:{rec.phenotype_mim}" if rec.phenotype_mim else f"OMIM:{rec.mim_number}"
        rows.append(
            {
                "gene_symbol": rec.gene_symbol,
                "disease_name": rec.phenotype_text,
                "disease_id": disease_id,
                "hpo_terms": None,  # OMIM doesn't provide HPO terms directly
                "source": "omim",
                "inheritance": rec.inheritance,
            }
        )
    return rows


def load_omim_enrichment(
    records: list[OMIMRecord],
    engine: sa.Engine,
    *,
    clear_existing: bool = True,
) -> int:
    """Load OMIM records into the gene_phenotype table.

    Only touches rows with source='omim'. Existing MONDO/HPO data
    is preserved.

    Args:
        records: List of OMIMRecord objects.
        engine: SQLAlchemy engine for reference.db.
        clear_existing: Whether to DELETE existing OMIM rows first.

    Returns:
        Number of rows loaded.
    """
    rows = _records_to_rows(records)
    if not rows:
        return 0

    with engine.begin() as conn:
        if clear_existing:
            conn.execute(gene_phenotype.delete().where(gene_phenotype.c.source == "omim"))

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            conn.execute(gene_phenotype.insert(), batch)

    _wal_checkpoint(engine)
    return len(rows)


def _wal_checkpoint(engine: sa.Engine) -> None:
    """Run WAL checkpoint if the engine is file-backed."""
    url = str(engine.url)
    if url == "sqlite://" or ":memory:" in url:
        return
    with engine.connect() as conn:
        conn.execute(sa.text("PRAGMA wal_checkpoint(TRUNCATE)"))
        conn.commit()


def record_omim_version(
    engine: sa.Engine,
    *,
    version: str,
    records_count: int = 0,
) -> None:
    """Insert or update the OMIM version in database_versions."""
    with engine.begin() as conn:
        existing = conn.execute(
            sa.select(database_versions.c.db_name).where(database_versions.c.db_name == "omim")
        ).first()

        now = datetime.now(UTC)
        values = {
            "version": version,
            "downloaded_at": now,
        }

        if existing:
            conn.execute(
                database_versions.update()
                .where(database_versions.c.db_name == "omim")
                .values(**values)
            )
        else:
            conn.execute(database_versions.insert().values(db_name="omim", **values))


# ── Full enrichment pipeline ─────────────────────────────────────────────


def enrich_with_omim(
    engine: sa.Engine,
    api_key: str,
    *,
    timeout: float = 120.0,
) -> OMIMLoadStats:
    """Full pipeline: fetch genemap2, parse, and load OMIM enrichment.

    MONDO/HPO data is preserved. Only adds/replaces OMIM-source rows.

    Args:
        engine: SQLAlchemy engine for reference.db.
        api_key: OMIM API key.
        timeout: HTTP timeout seconds.

    Returns:
        OMIMLoadStats with counts.

    Raises:
        ValueError: If API key is empty.
    """
    if not api_key:
        raise ValueError("OMIM API key is required for enrichment")

    # Fetch genemap2
    text = fetch_omim_genemap2(api_key, timeout=timeout)

    # Parse
    records, stats = parse_genemap2_text(text)

    # Load
    loaded = load_omim_enrichment(records, engine)
    stats.records_loaded = loaded

    # Count distinct genes enriched
    stats.genes_enriched = len({r.gene_symbol for r in records})

    # Record version
    version = datetime.now(UTC).strftime("%Y%m%d")
    record_omim_version(engine, version=version, records_count=loaded)

    logger.info(
        "omim_enrichment_complete",
        records=loaded,
        genes=stats.genes_enriched,
    )

    return stats
