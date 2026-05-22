"""Source-deletion cascade tests (Step 66 / MRG-02a; AncestryDNA Plan §10.8).

Exercises :mod:`backend.services.sample_delete` plus the DELETE route +
``GET /api/samples/{id}/merged-children`` preview surface. Tests are
self-contained: every merged child is materialised by hand (samples row +
per-sample DB with a ``merge_provenance`` payload) so the cascade walk is
exercised in isolation from the full merge orchestration in Step 65.

Step 82 (MRG-08g) lands the end-to-end merge → delete → cascade flow
through ``merge_samples`` itself; Step 66 locks the cascade contract.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.db.connection import DBRegistry, get_registry, reset_registry
from backend.db.sample_schema import create_sample_tables
from backend.db.tables import (
    merge_provenance,
    raw_variants,
    reference_metadata,
    sample_metadata_table,
    samples,
)
from backend.services.sample_delete import (
    delete_sample_with_cascade,
    list_merged_children,
)

# ── Test-scoped registry mirroring test_sample_merge.py ──────────────


@pytest.fixture
def cascade_registry(tmp_data_dir: Path):
    settings = Settings(data_dir=tmp_data_dir, wal_mode=False)
    ref_engine = sa.create_engine(f"sqlite:///{settings.reference_db_path}")
    reference_metadata.create_all(ref_engine)
    ref_engine.dispose()

    with patch("backend.db.connection.get_settings", return_value=settings):
        reset_registry()
        registry = get_registry()
        try:
            yield registry
        finally:
            registry.dispose_all()
            reset_registry()


# ── Helpers — build samples + per-sample DBs by hand ─────────────────


def _make_source_sample(
    registry: DBRegistry,
    *,
    name: str,
    file_format: str = "23andme_v5",
    file_hash: str = "deadbeef",
    is_merged: bool = False,
) -> int:
    """Insert a samples row and materialise its per-sample DB."""
    now = datetime.now(UTC)
    with registry.reference_engine.begin() as conn:
        result = conn.execute(
            samples.insert().values(
                name=name,
                db_path="",
                file_format=file_format,
                file_hash=file_hash,
                created_at=now,
                updated_at=now,
            )
        )
        sample_id = int(result.inserted_primary_key[0])
        db_path = f"samples/sample_{sample_id}.db"
        conn.execute(
            samples.update().where(samples.c.id == sample_id).values(db_path=db_path)
        )

    sample_db_path = registry.settings.data_dir / db_path
    sample_db_path.parent.mkdir(parents=True, exist_ok=True)
    bootstrap = sa.create_engine(f"sqlite:///{sample_db_path}")
    try:
        create_sample_tables(bootstrap, is_merged_sample=is_merged)
    finally:
        bootstrap.dispose()

    engine = registry.get_sample_engine(sample_db_path)
    with engine.begin() as conn:
        conn.execute(
            sample_metadata_table.insert().values(
                id=1,
                name=name,
                file_format=file_format,
                file_hash=file_hash,
                created_at=now,
                updated_at=now,
            )
        )
        # Drop in one row so the file isn't empty.
        conn.execute(
            raw_variants.insert(),
            [{"rsid": "rs1", "chrom": "1", "pos": 100, "genotype": "AG"}],
        )
    return sample_id


def _make_merged_child(
    registry: DBRegistry,
    *,
    name: str,
    source_ids: list[int],
    strategy: str = "flag_only",
    file_hash: str = "mergedhash",
) -> int:
    """Insert a samples row with ``file_format='merged_v1'`` and a merge_provenance row."""
    merged_id = _make_source_sample(
        registry,
        name=name,
        file_format="merged_v1",
        file_hash=file_hash,
        is_merged=True,
    )
    with registry.reference_engine.connect() as conn:
        row = conn.execute(
            sa.select(samples.c.db_path).where(samples.c.id == merged_id)
        ).fetchone()
    assert row is not None
    sample_db_path = registry.settings.data_dir / row.db_path
    engine = registry.get_sample_engine(sample_db_path)
    with engine.begin() as conn:
        conn.execute(
            merge_provenance.insert().values(
                id=1,
                merged_at=datetime.now(UTC),
                strategy=strategy,
                source_sample_ids=json.dumps(source_ids),
                source_file_hashes=json.dumps(["a", "b"]),
                concordance_summary=json.dumps(
                    {
                        "match": 1,
                        "filled_nocall": 0,
                        "discordant": 0,
                        "unique_S1": 0,
                        "unique_S2": 0,
                        "collapsed_rsid": 0,
                    }
                ),
            )
        )
    return merged_id


def _sample_db_path(registry: DBRegistry, sample_id: int) -> Path:
    with registry.reference_engine.connect() as conn:
        row = conn.execute(
            sa.select(samples.c.db_path).where(samples.c.id == sample_id)
        ).fetchone()
    assert row is not None
    return registry.settings.data_dir / row.db_path


# ── list_merged_children ─────────────────────────────────────────────


class TestListMergedChildren:
    def test_no_merged_children_when_sample_never_merged(
        self, cascade_registry: DBRegistry
    ) -> None:
        sid = _make_source_sample(cascade_registry, name="alice.txt")
        assert list_merged_children(cascade_registry, sid) == []

    def test_lists_merged_child_referencing_source(
        self, cascade_registry: DBRegistry
    ) -> None:
        s1 = _make_source_sample(cascade_registry, name="alice_23andme.txt")
        s2 = _make_source_sample(cascade_registry, name="alice_ancestrydna.txt")
        merged = _make_merged_child(
            cascade_registry,
            name="alice (merged)",
            source_ids=[s1, s2],
        )
        children = list_merged_children(cascade_registry, s1)
        assert [c.id for c in children] == [merged]
        assert children[0].name == "alice (merged)"

    def test_lists_both_sources_pointing_to_same_merged(
        self, cascade_registry: DBRegistry
    ) -> None:
        s1 = _make_source_sample(cascade_registry, name="a.txt")
        s2 = _make_source_sample(cascade_registry, name="b.txt")
        merged = _make_merged_child(
            cascade_registry, name="ab (merged)", source_ids=[s1, s2]
        )
        assert [c.id for c in list_merged_children(cascade_registry, s1)] == [merged]
        assert [c.id for c in list_merged_children(cascade_registry, s2)] == [merged]

    def test_skips_merged_with_missing_db_file(
        self, cascade_registry: DBRegistry, caplog: pytest.LogCaptureFixture
    ) -> None:
        s1 = _make_source_sample(cascade_registry, name="a.txt")
        s2 = _make_source_sample(cascade_registry, name="b.txt")
        merged = _make_merged_child(
            cascade_registry, name="m.txt", source_ids=[s1, s2]
        )
        # Drop the merged DB file but keep the reference row — half-broken
        # install. The walk should skip + log, not raise.
        merged_db = _sample_db_path(cascade_registry, merged)
        cascade_registry.dispose_sample_engine(merged_db)
        merged_db.unlink()

        with caplog.at_level("WARNING"):
            children = list_merged_children(cascade_registry, s1)
        assert children == []
        assert any(
            r.message == "merged_sample_db_missing" for r in caplog.records
        )

    def test_skips_merged_with_malformed_provenance(
        self, cascade_registry: DBRegistry, caplog: pytest.LogCaptureFixture
    ) -> None:
        s1 = _make_source_sample(cascade_registry, name="a.txt")
        s2 = _make_source_sample(cascade_registry, name="b.txt")
        merged = _make_merged_child(
            cascade_registry, name="m.txt", source_ids=[s1, s2]
        )
        merged_db = _sample_db_path(cascade_registry, merged)
        engine = cascade_registry.get_sample_engine(merged_db)
        with engine.begin() as conn:
            conn.execute(
                merge_provenance.update()
                .where(merge_provenance.c.id == 1)
                .values(source_sample_ids="not-json")
            )

        with caplog.at_level("WARNING"):
            children = list_merged_children(cascade_registry, s1)
        assert children == []
        assert any(
            r.message == "merged_provenance_malformed" for r in caplog.records
        )


# ── delete_sample_with_cascade ───────────────────────────────────────


class TestDeleteSampleWithCascade:
    def test_deletes_unmerged_sample_returns_no_children(
        self, cascade_registry: DBRegistry
    ) -> None:
        sid = _make_source_sample(cascade_registry, name="alone.txt")
        db_path = _sample_db_path(cascade_registry, sid)
        assert db_path.exists()

        result = delete_sample_with_cascade(cascade_registry, sid)
        assert result is not None
        assert result.deleted_sample_id == sid
        assert result.deleted_merged_children == []
        assert not db_path.exists()
        with cascade_registry.reference_engine.connect() as conn:
            row = conn.execute(
                sa.select(samples).where(samples.c.id == sid)
            ).fetchone()
        assert row is None

    def test_cascade_removes_merged_child_when_source_deleted(
        self, cascade_registry: DBRegistry
    ) -> None:
        s1 = _make_source_sample(cascade_registry, name="s1.txt")
        s2 = _make_source_sample(cascade_registry, name="s2.txt")
        merged = _make_merged_child(
            cascade_registry, name="m.txt", source_ids=[s1, s2]
        )

        merged_db = _sample_db_path(cascade_registry, merged)
        s1_db = _sample_db_path(cascade_registry, s1)
        s2_db = _sample_db_path(cascade_registry, s2)
        assert merged_db.exists() and s1_db.exists() and s2_db.exists()

        result = delete_sample_with_cascade(cascade_registry, s1)
        assert result is not None
        assert result.deleted_sample_id == s1
        assert [c.id for c in result.deleted_merged_children] == [merged]

        # Source + merged gone; other source survives.
        with cascade_registry.reference_engine.connect() as conn:
            ids = [
                r.id for r in conn.execute(sa.select(samples.c.id))
            ]
        assert s1 not in ids
        assert merged not in ids
        assert s2 in ids
        assert not s1_db.exists()
        assert not merged_db.exists()
        assert s2_db.exists()

    def test_returns_none_for_missing_sample(
        self, cascade_registry: DBRegistry
    ) -> None:
        assert delete_sample_with_cascade(cascade_registry, 99999) is None

    def test_cascade_logged_with_child_ids(
        self,
        cascade_registry: DBRegistry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        s1 = _make_source_sample(cascade_registry, name="s1.txt")
        s2 = _make_source_sample(cascade_registry, name="s2.txt")
        merged = _make_merged_child(
            cascade_registry, name="merged.txt", source_ids=[s1, s2]
        )

        with caplog.at_level("INFO"):
            delete_sample_with_cascade(cascade_registry, s1)
        cascade_logs = [
            r for r in caplog.records if r.message == "sample_delete_cascade"
        ]
        assert len(cascade_logs) == 1
        # structlog-style ``extra`` lands as attributes on the LogRecord.
        record = cascade_logs[0]
        assert record.deleted_sample_id == s1
        assert record.deleted_merged_children == [
            {"id": merged, "name": "merged.txt"}
        ]

    def test_unmerged_delete_has_empty_cascade_in_log(
        self,
        cascade_registry: DBRegistry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        sid = _make_source_sample(cascade_registry, name="alone.txt")
        with caplog.at_level("INFO"):
            delete_sample_with_cascade(cascade_registry, sid)
        cascade_logs = [
            r for r in caplog.records if r.message == "sample_delete_cascade"
        ]
        assert len(cascade_logs) == 1
        assert cascade_logs[0].deleted_merged_children == []


# ── DELETE + preview routes ──────────────────────────────────────────


@pytest.fixture
def client(tmp_data_dir: Path):
    settings = Settings(data_dir=tmp_data_dir, wal_mode=False)
    ref_engine = sa.create_engine(f"sqlite:///{settings.reference_db_path}")
    reference_metadata.create_all(ref_engine)
    ref_engine.dispose()

    with (
        patch("backend.main.get_settings", return_value=settings),
        patch("backend.db.connection.get_settings", return_value=settings),
    ):
        reset_registry()
        from backend.main import create_app

        app = create_app()
        with TestClient(app) as tc:
            yield tc, get_registry()
        reset_registry()


class TestMergedChildrenRoute:
    def test_empty_list_for_unmerged_sample(self, client) -> None:
        tc, registry = client
        sid = _make_source_sample(registry, name="solo.txt")
        resp = tc.get(f"/api/samples/{sid}/merged-children")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_lists_merged_children_for_source(self, client) -> None:
        tc, registry = client
        s1 = _make_source_sample(registry, name="s1.txt")
        s2 = _make_source_sample(registry, name="s2.txt")
        merged = _make_merged_child(
            registry, name="merged.txt", source_ids=[s1, s2]
        )
        resp = tc.get(f"/api/samples/{s1}/merged-children")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload == [{"id": merged, "name": "merged.txt"}]

    def test_returns_404_when_sample_missing(self, client) -> None:
        tc, _ = client
        resp = tc.get("/api/samples/99999/merged-children")
        assert resp.status_code == 404


class TestDeleteRouteCascade:
    def test_delete_cascades_via_route(self, client) -> None:
        tc, registry = client
        s1 = _make_source_sample(registry, name="s1.txt")
        s2 = _make_source_sample(registry, name="s2.txt")
        merged = _make_merged_child(
            registry, name="merged.txt", source_ids=[s1, s2]
        )

        resp = tc.delete(f"/api/samples/{s1}")
        assert resp.status_code == 204

        with registry.reference_engine.connect() as conn:
            ids = [
                r.id for r in conn.execute(sa.select(samples.c.id))
            ]
        assert s1 not in ids
        assert merged not in ids
        assert s2 in ids

    def test_delete_unmerged_sample_returns_204(self, client) -> None:
        tc, registry = client
        sid = _make_source_sample(registry, name="solo.txt")
        resp = tc.delete(f"/api/samples/{sid}")
        assert resp.status_code == 204
        with registry.reference_engine.connect() as conn:
            row = conn.execute(
                sa.select(samples).where(samples.c.id == sid)
            ).fetchone()
        assert row is None

    def test_delete_missing_sample_returns_404(self, client) -> None:
        tc, _ = client
        resp = tc.delete("/api/samples/99999")
        assert resp.status_code == 404
