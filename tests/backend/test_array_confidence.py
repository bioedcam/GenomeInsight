"""Unit tests for the array-confidence reliability badge (SW-A11 / #14).

Covers the pure Weedon-PPV classification, the catalogue/novelty signal, and the
badge envelope. The badge is a reliability flag only — these tests lock that it
never carries or implies an evidence-level/significance change.
"""

from __future__ import annotations

import pytest

from backend.analysis.array_confidence import (
    RELIABILITY_HIGH,
    RELIABILITY_LOW,
    RELIABILITY_MODERATE,
    RELIABILITY_UNKNOWN,
    RELIABILITY_VERY_LOW,
    WEEDON_PMID,
    _is_catalogued,
    array_confidence_badge,
    classify_array_reliability,
)
from backend.disclaimers import ARRAY_CONFIDENCE_CONTEXT_ONLY


class TestClassifyArrayReliability:
    @pytest.mark.parametrize(
        "popmax_af,expected",
        [
            (0.30, RELIABILITY_HIGH),
            (0.01, RELIABILITY_HIGH),
            (1e-3, RELIABILITY_HIGH),  # band edge inclusive
            (9.9e-4, RELIABILITY_MODERATE),
            (5e-4, RELIABILITY_MODERATE),
            (1e-5, RELIABILITY_MODERATE),  # band edge inclusive
            (9e-6, RELIABILITY_LOW),
            (1e-7, RELIABILITY_LOW),
            (0.0, RELIABILITY_LOW),
        ],
    )
    def test_frequency_bands(self, popmax_af: float, expected: str) -> None:
        # Catalogue status is irrelevant once a frequency is known.
        assert classify_array_reliability(popmax_af, is_catalogued=True) == expected
        assert classify_array_reliability(popmax_af, is_catalogued=False) == expected

    def test_no_frequency_catalogued_is_unknown_not_high(self) -> None:
        # Fail-safe: missing AF is never treated as "common/reliable".
        assert classify_array_reliability(None, is_catalogued=True) == RELIABILITY_UNKNOWN

    def test_no_frequency_uncatalogued_is_very_low(self) -> None:
        assert classify_array_reliability(None, is_catalogued=False) == RELIABILITY_VERY_LOW


class TestIsCatalogued:
    def test_dbsnp_rs_identifier(self) -> None:
        assert _is_catalogued("rs80357906", None, None) is True

    def test_clinvar_significance(self) -> None:
        assert _is_catalogued(None, "Pathogenic", None) is True

    def test_clinvar_accession(self) -> None:
        assert _is_catalogued(None, None, "VCV000017661") is True

    def test_i_prefix_chip_id_is_not_catalogued(self) -> None:
        # Vendor "i" probe IDs are not dbSNP identifiers.
        assert _is_catalogued("i5000123", None, None) is False

    def test_nothing_known_is_not_catalogued(self) -> None:
        assert _is_catalogued(None, None, None) is False


class TestArrayConfidenceBadge:
    def test_high_band_does_not_recommend_confirmation(self) -> None:
        badge = array_confidence_badge(0.05, is_catalogued=True)
        assert badge["reliability"] == RELIABILITY_HIGH
        assert badge["confirm_in_clia_recommended"] is False
        assert badge["is_novel"] is False

    def test_low_band_recommends_confirmation(self) -> None:
        badge = array_confidence_badge(1e-6, is_catalogued=True)
        assert badge["reliability"] == RELIABILITY_LOW
        assert badge["confirm_in_clia_recommended"] is True

    def test_novel_flag_only_when_uncatalogued_and_no_af(self) -> None:
        assert array_confidence_badge(None, is_catalogued=False)["is_novel"] is True
        assert array_confidence_badge(None, is_catalogued=True)["is_novel"] is False
        assert array_confidence_badge(1e-6, is_catalogued=False)["is_novel"] is False

    def test_badge_envelope_is_context_only(self) -> None:
        badge = array_confidence_badge(5e-4, is_catalogued=True)
        assert badge["context_only"] is True
        assert badge["note"] == ARRAY_CONFIDENCE_CONTEXT_ONLY
        assert WEEDON_PMID in badge["pmid_citations"]
        # A reliability flag must never carry evidence-tier / significance fields.
        assert "evidence_level" not in badge
        assert "clinvar_significance" not in badge
        assert badge["gnomad_af_popmax"] == 5e-4
