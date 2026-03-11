"""23andMe raw data TSV parser.

Auto-detects format version (v3/v4/v5), normalizes chromosomes,
validates data lines, and returns a pure ParseResult with no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TextIO

# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


class FormatVersion(Enum):
    """23andMe raw-data format versions."""

    V3 = "v3"  # Build 36 (hg18)
    V4 = "v4"  # Build 37 (GRCh37), fewer header comment lines
    V5 = "v5"  # Build 37 (GRCh37), 15+ header comment lines


@dataclass(frozen=True, slots=True)
class ParsedVariant:
    """A single variant row extracted from a 23andMe file."""

    rsid: str
    chrom: str
    pos: int
    genotype: str


@dataclass
class ParseResult:
    """Aggregate result of parsing a complete 23andMe file."""

    version: FormatVersion
    variants: list[ParsedVariant]
    nocall_count: int
    total_lines: int
    skipped_lines: int  # comment + blank lines


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ParserError(Exception):
    """Base parser error."""


class UnsupportedFormatError(ParserError):
    """File is not 23andMe format -- includes guidance message."""


class MalformedDataError(ParserError):
    """23andMe file but with corrupt / invalid data lines."""


class UnrecognizedVersionError(ParserError):
    """Looks like 23andMe but version cannot be determined."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_COLUMN_HEADER = "# rsid\tchromosome\tposition\tgenotype"

_VALID_CHROMOSOMES: frozenset[str] = frozenset([str(n) for n in range(1, 23)] + ["X", "Y", "MT"])

_CHROM_MAP: dict[str, str] = {
    "23": "X",
    "24": "Y",
    "25": "MT",
    "26": "MT",
}

# Number of leading lines sampled during format detection.
_DETECT_LINE_LIMIT = 50

# v5 files typically have 15+ comment lines; v4 has fewer.
_V5_COMMENT_THRESHOLD = 15

# Error messages ---------------------------------------------------------

_ERR_VCF = (
    "This looks like a VCF file. GenomeInsight v1 expects 23andMe raw data "
    "format. VCF support is planned for a future release."
)
_ERR_ANCESTRY = (
    "This looks like an AncestryDNA file. GenomeInsight v1 supports 23andMe "
    "format only. AncestryDNA support is planned for a future release."
)
_ERR_CSV = (
    "This file appears to be comma-separated. 23andMe raw data files use tab-separated format."
)
_ERR_BINARY = "This file contains binary data and is not a valid 23andMe text file."
_ERR_UNKNOWN = (
    "Unrecognized file format. GenomeInsight expects 23andMe raw data (tab-separated, .txt)."
)
_ERR_VERSION = (
    "Header pattern not recognized as 23andMe v3/v4/v5. "
    "Expected: '# rsid\\tchromosome\\tposition\\tgenotype'. "
    "Please file a GitHub issue at "
    "https://github.com/bioedcam/GenomeInsight/issues"
)


# ---------------------------------------------------------------------------
# Chromosome normalisation
# ---------------------------------------------------------------------------


def normalize_chromosome(chrom: str) -> str:
    """Normalize a raw chromosome string to one of 1-22, X, Y, MT.

    Raises ``MalformedDataError`` if the value is not recognisable.
    """
    upper = chrom.strip().upper()
    if upper in _CHROM_MAP:
        return _CHROM_MAP[upper]
    if upper in _VALID_CHROMOSOMES:
        return upper
    raise MalformedDataError(f"Invalid chromosome value: {chrom!r}")


# ---------------------------------------------------------------------------
# Line validation
# ---------------------------------------------------------------------------


def _validate_line(parts: list[str], line_num: int) -> ParsedVariant:
    """Validate a single tab-split data line and return a ``ParsedVariant``.

    Parameters
    ----------
    parts:
        Already-split columns (expected length 4).
    line_num:
        1-based line number in the source file, used in error messages.
    """
    if len(parts) != 4:
        raise MalformedDataError(f"Line {line_num}: expected 4 columns, got {len(parts)}")

    rsid_raw, chrom_raw, pos_raw, genotype_raw = (p.strip() for p in parts)

    # -- rsid (must be non-empty) ------------------------------------------
    if not rsid_raw:
        raise MalformedDataError(f"Line {line_num}: empty rsid")

    # -- chromosome --------------------------------------------------------
    chrom = normalize_chromosome(chrom_raw)

    # -- position ----------------------------------------------------------
    try:
        pos = int(pos_raw)
    except ValueError:
        raise MalformedDataError(f"Line {line_num}: non-numeric position {pos_raw!r}") from None
    if pos < 0:
        raise MalformedDataError(f"Line {line_num}: negative position {pos}")

    # -- genotype (keep as-is, including "--" for no-calls) ----------------
    if not genotype_raw:
        raise MalformedDataError(f"Line {line_num}: empty genotype")

    return ParsedVariant(rsid=rsid_raw, chrom=chrom, pos=pos, genotype=genotype_raw)


# ---------------------------------------------------------------------------
# Format / version detection helpers
# ---------------------------------------------------------------------------


def _check_binary(head: bytes) -> bool:
    """Return True if *head* looks like binary content."""
    # Null bytes are a reliable indicator of non-text data.
    return b"\x00" in head


def _open_input(file_or_path: str | Path | TextIO) -> tuple[TextIO, bool]:
    """Return (readable text stream, should_close).

    Accepts a path (str / Path) or an already-open text stream.
    """
    if isinstance(file_or_path, (str, Path)):
        path = Path(file_or_path)
        # Quick binary check on the first 512 bytes.
        raw = path.read_bytes()[:512]
        if _check_binary(raw):
            raise UnsupportedFormatError(_ERR_BINARY)
        return open(path, encoding="utf-8", errors="replace"), True

    # Already a TextIO -- caller manages lifetime.
    return file_or_path, False


