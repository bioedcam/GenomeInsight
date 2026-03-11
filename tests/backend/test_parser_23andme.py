"""Tests for 23andMe TSV parser (P1-04).

Covers test IDs: T1-01, T1-01a, T1-01b, T1-01c, T1-02, T1-03, T1-04, T1-05.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
import sqlalchemy as sa

from backend.db.sample_schema import create_sample_tables
from backend.db.tables import raw_variants
from backend.ingestion.parser_23andme import (
    FormatVersion,
    MalformedDataError,
    ParsedVariant,
    ParserError,
    UnrecognizedVersionError,
    UnsupportedFormatError,
    detect_format,
    normalize_chromosome,
    parse_23andme,
)

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

V5_FILE = FIXTURES / "sample_23andme_v5.txt"
V3_FILE = FIXTURES / "sample_23andme_v3.txt"
V4_FILE = FIXTURES / "sample_23andme_v4.txt"
VCF_FILE = FIXTURES / "sample_not_23andme.vcf"
ANCESTRY_FILE = FIXTURES / "sample_ancestrydna.txt"
CSV_FILE = FIXTURES / "sample_random.csv"


# ═══════════════════════════════════════════════════════════════════════════
# T1-01: Parser reads valid v5 file, extracts 4 fields, assigns version
# ═══════════════════════════════════════════════════════════════════════════


class TestParseV5:
    """T1-01: Parser correctly reads valid 23andMe v5 file."""

    def test_detects_v5_format(self) -> None:
        assert detect_format(V5_FILE) == FormatVersion.V5

    def test_parse_returns_v5_version(self) -> None:
        result = parse_23andme(V5_FILE)
        assert result.version == FormatVersion.V5

    def test_variant_count(self) -> None:
        result = parse_23andme(V5_FILE)
        assert len(result.variants) == 1000

    def test_variant_has_four_fields(self) -> None:
        result = parse_23andme(V5_FILE)
        v = result.variants[0]
        assert isinstance(v, ParsedVariant)
        assert isinstance(v.rsid, str) and v.rsid
        assert isinstance(v.chrom, str) and v.chrom
        assert isinstance(v.pos, int) and v.pos >= 0
        assert isinstance(v.genotype, str) and v.genotype

    def test_skipped_lines_counted(self) -> None:
        result = parse_23andme(V5_FILE)
        # v5 has 18 comment lines (including column header)
        assert result.skipped_lines > 0
        assert result.total_lines == result.skipped_lines + len(result.variants)

    def test_apoe_snps_present(self) -> None:
        """Verify APOE-relevant SNPs are parsed correctly."""
        result = parse_23andme(V5_FILE)
        rsid_map = {v.rsid: v for v in result.variants}

        rs429358 = rsid_map.get("rs429358")
        assert rs429358 is not None
        assert rs429358.chrom == "19"
        assert rs429358.pos == 44908684
        assert rs429358.genotype == "TT"

        rs7412 = rsid_map.get("rs7412")
        assert rs7412 is not None
        assert rs7412.chrom == "19"
        assert rs7412.pos == 44908822
        assert rs7412.genotype == "CC"


# ═══════════════════════════════════════════════════════════════════════════
# T1-01a: Auto-detect v3 and v4 formats, i-prefixed rsid handling
# ═══════════════════════════════════════════════════════════════════════════


class TestParseV3V4:
    """T1-01a: Parser auto-detects v3/v4 formats."""

    def test_detects_v3_format(self) -> None:
        assert detect_format(V3_FILE) == FormatVersion.V3

    def test_detects_v4_format(self) -> None:
        assert detect_format(V4_FILE) == FormatVersion.V4

    def test_parse_v3_variant_count(self) -> None:
        result = parse_23andme(V3_FILE)
        assert result.version == FormatVersion.V3
        assert len(result.variants) == 100

    def test_parse_v4_variant_count(self) -> None:
        result = parse_23andme(V4_FILE)
        assert result.version == FormatVersion.V4
        assert len(result.variants) == 100

    def test_v3_i_prefixed_rsids_preserved(self) -> None:
        """i-prefixed rsids (23andMe internal IDs) are kept as-is."""
        result = parse_23andme(V3_FILE)
        i_rsids = [v for v in result.variants if v.rsid.startswith("i")]
        assert len(i_rsids) > 0
        for v in i_rsids:
            assert v.rsid[0] == "i"
            assert v.rsid[1:].isdigit()

    def test_v5_i_prefixed_rsids_preserved(self) -> None:
        result = parse_23andme(V5_FILE)
        i_rsids = [v for v in result.variants if v.rsid.startswith("i")]
        assert len(i_rsids) == 40


# ═══════════════════════════════════════════════════════════════════════════
# T1-01b: Detect non-23andMe files with format-specific error messages
# ═══════════════════════════════════════════════════════════════════════════


class TestNon23andMeDetection:
    """T1-01b: Parser detects non-23andMe files with specific errors."""

    def test_rejects_vcf_with_message(self) -> None:
        with pytest.raises(UnsupportedFormatError, match="VCF file"):
            parse_23andme(VCF_FILE)

    def test_rejects_ancestrydna_with_message(self) -> None:
        with pytest.raises(UnsupportedFormatError, match="AncestryDNA"):
            parse_23andme(ANCESTRY_FILE)

    def test_rejects_csv_with_message(self) -> None:
        with pytest.raises(UnsupportedFormatError, match="comma-separated"):
            parse_23andme(CSV_FILE)

    def test_rejects_binary_with_message(self, tmp_path: Path) -> None:
        bin_file = tmp_path / "test.bin"
        bin_file.write_bytes(b"\x00\x01\x02\xff" * 100)
        with pytest.raises(UnsupportedFormatError, match="binary"):
            parse_23andme(bin_file)

    def test_rejects_unknown_format_with_message(self) -> None:
        content = "some random text\nwithout any structure\nat all\n"
        with pytest.raises(UnsupportedFormatError, match="Unrecognized"):
            parse_23andme(io.StringIO(content))


# ═══════════════════════════════════════════════════════════════════════════
# T1-01c: Unrecognized 23andMe version → specific guidance
# ═══════════════════════════════════════════════════════════════════════════


class TestUnrecognizedVersion:
    """T1-01c: Parser rejects ambiguous 23andMe-like files."""

    def test_rejects_unknown_version_with_guidance(self) -> None:
        """File has the column header but no build string."""
        content = (
            "# This data file generated by 23andMe\n"
            "#\n"
            "# rsid\tchromosome\tposition\tgenotype\n"
            "rs123\t1\t100\tAA\n"
        )
        with pytest.raises(UnrecognizedVersionError, match="GitHub issue"):
            parse_23andme(io.StringIO(content))


# ═══════════════════════════════════════════════════════════════════════════
# T1-02: Parser rejects malformed files
# ═══════════════════════════════════════════════════════════════════════════


class TestMalformedData:
    """T1-02: Parser rejects malformed files."""

    def _make_v5_stream(self, *data_lines: str) -> io.StringIO:
        """Create a minimal v5-like stream with custom data lines."""
        header = (
            "# This data file generated by 23andMe\n"
            "# reference human assembly build 37\n"
            "# rsid\tchromosome\tposition\tgenotype\n"
        )
        return io.StringIO(header + "\n".join(data_lines) + "\n")

    def test_wrong_column_count_too_few(self) -> None:
        stream = self._make_v5_stream("rs123\t1\t100")
        with pytest.raises(MalformedDataError, match="expected 4 columns"):
            parse_23andme(stream)

    def test_wrong_column_count_too_many(self) -> None:
        stream = self._make_v5_stream("rs123\t1\t100\tAA\textra")
        with pytest.raises(MalformedDataError, match="expected 4 columns"):
            parse_23andme(stream)

    def test_invalid_chromosome(self) -> None:
        stream = self._make_v5_stream("rs123\t99\t100\tAA")
        with pytest.raises(MalformedDataError, match="Invalid chromosome"):
            parse_23andme(stream)

    def test_non_numeric_position(self) -> None:
        stream = self._make_v5_stream("rs123\t1\tabc\tAA")
        with pytest.raises(MalformedDataError, match="non-numeric position"):
            parse_23andme(stream)

    def test_empty_rsid(self) -> None:
        stream = self._make_v5_stream("\t1\t100\tAA")
        with pytest.raises(MalformedDataError, match="empty rsid"):
            parse_23andme(stream)

    def test_empty_genotype(self) -> None:
        stream = self._make_v5_stream("rs123\t1\t100\t")
        with pytest.raises(MalformedDataError, match="empty genotype"):
            parse_23andme(stream)

    def test_negative_position(self) -> None:
        stream = self._make_v5_stream("rs123\t1\t-5\tAA")
        with pytest.raises(MalformedDataError, match="negative position"):
            parse_23andme(stream)


# ═══════════════════════════════════════════════════════════════════════════
# T1-03: No-call (--) genotypes flagged separately
# ═══════════════════════════════════════════════════════════════════════════


class TestNoCalls:
    """T1-03: Parser flags no-call genotypes."""

    def test_nocall_counted(self) -> None:
        result = parse_23andme(V5_FILE)
        assert result.nocall_count == 25

    def test_nocall_variants_have_dash_genotype(self) -> None:
        result = parse_23andme(V5_FILE)
        nocalls = [v for v in result.variants if v.genotype == "--"]
        assert len(nocalls) == result.nocall_count

    def test_nocalls_still_in_variants_list(self) -> None:
        """No-calls are not filtered out — they appear in the variants list."""
        result = parse_23andme(V5_FILE)
        assert result.nocall_count > 0
        assert len(result.variants) == 1000  # all lines including no-calls


# ═══════════════════════════════════════════════════════════════════════════
# T1-04: Chromosome notation normalized
# ═══════════════════════════════════════════════════════════════════════════


class TestChromosomeNormalization:
    """T1-04: Chromosome notation normalized: 23→X, 24→Y, 25→MT, 26→MT."""

    def test_normalize_23_to_x(self) -> None:
        assert normalize_chromosome("23") == "X"

    def test_normalize_24_to_y(self) -> None:
        assert normalize_chromosome("24") == "Y"

    def test_normalize_25_to_mt(self) -> None:
        assert normalize_chromosome("25") == "MT"

    def test_normalize_26_to_mt(self) -> None:
        assert normalize_chromosome("26") == "MT"

    def test_normalize_standard_chroms_unchanged(self) -> None:
        for c in ["1", "10", "22", "X", "Y", "MT"]:
            assert normalize_chromosome(c) == c

    def test_normalize_case_insensitive(self) -> None:
        assert normalize_chromosome("x") == "X"
        assert normalize_chromosome("y") == "Y"
        assert normalize_chromosome("mt") == "MT"

    def test_v3_numeric_chroms_normalized(self) -> None:
        """v3 file uses 23/24/25/26 — parser normalizes them."""
        result = parse_23andme(V3_FILE)
        chroms = {v.chrom for v in result.variants}
        # After normalization, no numeric 23-26 should remain
        assert "23" not in chroms
        assert "24" not in chroms
        assert "25" not in chroms
        assert "26" not in chroms
        # Should have X, Y, MT instead
        assert "X" in chroms
        assert "Y" in chroms
        assert "MT" in chroms

    def test_invalid_chromosome_raises(self) -> None:
        with pytest.raises(MalformedDataError):
            normalize_chromosome("99")
        with pytest.raises(MalformedDataError):
            normalize_chromosome("Z")


# ═══════════════════════════════════════════════════════════════════════════
# T1-05: Integration — parse → write to SQLite → read back
# ═══════════════════════════════════════════════════════════════════════════


class TestIntegration:
    """T1-05: Parse sample file → write to per-sample SQLite → verify."""

    @pytest.fixture()
    def sample_engine(self, tmp_path: Path) -> sa.Engine:
        """Create a per-sample SQLite database engine."""
        db_path = tmp_path / "sample_test.db"
        engine = sa.create_engine(f"sqlite:///{db_path}")
        create_sample_tables(engine)
        return engine

    def test_roundtrip_v5(self, sample_engine: sa.Engine) -> None:
        """Parse v5 → bulk insert → SELECT back and verify."""
        result = parse_23andme(V5_FILE)

        # Bulk insert using executemany
        rows = [
            {"rsid": v.rsid, "chrom": v.chrom, "pos": v.pos, "genotype": v.genotype}
            for v in result.variants
        ]
        with sample_engine.connect() as conn:
            conn.execute(raw_variants.insert(), rows)
            conn.commit()

        # Read back
        with sample_engine.connect() as conn:
            count = conn.execute(sa.select(sa.func.count()).select_from(raw_variants)).scalar()
            assert count == 1000

            # Verify a specific variant
            row = conn.execute(
                sa.select(raw_variants).where(raw_variants.c.rsid == "rs429358")
            ).fetchone()
            assert row is not None
            assert row.chrom == "19"
            assert row.pos == 44908684
            assert row.genotype == "TT"

    def test_roundtrip_v3(self, sample_engine: sa.Engine) -> None:
        """Parse v3 → bulk insert → verify row count and chrom normalization."""
        result = parse_23andme(V3_FILE)

        rows = [
            {"rsid": v.rsid, "chrom": v.chrom, "pos": v.pos, "genotype": v.genotype}
            for v in result.variants
        ]
        with sample_engine.connect() as conn:
            conn.execute(raw_variants.insert(), rows)
            conn.commit()

        with sample_engine.connect() as conn:
            count = conn.execute(sa.select(sa.func.count()).select_from(raw_variants)).scalar()
            assert count == 100

            # Verify chromosome normalization in DB
            x_rows = conn.execute(
                sa.select(raw_variants).where(raw_variants.c.chrom == "X")
            ).fetchall()
            assert len(x_rows) > 0

    def test_nocalls_stored_in_db(self, sample_engine: sa.Engine) -> None:
        """No-call variants are stored with genotype='--'."""
        result = parse_23andme(V5_FILE)

        rows = [
            {"rsid": v.rsid, "chrom": v.chrom, "pos": v.pos, "genotype": v.genotype}
            for v in result.variants
        ]
        with sample_engine.connect() as conn:
            conn.execute(raw_variants.insert(), rows)
            conn.commit()

        with sample_engine.connect() as conn:
            nocalls = conn.execute(
                sa.select(raw_variants).where(raw_variants.c.genotype == "--")
            ).fetchall()
            assert len(nocalls) == result.nocall_count


# ═══════════════════════════════════════════════════════════════════════════
# Edge cases & TextIO support
# ═══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Additional edge-case coverage."""

    def test_parse_from_string_io(self) -> None:
        """Parser works with TextIO (not just file paths)."""
        content = V5_FILE.read_text()
        result = parse_23andme(io.StringIO(content))
        assert result.version == FormatVersion.V5
        assert len(result.variants) == 1000

    def test_all_exception_types_are_parser_errors(self) -> None:
        assert issubclass(UnsupportedFormatError, ParserError)
        assert issubclass(MalformedDataError, ParserError)
        assert issubclass(UnrecognizedVersionError, ParserError)

    def test_parsed_variant_is_frozen(self) -> None:
        v = ParsedVariant(rsid="rs1", chrom="1", pos=100, genotype="AA")
        with pytest.raises(AttributeError):
            v.rsid = "rs2"  # type: ignore[misc]

    def test_detect_format_from_text_io(self) -> None:
        content = V4_FILE.read_text()
        assert detect_format(io.StringIO(content)) == FormatVersion.V4

    def test_position_zero_allowed(self) -> None:
        """Position 0 is valid (some markers use it)."""
        header = (
            "# This data file generated by 23andMe\n"
            "# reference human assembly build 37\n"
            "# rsid\tchromosome\tposition\tgenotype\n"
        )
        stream = io.StringIO(header + "rs123\t1\t0\tAA\n")
        result = parse_23andme(stream)
        assert result.variants[0].pos == 0
