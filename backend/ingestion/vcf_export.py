"""VCF 4.2 export from raw_variants table.

Converts 23andMe-format genotype data into a valid VCF 4.2 file.
Since 23andMe raw data does not include REF/ALT alleles, homozygous
calls use the observed allele as REF with ALT='.', and heterozygous
calls assign the first allele as REF and the second as ALT.
No-call genotypes ('--') are skipped by default.

Reference: VCF 4.2 specification
  https://samtools.github.io/hts-specs/VCFv4.2.pdf
"""

from __future__ import annotations

import io
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import TextIO

import sqlalchemy as sa

from backend.db.tables import raw_variants

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VCF_VERSION = "VCFv4.2"
_SOURCE = "GenomeInsight"
_REFERENCE = "GRCh37"

# Canonical chromosome sort order for VCF output.
_CHROM_ORDER: dict[str, int] = {
    **{str(i): i for i in range(1, 23)},
    "X": 23,
    "Y": 24,
    "MT": 25,
}

# VCF header column names.
_VCF_COLUMNS = (
    "#CHROM", "POS", "ID", "REF", "ALT", "QUAL", "FILTER", "INFO", "FORMAT",
    "SAMPLE",
)

# Valid nucleotide bases for VCF allele fields.
_VALID_BASES: frozenset[str] = frozenset("ACGT")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _chrom_sort_key(chrom: str) -> int:
    """Return an integer sort key for a chromosome string."""
    return _CHROM_ORDER.get(chrom, 99)


def _genotype_to_vcf_fields(
    genotype: str,
) -> tuple[str, str, str] | None:
    """Convert a 23andMe genotype string to (REF, ALT, GT).

    Returns ``None`` for no-call genotypes ('--'), empty strings, and
    genotypes containing non-nucleotide characters (D/I indel codes from
    23andMe v3).

    For single-character genotypes (haploid, e.g. Y/MT), the GT field
    uses haploid notation (e.g. '0').
    """
    if not genotype or genotype == "--":
        return None

    # Reject non-nucleotide characters (e.g. D/I indel codes).
    if not all(c in _VALID_BASES for c in genotype):
        return None

    if len(genotype) == 1:
        # Haploid call (Y chromosome, MT).
        return genotype, ".", "0"

    allele1, allele2 = genotype[0], genotype[1]

    if allele1 == allele2:
        # Homozygous — observed allele is REF, no ALT.
        return allele1, ".", "0/0"

    # Heterozygous — first allele as REF, second as ALT.
    return allele1, allele2, "0/1"


def _build_header_lines(
    sample_name: str = "SAMPLE",
    file_date: date | None = None,
) -> list[str]:
    """Build VCF meta-information and header lines."""
    if file_date is None:
        file_date = date.today()

    # Sanitize sample name: strip tabs, newlines, control characters.
    safe_name = "".join(
        c for c in sample_name if c.isprintable() and c not in "\t\n\r"
    ) or "SAMPLE"

    lines = [
        f"##fileformat={_VCF_VERSION}",
        f"##fileDate={file_date.strftime('%Y%m%d')}",
        f"##source={_SOURCE}",
        f"##reference={_REFERENCE}",
        (
            "##GenomeInsight_note=REF/ALT alleles are inferred from genotype "
            "calls, not from a reference genome. Heterozygous REF/ALT "
            "assignment may not match the true reference allele."
        ),
        '##FILTER=<ID=PASS,Description="All filters passed">',
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
    ]

    # Contig lines for standard chromosomes.
    for chrom in sorted(_CHROM_ORDER, key=_chrom_sort_key):
        lines.append(f"##contig=<ID={chrom}>")

    # Column header — replace "SAMPLE" with sanitized sample name.
    cols = list(_VCF_COLUMNS)
    cols[-1] = safe_name
    lines.append("\t".join(cols))

    return lines


# ---------------------------------------------------------------------------
# Data row type
# ---------------------------------------------------------------------------

class _VariantRow:
    """Lightweight container for a variant to be exported."""

    __slots__ = ("rsid", "chrom", "pos", "genotype")

    def __init__(self, rsid: str, chrom: str, pos: int, genotype: str) -> None:
        self.rsid = rsid
        self.chrom = chrom
        self.pos = pos
        self.genotype = genotype


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_vcf_from_rows(
    variants: Iterable[tuple[str, str, int, str]],
    dest: str | Path | TextIO | None = None,
    *,
    sample_name: str = "SAMPLE",
    skip_nocalls: bool = True,
    file_date: date | None = None,
) -> str:
    """Export variant rows to VCF 4.2 format.

    Parameters
    ----------
    variants:
        Iterable of ``(rsid, chrom, pos, genotype)`` tuples. Must already
        be sorted by (chrom, pos) in canonical order, or will be sorted
        internally.
    dest:
        Destination — a file path (str/Path), a writable text stream, or
        ``None`` to return the VCF content as a string.
    sample_name:
        Name used in the VCF sample column header.
    skip_nocalls:
        If True (default), skip variants with '--' or empty genotype.
    file_date:
        Date for the ``##fileDate`` header. Defaults to today.

    Returns
    -------
    str
        The VCF content as a string. If *dest* is a file path, the string
        is also written to that file.
    """
    # Materialise and sort.
    rows = [
        _VariantRow(rsid, chrom, pos, gt)
        for rsid, chrom, pos, gt in variants
    ]
    rows.sort(key=lambda r: (_chrom_sort_key(r.chrom), r.pos))

    header_lines = _build_header_lines(sample_name=sample_name, file_date=file_date)

    buf = io.StringIO()
    for line in header_lines:
        buf.write(line)
        buf.write("\n")

    for row in rows:
        fields = _genotype_to_vcf_fields(row.genotype)
        if fields is None:
            if skip_nocalls:
                continue
            # Emit no-call with missing GT.
            ref, alt, gt = "N", ".", "./."
        else:
            ref, alt, gt = fields

        data_line = "\t".join([
            row.chrom,
            str(row.pos),
            row.rsid,
            ref,
            alt,
            ".",      # QUAL
            "PASS",   # FILTER
            ".",      # INFO
            "GT",     # FORMAT
            gt,       # sample genotype
        ])
        buf.write(data_line)
        buf.write("\n")

    content = buf.getvalue()

    # Write to destination if provided.
    if dest is not None:
        if isinstance(dest, (str, Path)):
            Path(dest).write_text(content, encoding="utf-8")
        else:
            dest.write(content)

    return content


def export_vcf_from_engine(
    engine: sa.Engine,
    dest: str | Path | TextIO | None = None,
    *,
    sample_name: str = "SAMPLE",
    skip_nocalls: bool = True,
    file_date: date | None = None,
) -> str:
    """Export all raw_variants from a sample database to VCF 4.2.

    Parameters
    ----------
    engine:
        SQLAlchemy engine connected to a per-sample SQLite database
        containing a ``raw_variants`` table.
    dest:
        Destination file path, writable stream, or ``None`` for string.
    sample_name:
        Name for the VCF sample column.
    skip_nocalls:
        Skip no-call genotypes (default True).
    file_date:
        Override for ``##fileDate``.

    Returns
    -------
    str
        The complete VCF content.
    """
    # No ORDER BY — export_vcf_from_rows re-sorts by canonical chrom order.
    stmt = sa.select(
        raw_variants.c.rsid,
        raw_variants.c.chrom,
        raw_variants.c.pos,
        raw_variants.c.genotype,
    )

    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()

    return export_vcf_from_rows(
        rows,
        dest=dest,
        sample_name=sample_name,
        skip_nocalls=skip_nocalls,
        file_date=file_date,
    )
