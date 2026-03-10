"""Per-sample database schema.

Each sample gets its own SQLite file (sample_{id}.db). Tables are created
via create_sample_tables() when a new sample is imported — not via Alembic,
since each sample DB is a separate file created at runtime.

Table definitions live in ``backend.db.tables`` (sample_metadata_obj).
This module provides the creation function that materialises those tables
and seeds initial data.
"""

import sqlalchemy as sa

from backend.db.tables import PREDEFINED_TAGS, sample_metadata_obj


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

    # Seed predefined tags
    with engine.connect() as conn:
        for tag_name in PREDEFINED_TAGS:
            conn.execute(
                sa.text(
                    "INSERT OR IGNORE INTO tags (name, is_predefined) VALUES (:name, 1)"
                ),
                {"name": tag_name},
            )
        conn.commit()