def _read_head_lines(
    file_or_path: str | Path | TextIO,
    limit: int = _DETECT_LINE_LIMIT,
) -> list[str]:
    """Read up to *limit* lines from the beginning of a file.

    For path inputs the file is opened, partially read, and closed.
    For TextIO inputs the stream position is saved and restored when
    possible (seekable streams), otherwise the lines are consumed.
    """
    if isinstance(file_or_path, (str, Path)):
        path = Path(file_or_path)
        raw = path.read_bytes()[:512]
        if _check_binary(raw):
            raise UnsupportedFormatError(_ERR_BINARY)
        with open(path, encoding="utf-8", errors="replace") as fh:
            return [fh.readline() for _ in range(limit)]

    # TextIO path
    stream: TextIO = file_or_path
    seekable = hasattr(stream, "seekable") and stream.seekable()
    if seekable:
        pos = stream.tell()
    lines = [stream.readline() for _ in range(limit)]
    if seekable:
        stream.seek(pos)
    return lines


def _reject_non_23andme(lines: list[str]) -> None:
    """Raise ``UnsupportedFormatError`` if the file matches a known
    non-23andMe format, or ``UnsupportedFormatError`` with a generic
    message if no pattern is recognised at all.
    """
    joined = "".join(lines)
    lower = joined.lower()

    # VCF
    if "##fileformat=vcf" in lower or "#chrom\tpos\tid" in lower:
        raise UnsupportedFormatError(_ERR_VCF)

    # AncestryDNA
    if "#ancestrydna" in lower:
        raise UnsupportedFormatError(_ERR_ANCESTRY)

    # Comma-separated (heuristic: majority of non-comment lines have commas)
    data_lines = [ln for ln in lines if ln.strip() and not ln.startswith("#")]
    if data_lines:
        comma_count = sum(1 for ln in data_lines if "," in ln)
        if comma_count > len(data_lines) * 0.5:
            raise UnsupportedFormatError(_ERR_CSV)

    raise UnsupportedFormatError(_ERR_UNKNOWN)


def _detect_version_from_header(
    comment_lines: list[str],
) -> FormatVersion:
    """Determine the 23andMe format version from collected comment lines."""
    lower_comments = " ".join(comment_lines).lower()

    if "build 36" in lower_comments:
        return FormatVersion.V3

    if "build 37" in lower_comments or "grch37" in lower_comments:
        # Distinguish v4 vs v5 by comment-line count.
        if len(comment_lines) >= _V5_COMMENT_THRESHOLD:
            return FormatVersion.V5
        return FormatVersion.V4

    # Fallback: if we saw the canonical column header but no build string,
    # treat as unrecognised.
    raise UnrecognizedVersionError(_ERR_VERSION)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_format(file_or_path: str | Path | TextIO) -> FormatVersion:
    """Detect the 23andMe format version by inspecting the file header.

    Raises
    ------
    UnsupportedFormatError
        If the file is not a 23andMe raw-data file.
    UnrecognizedVersionError
        If the file appears to be 23andMe but the version cannot be
        determined.
    """
    lines = _read_head_lines(file_or_path)

    comment_lines: list[str] = []
    has_column_header = False

    for raw_line in lines:
        line = raw_line.rstrip("\n\r")
        if not line:
            continue
        if line.startswith("#"):
            if line.lower().strip() == _COLUMN_HEADER.lower().strip():
                has_column_header = True
            comment_lines.append(line)
        else:
            break  # first data line — stop scanning

    if not has_column_header:
        _reject_non_23andme(lines)

    return _detect_version_from_header(comment_lines)


def parse_23andme(file_or_path: str | Path | TextIO) -> ParseResult:
    """Parse a 23andMe raw-data file and return a ``ParseResult``.

    The function is **pure**: it reads the file and produces an in-memory
    result — no database writes, no side effects.

    Raises
    ------
    ValueError
        If *file_or_path* is a non-seekable TextIO stream (wrap in
        ``io.StringIO(stream.read())`` first).
    UnsupportedFormatError
        If the file is not a 23andMe raw-data file.
    UnrecognizedVersionError
        If the file appears to be 23andMe but the version cannot be
        determined.
    MalformedDataError
        If a data line has an invalid structure (wrong column count,
        bad chromosome, non-numeric position, etc.).
    """
    # Reject non-seekable streams to prevent silent data loss.
    if not isinstance(file_or_path, (str, Path)):
        if not (hasattr(file_or_path, "seekable") and file_or_path.seekable()):
            raise ValueError(
                "TextIO streams must be seekable. Wrap non-seekable streams "
                "in io.StringIO(stream.read()) before calling parse_23andme."
            )

    # -- Detect version first (rewinds / re-opens as needed) ---------------
    version = detect_format(file_or_path)

    # -- Full parse --------------------------------------------------------
    stream, should_close = _open_input(file_or_path)
    try:
        variants: list[ParsedVariant] = []
        nocall_count = 0
        total_lines = 0
        skipped_lines = 0

        for line_num, raw_line in enumerate(stream, start=1):
            total_lines += 1
            line = raw_line.rstrip("\n\r")

            # Skip blank lines and comments.
            if not line or line.startswith("#"):
                skipped_lines += 1
                continue

            parts = line.split("\t")
            variant = _validate_line(parts, line_num)
            variants.append(variant)

            if variant.genotype == "--":
                nocall_count += 1

        return ParseResult(
            version=version,
            variants=variants,
            nocall_count=nocall_count,
            total_lines=total_lines,
            skipped_lines=skipped_lines,
        )
    finally:
        if should_close:
            stream.close()
