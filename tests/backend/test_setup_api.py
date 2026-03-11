"""Tests for the setup wizard API (P1-19a).

Covers:
- GET /api/setup/status — first-launch detection
- GET /api/setup/disclaimer — disclaimer text retrieval
- POST /api/setup/accept-disclaimer — disclaimer acceptance persistence
- Edge cases: already accepted, data dir creation
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.db.connection import reset_registry
from backend.db.tables import reference_metadata
from backend.disclaimers import (
    GLOBAL_DISCLAIMER_ACCEPT_LABEL,
    GLOBAL_DISCLAIMER_TEXT,
    GLOBAL_DISCLAIMER_TITLE,
)


@pytest.fixture
def setup_client(tmp_data_dir: Path) -> TestClient:
    """FastAPI TestClient with patched settings for setup API tests."""
    settings = Settings(data_dir=tmp_data_dir, wal_mode=False)

    # Create reference.db so the registry can initialize
    ref_path = settings.reference_db_path
    engine = sa.create_engine(f"sqlite:///{ref_path}")
    reference_metadata.create_all(engine)
    engine.dispose()

    with (
        patch("backend.main.get_settings", return_value=settings),
        patch("backend.db.connection.get_settings", return_value=settings),
        patch("backend.api.routes.setup.get_settings", return_value=settings),
        patch("backend.api.routes.databases.get_settings", return_value=settings),
    ):
        reset_registry()

        from backend.main import create_app

        app = create_app()
        with TestClient(app) as tc:
            yield tc

        reset_registry()


@pytest.fixture
def setup_settings(tmp_data_dir: Path) -> Settings:
    """Settings instance for direct inspection."""
    return Settings(data_dir=tmp_data_dir, wal_mode=False)


# ═══════════════════════════════════════════════════════════════════════
# GET /api/setup/status
# ═══════════════════════════════════════════════════════════════════════


class TestSetupStatus:
    """Tests for the setup status endpoint."""

    def test_fresh_install_needs_setup(self, setup_client: TestClient) -> None:
        """Fresh install (no disclaimer, no DBs) should need setup."""
        resp = setup_client.get("/api/setup/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["needs_setup"] is True
        assert data["disclaimer_accepted"] is False
        assert data["has_databases"] is False
        assert data["has_samples"] is False

    def test_disclaimer_accepted_still_needs_setup_without_dbs(
        self, setup_client: TestClient, tmp_data_dir: Path
    ) -> None:
        """After disclaimer accepted but no DBs, still needs setup."""
        flag_path = tmp_data_dir / ".disclaimer_accepted"
        flag_path.write_text('{"accepted_at": "2026-01-01T00:00:00", "version": "1.0"}')

        resp = setup_client.get("/api/setup/status")
        data = resp.json()
        assert data["disclaimer_accepted"] is True
        assert data["has_databases"] is False
        assert data["needs_setup"] is True

    def test_complete_setup_no_longer_needed(
        self, setup_client: TestClient, tmp_data_dir: Path
    ) -> None:
        """With disclaimer accepted and DBs present, setup is complete."""
        flag_path = tmp_data_dir / ".disclaimer_accepted"
        flag_path.write_text('{"accepted_at": "2026-01-01T00:00:00", "version": "1.0"}')
        (tmp_data_dir / "clinvar.db").write_text("fake")

        resp = setup_client.get("/api/setup/status")
        data = resp.json()
        assert data["disclaimer_accepted"] is True
        assert data["has_databases"] is True
        assert data["needs_setup"] is False

    def test_has_samples_detection(
        self, setup_client: TestClient, tmp_data_dir: Path
    ) -> None:
        """Detect existing sample databases."""
        samples_dir = tmp_data_dir / "samples"
        samples_dir.mkdir(exist_ok=True)
        (samples_dir / "sample_abc123.db").write_text("fake")

        resp = setup_client.get("/api/setup/status")
        data = resp.json()
        assert data["has_samples"] is True

    def test_data_dir_in_response(
        self, setup_client: TestClient, tmp_data_dir: Path
    ) -> None:
        """Response includes the data directory path."""
        resp = setup_client.get("/api/setup/status")
        data = resp.json()
        assert data["data_dir"] == str(tmp_data_dir)


# ═══════════════════════════════════════════════════════════════════════
# GET /api/setup/disclaimer
# ═══════════════════════════════════════════════════════════════════════


class TestGetDisclaimer:
    """Tests for the disclaimer text endpoint."""

    def test_returns_disclaimer_text(self, setup_client: TestClient) -> None:
        """Should return the full disclaimer content."""
        resp = setup_client.get("/api/setup/disclaimer")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == GLOBAL_DISCLAIMER_TITLE
        assert data["text"] == GLOBAL_DISCLAIMER_TEXT
        assert data["accept_label"] == GLOBAL_DISCLAIMER_ACCEPT_LABEL

    def test_disclaimer_text_not_empty(self, setup_client: TestClient) -> None:
        """Disclaimer text should be substantial."""
        resp = setup_client.get("/api/setup/disclaimer")
        data = resp.json()
        assert len(data["text"]) > 500
        assert "educational" in data["text"].lower()
        assert "research" in data["text"].lower()


# ═══════════════════════════════════════════════════════════════════════
# POST /api/setup/accept-disclaimer
# ═══════════════════════════════════════════════════════════════════════


class TestAcceptDisclaimer:
    """Tests for the disclaimer acceptance endpoint."""

    def test_accept_creates_flag_file(
        self, setup_client: TestClient, tmp_data_dir: Path
    ) -> None:
        """Accepting the disclaimer should persist a flag file."""
        resp = setup_client.post("/api/setup/accept-disclaimer")
        assert resp.status_code == 200
        data = resp.json()
        assert data["accepted"] is True
        assert "accepted_at" in data

        flag_path = tmp_data_dir / ".disclaimer_accepted"
        assert flag_path.exists()
        flag_data = json.loads(flag_path.read_text())
        assert "accepted_at" in flag_data
        assert flag_data["version"] == "1.0"

    def test_accept_idempotent(
        self, setup_client: TestClient,
    ) -> None:
        """Accepting twice should succeed (overwrite the flag)."""
        resp1 = setup_client.post("/api/setup/accept-disclaimer")
        assert resp1.status_code == 200

        resp2 = setup_client.post("/api/setup/accept-disclaimer")
        assert resp2.status_code == 200

    def test_accept_changes_status(
        self, setup_client: TestClient,
    ) -> None:
        """After accepting, status should reflect disclaimer_accepted=True."""
        resp = setup_client.get("/api/setup/status")
        assert resp.json()["disclaimer_accepted"] is False

        setup_client.post("/api/setup/accept-disclaimer")

        resp = setup_client.get("/api/setup/status")
        assert resp.json()["disclaimer_accepted"] is True

    def test_accept_creates_data_dir_if_missing(
        self, tmp_data_dir: Path,
    ) -> None:
        """Accept should create data_dir if it doesn't exist yet."""
        import asyncio

        # Use a sub-directory that doesn't exist yet
        new_data_dir = tmp_data_dir / "nonexistent_subdir"
        settings = Settings(data_dir=new_data_dir, wal_mode=False)

        with patch("backend.api.routes.setup.get_settings", return_value=settings):
            from backend.api.routes.setup import accept_disclaimer

            result = asyncio.get_event_loop().run_until_complete(accept_disclaimer())
            assert result.accepted is True
            assert new_data_dir.exists()
            assert (new_data_dir / ".disclaimer_accepted").exists()


# ═══════════════════════════════════════════════════════════════════════
# Unit tests for disclaimers module
# ═══════════════════════════════════════════════════════════════════════


class TestDisclaimersModule:
    """Tests for the hardcoded disclaimer text."""

    def test_global_disclaimer_mentions_key_topics(self) -> None:
        """Global disclaimer should cover essential topics."""
        text = GLOBAL_DISCLAIMER_TEXT.lower()
        assert "not a diagnostic tool" in text
        assert "healthcare provider" in text or "genetic counselor" in text
        assert "educational" in text
        assert "research" in text
        assert "privacy" in text

    def test_global_disclaimer_title_not_empty(self) -> None:
        assert len(GLOBAL_DISCLAIMER_TITLE) > 0

    def test_accept_label_not_empty(self) -> None:
        assert len(GLOBAL_DISCLAIMER_ACCEPT_LABEL) > 0
