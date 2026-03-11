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

from backend.config import Settings


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

    def dest_path(self, settings: Settings) -> Path:
        """Resolve the destination file path for this database."""
        return settings.data_dir / self.filename


# ── Database Definitions ──────────────────────────────────────────────
# URLs point to GitHub Releases (placeholder URLs until actual releases
# are published).  SHA-256 values are None until bundles are built.

DATABASES: dict[str, DatabaseInfo] = {
    "clinvar": DatabaseInfo(
        name="clinvar",
        display_name="ClinVar",
        description="Clinical variant interpretations from NCBI ClinVar",
        url="https://github.com/GenomeInsight/data/releases/download/v1.0/clinvar.db.gz",
        filename="clinvar.db",
        expected_size_bytes=250_000_000,  # ~250 MB
        required=True,
        phase=1,
    ),
    "vep_bundle": DatabaseInfo(
        name="vep_bundle",
        display_name="VEP Bundle",
        description="Pre-computed variant effect predictions for 23andMe v5 rsids",
        url="https://github.com/GenomeInsight/data/releases/download/v1.0/vep_bundle.db.gz",
        filename="vep_bundle.db",
        expected_size_bytes=500_000_000,  # ~500 MB
        required=True,
        phase=2,
    ),
    "gnomad": DatabaseInfo(
        name="gnomad",
        display_name="gnomAD",
        description="Population allele frequencies from the Genome Aggregation Database",
        url="https://github.com/GenomeInsight/data/releases/download/v1.0/gnomad_af.db.gz",
        filename="gnomad_af.db",
        expected_size_bytes=2_000_000_000,  # ~2 GB
        required=True,
        phase=2,
    ),
    "dbnsfp": DatabaseInfo(
        name="dbnsfp",
        display_name="dbNSFP",
        description=(
            "In-silico pathogenicity prediction scores (SIFT, PolyPhen-2, CADD, REVEL, etc.)"
        ),
        url="https://github.com/GenomeInsight/data/releases/download/v1.0/dbnsfp.db.gz",
        filename="dbnsfp.db",
        expected_size_bytes=1_500_000_000,  # ~1.5 GB
        required=True,
        phase=2,
    ),
    "cpic": DatabaseInfo(
        name="cpic",
        display_name="CPIC",
        description="Pharmacogenomics allele definitions and drug guidelines",
        url="https://github.com/GenomeInsight/data/releases/download/v1.0/cpic.db.gz",
        filename="cpic.db",
        expected_size_bytes=5_000_000,  # ~5 MB
        required=True,
        phase=3,
    ),
    "ancestry_pca": DatabaseInfo(
        name="ancestry_pca",
        display_name="Ancestry PCA Bundle",
        description="Pre-computed PCA loadings and reference population coordinates",
        url="https://github.com/GenomeInsight/data/releases/download/v1.0/ancestry_pca.db.gz",
        filename="ancestry_pca.db",
        expected_size_bytes=50_000_000,  # ~50 MB
        required=False,
        phase=3,
    ),
}


def get_all_databases() -> list[DatabaseInfo]:
    """Return all registered databases."""
    return list(DATABASES.values())


def get_database(name: str) -> DatabaseInfo | None:
    """Look up a database by name, or None if not found."""
    return DATABASES.get(name)


def get_database_status(db_info: DatabaseInfo, settings: Settings) -> dict:
    """Check the on-disk status of a single database.

    Returns a dict with download/presence status suitable for API responses.
    """
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
    }
