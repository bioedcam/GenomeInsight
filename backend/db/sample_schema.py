"""Per-sample database schema.

Each sample gets its own SQLite file (sample_{id}.db). Tables are created
via create_sample_tables() when a new sample is imported — not via Alembic,
since each sample DB is a separate file created at runtime.

Table definitions live in ``backend.db.tables`` (sample_metadata_obj).
This module provides the creation function that materialises those tables
and seeds initial data.

For existing sample databases that were created before new tables were added
(e.g. ``haplogroup_assignments`` from P3-33), ``ensure_sample_schema_current()``
adds any missing tables without affecting existing data.
"""

import sqlalchemy as sa
import structlog

from backend.db.tables import PREDEFINED_TAGS, sample_metadata_obj

logger = structlog.get_logger(__name__)

# Current schema version. Bump when new tables/columns are added to sample_metadata_obj.
# v7: Add watched_variants table (P4-21g — VUS tracking)
SAMPLE_SCHEMA_VERSION = 7


def create_sample_tables(engine: sa.Engine) -> None:
    """Create all per-sample tables in the given SQLite database.

    Sets WAL journal mode, creates tables from the Core definitions,
    and seeds predefined tags.

    Args:
        engine: SQLAlchemy engine connected to a sample database file.
    """
    with engine.connect() as conn:
        conn.execute(sa.text("PRAGMA journal_mode=WAL"))
        conn.commit()

    # Create all tables defined in sample_metadata_obj
    sample_metadata_obj.create_all(engine, checkfirst=True)

    # Seed predefined tags (batch insert)
    with engine.connect() as conn:
        conn.execute(
            sa.text("INSERT OR IGNORE INTO tags (name, is_predefined) VALUES (:name, 1)"),
            [{"name": tag_name} for tag_name in PREDEFINED_TAGS],
        )
        conn.commit()

    # Stamp the schema version
    _stamp_schema_version(engine, SAMPLE_SCHEMA_VERSION)


def ensure_sample_schema_current(engine: sa.Engine) -> bool:
    """Ensure an existing sample database has all current tables.

    Uses ``CREATE TABLE IF NOT EXISTS`` (via ``checkfirst=True``) so it is
    safe to call on every sample DB open. Returns True if any tables were
    added, False if schema was already current.

    This replaces Alembic for sample databases (P3-33): since each sample
    is an independent SQLite file created at runtime, a lightweight
    version-check + ``create_all(checkfirst=True)`` is sufficient.

    Args:
        engine: SQLAlchemy engine for a sample database file.

    Returns:
        True if the schema was updated, False if already current.
    """
    current_version = _get_schema_version(engine)

    if current_version >= SAMPLE_SCHEMA_VERSION:
        return False

    # Inspect existing tables before upgrade
    inspector = sa.inspect(engine)
    existing = set(inspector.get_table_names())

    # Add any missing tables (checkfirst=True prevents recreation)
    sample_metadata_obj.create_all(engine, checkfirst=True)

    # Check what was added
    inspector2 = sa.inspect(engine)
    after = set(inspector2.get_table_names())
    added = after - existing

    if added:
        logger.info(
            "sample_schema_upgraded",
            added_tables=sorted(added),
            from_version=current_version,
            to_version=SAMPLE_SCHEMA_VERSION,
        )

    # Add missing columns to existing tables (v3 → v4: findings cross-link columns)
    columns_added = _add_missing_columns(engine, current_version)

    _stamp_schema_version(engine, SAMPLE_SCHEMA_VERSION)
    return bool(added) or columns_added


def _add_missing_columns(engine: sa.Engine, from_version: int) -> bool:
    """Add columns introduced after the initial table creation.

    Uses ALTER TABLE ADD COLUMN which is safe on SQLite (no-op if column
    already exists is handled by checking existing columns first).

    Returns True if any columns were added.
    """
    added = False

    if from_version < 4:
        # P3-67: Add cross-module link columns to findings table
        inspector = sa.inspect(engine)
        if "findings" in inspector.get_table_names():
            existing_cols = {c["name"] for c in inspector.get_columns("findings")}
            with engine.begin() as conn:
                if "related_module" not in existing_cols:
                    conn.execute(sa.text("ALTER TABLE findings ADD COLUMN related_module TEXT"))
                    added = True
                if "related_finding_id" not in existing_cols:
                    conn.execute(
                        sa.text("ALTER TABLE findings ADD COLUMN related_finding_id INTEGER")
                    )
                    added = True
            if added:
                # Create index on related_module for cross-module queries
                with engine.begin() as conn:
                    conn.execute(
                        sa.text(
                            "CREATE INDEX IF NOT EXISTS idx_findings_related_module "
                            "ON findings (related_module)"
                        )
                    )
                logger.info(
                    "findings_columns_added",
                    columns=["related_module", "related_finding_id"],
                    from_version=from_version,
                )

    if from_version < 6:
        # P4-19: Add GRCh38 liftover columns to annotated_variants
        added_liftover = False
        inspector = sa.inspect(engine)
        if "annotated_variants" in inspector.get_table_names():
            existing_cols = {c["name"] for c in inspector.get_columns("annotated_variants")}
            with engine.begin() as conn:
                if "chrom_grch38" not in existing_cols:
                    conn.execute(
                        sa.text("ALTER TABLE annotated_variants ADD COLUMN chrom_grch38 TEXT")
                    )
                    added_liftover = True
                if "pos_grch38" not in existing_cols:
                    conn.execute(
                        sa.text("ALTER TABLE annotated_variants ADD COLUMN pos_grch38 INTEGER")
                    )
                    added_liftover = True
            if added_liftover:
                logger.info(
                    "liftover_columns_added",
                    columns=["chrom_grch38", "pos_grch38"],
                    from_version=from_version,
                )
                added = True

    return added


def _get_schema_version(engine: sa.Engine) -> int:
    """Read the schema_version from the sample DB's user_version PRAGMA."""
    with engine.connect() as conn:
        row = conn.execute(sa.text("PRAGMA user_version")).fetchone()
        return row[0] if row else 0


def _stamp_schema_version(engine: sa.Engine, version: int) -> None:
    """Write the schema version into SQLite's user_version PRAGMA."""
    if not isinstance(version, int):
        raise TypeError(f"version must be int, got {type(version).__name__}")
    with engine.connect() as conn:
        conn.execute(sa.text(f"PRAGMA user_version = {version}"))
        conn.commit()
