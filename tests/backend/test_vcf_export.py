"""Tests for VCF 4.2 export (P1-09).

Test IDs covered:
  T1-09 — VCF export produces valid VCF 4.2
  T1-10 — VCF contains correct ##reference=GRCh37 and ##source=GenomeInsight
"""

from __future__ import annotations

import re
from datetime import date
from io import StringIO
from pathlib import Path

import sqlalchemy as sa

from backend.ingestion.vcf_export import (
    _genotype_to_vcf_fields,
    export_vcf_from_engine,
    export_vcf_from_rows,
)

# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

FIXED_DATE = date(2026, 3, 10)

SAMPLE_ROWS: list[tuple[str, str, int, str]] = [
    ("rs1000001", "1", 100000, "AA"),
    ("rs1000002", "1", 200000, "AG"),
    ("rs1000003", "2", 50000, "CC"),
    ("rs1000004", "X", 10000, "AT"),
    ("rs1000005", "Y", 5000, "T"),
    ("rs1000006", "MT", 10740, "G"),
    ("rs1000007", "1", 150000, "--"),
]


# ═══════════════════════════════════════════════════════════════════════
# T1-10: Header validation
# ═══════════════════════════════════════════════════════════════════════


class TestVCFHeaders:
    """T1-10: VCF contains correct meta-information headers."""

    def test_fileformat_header(self) -> None:
        vcf = export_vcf_from_rows([], file_date=FIXED_DATE)
        assert vcf.startswith("##fileformat=VCFv4.2\n")

    def test_reference_header(self) -> None:
        vcf = export_vcf_from_rows([], file_date=FIXED_DATE)
        assert "##reference=GRCh37\n" in vcf

    def test_source_header(self) -> None:
        vcf = export_vcf_from_rows([], file_date=FIXED_DATE)
        assert "##source=GenomeInsight\n" in vcf

    def test_filedate_header(self) -> None:
        vcf = export_vcf_from_rows([], file_date=FIXED_DATE)
        assert "##fileDate=20260310\n" in vcf

    def test_format_gt_header(self) -> None:
        vcf = export_vcf_from_rows([], file_date=FIXED_DATE)
        assert '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">' in vcf

    def test_contig_lines_present(self) -> None:
        vcf = export_vcf_from_rows([], file_date=FIXED_DATE)
        for chrom in [str(i) for i in range(1, 23)] + ["X", "Y", "MT"]:
            assert f"##contig=<ID={chrom}>" in vcf

    def test_column_header_line(self) -> None:
        vcf = export_vcf_from_rows([], sample_name="TestSample", file_date=FIXED_DATE)
        expected = "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tTestSample"
        assert expected in vcf

    def test_sample_name_in_header(self) -> None:
        vcf = export_vcf_from_rows([], sample_name="MySample", file_date=FIXED_DATE)
        lines = vcf.strip().split("\n")
        header_line = [ln for ln in lines if ln.startswith("#CHROM")][0]
        assert header_line.endswith("MySample")


# ═══════════════════════════════════════════════════════════════════════
# T1-09: Valid VCF 4.2 output
# ═══════════════════════════════════════════════════════════════════════


class TestVCFDataLines:
    """T1-09: VCF export produces valid VCF 4.2 data lines."""

    def test_homozygous_call(self) -> None:
        rows = [("rs100", "1", 1000, "AA")]
        vcf = export_vcf_from_rows(rows, file_date=FIXED_DATE)
        data = _get_data_lines(vcf)
        assert len(data) == 1
        fields = data[0].split("\t")
        assert fields[0] == "1"       # CHROM
        assert fields[1] == "1000"    # POS
        assert fields[2] == "rs100"   # ID
        assert fields[3] == "A"       # REF
        assert fields[4] == "."       # ALT (hom → no alt)
        assert fields[5] == "."       # QUAL
        assert fields[6] == "PASS"    # FILTER
        assert fields[7] == "."       # INFO
        assert fields[8] == "GT"      # FORMAT
        assert fields[9] == "0/0"     # GT value

    def test_heterozygous_call(self) -> None:
        rows = [("rs200", "2", 2000, "AG")]
        vcf = export_vcf_from_rows(rows, file_date=FIXED_DATE)
        data = _get_data_lines(vcf)
        fields = data[0].split("\t")
        assert fields[3] == "A"       # REF = first allele
        assert fields[4] == "G"       # ALT = second allele
        assert fields[9] == "0/1"     # het GT

    def test_haploid_call(self) -> None:
        """Y/MT chromosomes may have single-character genotypes."""
        rows = [("rs300", "Y", 5000, "T")]
        vcf = export_vcf_from_rows(rows, file_date=FIXED_DATE)
        data = _get_data_lines(vcf)
        fields = data[0].split("\t")
        assert fields[3] == "T"       # REF
        assert fields[4] == "."       # ALT
        assert fields[9] == "0"       # haploid GT

    def test_nocalls_skipped_by_default(self) -> None:
        rows = [
            ("rs100", "1", 1000, "AA"),
            ("rs101", "1", 2000, "--"),
        ]
        vcf = export_vcf_from_rows(rows, file_date=FIXED_DATE)
        data = _get_data_lines(vcf)
        assert len(data) == 1
        assert "rs101" not in vcf.split("\n")[-2]  # no-call absent

    def test_nocalls_included_when_requested(self) -> None:
        rows = [
            ("rs100", "1", 1000, "AA"),
            ("rs101", "1", 2000, "--"),
        ]
        vcf = export_vcf_from_rows(rows, skip_nocalls=False, file_date=FIXED_DATE)
        data = _get_data_lines(vcf)
        assert len(data) == 2
        nocall_fields = data[1].split("\t")
        assert nocall_fields[3] == "N"     # REF = N for no-call
        assert nocall_fields[9] == "./."   # missing GT

    def test_rows_sorted_by_chrom_pos(self) -> None:
        rows = [
            ("rs300", "2", 500, "CC"),
            ("rs100", "1", 2000, "AA"),
            ("rs200", "1", 1000, "GG"),
        ]
        vcf = export_vcf_from_rows(rows, file_date=FIXED_DATE)
        data = _get_data_lines(vcf)
        assert len(data) == 3
        # chr1:1000, chr1:2000, chr2:500
        assert data[0].split("\t")[1] == "1000"
        assert data[1].split("\t")[1] == "2000"
        assert data[2].split("\t")[0] == "2"

    def test_all_data_lines_have_10_columns(self) -> None:
        vcf = export_vcf_from_rows(SAMPLE_ROWS, file_date=FIXED_DATE)
        data = _get_data_lines(vcf)
        for line in data:
            assert len(line.split("\t")) == 10

    def test_vcf_header_regex_validates(self) -> None:
        """VCF 4.2 header must match ##fileformat=VCFv4.2."""
        vcf = export_vcf_from_rows(SAMPLE_ROWS, file_date=FIXED_DATE)
        assert re.match(r"^##fileformat=VCFv4\.2\n", vcf)

    def test_complete_export_with_sample_rows(self) -> None:
        """Full export of SAMPLE_ROWS produces expected line count."""
        vcf = export_vcf_from_rows(SAMPLE_ROWS, file_date=FIXED_DATE)
        data = _get_data_lines(vcf)
        # 7 rows, 1 is a no-call (skipped by default) → 6 data lines
        assert len(data) == 6


