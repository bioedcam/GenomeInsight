"""Tests for GRCh38 liftover integration (P4-19, T4-19).

T4-19: pyliftover converts rs1801133 GRCh37 position to correct GRCh38 position.
"""

from __future__ import annotations

from backend.ingestion.liftover import batch_convert, convert_coordinate, reset_liftover

# ── Unit tests: convert_coordinate ────────────────────────────────────


class TestConvertCoordinate:
    """T4-19: Single coordinate conversion from GRCh37 to GRCh38."""

    def test_rs1801133_mthfr(self) -> None:
        """T4-19 core: rs1801133 (MTHFR C677T) on chr1 GRCh37 → GRCh38.

        GRCh37 chr1:11856378 → GRCh38 chr1:11796321
        (verified via UCSC liftOver and Ensembl)
        """
        result = convert_coordinate("1", 11856378)
        assert result is not None
        chrom, pos = result
        assert chrom == "1"
        # GRCh38 position for rs1801133
        assert pos == 11796321

    def test_rs429358_apoe(self) -> None:
        """APOE rs429358 on chr19 lifts correctly."""
        result = convert_coordinate("19", 44908684)
        assert result is not None
        chrom, pos = result
        assert chrom == "19"
        # GRCh38 position for rs429358
        assert pos == 44404524

    def test_rs7412_apoe(self) -> None:
        """APOE rs7412 on chr19 lifts correctly."""
        result = convert_coordinate("19", 44908822)
        assert result is not None
        chrom, pos = result
        assert chrom == "19"
        assert pos == 44404662

    def test_x_chromosome(self) -> None:
        """X chromosome coordinates lift correctly."""
        result = convert_coordinate("X", 1000000)
        assert result is not None
        chrom, pos = result
        assert chrom == "X"
        assert pos == 1039265  # GRCh38 (1-based)

    def test_mt_chromosome(self) -> None:
        """MT chromosome — mitochondrial positions should lift (MT→chrM mapping)."""
        result = convert_coordinate("MT", 7028)
        assert result is not None
        chrom, pos = result
        assert chrom == "MT"
        # MT genome is nearly identical between builds
        assert pos == 7027

    def test_chr_prefix_handled(self) -> None:
        """Input with 'chr' prefix works the same as without."""
        result_no_prefix = convert_coordinate("1", 11856378)
        result_with_prefix = convert_coordinate("chr1", 11856378)
        assert result_no_prefix is not None
        assert result_with_prefix is not None
        assert result_no_prefix == result_with_prefix

    def test_returns_none_for_invalid_chrom(self) -> None:
        """Invalid chromosome returns None."""
        result = convert_coordinate("99", 100)
        assert result is None


# ── Unit tests: batch_convert ─────────────────────────────────────────


class TestBatchConvert:
    """Batch coordinate conversion."""

    def test_batch_multiple_variants(self) -> None:
        """Batch convert returns results for all variants."""
        variants = [
            ("rs1801133", "1", 11856378),
            ("rs429358", "19", 44908684),
            ("rs7412", "19", 44908822),
        ]
        results = batch_convert(variants)
        assert len(results) == 3
        assert results["rs1801133"] is not None
        assert results["rs429358"] is not None
        assert results["rs7412"] is not None

    def test_batch_empty_list(self) -> None:
        """Empty variant list returns empty dict."""
        results = batch_convert([])
        assert results == {}

    def test_batch_preserves_rsid_keys(self) -> None:
        """Result dict is keyed by rsid."""
        variants = [("rs123", "1", 100000)]
        results = batch_convert(variants)
        assert "rs123" in results


# ── Reset helper ──────────────────────────────────────────────────────


class TestResetLiftover:
    """Test the reset helper for test isolation."""

    def test_reset_and_reinit(self) -> None:
        """After reset, next call re-initialises the LiftOver instance."""
        # Ensure it's loaded
        result1 = convert_coordinate("1", 11856378)
        assert result1 is not None

        # Reset and convert again
        reset_liftover()
        result2 = convert_coordinate("1", 11856378)
        assert result2 is not None
        assert result1 == result2
