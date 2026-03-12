"""Tests for most-severe consequence selector + MANE Select flagging (P2-03).

Dedicated test coverage for:
- T2-02: Most-severe consequence correctly ranks stop_gained > missense > synonymous
- T2-03: MANE Select transcript is flagged when present in VEP bundle

Also covers:
- consequence_severity() public API
- most_severe_consequence() compound term extraction
- select_best_transcript() MANE + severity deduplication
- Edge cases: empty/None inputs, unknown terms, single terms
"""

from __future__ import annotations

from backend.annotation.vep_bundle import (
    CONSEQUENCE_SEVERITY,
    VEPAnnotation,
    consequence_severity,
    most_severe_consequence,
    select_best_transcript,
)

# ── Helpers ────────────────────────────────────────────────────────────


def _make_annot(
    *,
    rsid: str = "rs_test",
    gene_symbol: str | None = "GENE",
    transcript_id: str | None = "ENST_1",
    consequence: str | None = "missense_variant",
    mane_select: bool = False,
    matched_by: str = "rsid",
) -> VEPAnnotation:
    """Factory for VEPAnnotation with sensible defaults."""
    return VEPAnnotation(
        rsid=rsid,
        gene_symbol=gene_symbol,
        transcript_id=transcript_id,
        consequence=consequence,
        hgvs_coding=None,
        hgvs_protein=None,
        strand="+",
        exon_number=None,
        intron_number=None,
        mane_select=mane_select,
        matched_by=matched_by,
    )


# ═══════════════════════════════════════════════════════════════════════
# T2-02: consequence_severity ranking
# ═══════════════════════════════════════════════════════════════════════


class TestConsequenceSeverity:
    """T2-02: Most-severe consequence correctly ranks SO terms."""

    def test_stop_gained_gt_missense(self) -> None:
        """stop_gained > missense_variant."""
        assert consequence_severity("stop_gained") > consequence_severity("missense_variant")

    def test_missense_gt_synonymous(self) -> None:
        """missense_variant > synonymous_variant."""
        assert consequence_severity("missense_variant") > consequence_severity(
            "synonymous_variant"
        )

    def test_stop_gained_gt_synonymous(self) -> None:
        """Transitive: stop_gained > synonymous_variant."""
        assert consequence_severity("stop_gained") > consequence_severity("synonymous_variant")

    def test_frameshift_gt_missense(self) -> None:
        assert consequence_severity("frameshift_variant") > consequence_severity(
            "missense_variant"
        )

    def test_splice_acceptor_gt_splice_region(self) -> None:
        assert consequence_severity("splice_acceptor_variant") > consequence_severity(
            "splice_region_variant"
        )

    def test_transcript_ablation_is_most_severe(self) -> None:
        """transcript_ablation has the highest severity score."""
        max_term = max(CONSEQUENCE_SEVERITY, key=CONSEQUENCE_SEVERITY.get)
        assert max_term == "transcript_ablation"
        assert consequence_severity("transcript_ablation") == 35

    def test_intergenic_is_least_severe(self) -> None:
        assert consequence_severity("intergenic_variant") == 0

    def test_compound_consequence_uses_max(self) -> None:
        """Compound &-delimited terms return the max severity."""
        compound = "missense_variant&splice_region_variant"
        assert consequence_severity(compound) == CONSEQUENCE_SEVERITY["missense_variant"]

    def test_compound_three_terms(self) -> None:
        compound = "synonymous_variant&missense_variant&intron_variant"
        assert consequence_severity(compound) == CONSEQUENCE_SEVERITY["missense_variant"]

    def test_none_returns_negative(self) -> None:
        assert consequence_severity(None) == -1

    def test_empty_string_returns_negative(self) -> None:
        assert consequence_severity("") == -1

    def test_unknown_term_returns_zero(self) -> None:
        assert consequence_severity("totally_unknown_term") == 0

    def test_all_so_terms_have_scores(self) -> None:
        """Every term in the ranking dict has a non-negative score."""
        for term, score in CONSEQUENCE_SEVERITY.items():
            assert score >= 0, f"{term} has negative score {score}"

    def test_ranking_covers_ensembl_core_terms(self) -> None:
        """Key Ensembl VEP terms are present in the ranking."""
        core_terms = [
            "transcript_ablation",
            "stop_gained",
            "frameshift_variant",
            "missense_variant",
            "synonymous_variant",
            "intron_variant",
            "intergenic_variant",
        ]
        for term in core_terms:
            assert term in CONSEQUENCE_SEVERITY, f"Missing core term: {term}"


# ═══════════════════════════════════════════════════════════════════════
# most_severe_consequence()
# ═══════════════════════════════════════════════════════════════════════


class TestMostSevereConsequence:
    """Tests for extracting the single most-severe term."""

    def test_single_term_returned_as_is(self) -> None:
        assert most_severe_consequence("missense_variant") == "missense_variant"

    def test_compound_returns_most_severe(self) -> None:
        result = most_severe_consequence("synonymous_variant&stop_gained")
        assert result == "stop_gained"

    def test_compound_three_terms(self) -> None:
        result = most_severe_consequence("intron_variant&missense_variant&synonymous_variant")
        assert result == "missense_variant"

    def test_none_returns_none(self) -> None:
        assert most_severe_consequence(None) is None

    def test_empty_returns_none(self) -> None:
        assert most_severe_consequence("") is None

    def test_unknown_term_still_returned(self) -> None:
        """Unknown terms have score 0 but are still valid returns."""
        assert most_severe_consequence("unknown_term") == "unknown_term"

    def test_unknown_mixed_with_known(self) -> None:
        """Known term beats unknown term (score 0)."""
        result = most_severe_consequence("unknown_term&missense_variant")
        assert result == "missense_variant"