# ═══════════════════════════════════════════════════════════════════════
# Genotype conversion unit tests
# ═══════════════════════════════════════════════════════════════════════


class TestGenotypeConversion:
    def test_nocall_returns_none(self) -> None:
        assert _genotype_to_vcf_fields("--") is None

    def test_empty_returns_none(self) -> None:
        assert _genotype_to_vcf_fields("") is None

    def test_homozygous(self) -> None:
        assert _genotype_to_vcf_fields("CC") == ("C", ".", "0/0")

    def test_heterozygous(self) -> None:
        assert _genotype_to_vcf_fields("CT") == ("C", "T", "0/1")

    def test_haploid(self) -> None:
        assert _genotype_to_vcf_fields("A") == ("A", ".", "0")


# ═══════════════════════════════════════════════════════════════════════
# File / stream output tests
# ═══════════════════════════════════════════════════════════════════════


class TestOutputDestinations:
    def test_write_to_file(self, tmp_path: Path) -> None:
        dest = tmp_path / "output.vcf"
        content = export_vcf_from_rows(
            SAMPLE_ROWS, dest=dest, file_date=FIXED_DATE,
        )
        assert dest.exists()
        assert dest.read_text(encoding="utf-8") == content

    def test_write_to_stream(self) -> None:
        stream = StringIO()
        content = export_vcf_from_rows(
            SAMPLE_ROWS, dest=stream, file_date=FIXED_DATE,
        )
        assert stream.getvalue() == content

    def test_return_string_when_no_dest(self) -> None:
        content = export_vcf_from_rows(SAMPLE_ROWS, file_date=FIXED_DATE)
        assert isinstance(content, str)
        assert content.startswith("##fileformat=VCFv4.2")


# ═══════════════════════════════════════════════════════════════════════
# Database integration test
# ═══════════════════════════════════════════════════════════════════════


class TestExportFromEngine:
    """Integration: export VCF directly from a sample SQLite engine."""

    def test_export_from_sample_engine(self, sample_with_variants: sa.Engine) -> None:
        vcf = export_vcf_from_engine(
            sample_with_variants,
            sample_name="TestPatient",
            file_date=FIXED_DATE,
        )
        assert "##fileformat=VCFv4.2" in vcf
        assert "##reference=GRCh37" in vcf
        assert "##source=GenomeInsight" in vcf
        assert "TestPatient" in vcf
        data = _get_data_lines(vcf)
        # sample_with_variants has 10 rows, none are no-calls → 10 lines
        assert len(data) == 10

    def test_export_to_file(
        self, sample_with_variants: sa.Engine, tmp_path: Path,
    ) -> None:
        dest = tmp_path / "sample.vcf"
        export_vcf_from_engine(
            sample_with_variants, dest=dest, file_date=FIXED_DATE,
        )
        assert dest.exists()
        text = dest.read_text(encoding="utf-8")
        assert text.startswith("##fileformat=VCFv4.2")

    def test_empty_table_produces_header_only(self, sample_engine: sa.Engine) -> None:
        vcf = export_vcf_from_engine(sample_engine, file_date=FIXED_DATE)
        assert "##fileformat=VCFv4.2" in vcf
        data = _get_data_lines(vcf)
        assert len(data) == 0


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _get_data_lines(vcf: str) -> list[str]:
    """Extract non-header, non-empty lines from a VCF string."""
    return [
        line for line in vcf.strip().split("\n")
        if line and not line.startswith("#")
    ]
