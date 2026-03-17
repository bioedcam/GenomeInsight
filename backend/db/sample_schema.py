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

# Current schema version. Bump when new tables are added to sample_metadata_obj.
SAMPLE_SCHEMA_VERSION = 2


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

    _stamp_schema_version(engine, SAMPLE_SCHEMA_VERSION)
    return bool(added)


def _get_schema_version(engine: sa.Engine) -> int:
    """Read the schema_version from the sample DB's user_version PRAGMA."""
    with engine.connect() as conn:
        row = conn.execute(sa.text("PRAGMA user_version")).fetchone()
        return row[0] if row else 0


def _stamp_schema_version(engine: sa.Engine, version: int) -> None:
    """Write the schema version into SQLite's user_version PRAGMA."""
    with engine.connect() as conn:
        conn.execute(sa.text(f"PRAGMA user_version = {version}"))
        conn.commit()
