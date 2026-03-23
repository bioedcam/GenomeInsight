"""Custom gene panel import and management (P4-11).

Supports two file formats:
  - **Gene list** (.txt, .csv, .tsv): One gene symbol per line, or
    comma/tab-separated. Lines starting with ``#`` are ignored.
  - **BED file** (.bed): Standard BED3+ format (chrom, start, end, optional
    name column used as gene symbol). Lines starting with ``track``,
    ``browser``, or ``#`` are skipped.

Parsed panels are stored in the ``custom_panels`` table in reference.db
and can be loaded into the rare variant finder as a gene list filter.

Usage::

    from backend.analysis.custom_panels import (
        parse_gene_list,
        parse_bed_file,
        CustomPanel,
        save_custom_panel,
        list_custom_panels,
        get_custom_panel,
        delete_custom_panel,
    )
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import sqlalchemy as sa
import structlog

from backend.db.tables import custom_panels

logger = structlog.get_logger(__name__)

# Maximum number of genes allowed in a single panel (safety limit)
MAX_PANEL_GENES = 5000

# Maximum file size for uploaded panel files (1 MB)
MAX_FILE_SIZE_BYTES = 1_048_576

# Valid gene symbol pattern (HGNC-style: letters, digits, hyphens)
_GENE_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9\-\.]{0,30}$", re.IGNORECASE)

# Valid BED chromosome names
_CHROM_RE = re.compile(r"^(chr)?\d{1,2}$|^(chr)?[XYM]$|^(chr)?MT$", re.IGNORECASE)


# ── Data classes ──────────────────────────────────────────────────────


@dataclass
class BedRegion:
    """A genomic region from a BED file."""

    chrom: str
    start: int
    end: int
    name: str | None = None  # Optional gene symbol or region name


@dataclass
class ParsedPanel:
    """Result of parsing a gene panel file."""

    gene_symbols: list[str] = field(default_factory=list)
    bed_regions: list[BedRegion] = field(default_factory=list)
    source_type: str = "gene_list"  # "gene_list" or "bed"
    warnings: list[str] = field(default_factory=list)

    @property
    def gene_count(self) -> int:
        return len(self.gene_symbols)

    @property
    def region_count(self) -> int:
        return len(self.bed_regions)


@dataclass
class CustomPanel:
    """A stored custom gene panel."""

    id: int
    name: str
    description: str
    gene_symbols: list[str]
    bed_regions: list[dict] | None  # Serialized BedRegion dicts
    source_type: str
    gene_count: int
    created_at: str | None = None


# ── Parsers ─────────────────────────────────────────────────────────


def _is_valid_gene_symbol(symbol: str) -> bool:
    """Check if a string looks like a valid HGNC gene symbol."""
    return bool(_GENE_SYMBOL_RE.match(symbol))


def parse_gene_list(content: str) -> ParsedPanel:
    """Parse a gene list from text content.

    Accepts one gene per line or comma/tab-separated values.
    Lines starting with ``#`` are treated as comments.

    Args:
        content: Raw text content of the gene list file.

    Returns:
        ParsedPanel with extracted gene symbols.

    Raises:
        ValueError: If no valid gene symbols found or limit exceeded.
    """
    warnings: list[str] = []
    genes: list[str] = []
    seen: set[str] = set()

    for line_num, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Split on comma, tab, semicolon, or whitespace
        tokens = re.split(r"[,;\t\s]+", line)
        for token in tokens:
            token = token.strip().upper()
            if not token:
                continue
            if not _is_valid_gene_symbol(token):
                warnings.append(f"Line {line_num}: Skipped invalid symbol '{token}'")
                continue
            if token in seen:
                continue
            seen.add(token)
            genes.append(token)

    if len(genes) > MAX_PANEL_GENES:
        raise ValueError(
            f"Panel exceeds maximum of {MAX_PANEL_GENES} genes "
            f"({len(genes)} found). Please reduce the gene list."
        )

    if not genes:
        raise ValueError(
            "No valid gene symbols found in the uploaded file. "
            "Expected format: one gene symbol per line (e.g., BRCA1) "
            "or comma-separated (e.g., BRCA1, TP53, CFTR)."
        )

    return ParsedPanel(
        gene_symbols=genes,
        source_type="gene_list",
        warnings=warnings,
    )


def parse_bed_file(content: str) -> ParsedPanel:
    """Parse a BED file and extract gene symbols and genomic regions.

    Standard BED format: chrom, start, end, [name, ...].
    If the 4th column (name) looks like a gene symbol, it is collected.
    All valid regions are stored for position-based filtering.

    Args:
        content: Raw text content of the BED file.

    Returns:
        ParsedPanel with gene symbols (from name column) and BED regions.

    Raises:
        ValueError: If no valid BED regions found or limit exceeded.
    """
    warnings: list[str] = []
    regions: list[BedRegion] = []
    genes: list[str] = []
    seen_genes: set[str] = set()

    for line_num, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith(("#", "track", "browser")):
            continue

        fields = line.split("\t")
        if len(fields) < 3:
            # Try space splitting as fallback
            fields = line.split()
        if len(fields) < 3:
            warnings.append(f"Line {line_num}: Skipped (fewer than 3 columns)")
            continue

        chrom = fields[0].strip()
        if not _CHROM_RE.match(chrom):
            warnings.append(f"Line {line_num}: Skipped invalid chromosome '{chrom}'")
            continue

        try:
            start = int(fields[1].strip())
            end = int(fields[2].strip())
        except ValueError:
            warnings.append(f"Line {line_num}: Skipped (non-integer coordinates)")
            continue

        if start < 0 or end < 0 or end <= start:
            warnings.append(f"Line {line_num}: Skipped (invalid coordinates {start}-{end})")
            continue

        name = fields[3].strip() if len(fields) > 3 else None
        region = BedRegion(chrom=chrom, start=start, end=end, name=name)
        regions.append(region)

        # Extract gene symbol from name column if valid
        if name:
            upper_name = name.upper()
            if _is_valid_gene_symbol(upper_name) and upper_name not in seen_genes:
                seen_genes.add(upper_name)
                genes.append(upper_name)

    if len(regions) > MAX_PANEL_GENES:
        raise ValueError(
            f"BED file exceeds maximum of {MAX_PANEL_GENES} regions "
            f"({len(regions)} found). Please reduce the region list."
        )

    if not regions:
        raise ValueError(
            "No valid BED regions found in the uploaded file. "
            "Expected BED format: chrom<tab>start<tab>end[<tab>name]. "
            "Example: chr17\t41196312\t41277500\tBRCA1"
        )

    return ParsedPanel(
        gene_symbols=genes,
        bed_regions=regions,
        source_type="bed",
        warnings=warnings,
    )


def detect_and_parse(content: str, filename: str) -> ParsedPanel:
    """Auto-detect file format and parse accordingly.

    BED files are detected by .bed extension or if >50% of non-comment
    lines have tab-separated numeric columns 2 and 3.

    Args:
        content: Raw file content.
        filename: Original filename for format detection.

    Returns:
        ParsedPanel result.
    """
    if filename.lower().endswith(".bed"):
        return parse_bed_file(content)

    # Heuristic: check if content looks like BED format
    lines = [
        ln.strip() for ln in content.splitlines() if ln.strip() and not ln.strip().startswith("#")
    ]
    if lines:
        bed_like = 0
        for ln in lines[:20]:  # Check first 20 non-comment lines
            fields = ln.split("\t")
            if len(fields) >= 3:
                try:
                    int(fields[1])
                    int(fields[2])
                    bed_like += 1
                except ValueError:
                    pass
        if bed_like > len(lines[:20]) * 0.5:
            return parse_bed_file(content)

    return parse_gene_list(content)


# ── Database operations ──────────────────────────────────────────────


def save_custom_panel(
    name: str,
    description: str,
    parsed: ParsedPanel,
    engine: sa.Engine,
) -> int:
    """Save a parsed panel to the custom_panels table.

    Args:
        name: Panel display name.
        description: Panel description.
        parsed: Parsed panel data.
        engine: Reference DB engine.

    Returns:
        ID of the inserted panel row.
    """
    bed_regions_json = None
    if parsed.bed_regions:
        bed_regions_json = json.dumps(
            [
                {"chrom": r.chrom, "start": r.start, "end": r.end, "name": r.name}
                for r in parsed.bed_regions
            ]
        )

    with engine.begin() as conn:
        result = conn.execute(
            sa.insert(custom_panels).values(
                name=name,
                description=description,
                gene_symbols=json.dumps(parsed.gene_symbols),
                bed_regions=bed_regions_json,
                source_type=parsed.source_type,
                gene_count=parsed.gene_count,
            )
        )
        panel_id = result.lastrowid

    logger.info(
        "custom_panel_saved",
        panel_id=panel_id,
        name=name,
        gene_count=parsed.gene_count,
        source_type=parsed.source_type,
    )
    return panel_id  # type: ignore[return-value]


def list_custom_panels(engine: sa.Engine) -> list[CustomPanel]:
    """List all saved custom panels.

    Args:
        engine: Reference DB engine.

    Returns:
        List of CustomPanel objects ordered by creation date (newest first).
    """
    with engine.connect() as conn:
        rows = conn.execute(
            sa.select(custom_panels).order_by(custom_panels.c.created_at.desc())
        ).fetchall()

    panels: list[CustomPanel] = []
    for row in rows:
        genes = json.loads(row.gene_symbols) if row.gene_symbols else []
        bed = json.loads(row.bed_regions) if row.bed_regions else None
        panels.append(
            CustomPanel(
                id=row.id,
                name=row.name,
                description=row.description or "",
                gene_symbols=genes,
                bed_regions=bed,
                source_type=row.source_type,
                gene_count=row.gene_count,
                created_at=str(row.created_at) if row.created_at else None,
            )
        )
    return panels


def get_custom_panel(panel_id: int, engine: sa.Engine) -> CustomPanel | None:
    """Get a single custom panel by ID.

    Args:
        panel_id: Panel primary key.
        engine: Reference DB engine.

    Returns:
        CustomPanel or None if not found.
    """
    with engine.connect() as conn:
        row = conn.execute(
            sa.select(custom_panels).where(custom_panels.c.id == panel_id)
        ).fetchone()

    if row is None:
        return None

    genes = json.loads(row.gene_symbols) if row.gene_symbols else []
    bed = json.loads(row.bed_regions) if row.bed_regions else None
    return CustomPanel(
        id=row.id,
        name=row.name,
        description=row.description or "",
        gene_symbols=genes,
        bed_regions=bed,
        source_type=row.source_type,
        gene_count=row.gene_count,
        created_at=str(row.created_at) if row.created_at else None,
    )


def delete_custom_panel(panel_id: int, engine: sa.Engine) -> bool:
    """Delete a custom panel by ID.

    Args:
        panel_id: Panel primary key.
        engine: Reference DB engine.

    Returns:
        True if deleted, False if not found.
    """
    with engine.begin() as conn:
        result = conn.execute(sa.delete(custom_panels).where(custom_panels.c.id == panel_id))
    deleted = result.rowcount > 0
    if deleted:
        logger.info("custom_panel_deleted", panel_id=panel_id)
    return deleted
