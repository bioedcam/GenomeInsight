"""Tests for custom gene panel parser (P4-11).

Covers:
  - Gene list parsing (.txt/.csv format)
  - BED file parsing
  - Format auto-detection
  - Invalid input handling
  - Edge cases (duplicates, comments, empty lines)
"""

from __future__ import annotations

import pytest

from backend.analysis.custom_panels import (
    detect_and_parse,
    parse_bed_file,
    parse_gene_list,
)

# ═══════════════════════════════════════════════════════════════════════
# Gene list parsing
# ═══════════════════════════════════════════════════════════════════════


class TestParseGeneList:
    """Tests for gene list parser."""

    def test_one_per_line(self) -> None:
        """Parses one gene symbol per line."""
        content = "BRCA1\nBRCA2\nTP53\n"
        result = parse_gene_list(content)
        assert result.gene_symbols == ["BRCA1", "BRCA2", "TP53"]
        assert result.source_type == "gene_list"
        assert result.gene_count == 3

    def test_comma_separated(self) -> None:
        """Parses comma-separated gene symbols."""
        content = "BRCA1, BRCA2, TP53"
        result = parse_gene_list(content)
        assert result.gene_symbols == ["BRCA1", "BRCA2", "TP53"]

    def test_tab_separated(self) -> None:
        """Parses tab-separated gene symbols."""
        content = "BRCA1\tBRCA2\tTP53"
        result = parse_gene_list(content)
        assert result.gene_symbols == ["BRCA1", "BRCA2", "TP53"]

    def test_mixed_separators(self) -> None:
        """Parses mixed separator formats."""
        content = "BRCA1, BRCA2\nTP53; CFTR"
        result = parse_gene_list(content)
        assert result.gene_symbols == ["BRCA1", "BRCA2", "TP53", "CFTR"]

    def test_case_normalization(self) -> None:
        """Normalizes gene symbols to uppercase."""
        content = "brca1\nBrca2\ntp53"
        result = parse_gene_list(content)
        assert result.gene_symbols == ["BRCA1", "BRCA2", "TP53"]

    def test_skips_comments(self) -> None:
        """Lines starting with # are skipped."""
        content = "# This is a comment\nBRCA1\n# Another comment\nTP53"
        result = parse_gene_list(content)
        assert result.gene_symbols == ["BRCA1", "TP53"]

    def test_skips_empty_lines(self) -> None:
        """Empty lines are ignored."""
        content = "\nBRCA1\n\n\nTP53\n\n"
        result = parse_gene_list(content)
        assert result.gene_symbols == ["BRCA1", "TP53"]

    def test_deduplicates(self) -> None:
        """Duplicate gene symbols are removed."""
        content = "BRCA1\nBRCA2\nBRCA1\nTP53\nBRCA2"
        result = parse_gene_list(content)
        assert result.gene_symbols == ["BRCA1", "BRCA2", "TP53"]

    def test_invalid_symbols_warned(self) -> None:
        """Invalid symbols generate warnings but don't fail."""
        content = "BRCA1\n12345\nTP53\n@invalid"
        result = parse_gene_list(content)
        assert result.gene_symbols == ["BRCA1", "TP53"]
        assert len(result.warnings) == 2

    def test_empty_content_raises(self) -> None:
        """Empty content raises ValueError."""
        with pytest.raises(ValueError, match="No valid gene symbols"):
            parse_gene_list("")

    def test_only_comments_raises(self) -> None:
        """Content with only comments raises ValueError."""
        with pytest.raises(ValueError, match="No valid gene symbols"):
            parse_gene_list("# comment\n# another")

    def test_gene_with_hyphen(self) -> None:
        """Gene symbols with hyphens are valid (e.g., HLA-B)."""
        content = "HLA-B\nHLA-DQB1"
        result = parse_gene_list(content)
        assert result.gene_symbols == ["HLA-B", "HLA-DQB1"]

    def test_gene_with_dot(self) -> None:
        """Gene symbols with dots are valid (e.g., APOBEC3G.1)."""
        content = "APOBEC3G.1\nMTHFR"
        result = parse_gene_list(content)
        assert result.gene_symbols == ["APOBEC3G.1", "MTHFR"]

    def test_whitespace_trimming(self) -> None:
        """Leading/trailing whitespace is trimmed."""
        content = "  BRCA1  \n  TP53  "
        result = parse_gene_list(content)
        assert result.gene_symbols == ["BRCA1", "TP53"]


# ═══════════════════════════════════════════════════════════════════════
# BED file parsing
# ═══════════════════════════════════════════════════════════════════════


