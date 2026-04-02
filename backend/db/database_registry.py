"""Registry of reference databases available for download.

Defines metadata for each database that GenomeInsight uses: name, description,
approximate size, download URL, expected SHA-256, and whether it is required
or optional for core functionality.

The setup wizard API (P1-18) uses this registry to list databases and
orchestrate parallel downloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from backend.config import Settings

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True)
class DatabaseInfo:
    """Metadata for a downloadable reference database."""

    name: str
    display_name: str
    description: str
    url: str
    filename: str
    expected_size_bytes: int
    sha256: str | None = None
    required: bool = True
    phase: int = 1
    post_download: Callable[[Path, Path], None] | None = None
    build_mode: str = "pipeline"  # "pipeline" | "download" | "manual" | "bundled"
    target_db: str = "standalone"  # "standalone" | "reference"

    def dest_path(self, settings: Settings) -> Path:
        """Resolve the destination file path for this database."""
        return settings.data_dir / self.filename


# ── Post-download transforms ─────────────────────────────────────────


def _build_encode_ccres_db(raw_bed_path: Path, db_path: Path) -> None:
    """Transform a downloaded ENCODE cCREs BED file into a SQLite database.

    Called by the download pipeline as a ``post_download`` hook. Creates a
    SQLite database at *db_path* from the raw BED at *raw_bed_path*, then
    removes the raw BED file.
    """
    import sqlalchemy as sa

    from backend.annotation.encode_ccres import load_encode_ccres

    engine = sa.create_engine(f"sqlite:///{db_path}", echo=False)
    try:
        load_encode_ccres(raw_bed_path, engine)
    except Exception:
        engine.dispose()
        db_path.unlink(missing_ok=True)
        raise
    engine.dispose()
    # Clean up the raw BED — the SQLite DB is the final artifact
    raw_bed_path.unlink(missing_ok=True)


# ── Database Definitions ──────────────────────────────────────────────
# URLs point to GitHub Releases (placeholder URLs until actual releases
# are published).  SHA-256 values are None until bundles are built.

DATABASES: dict[str, DatabaseInfo] = {
    "clinvar": DatabaseInfo(
        name="clinvar",
        display_name="ClinVar",
        description="Clinical variant interpretations from NCBI ClinVar",
        url="",
        filename="clinvar.db",
        expected_size_bytes=250_000_000,  # ~250 MB
        required=True,
        phase=1,
        build_mode="pipeline",
        target_db="reference",
    ),
    "vep_bundle": DatabaseInfo(
        name="vep_bundle",
        display_name="VEP Bundle",
        description="Pre-computed variant effect predictions for 23andMe v5 rsids",
        url="",
        filename="vep_bundle.db",
        expected_size_bytes=500_000_000,  # ~500 MB
        required=False,
        phase=2,
        build_mode="manual",
        target_db="standalone",
    ),
    "gnomad": DatabaseInfo(
        name="gnomad",
        display_name="gnomAD",
        description="Population allele frequencies from the Genome Aggregation Database",
        url="",
        filename="gnomad_af.db",
        expected_size_bytes=2_000_000_000,  # ~2 GB
        required=True,
        phase=2,
        build_mode="pipeline",
        target_db="standalone",
    ),
    "dbnsfp": DatabaseInfo(
        name="dbnsfp",
        display_name="dbNSFP",
        description=(
            "In-silico pathogenicity prediction scores (SIFT, PolyPhen-2, CADD, REVEL, etc.)"
        ),
        url="",
        filename="dbnsfp.db",
        expected_size_bytes=1_500_000_000,  # ~1.5 GB
        required=True,
        phase=2,
        build_mode="pipeline",
        target_db="standalone",
    ),
    "cpic": DatabaseInfo(
        name="cpic",
        display_name="CPIC",
        description="Pharmacogenomics allele definitions and drug guidelines",
        url="",
        filename="cpic.db",
        expected_size_bytes=5_000_000,  # ~5 MB
        required=True,
        phase=3,
        build_mode="pipeline",
        target_db="reference",
    ),
    "ancestry_pca": DatabaseInfo(
        name="ancestry_pca",
        display_name="Ancestry PCA Bundle",
        description="Pre-computed PCA loadings and reference population coordinates",
        url="",
        filename="ancestry_pca.db",
        expected_size_bytes=50_000_000,  # ~50 MB
        required=False,
        phase=3,
        build_mode="bundled",
        target_db="standalone",
    ),
    "encode_ccres": DatabaseInfo(
        name="encode_ccres",
        display_name="ENCODE cCREs",
        description="Candidate cis-Regulatory Elements for IGV.js track visualization",
        url="https://downloads.wenglab.org/V3/GRCh37-cCREs.bed",
        filename="encode_ccres.db",
        expected_size_bytes=30_000_000,  # ~30 MB (SQLite after BED loading)
        required=False,
        phase=2,
        build_mode="download",
        target_db="standalone",
        post_download=_build_encode_ccres_db,
    ),
    "gwas_catalog": DatabaseInfo(
        name="gwas_catalog",
        display_name="GWAS Catalog",
        description="Genome-wide association study results from EBI GWAS Catalog",
        url="",
        filename="",
        expected_size_bytes=100_000_000,  # ~100 MB
        required=True,
        phase=2,
        build_mode="pipeline",
        target_db="reference",
    ),
    "dbsnp": DatabaseInfo(
        name="dbsnp",
        display_name="dbSNP",
        description="SNP merge history for rsid validation (NCBI dbSNP b151)",
        url="",
        filename="",
        expected_size_bytes=20_000_000,  # ~20 MB
        required=True,
        phase=2,
        build_mode="pipeline",
        target_db="reference",
    ),
    "mondo_hpo": DatabaseInfo(
        name="mondo_hpo",
        display_name="MONDO/HPO",
        description="Gene-disease-phenotype associations from Monarch Initiative and HPO",
        url="",
        filename="",
        expected_size_bytes=15_000_000,  # ~15 MB
        required=True,
        phase=2,
        build_mode="pipeline",
        target_db="reference",
    ),
}


def get_all_databases() -> list[DatabaseInfo]:
    """Return all registered databases."""
    return list(DATABASES.values())


def get_database(name: str) -> DatabaseInfo | None:
    """Look up a database by name, or None if not found."""
    return DATABASES.get(name)


# ── Build function registry (lazy-loaded) ────────────────────────

_BUILD_FN_MAP: dict[str, Callable] | None = None


def get_build_fn(db_name: str) -> Callable | None:
    """Return the build function for a pipeline database, or None."""
    global _BUILD_FN_MAP  # noqa: PLW0603
    if _BUILD_FN_MAP is None:
        from backend.annotation.clinvar import download_and_load_clinvar
        from backend.annotation.cpic import download_and_load_cpic
        from backend.annotation.dbnsfp import download_and_load_dbnsfp
        from backend.annotation.dbsnp import download_and_load_rsmerge
        from backend.annotation.gnomad import download_and_load_gnomad
        from backend.annotation.gwas import download_and_load_gwas
        from backend.annotation.mondo_hpo import download_and_load_mondo_hpo

        _BUILD_FN_MAP = {
            "clinvar": download_and_load_clinvar,
            "gnomad": download_and_load_gnomad,
            "dbnsfp": download_and_load_dbnsfp,
            "gwas_catalog": download_and_load_gwas,
            "dbsnp": download_and_load_rsmerge,
            "mondo_hpo": download_and_load_mondo_hpo,
            "cpic": download_and_load_cpic,
        }
    return _BUILD_FN_MAP.get(db_name)


# ── Status checking ──────────────────────────────────────────────


def _check_db_version_exists(db_name: str, settings: Settings) -> bool:
    """Check if a database has a record in the database_versions table."""
    import sqlalchemy as sa

    from backend.db.tables import database_versions

    ref_path = settings.reference_db_path
    if not ref_path.exists():
        return False

    engine = sa.create_engine(f"sqlite:///{ref_path}")
    try:
        with engine.connect() as conn:
            row = conn.execute(
                sa.select(database_versions.c.db_name).where(
                    database_versions.c.db_name == db_name
                )
            ).fetchone()
        return row is not None
    except Exception:
        return False
    finally:
        engine.dispose()


def get_database_status(db_info: DatabaseInfo, settings: Settings) -> dict:
    """Check the on-disk status of a single database.

    Returns a dict with download/presence status suitable for API responses.
    """
    if db_info.build_mode == "bundled":
        downloaded = True
        file_size = None
    elif db_info.target_db == "reference":
        # reference.db-resident: check database_versions table
        downloaded = _check_db_version_exists(db_info.name, settings)
        file_size = None
    else:
        # standalone or manual: check file existence
        dest = db_info.dest_path(settings)
        downloaded = dest.exists()
        file_size = dest.stat().st_size if downloaded else None

    return {
        "name": db_info.name,
        "display_name": db_info.display_name,
        "description": db_info.description,
        "filename": db_info.filename,
        "expected_size_bytes": db_info.expected_size_bytes,
        "required": db_info.required,
        "phase": db_info.phase,
        "downloaded": downloaded,
        "file_size_bytes": file_size,
        "build_mode": db_info.build_mode,
    }
