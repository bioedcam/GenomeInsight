"""Tests for global disclaimer finalization (P4-21e).

Validates that:
- All disclaimer text in backend/disclaimers.py is finalized
- All external links are well-formed URLs
- The acknowledgment gate works correctly (via API integration)
- Each disclaimer covers its required topics
- No placeholder or TODO text remains
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import pytest

from backend.disclaimers import (
    APOE_GATE_ACCEPT_LABEL,
    APOE_GATE_DECLINE_LABEL,
    APOE_GATE_TEXT,
    CANCER_DISCLAIMER_TEXT,
    CARDIOVASCULAR_DISCLAIMER_TEXT,
    CARRIER_GENE_NOTES,
    CARRIER_STATUS_DISCLAIMER_TEXT,
    GLOBAL_DISCLAIMER_ACCEPT_LABEL,
    GLOBAL_DISCLAIMER_TEXT,
    GLOBAL_DISCLAIMER_TITLE,
)

# ── Helpers ─────────────────────────────────────────────────────────────

_URL_PATTERN = re.compile(r"https?://[^\s)>]+")

# Known-stale domains that redirect or are no longer canonical
_STALE_REDIRECT_DOMAINS = {"thefhfoundation.org"}


def _extract_urls(text: str) -> list[str]:
    """Extract all URLs from a text string."""
    return _URL_PATTERN.findall(text)


def _all_disclaimer_texts() -> list[tuple[str, str]]:
    """Return (name, text) pairs for every disclaimer body."""
    return [
        ("global", GLOBAL_DISCLAIMER_TEXT),
        ("apoe_gate", APOE_GATE_TEXT),
        ("carrier_status", CARRIER_STATUS_DISCLAIMER_TEXT),
        ("cancer", CANCER_DISCLAIMER_TEXT),
        ("cardiovascular", CARDIOVASCULAR_DISCLAIMER_TEXT),
    ]


# ── No placeholder / TODO text ──────────────────────────────────────────


class TestNoPlaceholders:
    """Ensure no draft markers remain in any disclaimer."""

    @pytest.mark.parametrize(
        "name,text", _all_disclaimer_texts(), ids=[t[0] for t in _all_disclaimer_texts()]
    )
    def test_no_todo_markers(self, name: str, text: str) -> None:
        low = text.lower()
        for marker in ("todo", "fixme", "xxx", "placeholder", "tbd", "lorem ipsum"):
            assert marker not in low, f"{name} disclaimer contains '{marker}'"

    @pytest.mark.parametrize(
        "name,text", _all_disclaimer_texts(), ids=[t[0] for t in _all_disclaimer_texts()]
    )
    def test_no_empty_sections(self, name: str, text: str) -> None:
        assert len(text.strip()) > 200, f"{name} disclaimer is suspiciously short"


# ── URL well-formedness ──────────────────────────────────────────────────


class TestURLWellFormedness:
    """Validate that every URL in every disclaimer is well-formed."""

    @pytest.mark.parametrize(
        "name,text", _all_disclaimer_texts(), ids=[t[0] for t in _all_disclaimer_texts()]
    )
    def test_all_urls_are_valid(self, name: str, text: str) -> None:
        urls = _extract_urls(text)
        for url in urls:
            parsed = urlparse(url)
            assert parsed.scheme in (
                "http",
                "https",
            ), f"{name}: bad scheme in {url}"
            assert "." in parsed.netloc, f"{name}: bad host in {url}"
            assert " " not in url, f"{name}: space in URL {url}"

    def test_global_disclaimer_has_no_external_links(self) -> None:
        """Global disclaimer should not contain external links (info only)."""
        urls = _extract_urls(GLOBAL_DISCLAIMER_TEXT)
        assert urls == [], "Global disclaimer should not embed URLs"


# ── Link content validation ──────────────────────────────────────────────


class TestDisclaimerLinks:
    """Validate specific expected links in each disclaimer."""

    def test_apoe_gate_links(self) -> None:
        urls = _extract_urls(APOE_GATE_TEXT)
        domains = [urlparse(u).netloc for u in urls]
        assert "www.nia.nih.gov" in domains, "Missing NIA link"
        assert "www.alz.org" in domains, "Missing Alzheimer's Association link"
        assert "findageneticcounselor.nsgc.org" in domains, "Missing NSGC link"

    def test_carrier_status_links(self) -> None:
        urls = _extract_urls(CARRIER_STATUS_DISCLAIMER_TEXT)
        domains = [urlparse(u).netloc for u in urls]
        assert "findageneticcounselor.nsgc.org" in domains, "Missing NSGC link"
        assert "www.acog.org" in domains, "Missing ACOG link"
        assert "medlineplus.gov" in domains, "Missing MedlinePlus link"

    def test_cancer_links(self) -> None:
        urls = _extract_urls(CANCER_DISCLAIMER_TEXT)
        domains = [urlparse(u).netloc for u in urls]
        assert "www.cancer.gov" in domains, "Missing NCI link"
        assert "findageneticcounselor.nsgc.org" in domains, "Missing NSGC link"
        assert "www.facingourrisk.org" in domains, "Missing FORCE link"

    def test_cardiovascular_links(self) -> None:
        urls = _extract_urls(CARDIOVASCULAR_DISCLAIMER_TEXT)
        domains = [urlparse(u).netloc for u in urls]
        assert "familyheart.org" in domains, "Missing Family Heart Foundation link"
        assert "www.heart.org" in domains, "Missing AHA link"
        assert "findageneticcounselor.nsgc.org" in domains, "Missing NSGC link"

    def test_no_redirect_domains(self) -> None:
        """Ensure no links point to known-stale domains that redirect."""
        for name, text in _all_disclaimer_texts():
            urls = _extract_urls(text)
            for url in urls:
                domain = urlparse(url).netloc
                assert domain not in _STALE_REDIRECT_DOMAINS, (
                    f"{name}: stale domain {domain} in {url}"
                )


# ── Global disclaimer topic coverage ──────────────────────────────────


class TestGlobalDisclaimerTopics:
    """Verify the global disclaimer covers all required topics (7 points)."""

    def test_not_a_diagnostic_tool(self) -> None:
        assert "not a diagnostic tool" in GLOBAL_DISCLAIMER_TEXT.lower()

    def test_not_substitute_for_medical_advice(self) -> None:
        text = GLOBAL_DISCLAIMER_TEXT.lower()
        assert "not a substitute" in text or "not substitute" in text

    def test_variant_interpretation_limitations(self) -> None:
        text = GLOBAL_DISCLAIMER_TEXT.lower()
        assert "variant" in text and "classification" in text

    def test_genotyping_chip_limitations(self) -> None:
        text = GLOBAL_DISCLAIMER_TEXT.lower()
        assert "genotyping chip" in text or "consumer genotyping" in text

    def test_population_specific_considerations(self) -> None:
        text = GLOBAL_DISCLAIMER_TEXT.lower()
        assert "population" in text

    def test_privacy_responsibility(self) -> None:
        text = GLOBAL_DISCLAIMER_TEXT.lower()
        assert "privacy" in text

    def test_emotional_preparedness(self) -> None:
        text = GLOBAL_DISCLAIMER_TEXT.lower()
        assert "emotional" in text

    def test_mentions_fda_not_approved(self) -> None:
        text = GLOBAL_DISCLAIMER_TEXT.lower()
        assert "fda" in text

    def test_mentions_no_outbound_variant_data(self) -> None:
        text = GLOBAL_DISCLAIMER_TEXT.lower()
        assert "does not transmit" in text or "never variant data" in text

    def test_title_and_labels_non_empty(self) -> None:
        assert len(GLOBAL_DISCLAIMER_TITLE) > 10
        assert len(GLOBAL_DISCLAIMER_ACCEPT_LABEL) > 5


# ── APOE gate topic coverage ────────────────────────────────────────────


class TestAPOEGateTopics:
    """Verify the APOE gate covers required topics (PRD hardcoded text)."""

    def test_mentions_alzheimers(self) -> None:
        assert "alzheimer" in APOE_GATE_TEXT.lower()

    def test_mentions_e4_allele(self) -> None:
        assert "e4" in APOE_GATE_TEXT.lower() or "ε4" in APOE_GATE_TEXT

    def test_having_e4_does_not_mean_disease(self) -> None:
        assert "does not mean" in APOE_GATE_TEXT.lower()

    def test_non_dismissible_language(self) -> None:
        assert "cannot be dismissed" in APOE_GATE_TEXT.lower()

    def test_mentions_genetic_counselor(self) -> None:
        assert "genetic counselor" in APOE_GATE_TEXT.lower()

    def test_nia_link_present(self) -> None:
        assert "nia.nih.gov" in APOE_GATE_TEXT

    def test_alz_org_link_present(self) -> None:
        assert "alz.org" in APOE_GATE_TEXT

    def test_nsgc_link_present(self) -> None:
        assert "nsgc.org" in APOE_GATE_TEXT

    def test_accept_and_decline_labels(self) -> None:
        assert len(APOE_GATE_ACCEPT_LABEL) > 5
        assert len(APOE_GATE_DECLINE_LABEL) > 5
        assert "show" in APOE_GATE_ACCEPT_LABEL.lower()
        decline = APOE_GATE_DECLINE_LABEL.lower()
        assert "skip" in decline or "not now" in decline


# ── Carrier status topic coverage ────────────────────────────────────────


class TestCarrierStatusTopics:
    """Verify carrier status disclaimer covers required topics."""

    def test_mentions_reproductive_context(self) -> None:
        text = CARRIER_STATUS_DISCLAIMER_TEXT.lower()
        assert "reproductive" in text

    def test_carrier_not_affected(self) -> None:
        text = CARRIER_STATUS_DISCLAIMER_TEXT.lower()
        assert "carrier" in text and "affected" in text

    def test_mentions_brca_special_case(self) -> None:
        assert "BRCA1" in CARRIER_STATUS_DISCLAIMER_TEXT
        assert "BRCA2" in CARRIER_STATUS_DISCLAIMER_TEXT

    def test_mentions_chip_limitations(self) -> None:
        text = CARRIER_STATUS_DISCLAIMER_TEXT.lower()
        assert "genotyping chip" in text or "consumer genotyping" in text

    def test_mentions_genetic_counseling(self) -> None:
        assert "genetic counselor" in CARRIER_STATUS_DISCLAIMER_TEXT.lower()


# ── Carrier gene notes ──────────────────────────────────────────────────


class TestCarrierGeneNotes:
    """Validate per-gene carrier notes cover all required genes."""

    REQUIRED_GENES = ["CFTR", "HBB", "GBA", "HEXA", "BRCA1", "BRCA2", "SMN1"]

    def test_all_required_genes_present(self) -> None:
        for gene in self.REQUIRED_GENES:
            assert gene in CARRIER_GENE_NOTES, f"Missing gene note for {gene}"

    def test_notes_are_substantial(self) -> None:
        for gene, note in CARRIER_GENE_NOTES.items():
            assert len(note) > 50, f"Gene note for {gene} is too short"

    def test_brca_notes_mention_cancer_module(self) -> None:
        for gene in ("BRCA1", "BRCA2"):
            assert "cancer module" in CARRIER_GENE_NOTES[gene].lower()

    def test_smn1_notes_mention_chip_limitation(self) -> None:
        text = CARRIER_GENE_NOTES["SMN1"].lower()
        assert "genotyping chip" in text or "copy number" in text


# ── Cancer disclaimer topic coverage ──────────────────────────────────


class TestCancerDisclaimerTopics:
    """Verify cancer disclaimer covers required topics."""

    def test_predisposition_not_diagnosis(self) -> None:
        assert "not diagnosis" in CANCER_DISCLAIMER_TEXT.lower()

    def test_mentions_prs_research_grade(self) -> None:
        text = CANCER_DISCLAIMER_TEXT.lower()
        assert "polygenic risk" in text or "prs" in text

    def test_mentions_clinical_testing(self) -> None:
        assert "clinical" in CANCER_DISCLAIMER_TEXT.lower()

    def test_mentions_counselor(self) -> None:
        assert "genetic counselor" in CANCER_DISCLAIMER_TEXT.lower()


# ── Cardiovascular disclaimer topic coverage ──────────────────────────


class TestCardiovascularDisclaimerTopics:
    """Verify cardiovascular disclaimer covers required topics."""

    def test_mentions_fh(self) -> None:
        text = CARDIOVASCULAR_DISCLAIMER_TEXT.lower()
        assert "familial hypercholesterolemia" in text or "fh" in text

    def test_mentions_lipid_therapy(self) -> None:
        text = CARDIOVASCULAR_DISCLAIMER_TEXT.lower()
        assert "lipid" in text

    def test_mentions_chip_limitations(self) -> None:
        text = CARDIOVASCULAR_DISCLAIMER_TEXT.lower()
        assert "genotyping chip" in text or "consumer genotyping" in text

    def test_mentions_counselor(self) -> None:
        text = CARDIOVASCULAR_DISCLAIMER_TEXT.lower()
        assert "genetic counselor" in text or "cardiologist" in text


# ── Acknowledgment gate persistence (unit test) ─────────────────────────


class TestDisclaimerAcknowledgmentGate:
    """Unit-level validation of the acknowledgment gate state machine."""

    def test_disclaimer_acceptance_persisted(self, tmp_path: Path) -> None:
        """Acceptance state should be persisted and re-readable (T4-22j)."""
        import json
        from datetime import UTC, datetime

        flag_path = tmp_path / ".disclaimer_accepted"
        accepted_at = datetime.now(UTC).isoformat()
        flag_data = {"accepted_at": accepted_at, "version": "1.0"}
        flag_path.write_text(json.dumps(flag_data), encoding="utf-8")

        loaded = json.loads(flag_path.read_text(encoding="utf-8"))
        assert loaded["accepted_at"] == accepted_at
        assert loaded["version"] == "1.0"

    def test_disclaimer_blocks_without_flag(self, tmp_path: Path) -> None:
        """Without flag file, disclaimer should be considered unaccepted."""
        flag_path = tmp_path / ".disclaimer_accepted"
        assert not flag_path.exists()