class TestParseBedFile:
    """Tests for BED file parser."""

    def test_basic_bed3(self) -> None:
        """Parses BED3 format (chrom, start, end)."""
        content = "chr17\t41196312\t41277500\nchr7\t117120017\t117308718"
        result = parse_bed_file(content)
        assert result.region_count == 2
        assert result.source_type == "bed"
        assert result.bed_regions[0].chrom == "chr17"
        assert result.bed_regions[0].start == 41196312
        assert result.bed_regions[0].end == 41277500

    def test_bed4_with_gene_names(self) -> None:
        """Parses BED4 format with gene names in 4th column."""
        content = "chr17\t41196312\t41277500\tBRCA1\nchr7\t117120017\t117308718\tCFTR"
        result = parse_bed_file(content)
        assert result.gene_symbols == ["BRCA1", "CFTR"]
        assert result.region_count == 2
        assert result.bed_regions[0].name == "BRCA1"

    def test_skips_track_lines(self) -> None:
        """Track and browser lines are skipped."""
        content = "track name=test\nbrowser position chr17:1-100\nchr17\t41196312\t41277500\tBRCA1"
        result = parse_bed_file(content)
        assert result.region_count == 1

    def test_skips_comment_lines(self) -> None:
        """Comment lines starting with # are skipped."""
        content = "# Gene panel BED file\nchr17\t41196312\t41277500\tBRCA1"
        result = parse_bed_file(content)
        assert result.region_count == 1

    def test_invalid_chromosome(self) -> None:
        """Invalid chromosome names are warned and skipped."""
        content = "chrZ\t100\t200\tFAKE\nchr17\t41196312\t41277500\tBRCA1"
        result = parse_bed_file(content)
        assert result.region_count == 1
        assert len(result.warnings) == 1

    def test_invalid_coordinates(self) -> None:
        """Non-integer coordinates are warned and skipped."""
        content = "chr17\tabc\t200\tBRCA1\nchr7\t117120017\t117308718\tCFTR"
        result = parse_bed_file(content)
        assert result.region_count == 1
        assert len(result.warnings) == 1

    def test_end_before_start(self) -> None:
        """Regions where end <= start are skipped."""
        content = "chr17\t200\t100\tBRCA1\nchr7\t117120017\t117308718\tCFTR"
        result = parse_bed_file(content)
        assert result.region_count == 1
        assert len(result.warnings) == 1

    def test_empty_bed_raises(self) -> None:
        """Empty BED file raises ValueError."""
        with pytest.raises(ValueError, match="No valid BED regions"):
            parse_bed_file("")

    def test_no_prefix_chromosomes(self) -> None:
        """Chromosomes without 'chr' prefix are valid."""
        content = "17\t41196312\t41277500\tBRCA1\n7\t117120017\t117308718\tCFTR"
        result = parse_bed_file(content)
        assert result.region_count == 2

    def test_space_separated_fallback(self) -> None:
        """Space-separated BED lines are accepted as fallback."""
        content = "chr17 41196312 41277500"
        result = parse_bed_file(content)
        assert result.region_count == 1

    def test_deduplicates_gene_names(self) -> None:
        """Duplicate gene names in BED file are deduplicated."""
        content = (
            "chr17\t41196312\t41277500\tBRCA1\n"
            "chr17\t41300000\t41400000\tBRCA1\n"
            "chr7\t117120017\t117308718\tCFTR"
        )
        result = parse_bed_file(content)
        assert result.gene_symbols == ["BRCA1", "CFTR"]
        assert result.region_count == 3


# ═══════════════════════════════════════════════════════════════════════
# Format auto-detection
# ═══════════════════════════════════════════════════════════════════════


class TestDetectAndParse:
    """Tests for format auto-detection."""

    def test_bed_by_extension(self) -> None:
        """BED format detected by .bed extension."""
        content = "chr17\t41196312\t41277500\tBRCA1"
        result = detect_and_parse(content, "panel.bed")
        assert result.source_type == "bed"

    def test_gene_list_by_extension(self) -> None:
        """Gene list format detected by .txt extension."""
        content = "BRCA1\nTP53"
        result = detect_and_parse(content, "genes.txt")
        assert result.source_type == "gene_list"

    def test_bed_by_content_heuristic(self) -> None:
        """BED format detected by content heuristic (tab-separated numerics)."""
        content = "chr17\t41196312\t41277500\tBRCA1\nchr7\t117120017\t117308718\tCFTR"
        result = detect_and_parse(content, "panel.tsv")
        assert result.source_type == "bed"

    def test_gene_list_fallback(self) -> None:
        """Falls back to gene list when content doesn't look like BED."""
        content = "BRCA1\nTP53\nCFTR"
        result = detect_and_parse(content, "data.csv")
        assert result.source_type == "gene_list"
