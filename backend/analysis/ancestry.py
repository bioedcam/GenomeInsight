"""Ancestry inference via PCA projection and admixture estimation.

Implements P3-23 (PCA projection) and P3-24 (admixture fractions).

Projects user genotypes onto pre-computed PCA space via NumPy dot product
against loadings from the ancestry PCA bundle. Runtime target: < 1 second.

Admixture fractions are estimated via inverse-distance weighting against
reference population centroids in PCA space. Fractions sum to ~1.0.

The ancestry PCA bundle contains:
  - A curated set of ancestry informative markers (AIMs)
  - Pre-computed PCA loadings (eigenvectors) from a reference panel
  - Reference population centroids in PCA space
  - Global reference allele frequencies for centering

Algorithm:
  1. Load ancestry PCA bundle (SNPs, loadings, centroids, ref freqs)
  2. Query sample genotypes for bundle SNPs
  3. Encode genotypes as alt-allele dosage (0, 1, or 2)
  4. Center: dosage_i - 2 * ref_freq_i
  5. Project: pc_scores = centered @ loadings.T
  6. Classify: nearest centroid in PCA space → top population
  7. Compute admixture fractions via inverse-distance weighting

The ``top_population`` output is consumed by the PRS ancestry mismatch
check (P3-16) via ``prs.get_inferred_ancestry()``.

Usage::

    from backend.analysis.ancestry import (
        load_ancestry_bundle,
        infer_ancestry,
        compute_admixture_fractions,
        store_ancestry_findings,
        AncestryBundle,
        AncestryResult,
    )

    bundle = load_ancestry_bundle()
    result = infer_ancestry(bundle, sample_engine)
    # result.admixture_fractions contains per-population proportions
    store_ancestry_findings(result, sample_engine)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sqlalchemy as sa
import structlog

from backend.db.tables import annotated_variants, findings, raw_variants

logger = structlog.get_logger(__name__)

# Path to the pre-computed ancestry PCA bundle
_BUNDLE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "panels" / "ancestry_pca_bundle.json"
)

# Super-population codes used throughout the module
POPULATIONS = ("AFR", "AMR", "EAS", "EUR", "SAS", "OCE")


# ── Data classes ──────────────────────────────────────────────────────────


@dataclass
class AncestryAIM:
    """A single ancestry informative marker from the PCA bundle."""

    rsid: str
    chrom: str
    pos: int
    ref: str
    alt: str
    ref_freq: float


@dataclass
class AncestryBundle:
    """Pre-computed PCA bundle for ancestry inference.

    Attributes:
        version: Bundle version string.
        build: Genome build (e.g. "GRCh37").
        n_components: Number of principal components.
        populations: List of super-population codes.
        population_labels: Human-readable population names.
        snps: List of ancestry informative markers.
        loadings: PCA loadings matrix, shape (n_components, n_snps).
        reference_centroids: Population centroids in PCA space,
            mapping population code → array of PC coordinates.
    """

    version: str
    build: str
    n_components: int
    populations: list[str]
    population_labels: dict[str, str]
    snps: list[AncestryAIM]
    loadings: np.ndarray  # shape: (n_components, n_snps)
    reference_centroids: dict[str, np.ndarray]  # pop → (n_components,)

    @property
    def snp_count(self) -> int:
        """Number of SNPs in the bundle."""
        return len(self.snps)

    def rsid_set(self) -> set[str]:
        """Return the set of rsids in the bundle."""
        return {s.rsid for s in self.snps}

    def rsid_to_index(self) -> dict[str, int]:
        """Map rsid → index in the SNP/loadings arrays."""
        return {s.rsid: i for i, s in enumerate(self.snps)}


@dataclass
class AncestryResult:
    """Result of ancestry PCA projection for a sample.

    Attributes:
        pc_scores: Projected PC coordinates, shape (n_components,).
        top_population: Nearest super-population by centroid distance.
        population_distances: Squared Euclidean distance to each centroid.
        admixture_fractions: Estimated ancestry proportions per population,
            computed via inverse-distance weighting. Values sum to ~1.0.
        snps_used: Number of SNPs with available genotype data.
        snps_total: Total SNPs in the bundle.
        coverage_fraction: snps_used / snps_total.
        projection_time_ms: Wall-clock time for the projection step.
        is_sufficient: Whether enough SNPs were genotyped.
    """

    pc_scores: list[float]
    top_population: str
    population_distances: dict[str, float]
    admixture_fractions: dict[str, float]
    snps_used: int
    snps_total: int
    coverage_fraction: float
    projection_time_ms: float
    is_sufficient: bool

    @property
    def n_components(self) -> int:
        """Number of principal components."""
        return len(self.pc_scores)


# ── Bundle loading ────────────────────────────────────────────────────────


def load_ancestry_bundle(bundle_path: Path | None = None) -> AncestryBundle:
    """Load the pre-computed ancestry PCA bundle from JSON.

    Args:
        bundle_path: Optional override for the bundle JSON path.
            Defaults to ``backend/data/panels/ancestry_pca_bundle.json``.

    Returns:
        Parsed AncestryBundle with SNPs, loadings, and centroids.

    Raises:
        FileNotFoundError: If the bundle file does not exist.
        ValueError: If the bundle structure is invalid.
    """
    path = bundle_path or _BUNDLE_PATH
    logger.info("loading_ancestry_bundle", path=str(path))

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Parse SNPs
    snps: list[AncestryAIM] = []
    for snp_data in data["snps"]:
        snps.append(
            AncestryAIM(
                rsid=snp_data["rsid"],
                chrom=snp_data["chrom"],
                pos=snp_data["pos"],
                ref=snp_data["ref"],
                alt=snp_data["alt"],
                ref_freq=snp_data["ref_freq"],
            )
        )

    n_components = data["n_components"]
    n_snps = len(snps)

    # Parse loadings: shape (n_components, n_snps)
    loadings_raw = data["loadings"]
    if len(loadings_raw) != n_components:
        raise ValueError(f"Expected {n_components} loading vectors, got {len(loadings_raw)}")
    for i, row in enumerate(loadings_raw):
        if len(row) != n_snps:
            raise ValueError(f"Loading vector {i} has {len(row)} values, expected {n_snps}")
    loadings = np.array(loadings_raw, dtype=np.float64)

    # Parse reference centroids
    centroids: dict[str, np.ndarray] = {}
    for pop, coords in data["reference_centroids"].items():
        if len(coords) != n_components:
            raise ValueError(
                f"Centroid for {pop} has {len(coords)} values, expected {n_components}"
            )
        centroids[pop] = np.array(coords, dtype=np.float64)

    bundle = AncestryBundle(
        version=data.get("version", "1.0.0"),
        build=data.get("build", "GRCh37"),
        n_components=n_components,
        populations=data["populations"],
        population_labels=data.get("population_labels", {}),
        snps=snps,
        loadings=loadings,
        reference_centroids=centroids,
    )

    logger.info(
        "ancestry_bundle_loaded",
        snp_count=bundle.snp_count,
        n_components=bundle.n_components,
        populations=bundle.populations,
    )

    return bundle


# ── Genotype encoding ─────────────────────────────────────────────────────


def _encode_dosage(genotype: str | None, alt_allele: str) -> float | None:
    """Encode a genotype as alt-allele dosage (0, 1, or 2).

    Args:
        genotype: Two-character genotype string (e.g. "AG"), or None.
        alt_allele: The alternate allele to count.

    Returns:
        Dosage (0.0, 1.0, or 2.0), or None if genotype is missing.
    """
    if not genotype or len(genotype) < 2:
        return None

    if genotype in ("--", "00", "II", "DD", "DI", "ID"):
        return None

    count = 0
    for allele in genotype:
        if allele.upper() == alt_allele.upper():
            count += 1

    return float(min(count, 2))


# ── PCA projection ────────────────────────────────────────────────────────

# Minimum fraction of SNPs required for a meaningful projection
_MIN_COVERAGE = 0.3


def _project_onto_pca(
    bundle: AncestryBundle,
    genotype_map: dict[str, str | None],
) -> tuple[np.ndarray, int]:
    """Project sample genotypes onto PCA space.

    Encodes genotypes as alt-allele dosage, centers using reference
    allele frequencies, imputes missing values with 0 (mean), and
    projects via dot product with the loadings matrix.

    Args:
        bundle: Loaded ancestry PCA bundle.
        genotype_map: Mapping rsid → genotype string.

    Returns:
        Tuple of (pc_scores array shape (n_components,), snps_used count).
    """
    n_snps = bundle.snp_count

    # Build centered dosage vector
    centered = np.zeros(n_snps, dtype=np.float64)
    snps_used = 0

    for i, snp in enumerate(bundle.snps):
        genotype = genotype_map.get(snp.rsid)
        dosage = _encode_dosage(genotype, snp.alt)

        if dosage is not None:
            # Center: dosage - 2 * alt_freq
            # alt_freq = 1 - ref_freq
            alt_freq = 1.0 - snp.ref_freq
            centered[i] = dosage - 2.0 * alt_freq
            snps_used += 1
        # else: leave as 0.0 (mean-imputed)

    # Project: pc_scores = loadings @ centered
    # loadings shape: (n_components, n_snps)
    # centered shape: (n_snps,)
    # result shape: (n_components,)
    pc_scores = bundle.loadings @ centered

    return pc_scores, snps_used


def _classify_nearest_centroid(
    pc_scores: np.ndarray,
    centroids: dict[str, np.ndarray],
) -> tuple[str, dict[str, float]]:
    """Classify ancestry by nearest centroid in PCA space.

    Uses squared Euclidean distance to find the closest reference
    population centroid.

    Args:
        pc_scores: Sample PC coordinates, shape (n_components,).
        centroids: Population → centroid coordinates.

    Returns:
        Tuple of (top_population code, distances dict).
    """
    if not centroids:
        raise ValueError("No population centroids provided for classification")

    distances: dict[str, float] = {}
    best_pop = ""
    best_dist = float("inf")

    for pop, centroid in centroids.items():
        dist = float(np.sum((pc_scores - centroid) ** 2))
        distances[pop] = round(dist, 4)
        if dist < best_dist:
            best_dist = dist
            best_pop = pop

    return best_pop, distances


def compute_admixture_fractions(
    population_distances: dict[str, float],
) -> dict[str, float]:
    """Estimate admixture fractions via inverse-distance weighting.

    Converts squared Euclidean distances to population centroids into
    proportional ancestry estimates. Uses inverse-distance weighting
    with a small epsilon to avoid division by zero when a sample sits
    exactly on a centroid.

    The resulting fractions sum to ~1.0 (within floating point tolerance).

    Args:
        population_distances: Squared Euclidean distance to each
            population centroid (from _classify_nearest_centroid).

    Returns:
        Dict mapping population code → fraction (0.0–1.0).
        Empty dict if no distances provided.
    """
    if not population_distances:
        return {}

    epsilon = 1e-10

    # Check if sample is essentially on a centroid (distance ~ 0)
    min_dist = min(population_distances.values())
    if min_dist < epsilon:
        # Assign 1.0 to the exact-match population, 0.0 to others
        fractions = {}
        for pop, dist in population_distances.items():
            fractions[pop] = 1.0 if dist < epsilon else 0.0
        return fractions

    # Inverse-distance weighting: weight_i = 1 / d_i^2
    # Using squared distances directly (already squared Euclidean)
    inv_weights: dict[str, float] = {}
    total_weight = 0.0

    for pop, dist in population_distances.items():
        w = 1.0 / (dist + epsilon)
        inv_weights[pop] = w
        total_weight += w

    # Normalize to sum to 1.0
    fractions = {pop: round(w / total_weight, 4) for pop, w in inv_weights.items()}

    # Ensure exact sum to 1.0 by adjusting the largest fraction
    frac_sum = sum(fractions.values())
    if fractions and abs(frac_sum - 1.0) > 1e-8:
        max_pop = max(fractions, key=lambda p: fractions[p])
        fractions[max_pop] = round(fractions[max_pop] + (1.0 - frac_sum), 4)

    return fractions


# ── Main inference function ───────────────────────────────────────────────


def infer_ancestry(
    bundle: AncestryBundle,
    sample_engine: sa.Engine,
) -> AncestryResult:
    """Infer ancestry by PCA projection for a sample.

    Queries the sample database for genotypes at bundle SNP positions,
    projects onto PCA space, and classifies by nearest centroid.

    Tries annotated_variants first (post-annotation), falls back to
    raw_variants if annotated_variants is empty or doesn't exist.

    Args:
        bundle: Loaded ancestry PCA bundle.
        sample_engine: SQLAlchemy engine for the sample database.

    Returns:
        AncestryResult with PC scores and top population classification.
    """
    rsids = list(bundle.rsid_set())

    # Fetch genotypes — try annotated_variants first, fall back to raw_variants
    genotype_map: dict[str, str | None] = {}

    with sample_engine.connect() as conn:
        # Check if annotated_variants has data
        try:
            count = conn.execute(
                sa.select(sa.func.count()).select_from(annotated_variants)
            ).scalar()
        except sa.exc.OperationalError:
            logger.debug("annotated_variants_not_available", msg="Using raw_variants fallback")
            count = 0

        if count > 0:
            stmt = sa.select(
                annotated_variants.c.rsid,
                annotated_variants.c.genotype,
            ).where(annotated_variants.c.rsid.in_(rsids))
            rows = conn.execute(stmt).fetchall()
        else:
            # Fall back to raw_variants
            stmt = sa.select(
                raw_variants.c.rsid,
                raw_variants.c.genotype,
            ).where(raw_variants.c.rsid.in_(rsids))
            rows = conn.execute(stmt).fetchall()

    for row in rows:
        genotype_map[row.rsid] = row.genotype

    # Project onto PCA space
    t0 = time.perf_counter()
    pc_scores, snps_used = _project_onto_pca(bundle, genotype_map)
    projection_ms = (time.perf_counter() - t0) * 1000.0

    # Classify
    top_pop, distances = _classify_nearest_centroid(pc_scores, bundle.reference_centroids)

    # Compute admixture fractions (P3-24)
    admixture = compute_admixture_fractions(distances)

    coverage = snps_used / bundle.snp_count if bundle.snp_count > 0 else 0.0
    is_sufficient = coverage >= _MIN_COVERAGE

    result = AncestryResult(
        pc_scores=[round(float(s), 6) for s in pc_scores],
        top_population=top_pop,
        population_distances=distances,
        admixture_fractions=admixture,
        snps_used=snps_used,
        snps_total=bundle.snp_count,
        coverage_fraction=round(coverage, 4),
        projection_time_ms=round(projection_ms, 2),
        is_sufficient=is_sufficient,
    )

    logger.info(
        "ancestry_inferred",
        top_population=result.top_population,
        snps_used=result.snps_used,
        snps_total=result.snps_total,
        coverage=result.coverage_fraction,
        projection_ms=result.projection_time_ms,
        is_sufficient=result.is_sufficient,
    )

    return result


# ── Findings storage ──────────────────────────────────────────────────────


def store_ancestry_findings(
    result: AncestryResult,
    sample_engine: sa.Engine,
) -> int:
    """Store ancestry inference findings in the sample database.

    Creates a single finding with module='ancestry' and
    category='pca_projection' containing the full PCA result.
    The ``detail_json.top_population`` field is read by
    ``prs.get_inferred_ancestry()`` for ancestry mismatch checks.

    Args:
        result: AncestryResult from infer_ancestry.
        sample_engine: SQLAlchemy engine for the sample database.

    Returns:
        Number of findings inserted (0 or 1).
    """
    if not result.is_sufficient:
        logger.warning(
            "ancestry_finding_skipped_insufficient",
            coverage=result.coverage_fraction,
            snps_used=result.snps_used,
        )
        return 0

    # Sort populations by distance (ascending) for display
    sorted_pops = sorted(result.population_distances.items(), key=lambda x: x[1])

    # Build admixture summary for finding text (top 3 contributions)
    sorted_admixture = sorted(result.admixture_fractions.items(), key=lambda x: x[1], reverse=True)
    admixture_parts = [f"{pop} {frac:.0%}" for pop, frac in sorted_admixture[:3] if frac >= 0.01]
    admixture_summary = ", ".join(admixture_parts) if admixture_parts else result.top_population

    finding_text = (
        f"Inferred ancestry: {admixture_summary} "
        f"({result.snps_used}/{result.snps_total} markers, "
        f"{result.coverage_fraction:.0%} coverage)"
    )

    detail = {
        "top_population": result.top_population,
        "inferred_ancestry": result.top_population,
        "pc_scores": result.pc_scores,
        "population_distances": result.population_distances,
        "admixture_fractions": result.admixture_fractions,
        "population_ranking": [{"population": pop, "distance": dist} for pop, dist in sorted_pops],
        "snps_used": result.snps_used,
        "snps_total": result.snps_total,
        "coverage_fraction": result.coverage_fraction,
        "projection_time_ms": result.projection_time_ms,
        "is_sufficient": result.is_sufficient,
    }

    row = {
        "module": "ancestry",
        "category": "pca_projection",
        "evidence_level": 2,  # PCA-based inference = ★★☆☆
        "finding_text": finding_text,
        "detail_json": json.dumps(detail),
    }

    with sample_engine.begin() as conn:
        # Clear previous ancestry PCA findings
        conn.execute(
            sa.delete(findings).where(
                findings.c.module == "ancestry",
                findings.c.category == "pca_projection",
            )
        )
        conn.execute(sa.insert(findings), [row])

    logger.info(
        "ancestry_finding_stored",
        top_population=result.top_population,
    )
    return 1


# ── Convenience pipeline ──────────────────────────────────────────────────


def run_ancestry_inference(
    sample_engine: sa.Engine,
    bundle_path: Path | None = None,
) -> AncestryResult:
    """Run the full ancestry inference pipeline: load → infer → store.

    Args:
        sample_engine: SQLAlchemy engine for the sample database.
        bundle_path: Optional override for the bundle path.

    Returns:
        AncestryResult with PC scores and classification.
    """
    bundle = load_ancestry_bundle(bundle_path)
    result = infer_ancestry(bundle, sample_engine)
    store_ancestry_findings(result, sample_engine)
    return result
