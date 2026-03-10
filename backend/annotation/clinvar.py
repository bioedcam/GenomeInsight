"""ClinVar VCF downloader and SQLite loader.

Downloads the ClinVar VCF (GRCh37) from NCBI FTP, parses variant records,
and bulk-loads them into the ``clinvar_variants`` table in reference.db.

Usage::

    from backend.annotation.clinvar import download_clinvar_vcf, load_clinvar_vcf

    vcf_path = download_clinvar_vcf(dest_dir)
    stats = load_clinvar_vcf(vcf_path, engine)
"""

from __future__ import annotations

import gzip
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import sqlalchemy as sa
import structlog

from backend.db.tables import clinvar_variants, database_versions

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

logger = structlog.get_logger(__name__)

# NCBI FTP URL for ClinVar VCF (GRCh37/hg19)
CLINVAR_VCF_URL = (
    "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh37/clinvar.vcf.gz"
)

# Batch size for bulk inserts (executemany)
BATCH_SIZE = 10_000

# Map ClinVar CLNREVSTAT values to review star counts
REVIEW_STATUS_STARS: dict[str, int] = {
    "practice_guideline": 4,
    "reviewed_by_expert_panel": 3,
    "criteria_provided,_multiple_submitters,_no_conflicts": 2,
    "criteria_provided,_single_submitter": 1,
    "criteria_provided,_conflicting_interpretations": 1,
    "criteria_provided,_conflicting_classifications": 1,
    "no_assertion_criteria_provided": 0,
    "no_assertion_provided": 0,
    "no_classification_provided": 0,
    "no_classification_for_the_single_variant": 0,
}

# Chromosomes we accept (matching 23andMe scope)
VALID_CHROMS = {str(i) for i in range(1, 23)} | {"X", "Y", "MT"}


class SkipReason:
    """Enum-like constants for why a VCF line was skipped."""

    NO_RSID = "no_rsid"
    INVALID_CHROM = "invalid_chrom"
    MALFORMED = "malformed"


@dataclass
class LoadStats:
    """Statistics from a ClinVar VCF load operation."""

    total_lines: int = 0
    variants_loaded: int = 0
    skipped_no_rsid: int = 0
    skipped_invalid_chrom: int = 0
    skipped_malformed: int = 0
    file_date: str | None = None
    sha256: str | None = None


@dataclass
class ClinVarRecord:
    """A single parsed ClinVar variant record."""

    rsid: str
    chrom: str
    pos: int
    ref: str
    alt: str
    significance: str | None = None
    review_stars: int = 0
    accession: str | None = None
    conditions: str | None = None
    gene_symbol: str | None = None
    variation_id: int | None = None


def _parse_info_field(info: str) -> dict[str, str]:
    """Parse a VCF INFO field into a dict of key=value pairs.

    Flag fields (no ``=``) are stored with value ``""``.
    """
    result: dict[str, str] = {}
    for part in info.split(";"):
        if "=" in part:
            key, _, value = part.partition("=")
            result[key] = value
        else:
            result[part] = ""
    return result


def _review_status_to_stars(revstat: str) -> int:
    """Convert a CLNREVSTAT string to a review star count (0-4).

    CLNREVSTAT may contain multiple comma-separated tokens that together
    form a single status key (e.g. ``criteria_provided,_single_submitter``).
    """
    # Normalize underscores (some versions use spaces)
    normalized = revstat.strip().replace(" ", "_").lower()
    if normalized in REVIEW_STATUS_STARS:
        return REVIEW_STATUS_STARS[normalized]
    # Try the raw value
    if revstat in REVIEW_STATUS_STARS:
        return REVIEW_STATUS_STARS[revstat]
    return 0


def _normalize_chrom(chrom: str) -> str | None:
    """Normalize chromosome name. Returns None for invalid chromosomes."""
    c = chrom.removeprefix("chr").upper()
    if c in VALID_CHROMS:
        return c
    return None


def _extract_gene_symbol(geneinfo: str | None) -> str | None:
    """Extract gene symbol from GENEINFO field (format: ``GENE:GENEID``)."""
    if not geneinfo:
        return None
    # May have multiple genes separated by |
    first_gene = geneinfo.split("|")[0]
    symbol = first_gene.split(":")[0]
    return symbol if symbol else None


