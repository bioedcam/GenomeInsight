"""Database layer for GenomeInsight.

Public API::

    from backend.db import reference_metadata, sample_metadata_obj
    from backend.db import create_sample_tables, get_registry, DBRegistry

    # For individual tables, import from tables submodule:
    from backend.db.tables import clinvar_variants, annotated_variants
"""

from backend.db.connection import DBRegistry, get_registry, reset_registry
from backend.db.sample_schema import create_sample_tables
from backend.db.tables import reference_metadata, sample_metadata_obj

__all__ = [
    "DBRegistry",
    "create_sample_tables",
    "get_registry",
    "reference_metadata",
    "reset_registry",
    "sample_metadata_obj",
]
