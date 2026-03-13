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
    "encode_ccres": DatabaseInfo(
        name="encode_ccres",
        display_name="ENCODE cCREs",
        description="Candidate cis-Regulatory Elements for IGV.js track visualization",
        url="https://downloads.wenglab.org/V3/GRCh37-cCREs.bed",
        filename="encode_ccres.db",
        expected_size_bytes=30_000_000,  # ~30 MB (SQLite after BED loading)
        required=False,
        phase=2,
        post_download=_build_encode_ccres_db,
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