def parse_clinvar_vcf_line(line: str) -> tuple[ClinVarRecord | None, str | None]:
    """Parse a single non-header VCF line into a ClinVarRecord.

    Returns:
        Tuple of (record, skip_reason). If record is None, skip_reason
        indicates why the line was skipped.
    """
    parts = line.rstrip("\n\r").split("\t")
    if len(parts) < 8:
        return None, SkipReason.MALFORMED

    chrom_raw, pos_str, var_id, ref, alt, _qual, _filt, info_str = parts[:8]

    # Normalize chromosome
    chrom = _normalize_chrom(chrom_raw)
    if chrom is None:
        return None, SkipReason.INVALID_CHROM

    # Validate position
    try:
        pos = int(pos_str)
    except (ValueError, TypeError):
        return None, SkipReason.MALFORMED

    # Parse INFO
    info = _parse_info_field(info_str)

    # Extract rsid — require RS field
    rs_val = info.get("RS")
    if not rs_val:
        return None, SkipReason.NO_RSID
    rsid = f"rs{rs_val}"

    # Parse variation ID from the ID column
    variation_id: int | None = None
    try:
        variation_id = int(var_id)
    except (ValueError, TypeError):
        pass

    # Clinical significance
    significance = info.get("CLNSIG")
    if significance:
        # Replace underscores with spaces for readability,
        # but keep the standard ClinVar casing
        significance = significance.replace("_", " ").strip()
        # Use first significance if multiple separated by /
        # (multi-allelic sites)
        if "/" in significance:
            significance = significance.split("/")[0].strip()

    # Review stars
    revstat = info.get("CLNREVSTAT", "")
    review_stars = _review_status_to_stars(revstat)

    # Accession (VCV preferred, fall back to CLNACC)
    accession = None
    clnvcid = info.get("CLNVCID")
    if clnvcid:
        accession = f"VCV{clnvcid.zfill(9)}"
    elif "CLNACC" in info:
        accession = info["CLNACC"].split("|")[0]

    # Conditions / disease name
    conditions = info.get("CLNDN")
    if conditions:
        conditions = conditions.replace("_", " ")

    # Gene symbol
    gene_symbol = _extract_gene_symbol(info.get("GENEINFO", ""))

    # Handle multi-allelic ALTs: create record for first ALT only
    # (ClinVar VCF typically has one ALT per line)
    first_alt = alt.split(",")[0]

    record = ClinVarRecord(
        rsid=rsid,
        chrom=chrom,
        pos=pos,
        ref=ref,
        alt=first_alt,
        significance=significance,
        review_stars=review_stars,
        accession=accession,
        conditions=conditions,
        gene_symbol=gene_symbol,
        variation_id=variation_id,
    )
    return record, None


def _extract_file_date(header_lines: list[str]) -> str | None:
    """Extract the fileDate from VCF header lines."""
    for line in header_lines:
        if line.startswith("##fileDate="):
            return line.split("=", 1)[1].strip()
    return None


def _record_to_dict(record: ClinVarRecord) -> dict:
    """Convert a ClinVarRecord to a dict for database insertion."""
    return {
        "rsid": record.rsid,
        "chrom": record.chrom,
        "pos": record.pos,
        "ref": record.ref,
        "alt": record.alt,
        "significance": record.significance,
        "review_stars": record.review_stars,
        "accession": record.accession,
        "conditions": record.conditions,
        "gene_symbol": record.gene_symbol,
        "variation_id": record.variation_id,
    }


def iter_clinvar_vcf(
    vcf_path: Path,
    *,
    progress_callback: Callable[[int], None] | None = None,
) -> Iterator[tuple[dict, LoadStats]]:
    """Iterate over ClinVar VCF rows lazily, yielding (row_dict, stats).

    The final stats are accumulated across all yields. Callers should use
    the stats from the last yielded item for final counts.

    Args:
        vcf_path: Path to the VCF or VCF.gz file.
        progress_callback: Optional callback called with the count of
            parsed lines at regular intervals.

    Yields:
        Tuple of (row dict ready for insert, running LoadStats).
    """
    stats = LoadStats()
    header_lines: list[str] = []

    open_fn = gzip.open if vcf_path.suffix == ".gz" else open
    with open_fn(vcf_path, "rt", encoding="utf-8") as fh:  # type: ignore[call-overload]
        for line in fh:
            if line.startswith("##"):
                header_lines.append(line.rstrip())
                continue
            if line.startswith("#"):
                continue

            stats.total_lines += 1

            record, skip_reason = parse_clinvar_vcf_line(line)
            if record is None:
                if skip_reason == SkipReason.NO_RSID:
                    stats.skipped_no_rsid += 1
                elif skip_reason == SkipReason.INVALID_CHROM:
                    stats.skipped_invalid_chrom += 1
                else:
                    stats.skipped_malformed += 1
                continue

            stats.variants_loaded += 1
            yield _record_to_dict(record), stats

            if progress_callback and stats.total_lines % 10_000 == 0:
                progress_callback(stats.total_lines)

    stats.file_date = _extract_file_date(header_lines)


