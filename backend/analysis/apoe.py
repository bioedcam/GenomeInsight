"""APOE genotype determination (rs429358 + rs7412 → diplotype).

Implements P3-22a: Determine the APOE diplotype from two defining SNPs.

APOE alleles are defined by combinations at two positions on chromosome 19:
  - rs429358 (codon 112): T→C corresponds to Cys→Arg
  - rs7412   (codon 158): C→T corresponds to Arg→Cys

Haplotype definitions (forward-strand alleles):
  - ε2: rs429358=T + rs7412=T  (Cys112, Cys158)
  - ε3: rs429358=T + rs7412=C  (Cys112, Arg158)  ← reference/common
  - ε4: rs429358=C + rs7412=C  (Arg112, Arg158)

Both SNPs are on the 23andMe v5 array, so no partial-call ambiguity.

Usage::

    from backend.analysis.apoe import determine_apoe_genotype, APOEResult

    result = determine_apoe_genotype(sample_engine)
    print(result.diplotype)   # e.g. "ε3/ε4"
    print(result.has_e4)      # True
    print(result.e4_count)    # 1
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

import sqlalchemy as sa
import structlog

from backend.db.tables import findings, raw_variants

logger = structlog.get_logger(__name__)

# ── APOE defining SNPs ──────────────────────────────────────────────────

APOE_RS429358 = "rs429358"  # codon 112: T=Cys (ε2/ε3), C=Arg (ε4)
APOE_RS7412 = "rs7412"  # codon 158: C=Arg (ε3/ε4), T=Cys (ε2)

# Chromosome 19 positions (GRCh37)
APOE_RS429358_POS = 44908684
APOE_RS7412_POS = 44908822
APOE_CHROM = "19"


class APOEAllele(StrEnum):
    """Individual APOE allele (one per chromosome copy)."""

    E2 = "ε2"
    E3 = "ε3"
    E4 = "ε4"


# ── Haplotype → allele mapping ──────────────────────────────────────────
#
# Each chromosome carries one allele at each SNP position.
# The combination defines the APOE allele on that chromosome:
#
#   rs429358  rs7412   → allele
#   T         T        → ε2
#   T         C        → ε3
#   C         C        → ε4
#   C         T        → (ε1, extremely rare — not called in standard panels)

_HAPLOTYPE_TO_ALLELE: dict[tuple[str, str], APOEAllele] = {
    ("T", "T"): APOEAllele.E2,
    ("T", "C"): APOEAllele.E3,
    ("C", "C"): APOEAllele.E4,
}

# ── Diplotype lookup from unphased genotypes ────────────────────────────
#
# Since array data is unphased, we work with the two-SNP genotype
# combination (sorted allele counts) to determine the diplotype.
#
# rs429358 genotype × rs7412 genotype → diplotype
# (genotype strings are sorted pairs, e.g. "CC", "CT", "TT")

_DIPLOTYPE_TABLE: dict[tuple[str, str], tuple[APOEAllele, APOEAllele]] = {
    # rs429358=TT (both Cys112) × rs7412 options
    ("TT", "TT"): (APOEAllele.E2, APOEAllele.E2),  # ε2/ε2
    ("TT", "CT"): (APOEAllele.E2, APOEAllele.E3),  # ε2/ε3
    ("TT", "CC"): (APOEAllele.E3, APOEAllele.E3),  # ε3/ε3
    # rs429358=CT (one Cys112, one Arg112) × rs7412 options
    ("CT", "CT"): (APOEAllele.E2, APOEAllele.E4),  # ε2/ε4
    ("CT", "CC"): (APOEAllele.E3, APOEAllele.E4),  # ε3/ε4
    ("CT", "TT"): (APOEAllele.E2, APOEAllele.E2),  # ε2/ε2 (alt phasing not possible, see note)
    # rs429358=CC (both Arg112) × rs7412 options
    ("CC", "CC"): (APOEAllele.E4, APOEAllele.E4),  # ε4/ε4
    ("CC", "CT"): (APOEAllele.E4, APOEAllele.E4),  # impossible without ε1, treat as ε4/ε4
    ("CC", "TT"): (APOEAllele.E4, APOEAllele.E4),  # impossible without ε1, treat as ε4/ε4
}

# Note on CT/TT: rs429358=CT means one ε2-or-ε3 + one ε4 chromosome.
# rs7412=TT means both have T at 158 → both ε2. But the ε4 allele
# requires C at 158. This combination is biologically contradictory
# without invoking the extremely rare ε1 allele (C at 112, T at 158).
# We handle it defensively but it should essentially never occur.


class APOEStatus(StrEnum):
    """APOE determination status."""

    DETERMINED = "determined"
    MISSING_SNPS = "missing_snps"
    NO_CALL = "no_call"
    AMBIGUOUS = "ambiguous"


@dataclass
class APOEResult:
    """Result of APOE genotype determination.

    Attributes:
        status: Whether the diplotype was successfully determined.
        allele1: First APOE allele (lower or equal ε number), or None.
        allele2: Second APOE allele (higher or equal ε number), or None.
        diplotype: Human-readable diplotype string (e.g. "ε3/ε4"), or None.
        rs429358_genotype: Raw genotype at rs429358, or None if missing.
        rs7412_genotype: Raw genotype at rs7412, or None if missing.
        has_e4: Whether at least one ε4 allele is present.
        e4_count: Number of ε4 alleles (0, 1, or 2).
        has_e2: Whether at least one ε2 allele is present.
        e2_count: Number of ε2 alleles (0, 1, or 2).
    """

    status: APOEStatus
    allele1: APOEAllele | None = None
    allele2: APOEAllele | None = None
    diplotype: str | None = None
    rs429358_genotype: str | None = None
    rs7412_genotype: str | None = None

    @property
    def has_e4(self) -> bool:
        """Whether at least one ε4 allele is present."""
        return self.allele1 == APOEAllele.E4 or self.allele2 == APOEAllele.E4

    @property
    def e4_count(self) -> int:
        """Number of ε4 alleles (0, 1, or 2)."""
        count = 0
        if self.allele1 == APOEAllele.E4:
            count += 1
        if self.allele2 == APOEAllele.E4:
            count += 1
        return count

    @property
    def has_e2(self) -> bool:
        """Whether at least one ε2 allele is present."""
        return self.allele1 == APOEAllele.E2 or self.allele2 == APOEAllele.E2

    @property
    def e2_count(self) -> int:
        """Number of ε2 alleles (0, 1, or 2)."""
        count = 0
        if self.allele1 == APOEAllele.E2:
            count += 1
        if self.allele2 == APOEAllele.E2:
            count += 1
        return count

    @property
    def is_determined(self) -> bool:
        """Whether the diplotype was successfully determined."""
        return self.status == APOEStatus.DETERMINED


def _normalise_genotype(genotype: str) -> str:
    """Sort a two-character genotype so the alleles are in alphabetical order.

    23andMe reports genotypes as two-character strings (e.g. "TC" or "CT").
    We normalise to sorted order for consistent lookup.
    """
    if len(genotype) != 2:
        return genotype
    return "".join(sorted(genotype))


def _is_no_call(genotype: str) -> bool:
    """Check if a genotype represents a no-call (e.g. "--", "00", "DD", "II")."""
    return genotype in {"--", "00", "DD", "II", "DI", "ID", "D", "I", "-"}


def determine_apoe_genotype(sample_engine: sa.Engine) -> APOEResult:
    """Determine the APOE diplotype from raw variant genotypes.

    Looks up rs429358 and rs7412 in the raw_variants table and maps
    the genotype combination to an APOE diplotype (ε2/ε2 through ε4/ε4).

    Args:
        sample_engine: SQLAlchemy engine for the sample database.

    Returns:
        APOEResult with the diplotype determination.
    """
    with sample_engine.connect() as conn:
        stmt = sa.select(raw_variants.c.rsid, raw_variants.c.genotype).where(
            raw_variants.c.rsid.in_([APOE_RS429358, APOE_RS7412])
        )
        rows = {row.rsid: row.genotype for row in conn.execute(stmt)}

    rs429358_gt = rows.get(APOE_RS429358)
    rs7412_gt = rows.get(APOE_RS7412)

    # Check for missing SNPs
    missing = []
    if rs429358_gt is None:
        missing.append(APOE_RS429358)
    if rs7412_gt is None:
        missing.append(APOE_RS7412)

    if missing:
        logger.warning("apoe_snps_missing", missing_rsids=missing)
        return APOEResult(
            status=APOEStatus.MISSING_SNPS,
            rs429358_genotype=rs429358_gt,
            rs7412_genotype=rs7412_gt,
        )

    # Check for no-call genotypes
    if _is_no_call(rs429358_gt) or _is_no_call(rs7412_gt):
        logger.warning(
            "apoe_no_call",
            rs429358=rs429358_gt,
            rs7412=rs7412_gt,
        )
        return APOEResult(
            status=APOEStatus.NO_CALL,
            rs429358_genotype=rs429358_gt,
            rs7412_genotype=rs7412_gt,
        )

    # Normalise genotypes (sort alleles alphabetically)
    norm_429358 = _normalise_genotype(rs429358_gt)
    norm_7412 = _normalise_genotype(rs7412_gt)

    # Look up diplotype
    allele_pair = _DIPLOTYPE_TABLE.get((norm_429358, norm_7412))

    if allele_pair is None:
        logger.warning(
            "apoe_ambiguous_genotype",
            rs429358=norm_429358,
            rs7412=norm_7412,
        )
        return APOEResult(
            status=APOEStatus.AMBIGUOUS,
            rs429358_genotype=rs429358_gt,
            rs7412_genotype=rs7412_gt,
        )

    # Sort alleles so lower ε number comes first (ε2 < ε3 < ε4)
    allele1, allele2 = sorted(allele_pair, key=lambda a: a.value)
    diplotype = f"{allele1.value}/{allele2.value}"

    logger.info(
        "apoe_genotype_determined",
        diplotype=diplotype,
        rs429358=rs429358_gt,
        rs7412=rs7412_gt,
        has_e4=(allele1 == APOEAllele.E4 or allele2 == APOEAllele.E4),
        e4_count=sum(1 for a in (allele1, allele2) if a == APOEAllele.E4),
    )

    return APOEResult(
        status=APOEStatus.DETERMINED,
        allele1=allele1,
        allele2=allele2,
        diplotype=diplotype,
        rs429358_genotype=rs429358_gt,
        rs7412_genotype=rs7412_gt,
    )


# ── Findings storage ─────────────────────────────────────────────────────


def store_apoe_finding(
    result: APOEResult,
    sample_engine: sa.Engine,
) -> int:
    """Store the APOE genotype finding in the sample database.

    Creates a single finding with module='apoe' and category='genotype'.
    This records the diplotype determination for downstream use by
    P3-22b (three findings generation) and P3-22d (APOE UI).

    Always clears previous APOE genotype findings before inserting,
    ensuring idempotent re-runs.

    Args:
        result: APOEResult from determine_apoe_genotype.
        sample_engine: SQLAlchemy engine for the sample database.

    Returns:
        Number of findings inserted (0 or 1).
    """
    if not result.is_determined:
        logger.info(
            "apoe_finding_skipped",
            status=result.status.value,
            reason="APOE genotype not determined",
        )
        # Still clear any previous findings
        with sample_engine.begin() as conn:
            conn.execute(
                sa.delete(findings).where(
                    findings.c.module == "apoe",
                    findings.c.category == "genotype",
                )
            )
        return 0

    detail = {
        "allele1": result.allele1.value,
        "allele2": result.allele2.value,
        "rs429358_genotype": result.rs429358_genotype,
        "rs7412_genotype": result.rs7412_genotype,
        "has_e4": result.has_e4,
        "e4_count": result.e4_count,
        "has_e2": result.has_e2,
        "e2_count": result.e2_count,
    }

    finding_text = f"APOE genotype: {result.diplotype}"
    if result.has_e4:
        finding_text += f" ({result.e4_count}× ε4 allele)"

    row = {
        "module": "apoe",
        "category": "genotype",
        "evidence_level": 4,  # ★★★★ — both SNPs well-characterised
        "gene_symbol": "APOE",
        "rsid": None,  # composite of two rsids
        "finding_text": finding_text,
        "conditions": None,  # findings generation (P3-22b) assigns conditions
        "zygosity": None,
        "clinvar_significance": None,
        "diplotype": result.diplotype,
        "pmid_citations": None,
        "detail_json": json.dumps(detail),
    }

    with sample_engine.begin() as conn:
        # Clear previous APOE genotype finding
        conn.execute(
            sa.delete(findings).where(
                findings.c.module == "apoe",
                findings.c.category == "genotype",
            )
        )
        conn.execute(sa.insert(findings), [row])

    logger.info(
        "apoe_finding_stored",
        diplotype=result.diplotype,
        has_e4=result.has_e4,
        e4_count=result.e4_count,
    )
    return 1
