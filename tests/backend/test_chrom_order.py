"""Tests for the dependency-free ``backend.ingestion.chrom_order`` module.

``chrom_order`` was extracted from ``vcf_export`` so the Phase A union builders
can sort by chromosome without dragging in ``backend.db``/``backend.config``.
These tests pin the canonical order and the unknown-chromosome fallback, and
assert ``vcf_export`` still exposes the identical mapping (it re-exports this
module) so output ordering is byte-stable wherever it is used.
"""

from __future__ import annotations

from backend.ingestion.chrom_order import CHROM_ORDER, chrom_sort_key


def test_canonical_order_is_1_22_x_y_mt() -> None:
    expected = [str(i) for i in range(1, 23)] + ["X", "Y", "MT"]
    ordered = sorted(CHROM_ORDER, key=chrom_sort_key)
    assert ordered == expected


def test_autosomes_sort_numerically() -> None:
    # Lexical order would put "10" before "2"; the key must sort numerically.
    assert chrom_sort_key("2") < chrom_sort_key("10")
    assert chrom_sort_key("9") < chrom_sort_key("22")


def test_sex_and_mito_sort_after_autosomes() -> None:
    assert chrom_sort_key("22") < chrom_sort_key("X")
    assert chrom_sort_key("X") < chrom_sort_key("Y")
    assert chrom_sort_key("Y") < chrom_sort_key("MT")


def test_unknown_chromosome_sorts_last() -> None:
    assert chrom_sort_key("GL000209.1") == 99
    assert chrom_sort_key("") == 99
    assert chrom_sort_key("MT") < chrom_sort_key("unplaced")


def test_vcf_export_reexports_identical_mapping() -> None:
    # vcf_export re-exports CHROM_ORDER; the two must stay byte-identical so
    # exporter output and the union builders agree on ordering.
    from backend.ingestion.vcf_export import _CHROM_ORDER

    assert _CHROM_ORDER == CHROM_ORDER
