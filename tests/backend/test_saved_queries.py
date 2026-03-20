"""Tests for saved queries CRUD API (P4-06)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.db.connection import reset_registry
from backend.db.tables import reference_metadata


@pytest.fixture
def sq_client(tmp_data_dir: Path) -> TestClient:
    """TestClient with saved_queries.get_settings patched."""
    settings = Settings(data_dir=tmp_data_dir, wal_mode=False)

    ref_path = settings.reference_db_path
    engine = sa.create_engine(f"sqlite:///{ref_path}")
    reference_metadata.create_all(engine)
    engine.dispose()

    with (
        patch("backend.main.get_settings", return_value=settings),
        patch("backend.db.connection.get_settings", return_value=settings),
        patch("backend.api.routes.saved_queries.get_settings", return_value=settings),
    ):
        reset_registry()

        from backend.main import create_app

        app = create_app()
        with TestClient(app) as tc:
            yield tc

        reset_registry()


class TestListSavedQueries:
    def test_returns_empty_initially(self, sq_client: TestClient) -> None:
        resp = sq_client.get("/api/saved-queries")
        assert resp.status_code == 200
        assert resp.json()["queries"] == []

    def test_returns_saved_queries(self, sq_client: TestClient) -> None:
        filt = {
            "combinator": "and",
            "rules": [
                {"field": "clinvar_significance", "operator": "=", "value": "Pathogenic"},
            ],
        }
        sq_client.post(
            "/api/saved-queries",
            json={"name": "Pathogenic", "filter": filt},
        )
        resp = sq_client.get("/api/saved-queries")
        assert resp.status_code == 200
        queries = resp.json()["queries"]
        assert len(queries) == 1
        assert queries[0]["name"] == "Pathogenic"


class TestCreateSavedQuery:
    def test_creates_query(self, sq_client: TestClient) -> None:
        filt = {"combinator": "and", "rules": [{"field": "chrom", "operator": "=", "value": "1"}]}
        resp = sq_client.post(
            "/api/saved-queries",
            json={"name": "Chr1 Only", "filter": filt},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Chr1 Only"
        assert data["filter"] == filt
        assert "created_at" in data
        assert "updated_at" in data

    def test_rejects_duplicate_name(self, sq_client: TestClient) -> None:
        filt = {"combinator": "and", "rules": []}
        sq_client.post("/api/saved-queries", json={"name": "Dup", "filter": filt})
        resp = sq_client.post("/api/saved-queries", json={"name": "Dup", "filter": filt})
        assert resp.status_code == 409

    def test_rejects_empty_name(self, sq_client: TestClient) -> None:
        resp = sq_client.post(
            "/api/saved-queries",
            json={"name": "", "filter": {"combinator": "and", "rules": []}},
        )
        assert resp.status_code == 422

    def test_rejects_blank_name(self, sq_client: TestClient) -> None:
        resp = sq_client.post(
            "/api/saved-queries",
            json={"name": "   ", "filter": {"combinator": "and", "rules": []}},
        )
        assert resp.status_code == 400


class TestUpdateSavedQuery:
    def test_updates_filter(self, sq_client: TestClient) -> None:
        filt = {"combinator": "and", "rules": []}
        sq_client.post("/api/saved-queries", json={"name": "Editable", "filter": filt})

        new_filt = {
            "combinator": "or",
            "rules": [{"field": "chrom", "operator": "=", "value": "X"}],
        }
        resp = sq_client.put(
            "/api/saved-queries/Editable",
            json={"filter": new_filt},
        )
        assert resp.status_code == 200
        assert resp.json()["filter"] == new_filt

    def test_renames_query(self, sq_client: TestClient) -> None:
        filt = {"combinator": "and", "rules": []}
        sq_client.post("/api/saved-queries", json={"name": "OldName", "filter": filt})

        resp = sq_client.put(
            "/api/saved-queries/OldName",
            json={"new_name": "NewName"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "NewName"

        # Verify old name gone
        listing = sq_client.get("/api/saved-queries").json()
        names = [q["name"] for q in listing["queries"]]
        assert "OldName" not in names
        assert "NewName" in names

    def test_rejects_rename_to_existing(self, sq_client: TestClient) -> None:
        filt = {"combinator": "and", "rules": []}
        sq_client.post("/api/saved-queries", json={"name": "A", "filter": filt})
        sq_client.post("/api/saved-queries", json={"name": "B", "filter": filt})

        resp = sq_client.put("/api/saved-queries/A", json={"new_name": "B"})
        assert resp.status_code == 409

    def test_rejects_blank_new_name(self, sq_client: TestClient) -> None:
        filt = {"combinator": "and", "rules": []}
        sq_client.post("/api/saved-queries", json={"name": "Original", "filter": filt})
        resp = sq_client.put("/api/saved-queries/Original", json={"new_name": "   "})
        assert resp.status_code == 400

    def test_rejects_nonexistent(self, sq_client: TestClient) -> None:
        resp = sq_client.put(
            "/api/saved-queries/NoSuch",
            json={"filter": {"combinator": "and", "rules": []}},
        )
        assert resp.status_code == 404


class TestDeleteSavedQuery:
    def test_deletes_query(self, sq_client: TestClient) -> None:
        filt = {"combinator": "and", "rules": []}
        sq_client.post("/api/saved-queries", json={"name": "ToDelete", "filter": filt})

        resp = sq_client.delete("/api/saved-queries/ToDelete")
        assert resp.status_code == 204

        listing = sq_client.get("/api/saved-queries").json()
        names = [q["name"] for q in listing["queries"]]
        assert "ToDelete" not in names

    def test_rejects_nonexistent(self, sq_client: TestClient) -> None:
        resp = sq_client.delete("/api/saved-queries/NoSuch")
        assert resp.status_code == 404
