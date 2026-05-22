"""Parity tests locking the ``??``/``--`` equivalence across analysis modules.

Step 61 (MRG-01a part 2; Plan §10.3, §11.1, §11.2) adopts the shared
``backend.analysis.zygosity.is_no_call`` helper at the no-call filter site of
every analysis module that reads ``raw_variants.genotype``. This test asserts,
per module, that the ``??`` merge-ambiguity sentinel (emitted by
``backend/services/sample_merge.py`` ``flag_only`` strategy in Step 65)
produces identical finding emission/suppression as the legacy ``--`` no-call.

Coverage is the thirteen modules enumerated in Step 61:

    traits, gene_health, sleep, nutrigenomics, fitness, methylation,
    skin, allergy, pharmacogenomics (_count_alt_alleles),
    prs (_count_effect_allele), apoe (determine_apoe_genotype),
    ancestry (haplogroup tree-walk), lai_runner (pre-VCF-write drop filter).

If any module's no-call filter drifts from the shared helper, exactly one of
these parametrize cases will fail — that's the lock the cross-cutting
adoption depends on.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
import sqlalchemy as sa

from backend.analysis import (
    allergy,
    fitness,
    gene_health,
    methylation,
    nutrigenomics,
    skin,
    sleep,
    traits,
)
from backend.analysis.ancestry import (
    HaplogroupNode,
    HaplogroupSNP,
    _check_node_match,
)
from backend.analysis.apoe import (
    APOE_RS7412,
    APOE_RS429358,
    APOEStatus,
    determine_apoe_genotype,
)
from backend.analysis.lai_runner import LAIRunner
from backend.analysis.pharmacogenomics import _count_alt_alleles
from backend.analysis.prs import _count_effect_allele
from backend.db.sample_schema import create_sample_tables
from backend.db.tables import raw_variants

# ── Trait-style modules (8 modules sharing the _normalize_genotype contract) ─

_TRAIT_NORMALIZE: list[tuple[str, Callable[[str | None], str | None]]] = [
    ("traits", traits._normalize_genotype),
    ("gene_health", gene_health._normalize_genotype),
    ("sleep", sleep._normalize_genotype),
    ("nutrigenomics", nutrigenomics._normalize_genotype),
    ("fitness", fitness._normalize_genotype),
    ("methylation", methylation._normalize_genotype),
    ("skin", skin._normalize_genotype),
    ("allergy", allergy._normalize_genotype),
]


@pytest.mark.parametrize(
    "_module_name,normalize_fn",
    _TRAIT_NORMALIZE,
    ids=[name for name, _ in _TRAIT_NORMALIZE],
)
def test_trait_module_normalize_genotype_parity(
    _module_name: str,
    normalize_fn: Callable[[str | None], str | None],
) -> None:
    """``--`` and ``??`` both yield ``None`` from ``_normalize_genotype``.

    Locks suppression parity for the eight trait-association modules:
    a ``??`` row from a merged-sample ``flag_only`` discordance is treated
    identically to a legacy ``--`` no-call — no finding is emitted from
    either input.
    """
    assert normalize_fn("--") is None
    assert normalize_fn("??") is None
    assert normalize_fn("--") == normalize_fn("??")


# ── pharmacogenomics._count_alt_alleles ──────────────────────────────────────


def test_pharmacogenomics_count_alt_alleles_parity() -> None:
    """``--`` and ``??`` both yield ``None`` from ``_count_alt_alleles``.

    CPIC star-allele counting suppresses both legacy and merge-ambiguity
    no-calls identically.
    """
    assert _count_alt_alleles("--", "A", "T") is None
    assert _count_alt_alleles("??", "A", "T") is None
    assert _count_alt_alleles("--", "A", "T") == _count_alt_alleles("??", "A", "T")


# ── prs._count_effect_allele ─────────────────────────────────────────────────


def test_prs_count_effect_allele_parity() -> None:
    """``--`` and ``??`` both yield ``0`` from ``_count_effect_allele``.

    PRS dosage extraction treats merge-ambiguity rows as missing data, same as
    legacy no-call. (``0`` is the missing-data sentinel for PRS dosage —
    contributes nothing to the score.)
    """
    assert _count_effect_allele("--", "A") == 0
    assert _count_effect_allele("??", "A") == 0
    assert _count_effect_allele("--", "A") == _count_effect_allele("??", "A")


# ── apoe.determine_apoe_genotype ─────────────────────────────────────────────


def _make_apoe_sample_engine(rs429358_gt: str, rs7412_gt: str) -> sa.Engine:
    """In-memory sample DB seeded with the two APOE rsIDs at given genotypes."""
    engine = sa.create_engine("sqlite://")
    create_sample_tables(engine)
    with engine.begin() as conn:
        conn.execute(
            sa.insert(raw_variants),
            [
                {
                    "rsid": APOE_RS429358,
                    "chrom": "19",
                    "pos": 44908684,
                    "genotype": rs429358_gt,
                },
                {
                    "rsid": APOE_RS7412,
                    "chrom": "19",
                    "pos": 44908822,
                    "genotype": rs7412_gt,
                },
            ],
        )
    return engine


def test_apoe_determine_genotype_parity() -> None:
    """``--`` and ``??`` at APOE rsIDs both yield ``APOEStatus.NO_CALL``.

    The APOE gate suppresses diplotype determination identically for legacy
    no-call and merge-ambiguity rows at either rs429358 or rs7412.
    """
    result_dash = determine_apoe_genotype(_make_apoe_sample_engine("--", "--"))
    result_q = determine_apoe_genotype(_make_apoe_sample_engine("??", "??"))

    assert result_dash.status == APOEStatus.NO_CALL
    assert result_q.status == APOEStatus.NO_CALL
    assert result_dash.status == result_q.status


# ── ancestry._check_node_match (haplogroup tree-walk) ────────────────────────


def test_ancestry_haplogroup_tree_walk_parity() -> None:
    """``--`` and ``??`` at a defining SNP both yield ``snps_present == 0``.

    Haplogroup tree-walk evidence accumulation treats merge-ambiguity rows as
    missing evidence, same as legacy no-call.
    """
    snp = HaplogroupSNP(rsid="rs123", pos=1000, allele="A")
    node = HaplogroupNode(haplogroup="H1", defining_snps=[snp], children=[])

    present_dash, total_dash = _check_node_match(node, {"rs123": "--"})
    present_q, total_q = _check_node_match(node, {"rs123": "??"})

    assert present_dash == 0
    assert present_q == 0
    assert (present_dash, total_dash) == (present_q, total_q)


# ── lai_runner._filter_genotypes (pre-VCF-write drop filter) ─────────────────


def test_lai_runner_filter_genotypes_parity() -> None:
    """``--`` and ``??`` both get dropped by the pre-VCF-write filter.

    ``_filter_genotypes`` doesn't reference ``self``, so we call it as an
    unbound function to avoid materialising a real LAI bundle.
    """
    base_row = {"rsid": "rs1", "chrom": "1", "pos": 100}
    gts_dash = [{**base_row, "genotype": "--"}]
    gts_q = [{**base_row, "genotype": "??"}]

    filter_fn = LAIRunner._filter_genotypes
    assert filter_fn(None, gts_dash) == []
    assert filter_fn(None, gts_q) == []
    assert filter_fn(None, gts_dash) == filter_fn(None, gts_q)
