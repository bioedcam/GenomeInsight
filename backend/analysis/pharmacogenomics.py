"""Pharmacogenomics star-allele calling via CPIC lookup tables.

Implements P3-02: pure SQLite joins — rsid genotype → star allele component
→ diplotype inference → phenotype lookup. No PyPGx dependency.

Supported genes: CYP2D6, CYP2C19, CYP2C9, CYP3A5, SLCO1B1, DPYD, TPMT, UGT1A1.

Algorithm:
    1. For each CPIC gene, load allele definitions from reference.db
    2. Fetch the sample's raw genotypes for all defining rsids
    3. Count alt alleles per rsid from the sample genotype string
    4. Greedily assign star alleles (most specific first: alleles with the
       most defining variants take priority — handles phasing ambiguity
       per CPIC unphased-data guidelines)
    5. Look up the resulting diplotype in cpic_diplotypes → phenotype

Usage::

    from backend.analysis.pharmacogenomics import call_all_star_alleles

    results = call_all_star_alleles(reference_engine, sample_engine)
    for r in results:
        print(f"{r.gene}: {r.diplotype} → {r.phenotype}")
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import sqlalchemy as sa
import structlog

from backend.annotation.cpic import CPIC_GENES
from backend.db.tables import cpic_alleles, cpic_diplotypes, raw_variants

logger = structlog.get_logger(__name__)

_STAR_ALLELE_RE = re.compile(r"^\*?(\d+)(.*)")


def _allele_sort_key(name: str) -> tuple[int, str]:
    """Sort key for star allele names: numeric part first, then suffix.

    Examples: *1 < *1A < *2 < *3A < *3B < *3C < *10 < *15
    Non-star alleles (e.g. "c.2846A>T") sort after all star alleles.
    """
    m = _STAR_ALLELE_RE.match(name)
    if m:
        return (int(m.group(1)), m.group(2))
    return (999999, name)


@dataclass
class StarAlleleResult:
    """Result of star-allele calling for a single gene."""

    gene: str
    allele1: str
    allele2: str
    diplotype: str
    phenotype: str | None = None
    ehr_notation: str | None = None
    activity_score: float | None = None
    involved_rsids: set[str] = field(default_factory=set)
    missing_rsids: set[str] = field(default_factory=set)
    uncalled_rsids: set[str] = field(default_factory=set)


def _count_alt_alleles(genotype: str, ref: str, alt: str) -> int | None:
    """Count how many copies of the alt allele are in a genotype string.

    Args:
        genotype: Two-character genotype from 23andMe (e.g. "CT", "CC").
        ref: Reference allele (single base for SNPs).
        alt: Alternate allele (single base for SNPs).

    Returns:
        Number of alt alleles (0, 1, or 2), or None if the genotype
        cannot be interpreted (no-call, indel, unexpected bases).
    """
    if not genotype or len(genotype) < 2:
        return None

    # No-call genotypes
    if genotype in ("--", "00", "DD", "II", "DI", "ID"):
        return None

    # For indel-type alleles (multi-char ref or alt), array data is unreliable
    if len(ref) > 1 or len(alt) > 1:
        return None

    g1, g2 = genotype[0], genotype[1]
    count = 0
    if g1 == alt:
        count += 1
    if g2 == alt:
        count += 1

    # Validate that the alleles are ref or alt (not some third allele)
    valid_bases = {ref, alt}
    if g1 not in valid_bases or g2 not in valid_bases:
        return None

    return count


_SQLITE_BATCH = 500  # Stay well under SQLITE_MAX_VARIABLE_NUMBER (999)


def _fetch_sample_genotypes(
    rsids: list[str],
    sample_engine: sa.Engine,
) -> dict[str, str]:
    """Fetch raw genotypes for a list of rsids from the sample database.

    Batches the IN clause to stay under SQLite's variable limit.

    Args:
        rsids: List of rsid strings to look up.
        sample_engine: SQLAlchemy engine for the sample database.

    Returns:
        Dict mapping rsid → genotype string (e.g. "CT").
    """
    if not rsids:
        return {}

    results: dict[str, str] = {}

    with sample_engine.connect() as conn:
        for i in range(0, len(rsids), _SQLITE_BATCH):
            batch = rsids[i : i + _SQLITE_BATCH]
            stmt = sa.select(
                raw_variants.c.rsid,
                raw_variants.c.genotype,
            ).where(raw_variants.c.rsid.in_(batch))

            for row in conn.execute(stmt).fetchall():
                results[row.rsid] = row.genotype

    return results


def _fetch_alleles_for_gene(
    gene: str,
    reference_engine: sa.Engine,
) -> list[dict]:
    """Fetch all CPIC allele definitions for a gene.

    Returns list of dicts with keys: allele_name, defining_variants (parsed),
    function, activity_score.
    """
    with reference_engine.connect() as conn:
        stmt = (
            sa.select(
                cpic_alleles.c.allele_name,
                cpic_alleles.c.defining_variants,
                cpic_alleles.c.function,
                cpic_alleles.c.activity_score,
            )
            .where(cpic_alleles.c.gene == gene)
            .order_by(cpic_alleles.c.allele_name)
        )
        rows = conn.execute(stmt).fetchall()

    results = []
    for row in rows:
        try:
            variants = json.loads(row.defining_variants) if row.defining_variants else []
        except json.JSONDecodeError:
            variants = []

        results.append(
            {
                "allele_name": row.allele_name,
                "defining_variants": variants,
                "function": row.function,
                "activity_score": row.activity_score,
            }
        )
    return results


def _fetch_diplotype_phenotype(
    gene: str,
    diplotype: str,
    reference_engine: sa.Engine,
) -> dict | None:
    """Look up a diplotype→phenotype mapping from cpic_diplotypes.

    Args:
        gene: Gene symbol.
        diplotype: Diplotype string (e.g. "*1/*4").
        reference_engine: SQLAlchemy engine for reference.db.

    Returns:
        Dict with phenotype, ehr_notation, activity_score or None if not found.
    """
    with reference_engine.connect() as conn:
        stmt = (
            sa.select(
                cpic_diplotypes.c.phenotype,
                cpic_diplotypes.c.ehr_notation,
                cpic_diplotypes.c.activity_score,
            )
            .where(
                sa.and_(
                    cpic_diplotypes.c.gene == gene,
                    cpic_diplotypes.c.diplotype == diplotype,
                )
            )
            .limit(1)
        )
        row = conn.execute(stmt).first()

    if row is None:
        return None

    return {
        "phenotype": row.phenotype,
        "ehr_notation": row.ehr_notation,
        "activity_score": row.activity_score,
    }


def call_star_alleles_for_gene(
    gene: str,
    alleles: list[dict],
    sample_genotypes: dict[str, str],
    reference_engine: sa.Engine,
) -> StarAlleleResult:
    """Call star alleles for a single gene given allele definitions and genotypes.

    Uses a greedy algorithm: alleles with the most defining variants are
    prioritized (most specific first). This handles phasing ambiguity for
    unphased array data per CPIC recommendations.

    Args:
        gene: Gene symbol (e.g. "CYP2D6").
        alleles: List of allele dicts from _fetch_alleles_for_gene.
        sample_genotypes: Dict of rsid → genotype string from sample.
        reference_engine: SQLAlchemy engine for diplotype lookup.

    Returns:
        StarAlleleResult with called diplotype and phenotype.
    """
    # Separate reference allele (no defining variants) from non-reference
    ref_allele_name: str | None = None
    non_ref_alleles: list[dict] = []

    for allele in alleles:
        if not allele["defining_variants"]:
            if ref_allele_name is None:
                ref_allele_name = allele["allele_name"]
        else:
            non_ref_alleles.append(allele)

    # Default reference allele name
    if ref_allele_name is None:
        ref_allele_name = "*1"

    # Collect all defining rsids for this gene
    all_defining_rsids: set[str] = set()
    for allele in non_ref_alleles:
        for v in allele["defining_variants"]:
            all_defining_rsids.add(v["rsid"])

    # Track missing rsids (not genotyped in sample)
    missing_rsids = all_defining_rsids - set(sample_genotypes.keys())

    # Track remaining alt copies per rsid (from sample genotypes)
    remaining_alts: dict[str, int] = {}
    uncalled_rsids: set[str] = set()

    for allele in non_ref_alleles:
        for v in allele["defining_variants"]:
            rsid = v["rsid"]
            if rsid in remaining_alts or rsid in uncalled_rsids:
                continue
            if rsid not in sample_genotypes:
                continue
            alt_count = _count_alt_alleles(sample_genotypes[rsid], v["ref"], v["alt"])
            if alt_count is None:
                uncalled_rsids.add(rsid)
            else:
                remaining_alts[rsid] = alt_count

    # Sort non-ref alleles: most defining variants first (most specific),
    # then alphabetically for deterministic results
    non_ref_alleles.sort(key=lambda a: (-len(a["defining_variants"]), a["allele_name"]))

    # Greedily assign alleles
    called_alleles: list[str] = []
    involved_rsids: set[str] = set()

    for allele in non_ref_alleles:
        slots_left = 2 - len(called_alleles)
        if slots_left <= 0:
            break

        variants = allele["defining_variants"]
        max_copies = slots_left

        for v in variants:
            rsid = v["rsid"]
            if rsid not in remaining_alts:
                max_copies = 0
                break
            max_copies = min(max_copies, remaining_alts[rsid])

        if max_copies > 0:
            # Consume alt copies
            for v in variants:
                remaining_alts[v["rsid"]] -= max_copies
                involved_rsids.add(v["rsid"])

            called_alleles.extend([allele["allele_name"]] * max_copies)

    # Fill remaining slots with reference allele
    while len(called_alleles) < 2:
        called_alleles.append(ref_allele_name)

    # Sort for canonical diplotype string (e.g. "*1/*4" not "*4/*1")
    # Use CPIC-aware sorting: numeric part first, then suffix
    called_alleles = sorted(called_alleles[:2], key=_allele_sort_key)
    allele1, allele2 = called_alleles

    diplotype = f"{allele1}/{allele2}"

    # Look up diplotype → phenotype
    diplo_data = _fetch_diplotype_phenotype(gene, diplotype, reference_engine)

    return StarAlleleResult(
        gene=gene,
        allele1=allele1,
        allele2=allele2,
        diplotype=diplotype,
        phenotype=diplo_data["phenotype"] if diplo_data else None,
        ehr_notation=diplo_data["ehr_notation"] if diplo_data else None,
        activity_score=diplo_data["activity_score"] if diplo_data else None,
        involved_rsids=involved_rsids,
        missing_rsids=missing_rsids,
        uncalled_rsids=uncalled_rsids,
    )


def call_all_star_alleles(
    reference_engine: sa.Engine,
    sample_engine: sa.Engine,
    *,
    genes: frozenset[str] | None = None,
) -> list[StarAlleleResult]:
    """Call star alleles for all CPIC genes given a sample.

    This is the main entry point for pharmacogenomics star-allele calling.
    For each supported CPIC gene:
      1. Loads allele definitions from reference.db
      2. Fetches sample genotypes for relevant rsids
      3. Calls star alleles via greedy matching
      4. Looks up diplotype → phenotype

    Args:
        reference_engine: SQLAlchemy engine for reference.db.
        sample_engine: SQLAlchemy engine for the sample database.
        genes: Optional subset of genes to call. Defaults to all CPIC_GENES.

    Returns:
        List of StarAlleleResult, one per gene (sorted by gene name).
    """
    target_genes = sorted(genes or CPIC_GENES)
    results: list[StarAlleleResult] = []

    for gene in target_genes:
        # Step 1: Get allele definitions
        alleles = _fetch_alleles_for_gene(gene, reference_engine)
        if not alleles:
            logger.warning("cpic_no_alleles", gene=gene)
            continue

        # Step 2: Collect all rsids needed for this gene
        all_rsids: list[str] = []
        for allele in alleles:
            for v in allele["defining_variants"]:
                if v["rsid"] not in all_rsids:
                    all_rsids.append(v["rsid"])

        # Step 3: Fetch sample genotypes
        sample_genotypes = _fetch_sample_genotypes(all_rsids, sample_engine)

        # Step 4: Call star alleles
        result = call_star_alleles_for_gene(gene, alleles, sample_genotypes, reference_engine)

        results.append(result)

        logger.info(
            "pgx_star_allele_called",
            gene=gene,
            diplotype=result.diplotype,
            phenotype=result.phenotype,
            involved_rsids=sorted(result.involved_rsids),
            missing_rsids=sorted(result.missing_rsids),
        )

    return results