def parse_clinvar_vcf(
    vcf_path: Path,
    *,
    progress_callback: Callable[[int], None] | None = None,
) -> tuple[list[dict], LoadStats]:
    """Parse a ClinVar VCF file (plain or gzipped) and return rows + stats.

    For small files / testing. For large files, prefer ``iter_clinvar_vcf``
    with ``load_clinvar_from_iter`` to avoid loading all rows into memory.

    Args:
        vcf_path: Path to the VCF or VCF.gz file.
        progress_callback: Optional callback called with the count of
            parsed lines at regular intervals.

    Returns:
        Tuple of (list of row dicts ready for insert, LoadStats).
    """
    rows: list[dict] = []
    stats = LoadStats()
    for row, stats in iter_clinvar_vcf(vcf_path, progress_callback=progress_callback):
        rows.append(row)
    return rows, stats


def _compute_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _batched(iterator: Iterator[dict], size: int) -> Iterator[list[dict]]:
    """Yield successive batches of ``size`` items from an iterator."""
    while True:
        batch = list(islice(iterator, size))
        if not batch:
            break
        yield batch


def _wal_checkpoint(engine: sa.Engine) -> None:
    """Run WAL checkpoint if the engine is file-backed (not in-memory)."""
    url = str(engine.url)
    if url == "sqlite://" or ":memory:" in url:
        return
    with engine.connect() as conn:
        conn.execute(sa.text("PRAGMA wal_checkpoint(TRUNCATE)"))
        conn.commit()


def load_clinvar_into_db(
    rows: list[dict],
    engine: sa.Engine,
    *,
    stats: LoadStats | None = None,
    clear_existing: bool = True,
) -> LoadStats:
    """Bulk-load parsed ClinVar rows into the clinvar_variants table.

    Args:
        rows: List of dicts matching clinvar_variants columns.
        engine: SQLAlchemy engine for reference.db.
        stats: Optional LoadStats to update (if None, a new one is created).
        clear_existing: Whether to DELETE all existing rows first.

    Returns:
        Updated LoadStats with variants_loaded count.
    """
    if stats is None:
        stats = LoadStats(variants_loaded=len(rows))

    with engine.begin() as conn:
        if clear_existing:
            conn.execute(clinvar_variants.delete())

        # Bulk insert in batches
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            conn.execute(clinvar_variants.insert(), batch)

    # WAL checkpoint after bulk load (outside transaction)
    _wal_checkpoint(engine)

    logger.info(
        "clinvar_loaded",
        variants=stats.variants_loaded,
    )

    return stats


def load_clinvar_from_iter(
    row_iter: Iterator[tuple[dict, LoadStats]],
    engine: sa.Engine,
    *,
    clear_existing: bool = True,
) -> LoadStats:
    """Stream-load ClinVar rows from an iterator into the database.

    Memory-efficient: only holds one batch at a time, suitable for
    the full ClinVar VCF (~1.5M variants).

    Args:
        row_iter: Iterator yielding (row_dict, running_stats) tuples,
            as produced by ``iter_clinvar_vcf``.
        engine: SQLAlchemy engine for reference.db.
        clear_existing: Whether to DELETE all existing rows first.

    Returns:
        Final LoadStats.
    """
    stats = LoadStats()

    # Strip stats from iterator to get plain row dicts
    def rows_only() -> Iterator[dict]:
        nonlocal stats
        for row, stats in row_iter:
            yield row

    with engine.begin() as conn:
        if clear_existing:
            conn.execute(clinvar_variants.delete())

        for batch in _batched(rows_only(), BATCH_SIZE):
            conn.execute(clinvar_variants.insert(), batch)

    # WAL checkpoint after bulk load (outside transaction)
    _wal_checkpoint(engine)

    logger.info(
        "clinvar_loaded",
        variants=stats.variants_loaded,
    )

    return stats


