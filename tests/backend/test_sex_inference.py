"""Tests for ``backend.services.sex_inference`` (Plan §9.4, IND-08 part b).

Covers the four classifications (XX / XY / manual_review / unknown), the
order-of-operations short-circuits, the PAR pre-filter, and the
load-bearing threshold + PAR constants from
``docs/sex_inference_threshold_validation.md``.

See Step 53 (``docs/sex_inference_threshold_validation.md``) for the
bio-validator attestation that fixes the threshold values these tests
expect.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from backend.db.sample_schema import create_sample_tables
from backend.db.tables import raw_variants
from backend.services.sex_inference import (
    _PAR1,
    _PAR2,
    _THRESHOLD_PAR_NOISE,
    _THRESHOLD_XY_CONFIRM,
    Classification,
    infer_biological_sex,
)

# Positions well past PAR1's upper bound (2_699_520) and below PAR2's
# lower bound (154_931_044) — i.e. unambiguously non-PAR.
_NONPAR_X_BASE = 50_000_000
_PAR1_POS = 1_000_000  # inside PAR1
_PAR2_POS = 155_000_000  # inside PAR2


@pytest.fixture()
def sample_engine() -> sa.Engine:
    engine = sa.create_engine("sqlite://")
    create_sample_tables(engine)
    return engine


def _seed(engine: sa.Engine, rows: list[dict]) -> None:
    with engine.begin() as conn:
        conn.execute(sa.insert(raw_variants), rows)


def _y_rows(*, typed: int, nocall: int, base_pos: int = 1_000_000) -> list[dict]:
    """Build chrY rows: ``typed`` called rows + ``nocall`` no-call rows."""
    rows: list[dict] = []
    for i in range(typed):
        rows.append(
            {
                "rsid": f"rs_y_typed_{i}",
                "chrom": "Y",
                "pos": base_pos + i,
                "genotype": "TT",
            }
        )
    for i in range(nocall):
        rows.append(
            {
                "rsid": f"rs_y_nc_{i}",
                "chrom": "Y",
                "pos": base_pos + typed + i,
                "genotype": "--",
            }
        )
    return rows


# ── Threshold-constant attestation ──────────────────────────────────────


class TestValidatedConstants:
    """Lock the validated thresholds + PAR coordinates against the
    bio-validator attestation (``docs/sex_inference_threshold_validation.md``).
    Any drift here demands a re-attestation, not a test edit."""

    def test_xy_confirm_threshold(self) -> None:
        assert _THRESHOLD_XY_CONFIRM == 0.30

    def test_par_noise_threshold(self) -> None:
        assert _THRESHOLD_PAR_NOISE == 0.10

    def test_par1_interval_grch37(self) -> None:
        assert _PAR1 == (60001, 2_699_520)

    def test_par2_interval_grch37(self) -> None:
        assert _PAR2 == (154_931_044, 155_260_560)

    def test_par_noise_below_confirm(self) -> None:
        # Defensive: the manual-review band must be non-empty.
        assert _THRESHOLD_PAR_NOISE < _THRESHOLD_XY_CONFIRM


# ── Core classification paths ───────────────────────────────────────────


class TestClassificationBranches:
    """One canonical happy-path test per Plan §9.4 branch."""

    def test_xx_dispositive_single_nonpar_het(self, sample_engine: sa.Engine) -> None:
        """A single non-PAR chrX het overrides everything."""
        _seed(
            sample_engine,
            [
                {"rsid": "rs_x_het", "chrom": "X", "pos": _NONPAR_X_BASE, "genotype": "AG"},
                {"rsid": "rs_x_hom", "chrom": "X", "pos": _NONPAR_X_BASE + 1, "genotype": "GG"},
            ],
        )
        assert infer_biological_sex(sample_engine) == "XX"

    def test_xy_confirmed(self, sample_engine: sa.Engine) -> None:
        """All non-PAR chrX hom + chrY rate > 0.30 → XY."""
        _seed(
            sample_engine,
            [
                {"rsid": "rs_x1", "chrom": "X", "pos": _NONPAR_X_BASE, "genotype": "AA"},
                {"rsid": "rs_x2", "chrom": "X", "pos": _NONPAR_X_BASE + 1, "genotype": "GG"},
                # 4/5 typed = 0.80 — well above _THRESHOLD_XY_CONFIRM (0.30).
                *_y_rows(typed=4, nocall=1),
            ],
        )
        assert infer_biological_sex(sample_engine) == "XY"

    def test_manual_review_intermediate_y_rate(self, sample_engine: sa.Engine) -> None:
        """Candidate XY + chrY rate in (PAR_NOISE, XY_CONFIRM] → manual_review."""
        _seed(
            sample_engine,
            [
                {"rsid": "rs_x", "chrom": "X", "pos": _NONPAR_X_BASE, "genotype": "AA"},
                # 2/10 = 0.20 — strictly between 0.10 and 0.30.
                *_y_rows(typed=2, nocall=8),
            ],
        )
        assert infer_biological_sex(sample_engine) == "manual_review"

    def test_unknown_empty_sample(self, sample_engine: sa.Engine) -> None:
        """Empty raw_variants → unknown."""
        assert infer_biological_sex(sample_engine) == "unknown"

    def test_unknown_mt_only_data(self, sample_engine: sa.Engine) -> None:
        """mtDNA-only data → unknown (no chrX evidence)."""
        _seed(
            sample_engine,
            [
                {"rsid": "rs_mt", "chrom": "MT", "pos": 1234, "genotype": "AA"},
            ],
        )
        assert infer_biological_sex(sample_engine) == "unknown"

    def test_unknown_all_chrx_nocall(self, sample_engine: sa.Engine) -> None:
        """Every non-PAR chrX is no-call, no chrY → unknown."""
        _seed(
            sample_engine,
            [
                {"rsid": "rs_x_nc1", "chrom": "X", "pos": _NONPAR_X_BASE, "genotype": "--"},
                {"rsid": "rs_x_nc2", "chrom": "X", "pos": _NONPAR_X_BASE + 1, "genotype": "00"},
            ],
        )
        assert infer_biological_sex(sample_engine) == "unknown"

    def test_unknown_chrY_rate_below_par_noise(self, sample_engine: sa.Engine) -> None:
        """Candidate XY + chrY rate ≤ PAR_NOISE → unknown (don't auto-assign)."""
        _seed(
            sample_engine,
            [
                {"rsid": "rs_x", "chrom": "X", "pos": _NONPAR_X_BASE, "genotype": "AA"},
                # 1/20 = 0.05 — at/below 0.10.
                *_y_rows(typed=1, nocall=19),
            ],
        )
        assert infer_biological_sex(sample_engine) == "unknown"


# ── Order-of-operations and PAR pre-filter ──────────────────────────────


class TestPARPreFilter:
    """Plan §9.4 step 0 — PAR sites carry no sex signal and must be
    excluded before the chrX zygosity check."""

    def test_par1_het_alone_yields_unknown(self, sample_engine: sa.Engine) -> None:
        """Heterozygous PAR1 call without any non-PAR chrX evidence → unknown."""
        _seed(
            sample_engine,
            [
                {"rsid": "rs_par1", "chrom": "X", "pos": _PAR1_POS, "genotype": "AG"},
            ],
        )
        assert infer_biological_sex(sample_engine) == "unknown"

    def test_par2_het_alone_yields_unknown(self, sample_engine: sa.Engine) -> None:
        _seed(
            sample_engine,
            [
                {"rsid": "rs_par2", "chrom": "X", "pos": _PAR2_POS, "genotype": "AG"},
            ],
        )
        assert infer_biological_sex(sample_engine) == "unknown"

    def test_par_het_plus_nonpar_hom_yields_candidate_xy(
        self, sample_engine: sa.Engine
    ) -> None:
        """PAR het is pre-filtered; the non-PAR hom alone makes the sample
        a candidate XY, then confirmed by chrY rate."""
        _seed(
            sample_engine,
            [
                {"rsid": "rs_par", "chrom": "X", "pos": _PAR1_POS, "genotype": "AG"},
                {"rsid": "rs_x_hom", "chrom": "X", "pos": _NONPAR_X_BASE, "genotype": "GG"},
                *_y_rows(typed=3, nocall=1),  # 0.75
            ],
        )
        assert infer_biological_sex(sample_engine) == "XY"


class TestDispositiveXXShortCircuit:
    """A single non-PAR chrX het wins regardless of chrY signal — males
    cannot be heterozygous on a non-PAR chrX locus."""

    def test_chrY_noise_in_manual_review_band_does_not_override(
        self, sample_engine: sa.Engine
    ) -> None:
        _seed(
            sample_engine,
            [
                {"rsid": "rs_x_het", "chrom": "X", "pos": _NONPAR_X_BASE, "genotype": "AG"},
                # 2/10 chrY = 0.20 → in manual_review band, but dispositive XX wins.
                *_y_rows(typed=2, nocall=8),
            ],
        )
        assert infer_biological_sex(sample_engine) == "XX"

    def test_chrY_rate_above_confirm_does_not_override(
        self, sample_engine: sa.Engine
    ) -> None:
        """Defensive: even a confirm-grade chrY rate doesn't beat
        a dispositive non-PAR chrX het."""
        _seed(
            sample_engine,
            [
                {"rsid": "rs_x_het", "chrom": "X", "pos": _NONPAR_X_BASE, "genotype": "AG"},
                *_y_rows(typed=8, nocall=2),  # 0.80
            ],
        )
        assert infer_biological_sex(sample_engine) == "XX"


# ── Parametric assertion: returned type lands in the Literal alphabet ──


@pytest.mark.parametrize(
    "rows,expected",
    [
        # Branch coverage parametrized: each tuple exercises one branch of
        # Plan §9.4 from the same call site, so the type checker can lock
        # the Literal alphabet on the return.
        (
            [
                {"rsid": "rs_x_het", "chrom": "X", "pos": _NONPAR_X_BASE, "genotype": "AG"},
            ],
            "XX",
        ),
        (
            [
                {"rsid": "rs_x_hom", "chrom": "X", "pos": _NONPAR_X_BASE, "genotype": "GG"},
                {"rsid": "rs_y_t", "chrom": "Y", "pos": 1_000_000, "genotype": "TT"},
                {"rsid": "rs_y_t2", "chrom": "Y", "pos": 1_000_001, "genotype": "AA"},
            ],
            "XY",
        ),
        (
            [
                {"rsid": "rs_x_hom", "chrom": "X", "pos": _NONPAR_X_BASE, "genotype": "GG"},
                {"rsid": "rs_y_t", "chrom": "Y", "pos": 1_000_000, "genotype": "TT"},
                *[
                    {"rsid": f"rs_y_nc_{i}", "chrom": "Y", "pos": 1_000_001 + i, "genotype": "--"}
                    for i in range(4)
                ],
            ],
            "manual_review",
        ),
        ([], "unknown"),
    ],
)
def test_returns_literal_alphabet(
    rows: list[dict],
    expected: Classification,
    sample_engine: sa.Engine,
) -> None:
    if rows:
        _seed(sample_engine, rows)
    assert infer_biological_sex(sample_engine) == expected
