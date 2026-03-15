"""Tests for cancer module disclaimer API endpoint (P3-17).

Covers:
  - GET /api/analysis/cancer/disclaimer — Cancer disclaimer text retrieval
  - Response contains title and text fields
  - Text is substantial and covers key cancer-specific topics
  - Disclaimer matches hardcoded constants from disclaimers.py
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.db.connection import reset_registry
from backend.db.tables import reference_metadata
from backend.disclaimers import CANCER_DISCLAIMER_TEXT, CANCER_DISCLAIMER_TITLE

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture()
def cancer_client(tmp_data_dir: Path) -> Generator[TestClient, None, None]:
    """FastAPI test client wired to a temporary data directory."""
    settings = Settings(data_dir=tmp_data_dir, wal_mode=False)

    # Create reference.db so the registry can initialize
    ref_path = settings.reference_db_path
    engine = sa.create_engine(f"sqlite:///{ref_path}")
    reference_metadata.create_all(engine)
    engine.dispose()

    with (
        patch("backend.main.get_settings", return_value=settings),
        patch("backend.db.connection.get_settings", return_value=settings),
    ):
        reset_registry()

        from backend.main import create_app

        app = create_app()
        with TestClient(app) as tc:
            yield tc

        reset_registry()


# ═══════════════════════════════════════════════════════════════════════
# GET /api/analysis/cancer/disclaimer
# ═══════════════════════════════════════════════════════════════════════


class TestCancerDisclaimer:
    """Tests for the cancer disclaimer endpoint (P3-17)."""

    def test_returns_disclaimer_text(self, cancer_client: TestClient) -> None:
        """Should return the full cancer disclaimer content."""
        resp = cancer_client.get("/api/analysis/cancer/disclaimer")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == CANCER_DISCLAIMER_TITLE
        assert data["text"] == CANCER_DISCLAIMER_TEXT

    def test_disclaimer_text_not_empty(self, cancer_client: TestClient) -> None:
        """Disclaimer text should be substantial."""
        resp = cancer_client.get("/api/analysis/cancer/disclaimer")
        data = resp.json()
        assert len(data["text"]) > 500
        assert "cancer" in data["text"].lower()

    def test_disclaimer_covers_predisposition(self, cancer_client: TestClient) -> None:
        """Disclaimer should explain predisposition vs diagnosis."""
        resp = cancer_client.get("/api/analysis/cancer/disclaimer")
        text = resp.json()["text"].lower()
        assert "predisposition" in text
        assert "not mean you have cancer" in text or "does not mean" in text

    def test_disclaimer_covers_chip_limitations(self, cancer_client: TestClient) -> None:
        """Disclaimer should warn about genotyping chip limitations."""
        resp = cancer_client.get("/api/analysis/cancer/disclaimer")
        text = resp.json()["text"].lower()
        assert "genotyping chip" in text or "consumer" in text
        assert "clinical" in text

    def test_disclaimer_covers_prs_limitations(self, cancer_client: TestClient) -> None:
        """Disclaimer should explain PRS is research-grade."""
        resp = cancer_client.get("/api/analysis/cancer/disclaimer")
        text = resp.json()["text"].lower()
        assert "polygenic risk" in text or "prs" in text
        assert "research" in text or "educational" in text

    def test_disclaimer_recommends_professional_guidance(self, cancer_client: TestClient) -> None:
        """Disclaimer should recommend genetic counselor consultation."""
        resp = cancer_client.get("/api/analysis/cancer/disclaimer")
        text = resp.json()["text"].lower()
        assert "genetic counselor" in text or "medical geneticist" in text

    def test_disclaimer_includes_resource_links(self, cancer_client: TestClient) -> None:
        """Disclaimer should include resource URLs."""
        resp = cancer_client.get("/api/analysis/cancer/disclaimer")
        text = resp.json()["text"]
        assert "cancer.gov" in text
        assert "facingourrisk.org" in text
