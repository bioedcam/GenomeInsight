"""Load curated HLA proxy lookup data from JSON into reference.db.

Reads ``hla_proxy_lookup.json`` and bulk-inserts rows into the
``hla_proxy_lookup`` table.  Idempotent — clears existing rows before
inserting so the table always matches the current JSON bundle.
"""

from __future__ import annotations

import json
from pathlib import Path

import sqlalchemy as sa

from backend.db.tables import hla_proxy_lookup

_JSON_PATH = Path(__file__).resolve().parent / "panels" / "hla_proxy_lookup.json"


def load_hla_proxy_data(
    engine: sa.Engine,
    *,
    json_path: Path | None = None,
) -> int:
    """Populate ``hla_proxy_lookup`` from the curated JSON bundle.

    Parameters
    ----------
    engine:
        SQLAlchemy engine connected to reference.db.
    json_path:
        Override path to the JSON file (for testing).

    Returns
    -------
    int
        Number of rows inserted.
    """
    path = json_path or _JSON_PATH
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    entries = data.get("entries", [])
    if not entries:
        return 0

    rows = [
        {
            "hla_allele": e["hla_allele"],
            "proxy_rsid": e["proxy_rsid"],
            "r_squared": e["r_squared"],
            "ancestry_pop": e["ancestry_pop"],
            "clinical_context": e.get("clinical_context"),
            "pmid": e.get("pmid"),
        }
        for e in entries
    ]

    with engine.begin() as conn:
        conn.execute(hla_proxy_lookup.delete())
        conn.execute(hla_proxy_lookup.insert(), rows)

    return len(rows)