def record_clinvar_version(
    engine: sa.Engine,
    *,
    version: str,
    file_path: str | None = None,
    file_size_bytes: int | None = None,
    checksum: str | None = None,
) -> None:
    """Insert or update the ClinVar version in the database_versions table."""
    with engine.begin() as conn:
        # Check if a record exists
        existing = conn.execute(
            sa.select(database_versions.c.db_name).where(
                database_versions.c.db_name == "clinvar"
            )
        ).first()

        now = datetime.now(UTC)

        if existing:
            conn.execute(
                database_versions.update()
                .where(database_versions.c.db_name == "clinvar")
                .values(
                    version=version,
                    file_path=file_path,
                    file_size_bytes=file_size_bytes,
                    downloaded_at=now,
                    checksum_sha256=checksum,
                )
            )
        else:
            conn.execute(
                database_versions.insert().values(
                    db_name="clinvar",
                    version=version,
                    file_path=file_path,
                    file_size_bytes=file_size_bytes,
                    downloaded_at=now,
                    checksum_sha256=checksum,
                )
            )


def download_clinvar_vcf(
    dest_dir: Path,
    *,
    url: str = CLINVAR_VCF_URL,
    progress_callback: Callable[[int, int | None], None] | None = None,
    timeout: float = 300.0,
) -> Path:
    """Download the ClinVar VCF (GRCh37) from NCBI FTP.

    Writes to a temporary file and renames on success to avoid
    leaving partial files on failure.

    Args:
        dest_dir: Directory to save the downloaded file.
        url: Override URL (useful for testing).
        progress_callback: Called with (bytes_downloaded, total_bytes).
            ``total_bytes`` may be None if Content-Length is absent.
        timeout: HTTP request timeout in seconds.

    Returns:
        Path to the downloaded .vcf.gz file.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / "clinvar_GRCh37.vcf.gz"
    tmp_path = dest_dir / "clinvar_GRCh37.vcf.gz.tmp"

    logger.info("clinvar_download_start", url=url)

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(timeout, connect=30.0),
        ) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()

                total_bytes: int | None = None
                content_length = response.headers.get("Content-Length")
                if content_length:
                    total_bytes = int(content_length)

                with open(tmp_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=65536):
                        f.write(chunk)
                        if progress_callback:
                            progress_callback(
                                response.num_bytes_downloaded, total_bytes
                            )

        # Atomic rename on success
        tmp_path.rename(dest_path)
    except BaseException:
        # Clean up partial temp file on any failure
        tmp_path.unlink(missing_ok=True)
        raise

    logger.info("clinvar_download_complete", path=str(dest_path))
    return dest_path


def download_and_load_clinvar(
    engine: sa.Engine,
    dest_dir: Path,
    *,
    url: str = CLINVAR_VCF_URL,
    download_progress: Callable[[int, int | None], None] | None = None,
    parse_progress: Callable[[int], None] | None = None,
    timeout: float = 300.0,
) -> LoadStats:
    """Full pipeline: download ClinVar VCF, parse, and load into reference.db.

    Uses streaming parse + batch insert to keep memory usage low.

    Args:
        engine: SQLAlchemy engine for reference.db.
        dest_dir: Directory for downloaded files.
        url: ClinVar VCF URL (override for testing).
        download_progress: Callback for download progress.
        parse_progress: Callback for parse progress.
        timeout: HTTP timeout in seconds.

    Returns:
        LoadStats with counts and metadata.
    """
    # Download
    vcf_path = download_clinvar_vcf(
        dest_dir,
        url=url,
        progress_callback=download_progress,
        timeout=timeout,
    )

    # Compute checksum
    sha256 = _compute_sha256(vcf_path)

    # Stream parse + load
    row_iter = iter_clinvar_vcf(vcf_path, progress_callback=parse_progress)
    stats = load_clinvar_from_iter(row_iter, engine)
    stats.sha256 = sha256

    # Record version
    version = stats.file_date or datetime.now(UTC).strftime("%Y%m%d")
    record_clinvar_version(
        engine,
        version=version,
        file_path=str(vcf_path),
        file_size_bytes=vcf_path.stat().st_size,
        checksum=sha256,
    )

    return stats