# ═══════════════════════════════════════════════════════════════════════
# T2-03: select_best_transcript() + MANE Select flagging
# ═══════════════════════════════════════════════════════════════════════


class TestSelectBestTranscript:
    """T2-03: MANE Select transcript is flagged when present."""

    def test_empty_list_returns_none(self) -> None:
        assert select_best_transcript([]) is None

    def test_single_annotation_returned(self) -> None:
        annot = _make_annot()
        result = select_best_transcript([annot])
        assert result is annot

    def test_mane_select_preferred_over_non_mane(self) -> None:
        """MANE Select transcript wins even with less severe consequence."""
        non_mane = _make_annot(
            transcript_id="ENST_OTHER",
            consequence="stop_gained",
            mane_select=False,
        )
        mane = _make_annot(
            transcript_id="ENST_MANE",
            consequence="missense_variant",
            mane_select=True,
        )
        result = select_best_transcript([non_mane, mane])
        assert result is mane
        assert result.mane_select is True
        assert result.transcript_id == "ENST_MANE"

    def test_mane_select_preferred_order_independent(self) -> None:
        """MANE preference is independent of list order."""
        mane = _make_annot(
            transcript_id="ENST_MANE",
            consequence="synonymous_variant",
            mane_select=True,
        )
        non_mane = _make_annot(
            transcript_id="ENST_OTHER",
            consequence="frameshift_variant",
            mane_select=False,
        )
        # MANE first
        assert select_best_transcript([mane, non_mane]).transcript_id == "ENST_MANE"
        # MANE second
        assert select_best_transcript([non_mane, mane]).transcript_id == "ENST_MANE"

    def test_severity_breaks_tie_when_same_mane_status(self) -> None:
        """When both are non-MANE, most severe consequence wins."""
        mild = _make_annot(
            transcript_id="ENST_MILD",
            consequence="synonymous_variant",
            mane_select=False,
        )
        severe = _make_annot(
            transcript_id="ENST_SEVERE",
            consequence="stop_gained",
            mane_select=False,
        )
        result = select_best_transcript([mild, severe])
        assert result.transcript_id == "ENST_SEVERE"
        assert result.consequence == "stop_gained"

    def test_severity_breaks_tie_both_mane(self) -> None:
        """When both are MANE, most severe consequence wins."""
        mild = _make_annot(
            transcript_id="ENST_A",
            consequence="synonymous_variant",
            mane_select=True,
        )
        severe = _make_annot(
            transcript_id="ENST_B",
            consequence="missense_variant",
            mane_select=True,
        )
        result = select_best_transcript([mild, severe])
        assert result.transcript_id == "ENST_B"

    def test_mane_flag_preserved_in_result(self) -> None:
        """The selected annotation has mane_select=True when appropriate."""
        annot = _make_annot(mane_select=True, transcript_id="ENST_MANE")
        result = select_best_transcript([annot])
        assert result.mane_select is True

    def test_non_mane_flag_preserved(self) -> None:
        """Non-MANE annotation has mane_select=False."""
        annot = _make_annot(mane_select=False, transcript_id="ENST_OTHER")
        result = select_best_transcript([annot])
        assert result.mane_select is False

    def test_multiple_transcripts_real_scenario(self) -> None:
        """Simulate a real variant with 3 transcripts."""
        transcripts = [
            _make_annot(
                transcript_id="ENST_001",
                consequence="intron_variant",
                mane_select=False,
            ),
            _make_annot(
                transcript_id="ENST_002",
                consequence="missense_variant",
                mane_select=True,
            ),
            _make_annot(
                transcript_id="ENST_003",
                consequence="stop_gained",
                mane_select=False,
            ),
        ]
        result = select_best_transcript(transcripts)
        # MANE Select (ENST_002) should win over more severe non-MANE
        assert result.transcript_id == "ENST_002"
        assert result.mane_select is True

    def test_none_consequence_ranked_lowest(self) -> None:
        """Annotations with None consequence are ranked below all others."""
        no_csq = _make_annot(consequence=None, mane_select=False)
        with_csq = _make_annot(consequence="intergenic_variant", mane_select=False)
        result = select_best_transcript([no_csq, with_csq])
        assert result.consequence == "intergenic_variant"


# ═══════════════════════════════════════════════════════════════════════
# Integration: MANE Select in annotated_variants schema
# ═══════════════════════════════════════════════════════════════════════


class TestManeSelectSchema:
    """Verify mane_select column exists in annotated_variants schema."""

    def test_mane_select_column_exists(self) -> None:
        from backend.db.tables import annotated_variants

        col_names = [c.name for c in annotated_variants.columns]
        assert "mane_select" in col_names

    def test_mane_select_is_boolean(self) -> None:
        import sqlalchemy as sa

        from backend.db.tables import annotated_variants

        col = annotated_variants.c.mane_select
        assert isinstance(col.type, sa.Boolean)

    def test_mane_select_defaults_to_false(self) -> None:
        """mane_select has a server_default of 0 (false)."""
        from backend.db.tables import annotated_variants

        col = annotated_variants.c.mane_select
        assert col.server_default is not None
        assert str(col.server_default.arg) == "0"
