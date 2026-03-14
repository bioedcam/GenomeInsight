"""GWAS Catalog TSV downloader, EFO-filtered SQLite loader, and annotation lookup.

Downloads the GWAS Catalog associations TSV from the EBI GWAS Catalog,
filters to a whitelist of EFO trait terms relevant to GenomeInsight modules
(nutrigenomics, fitness, sleep, skin, allergy, traits), and bulk-loads
into the ``gwas_associations`` table in reference.db.

Also provides annotation lookup: given a list of rsids, returns matching
GWAS associations grouped by rsid.

Usage::

    from backend.annotation.gwas import download_gwas_catalog, load_gwas_into_db
    from backend.annotation.gwas import lookup_gwas_by_rsids

    tsv_path = download_gwas_catalog(dest_dir)
    stats = load_gwas_into_db(tsv_path, engine)

    # Annotation lookup
    matches = lookup_gwas_by_rsids(["rs429358", "rs7412"], engine)
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import sqlalchemy as sa
import structlog

from backend.db.tables import database_versions, gwas_associations

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

logger = structlog.get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

# GWAS Catalog associations TSV (all associations, alternative format)
GWAS_CATALOG_URL = (
    "https://www.ebi.ac.uk/gwas/api/search/downloads/alternative"
)

# Batch size for bulk inserts (executemany)
BATCH_SIZE = 10_000

# Batch size for rsid lookups (stay under SQLite 999-variable limit)
LOOKUP_BATCH_SIZE = 500

# Valid chromosomes (matching 23andMe scope)
VALID_CHROMS = {str(i) for i in range(1, 23)} | {"X", "Y", "MT"}

# rsid pattern
_RSID_PATTERN = re.compile(r"^rs\d+$")

# ── EFO Term Whitelist ────────────────────────────────────────────────────
# Each module defines a whitelist of EFO trait terms (case-insensitive
# substring matching against GWAS Catalog MAPPED_TRAIT / DISEASE/TRAIT).
# PRD §3.4b: "GWAS Catalog EFO filtering is mandatory."

# Terms are grouped by module for clarity but merged into a single set.

_NUTRIGENOMICS_TERMS = frozenset({
    "folate",
    "homocysteine",
    "vitamin d",
    "vitamin b12",
    "vitamin b6",
    "omega-3",
    "omega-6",
    "fatty acid",
    "iron",
    "ferritin",
    "transferrin",
    "lactose",
    "lactase",
    "caffeine",
    "caffeine consumption",
    "caffeine metabolism",
    "alcohol consumption",
    "alcohol dependence",
    "body mass index",
    "obesity",
    "type 2 diabetes",
    "triglyceride",
    "hdl cholesterol",
    "ldl cholesterol",
    "total cholesterol",
    "blood pressure",
    "selenium",
    "zinc",
    "magnesium",
    "calcium",
    "celiac",
    "gluten",
})

_FITNESS_TERMS = frozenset({
    "muscle",
    "exercise",
    "physical activity",
    "endurance",
    "power",
    "aerobic capacity",
    "vo2max",
    "sprint",
    "grip strength",
    "bone mineral density",
    "tendon",
    "ligament",
    "injury",
    "recovery",
    "athletic",
    "muscle fiber",
    "creatine kinase",
    "lactate",
})

_SLEEP_TERMS = frozenset({
    "sleep",
    "insomnia",
    "chronotype",
    "circadian",
    "restless legs",
    "sleep duration",
    "sleep apnea",
    "melatonin",
    "narcolepsy",
    "morningness",
    "eveningness",
})

_SKIN_TERMS = frozenset({
    "skin",
    "pigmentation",
    "melanoma",
    "hair color",
    "eye color",
    "freckling",
    "sun sensitivity",
    "sunburn",
    "psoriasis",
    "eczema",
    "dermatitis",
    "acne",
    "aging",
    "wrinkle",
    "vitiligo",
    "tanning",
    "skin cancer",
    "basal cell carcinoma",
    "squamous cell",
    "collagen",
})

_ALLERGY_TERMS = frozenset({
    "allergy",
    "allergic",
    "asthma",
    "atopic",
    "ige",
    "eosinophil",
    "rhinitis",
    "urticaria",
    "anaphylaxis",
    "drug hypersensitivity",
    "food allergy",
    "histamine",
    "mast cell",
    "celiac disease",
    "inflammatory bowel",
    "crohn",
    "ulcerative colitis",
})

_TRAITS_TERMS = frozenset({
    "educational attainment",
    "cognitive",
    "intelligence",
    "neuroticism",
    "extraversion",
    "risk tolerance",
    "risk taking",
    "adhd",
    "attention deficit",
    "depression",
    "anxiety",
    "schizophrenia",
    "bipolar",
    "personality",
    "memory",
    "reaction time",
    "openness",
    "agreeableness",
    "conscientiousness",
    "subjective well-being",
    "loneliness",
    "pain sensitivity",
    "reward",
})

# Merged whitelist for filtering
EFO_WHITELIST: frozenset[str] = (
    _NUTRIGENOMICS_TERMS
    | _FITNESS_TERMS
    | _SLEEP_TERMS
    | _SKIN_TERMS
    | _ALLERGY_TERMS
    | _TRAITS_TERMS
)

# Module-level groupings for downstream module use
EFO_MODULES: dict[str, frozenset[str]] = {
    "nutrigenomics": _NUTRIGENOMICS_TERMS,
    "fitness": _FITNESS_TERMS,
    "sleep": _SLEEP_TERMS,
    "skin": _SKIN_TERMS,
    "allergy": _ALLERGY_TERMS,
    "traits": _TRAITS_TERMS,
}


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass
class GWASLoadStats:
    """Statistics from a GWAS Catalog load operation."""

    total_lines: int = 0
    associations_loaded: int = 0
    skipped_no_rsid: int = 0
    skipped_invalid_chrom: int = 0
    skipped_no_trait: int = 0
    skipped_efo_filter: int = 0
    skipped_malformed: int = 0
    file_date: str | None = None
    sha256: str | None = None


@dataclass
class GWASAnnotation:
    """A single GWAS association for a variant."""

    rsid: str
    trait: str
    p_value: float | None
    odds_ratio: float | None
    beta: float | None
    risk_allele: str | None
    pubmed_id: str | None
    study: str | None
    sample_size: int | None


@dataclass
class GWASAnnotationSet:
    """All GWAS associations for a single variant (may have multiple traits)."""

    rsid: str
    associations: list[GWASAnnotation] = field(default_factory=list)

    @property
    def traits(self) -> list[str]:
        """Return all unique trait names."""
        return list(dict.fromkeys(a.trait for a in self.associations))

    @property
    def best_p_value(self) -> float | None:
        """Return the smallest (most significant) p-value."""
        p_values = [a.p_value for a in self.associations if a.p_value is not None]
        return min(p_values) if p_values else None


# ── Parsing helpers ───────────────────────────────────────────────────────


def _normalize_chrom(chrom: str) -> str | None:
    """Normalize chromosome name. Returns None for invalid chromosomes."""
    c = chrom.strip().removeprefix("chr").upper()
    if c in VALID_CHROMS:
        return c
    return None


def _parse_float(value: str | None) -> float | None:
    """Safely parse a float, returning None on failure."""
    if not value or value.strip() in ("", "NR", "NA", "-"):
        return None
    try:
        return float(value.strip())
    except (ValueError, TypeError):
        return None


def _parse_int(value: str | None) -> int | None:
    """Safely parse an integer, returning None on failure."""
    if not value or value.strip() in ("", "NR", "NA", "-"):
        return None
    try:
        # Handle comma-separated numbers (e.g. "74,046")
        return int(value.strip().replace(",", ""))
    except (ValueError, TypeError):
        return None


def _extract_rsid(snp_field: str) -> str | None:
    """Extract a valid rsid from the GWAS Catalog SNPs column.

    The SNPs column may contain multiple SNPs separated by '; ' or ' x ',
    or haplotype notations. We extract the first valid rsid.
    """
    if not snp_field:
        return None

    # Split on common delimiters
    for sep in (";", " x ", ","):
        if sep in snp_field:
            parts = snp_field.split(sep)
            for part in parts:
                candidate = part.strip().lower()
                if _RSID_PATTERN.match(candidate):
                    return candidate
            return None

    # Single value
    candidate = snp_field.strip().lower()
    if _RSID_PATTERN.match(candidate):
        return candidate
    return None


def _extract_risk_allele(strongest_snp_risk_allele: str) -> str | None:
    """Extract risk allele from 'STRONGEST SNP-RISK ALLELE' column.

    Format is typically 'rs12345-A' or 'rs12345-?' — extract the allele
    after the last hyphen.
    """
    if not strongest_snp_risk_allele:
        return None
    parts = strongest_snp_risk_allele.strip().rsplit("-", 1)
    if len(parts) == 2:
        allele = parts[1].strip().upper()
        if allele and allele != "?" and len(allele) <= 10:
            return allele
    return None


def _trait_matches_whitelist(trait: str) -> bool:
    """Check if a trait string matches any EFO whitelist term.

    Uses case-insensitive substring matching — a GWAS Catalog trait
    like "Type 2 diabetes mellitus" matches the whitelist term
    "type 2 diabetes".
    """
    trait_lower = trait.lower()
    return any(term in trait_lower for term in EFO_WHITELIST)


# ── GWAS Catalog TSV column mapping ──────────────────────────────────────
# GWAS Catalog alternative format TSV columns (as of 2024):
# https://www.ebi.ac.uk/gwas/docs/file-downloads

# Key columns we use (0-indexed):
_COL_PUBMEDID = "PUBMEDID"
_COL_STUDY = "STUDY"
_COL_DISEASE_TRAIT = "DISEASE/TRAIT"
_COL_INITIAL_SAMPLE = "INITIAL SAMPLE SIZE"
_COL_CHR_ID = "CHR_ID"
_COL_CHR_POS = "CHR_POS"
_COL_SNPS = "SNPS"
_COL_STRONGEST_ALLELE = "STRONGEST SNP-RISK ALLELE"
_COL_PVALUE = "P-VALUE"
_COL_OR_BETA = "OR or BETA"
_COL_CI_95 = "95% CI (TEXT)"
_COL_MAPPED_TRAIT = "MAPPED_TRAIT"


def _parse_sample_size(initial_sample: str | None) -> int | None:
    """Extract total sample size from INITIAL SAMPLE SIZE field.

    Format varies: "1,234 European ancestry cases, 5,678 controls"
    We extract all numbers and sum them.
    """
    if not initial_sample:
        return None
    numbers = re.findall(r"[\d,]+", initial_sample)
    if not numbers:
        return None
    total = 0
    for n in numbers:
        try:
            total += int(n.replace(",", ""))
        except ValueError:
            continue
    return total if total > 0 else None


def _is_odds_ratio(ci_text: str | None, or_beta_val: float | None) -> bool:
    """Heuristic to distinguish OR from beta in the 'OR or BETA' column.

    If the 95% CI text contains language like "increase"/"decrease"/"unit",
    it's a beta coefficient. If it only has brackets like [1.2-1.5], it's OR.
    """
    if ci_text:
        ci_lower = ci_text.lower().strip()
        # "increase" / "decrease" / "unit" / "sd" language suggests beta
        # (check before brackets — CI for betas also has brackets)
        if any(w in ci_lower for w in ("increase", "decrease", "unit", "sd")):
            return False
        # CI text with brackets only (no beta language) → OR
        if "[" in ci_lower or "(" in ci_lower:
            return True
    # Fallback: if value is between 0.1 and 20, treat as OR
    if or_beta_val is not None:
        return 0.1 <= abs(or_beta_val) <= 20
    return True


def parse_gwas_tsv_row(
    row: dict[str, str],
) -> tuple[dict | None, str | None]:
    """Parse a single GWAS Catalog TSV row into a dict for insertion.

    Args:
        row: Dict from csv.DictReader with GWAS Catalog column names.

    Returns:
        Tuple of (row_dict, skip_reason). If row_dict is None,
        skip_reason indicates why the row was skipped.
    """
    # Extract rsid
    rsid = _extract_rsid(row.get(_COL_SNPS, ""))
    if not rsid:
        return None, "no_rsid"

    # Trait — try MAPPED_TRAIT first (standardized), fall back to DISEASE/TRAIT
    trait = (row.get(_COL_MAPPED_TRAIT) or row.get(_COL_DISEASE_TRAIT) or "").strip()
    if not trait:
        return None, "no_trait"

    # EFO filter
    if not _trait_matches_whitelist(trait):
        return None, "efo_filter"

    # Chromosome & position
    chrom_raw = row.get(_COL_CHR_ID, "")
    chrom = _normalize_chrom(chrom_raw) if chrom_raw.strip() else None
    pos = _parse_int(row.get(_COL_CHR_POS))

    # p-value
    p_value = _parse_float(row.get(_COL_PVALUE))

    # OR or Beta
    or_beta_raw = _parse_float(row.get(_COL_OR_BETA))
    ci_text = row.get(_COL_CI_95)
    odds_ratio: float | None = None
    beta: float | None = None

    if or_beta_raw is not None:
        if _is_odds_ratio(ci_text, or_beta_raw):
            odds_ratio = or_beta_raw
        else:
            beta = or_beta_raw

    # Risk allele
    risk_allele = _extract_risk_allele(row.get(_COL_STRONGEST_ALLELE, ""))

    # PubMed ID and study
    pubmed_id = row.get(_COL_PUBMEDID, "").strip() or None
    study = row.get(_COL_STUDY, "").strip() or None

    # Sample size
    sample_size = _parse_sample_size(row.get(_COL_INITIAL_SAMPLE))

    return {
        "rsid": rsid,
        "chrom": chrom,
        "pos": pos,
        "trait": trait,
        "p_value": p_value,
        "odds_ratio": odds_ratio,
        "beta": beta,
        "risk_allele": risk_allele,
        "pubmed_id": pubmed_id,
        "study": study,
        "sample_size": sample_size,
    }, None


# ── Iterator / streaming parse ────────────────────────────────────────────


def iter_gwas_tsv(
    tsv_path: Path,
    *,
    progress_callback: Callable[[int], None] | None = None,
) -> Iterator[tuple[dict, GWASLoadStats]]:
    """Iterate over GWAS Catalog TSV rows lazily, yielding (row_dict, stats).

    Filters rows against the EFO whitelist. Only matching rows are yielded.

    Args:
        tsv_path: Path to the TSV or TSV.gz file.
        progress_callback: Optional callback called with line count.

    Yields:
        Tuple of (row dict ready for insert, running GWASLoadStats).
    """
    stats = GWASLoadStats()

    open_fn = gzip.open if tsv_path.suffix == ".gz" else open
    with open_fn(tsv_path, "rt", encoding="utf-8") as fh:  # type: ignore[call-overload]
        reader = csv.DictReader(fh, delimiter="\t")

        for row in reader:
            stats.total_lines += 1

            parsed, skip_reason = parse_gwas_tsv_row(row)

            if parsed is None:
                if skip_reason == "no_rsid":
                    stats.skipped_no_rsid += 1
                elif skip_reason == "no_trait":
                    stats.skipped_no_trait += 1
                elif skip_reason == "efo_filter":
                    stats.skipped_efo_filter += 1
                else:
                    stats.skipped_malformed += 1
                continue

            # Validate chromosome if present
            if parsed.get("chrom") is None and row.get(_COL_CHR_ID, "").strip():
                stats.skipped_invalid_chrom += 1
                continue

            stats.associations_loaded += 1
            yield parsed, stats

            if progress_callback and stats.total_lines % 10_000 == 0:
                progress_callback(stats.total_lines)


def parse_gwas_tsv(
    tsv_path: Path,
    *,
    progress_callback: Callable[[int], None] | None = None,
) -> tuple[list[dict], GWASLoadStats]:
    """Parse a GWAS Catalog TSV file and return all matching rows + stats.

    For small files / testing. For large files, prefer ``iter_gwas_tsv``
    with ``load_gwas_from_iter`` to keep memory usage low.
    """
    rows: list[dict] = []
    stats = GWASLoadStats()
    for row, stats in iter_gwas_tsv(tsv_path, progress_callback=progress_callback):
        rows.append(row)
    return rows, stats


# ── Database loading ──────────────────────────────────────────────────────


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


def _compute_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_gwas_into_db(
    rows: list[dict],
    engine: sa.Engine,
    *,
    stats: GWASLoadStats | None = None,
    clear_existing: bool = True,
) -> GWASLoadStats:
    """Bulk-load parsed GWAS rows into the gwas_associations table.

    Args:
        rows: List of dicts matching gwas_associations columns.
        engine: SQLAlchemy engine for reference.db.
        stats: Optional GWASLoadStats to update.
        clear_existing: Whether to DELETE all existing rows first.

    Returns:
        Updated GWASLoadStats.
    """
    if stats is None:
        stats = GWASLoadStats(associations_loaded=len(rows))

    with engine.begin() as conn:
        if clear_existing:
            conn.execute(gwas_associations.delete())

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            conn.execute(gwas_associations.insert(), batch)

    _wal_checkpoint(engine)

    logger.info(
        "gwas_loaded",
        associations=stats.associations_loaded,
    )

    return stats


def load_gwas_from_iter(
    row_iter: Iterator[tuple[dict, GWASLoadStats]],
    engine: sa.Engine,
    *,
    clear_existing: bool = True,
) -> GWASLoadStats:
    """Stream-load GWAS rows from an iterator into the database.

    Memory-efficient: only holds one batch at a time.
    """
    stats = GWASLoadStats()

    def rows_only() -> Iterator[dict]:
        nonlocal stats
        for row, stats in row_iter:
            yield row

    with engine.begin() as conn:
        if clear_existing:
            conn.execute(gwas_associations.delete())

        for batch in _batched(rows_only(), BATCH_SIZE):
            conn.execute(gwas_associations.insert(), batch)

    _wal_checkpoint(engine)

    logger.info(
        "gwas_loaded",
        associations=stats.associations_loaded,
    )

    return stats


def record_gwas_version(
    engine: sa.Engine,
    *,
    version: str,
    file_path: str | None = None,
    file_size_bytes: int | None = None,
    checksum: str | None = None,
) -> None:
    """Insert or update the GWAS Catalog version in database_versions."""
    with engine.begin() as conn:
        existing = conn.execute(
            sa.select(database_versions.c.db_name).where(
                database_versions.c.db_name == "gwas_catalog"
            )
        ).first()

        now = datetime.now(UTC)

        if existing:
            conn.execute(
                database_versions.update()
                .where(database_versions.c.db_name == "gwas_catalog")
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
                    db_name="gwas_catalog",
                    version=version,
                    file_path=file_path,
                    file_size_bytes=file_size_bytes,
                    downloaded_at=now,
                    checksum_sha256=checksum,
                )
            )


# ── Download ──────────────────────────────────────────────────────────────


def download_gwas_catalog(
    dest_dir: Path,
    *,
    url: str = GWAS_CATALOG_URL,
    progress_callback: Callable[[int, int | None], None] | None = None,
    timeout: float = 600.0,
) -> Path:
    """Download the GWAS Catalog associations TSV from EBI.

    Writes to a temporary file and renames on success.

    Args:
        dest_dir: Directory to save the downloaded file.
        url: Override URL (useful for testing).
        progress_callback: Called with (bytes_downloaded, total_bytes).
        timeout: HTTP request timeout in seconds.

    Returns:
        Path to the downloaded TSV file.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / "gwas_catalog_associations.tsv"
    tmp_path = dest_dir / "gwas_catalog_associations.tsv.tmp"

    logger.info("gwas_download_start", url=url)

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
                            progress_callback(response.num_bytes_downloaded, total_bytes)

        tmp_path.rename(dest_path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise

    logger.info("gwas_download_complete", path=str(dest_path))
    return dest_path


def download_and_load_gwas(
    engine: sa.Engine,
    dest_dir: Path,
    *,
    url: str = GWAS_CATALOG_URL,
    download_progress: Callable[[int, int | None], None] | None = None,
    parse_progress: Callable[[int], None] | None = None,
    timeout: float = 600.0,
) -> GWASLoadStats:
    """Full pipeline: download GWAS Catalog, parse with EFO filter, load into reference.db.

    Uses streaming parse + batch insert to keep memory usage low.
    """
    tsv_path = download_gwas_catalog(
        dest_dir,
        url=url,
        progress_callback=download_progress,
        timeout=timeout,
    )

    sha256 = _compute_sha256(tsv_path)

    row_iter = iter_gwas_tsv(tsv_path, progress_callback=parse_progress)
    stats = load_gwas_from_iter(row_iter, engine)
    stats.sha256 = sha256

    version = datetime.now(UTC).strftime("%Y%m%d")
    record_gwas_version(
        engine,
        version=version,
        file_path=str(tsv_path),
        file_size_bytes=tsv_path.stat().st_size,
        checksum=sha256,
    )

    return stats


# ═══════════════════════════════════════════════════════════════════════
# GWAS Catalog Annotation Lookup
# ═══════════════════════════════════════════════════════════════════════


def lookup_gwas_by_rsids(
    rsids: list[str],
    reference_engine: sa.Engine,
) -> dict[str, GWASAnnotationSet]:
    """Look up GWAS associations for a batch of rsids.

    Returns all associations for each rsid (a variant may be associated
    with multiple traits). Results are ordered by p-value (most significant
    first) within each rsid.

    Args:
        rsids: List of rsid strings (e.g. ["rs429358", "rs7412"]).
        reference_engine: SQLAlchemy engine for reference.db.

    Returns:
        Dict mapping rsid → GWASAnnotationSet for matched variants.
    """
    if not rsids:
        return {}

    results: dict[str, GWASAnnotationSet] = {}

    with reference_engine.connect() as conn:
        for i in range(0, len(rsids), LOOKUP_BATCH_SIZE):
            batch = rsids[i : i + LOOKUP_BATCH_SIZE]

            stmt = (
                sa.select(
                    gwas_associations.c.rsid,
                    gwas_associations.c.trait,
                    gwas_associations.c.p_value,
                    gwas_associations.c.odds_ratio,
                    gwas_associations.c.beta,
                    gwas_associations.c.risk_allele,
                    gwas_associations.c.pubmed_id,
                    gwas_associations.c.study,
                    gwas_associations.c.sample_size,
                )
                .where(gwas_associations.c.rsid.in_(batch))
                .order_by(
                    gwas_associations.c.rsid,
                    gwas_associations.c.p_value.asc(),
                )
            )

            rows = conn.execute(stmt).fetchall()

            for row in rows:
                rsid = row.rsid
                annot = GWASAnnotation(
                    rsid=rsid,
                    trait=row.trait,
                    p_value=row.p_value,
                    odds_ratio=row.odds_ratio,
                    beta=row.beta,
                    risk_allele=row.risk_allele,
                    pubmed_id=row.pubmed_id,
                    study=row.study,
                    sample_size=row.sample_size,
                )

                if rsid not in results:
                    results[rsid] = GWASAnnotationSet(rsid=rsid)
                results[rsid].associations.append(annot)

    return results


def lookup_gwas_traits_for_rsids(
    rsids: list[str],
    reference_engine: sa.Engine,
) -> dict[str, list[str]]:
    """Simplified lookup returning just trait names per rsid.

    Convenience function for modules that only need trait names
    without full association details.
    """
    annotation_sets = lookup_gwas_by_rsids(rsids, reference_engine)
    return {rsid: aset.traits for rsid, aset in annotation_sets.items()}
