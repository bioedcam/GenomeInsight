"""Tests for the setup wizard database API (P1-18).

Covers:
- GET /api/databases — list all databases with status
- POST /api/databases/download — trigger parallel downloads
- GET /api/databases/progress/{session_id} — SSE per-database progress
- Database registry helpers
- Edge cases: already downloaded, unknown DB name, empty request
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from backend.api.routes.databases import _active_sessions
from backend.config import Settings
from backend.db.connection import reset_registry
from backend.db.database_registry import (
    DATABASES,
    DatabaseInfo,
    get_all_databases,
    get_database,
    get_database_status,
)
from backend.db.tables import jobs, reference_metadata

# ═══════════════════════════════════════════════════════════════════════
# Test HTTP server for downloads
# ═══════════════════════════════════════════════════════════════════════

TEST_DB_DATA = b"FAKE_DATABASE_CONTENT_" * 100  # ~2.1 KiB


class FakeDBHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler serving test database content."""

    data = TEST_DB_DATA

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.data)))
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()
        self.wfile.write(self.data)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


@pytest.fixture
def fake_db_server():
    """Local HTTP server serving fake database files."""
    server = HTTPServer(("127.0.0.1", 0), FakeDBHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()


def server_url(server: HTTPServer) -> str:
    host, port = server.server_address
    return f"http://{host}:{port}"


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def db_client(tmp_data_dir: Path) -> TestClient:
    """FastAPI TestClient with patched settings for database API tests."""
    settings = Settings(data_dir=tmp_data_dir, wal_mode=False)

    ref_path = settings.reference_db_path
    engine = sa.create_engine(f"sqlite:///{ref_path}")
    reference_metadata.create_all(engine)
    engine.dispose()

    with (
        patch("backend.main.get_settings", return_value=settings),
        patch("backend.db.connection.get_settings", return_value=settings),
        patch("backend.api.routes.databases.get_settings", return_value=settings),
    ):
        reset_registry()

        from backend.main import create_app

        app = create_app()
        with TestClient(app) as tc:
            yield tc

        reset_registry()


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear active sessions between tests."""
    _active_sessions.clear()
    yield
    _active_sessions.clear()


# ═══════════════════════════════════════════════════════════════════════
# Tests: Database Registry
# ═══════════════════════════════════════════════════════════════════════


class TestDatabaseRegistry:
    """Unit tests for the database registry module."""

    def test_get_all_databases_returns_list(self):
        dbs = get_all_databases()
        assert isinstance(dbs, list)
        assert len(dbs) == len(DATABASES)

    def test_get_database_known(self):
        db = get_database("clinvar")
        assert db is not None
        assert db.name == "clinvar"
        assert db.display_name == "ClinVar"
        assert db.required is True

    def test_get_database_unknown(self):
        assert get_database("nonexistent") is None

    def test_all_databases_have_required_fields(self):
        for db in get_all_databases():
            assert db.name
            assert db.display_name
            assert db.description
            assert db.url
            assert db.filename
            assert db.expected_size_bytes > 0

    def test_database_names_match_keys(self):
        for key, db in DATABASES.items():
            assert key == db.name

    def test_get_database_status_not_downloaded(self, tmp_data_dir: Path):
        settings = Settings(data_dir=tmp_data_dir, wal_mode=False)
        db_info = get_database("clinvar")
        assert db_info is not None

        status = get_database_status(db_info, settings)
        assert status["name"] == "clinvar"
        assert status["downloaded"] is False
        assert status["file_size_bytes"] is None

    def test_get_database_status_downloaded(self, tmp_data_dir: Path):
        settings = Settings(data_dir=tmp_data_dir, wal_mode=False)
        db_info = get_database("clinvar")
        assert db_info is not None

        # Create a fake downloaded file
        dest = db_info.dest_path(settings)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake clinvar data")

        status = get_database_status(db_info, settings)
        assert status["downloaded"] is True
        assert status["file_size_bytes"] == len(b"fake clinvar data")

    def test_dest_path(self, tmp_data_dir: Path):
        settings = Settings(data_dir=tmp_data_dir, wal_mode=False)
        db_info = get_database("gnomad")
        assert db_info is not None
        expected = tmp_data_dir / "gnomad_af.db"
        assert db_info.dest_path(settings) == expected


# ═══════════════════════════════════════════════════════════════════════
# Tests: GET /api/databases
# ═══════════════════════════════════════════════════════════════════════


class TestListDatabases:
    """Tests for the GET /api/databases endpoint."""

    def test_list_databases_returns_all(self, db_client: TestClient):
        resp = db_client.get("/api/databases")
        assert resp.status_code == 200

        data = resp.json()
        assert "databases" in data
        assert len(data["databases"]) == len(DATABASES)
        assert data["total_count"] == len(DATABASES)

    def test_list_databases_none_downloaded(self, db_client: TestClient):
        resp = db_client.get("/api/databases")
        data = resp.json()
        assert data["downloaded_count"] == 0

    def test_list_databases_shows_downloaded(self, db_client: TestClient, tmp_data_dir: Path):
        # Create a fake downloaded ClinVar file
        clinvar_path = tmp_data_dir / "clinvar.db"
        clinvar_path.write_bytes(b"fake data")

        resp = db_client.get("/api/databases")
        data = resp.json()
        assert data["downloaded_count"] == 1

        clinvar_status = next(d for d in data["databases"] if d["name"] == "clinvar")
        assert clinvar_status["downloaded"] is True
        assert clinvar_status["file_size_bytes"] == len(b"fake data")

    def test_list_databases_has_total_size(self, db_client: TestClient):
        resp = db_client.get("/api/databases")
        data = resp.json()
        assert data["total_size_bytes"] > 0

    def test_list_databases_fields(self, db_client: TestClient):
        resp = db_client.get("/api/databases")
        db_entry = resp.json()["databases"][0]

        expected_fields = {
            "name",
            "display_name",
            "description",
            "filename",
            "expected_size_bytes",
            "required",
            "phase",
            "downloaded",
            "file_size_bytes",
        }
        assert set(db_entry.keys()) == expected_fields


# ═══════════════════════════════════════════════════════════════════════
# Tests: POST /api/databases/download
# ═══════════════════════════════════════════════════════════════════════


class TestTriggerDownload:
    """Tests for the POST /api/databases/download endpoint."""

    def test_download_unknown_db_returns_400(self, db_client: TestClient):
        resp = db_client.post(
            "/api/databases/download",
            json={"databases": ["nonexistent_db"]},
        )
        assert resp.status_code == 400
        assert "Unknown database" in resp.json()["detail"]

    def test_download_already_downloaded_returns_409(
        self, db_client: TestClient, tmp_data_dir: Path
    ):
        # Mark all required databases as downloaded
        for db in get_all_databases():
            if db.required:
                dest = tmp_data_dir / db.filename
                dest.write_bytes(b"fake")

        resp = db_client.post(
            "/api/databases/download",
            json={"databases": [db.name for db in get_all_databases() if db.required]},
        )
        assert resp.status_code == 409

    def test_download_specific_dbs(
        self,
        db_client: TestClient,
        fake_db_server: HTTPServer,
        tmp_data_dir: Path,
    ):
        url = server_url(fake_db_server)

        # Patch database URLs to point to our test server
        test_db = DatabaseInfo(
            name="clinvar",
            display_name="ClinVar",
            description="Test",
            url=f"{url}/clinvar.db",
            filename="clinvar.db",
            expected_size_bytes=len(TEST_DB_DATA),
        )

        with patch.dict(DATABASES, {"clinvar": test_db}):
            resp = db_client.post(
                "/api/databases/download",
                json={"databases": ["clinvar"]},
            )

        assert resp.status_code == 202
        data = resp.json()
        assert "session_id" in data
        assert len(data["downloads"]) == 1
        assert data["downloads"][0]["db_name"] == "clinvar"
        assert data["downloads"][0]["job_id"].startswith("dbdl-clinvar-")

    def test_download_default_selects_required(
        self,
        db_client: TestClient,
        fake_db_server: HTTPServer,
        tmp_data_dir: Path,
    ):
        url = server_url(fake_db_server)

        # Patch all databases to use test server
        test_dbs = {}
        for name, db in DATABASES.items():
            test_dbs[name] = DatabaseInfo(
                name=db.name,
                display_name=db.display_name,
                description=db.description,
                url=f"{url}/{db.filename}",
                filename=db.filename,
                expected_size_bytes=len(TEST_DB_DATA),
                required=db.required,
                phase=db.phase,
            )

        required_count = sum(1 for db in test_dbs.values() if db.required)

        with patch.dict(DATABASES, test_dbs, clear=True):
            resp = db_client.post(
                "/api/databases/download",
                json={},
            )

        assert resp.status_code == 202
        data = resp.json()
        assert len(data["downloads"]) == required_count

    def test_download_creates_session(
        self,
        db_client: TestClient,
        fake_db_server: HTTPServer,
        tmp_data_dir: Path,
    ):
        url = server_url(fake_db_server)

        test_db = DatabaseInfo(
            name="clinvar",
            display_name="ClinVar",
            description="Test",
            url=f"{url}/clinvar.db",
            filename="clinvar.db",
            expected_size_bytes=len(TEST_DB_DATA),
        )

        with patch.dict(DATABASES, {"clinvar": test_db}):
            resp = db_client.post(
                "/api/databases/download",
                json={"databases": ["clinvar"]},
            )

        session_id = resp.json()["session_id"]
        assert session_id.startswith("dbdl-")

    def test_download_creates_job_records(
        self,
        db_client: TestClient,
        fake_db_server: HTTPServer,
        tmp_data_dir: Path,
    ):
        url = server_url(fake_db_server)

        test_db = DatabaseInfo(
            name="clinvar",
            display_name="ClinVar",
            description="Test",
            url=f"{url}/clinvar.db",
            filename="clinvar.db",
            expected_size_bytes=len(TEST_DB_DATA),
        )

        with patch.dict(DATABASES, {"clinvar": test_db}):
            resp = db_client.post(
                "/api/databases/download",
                json={"databases": ["clinvar"]},
            )

        job_id = resp.json()["downloads"][0]["job_id"]

        # Verify job record exists in the DB
        ref_path = tmp_data_dir / "reference.db"
        engine = sa.create_engine(f"sqlite:///{ref_path}")
        with engine.connect() as conn:
            row = conn.execute(
                sa.select(jobs.c.job_id, jobs.c.job_type).where(jobs.c.job_id == job_id)
            ).fetchone()
        engine.dispose()

        assert row is not None
        assert row.job_type == "database_download"


# ═══════════════════════════════════════════════════════════════════════
# Tests: GET /api/databases/progress/{session_id}
# ═══════════════════════════════════════════════════════════════════════


class TestDownloadProgress:
    """Tests for the SSE progress endpoint."""

    def test_progress_unknown_session_404(self, db_client: TestClient):
        resp = db_client.get("/api/databases/progress/nonexistent-session")
        assert resp.status_code == 404

    def test_progress_stream_format(
        self,
        db_client: TestClient,
        tmp_data_dir: Path,
    ):
        # Create a fake session with a pre-existing completed job
        ref_path = tmp_data_dir / "reference.db"
        engine = sa.create_engine(f"sqlite:///{ref_path}")

        from datetime import UTC, datetime

        with engine.begin() as conn:
            conn.execute(
                jobs.insert().values(
                    job_id="test-job-1",
                    sample_id=None,
                    job_type="database_download",
                    status="complete",
                    progress_pct=100.0,
                    message="Done",
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
        engine.dispose()

        session_id = "test-session-001"
        _active_sessions[session_id] = [("clinvar", "test-job-1")]

        with db_client.stream("GET", f"/api/databases/progress/{session_id}") as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]

            # Read first event
            lines = []
            for line in resp.iter_lines():
                lines.append(line)
                if line == "":
                    break

            # Parse event
            event_line = next(ln for ln in lines if ln.startswith("event:"))
            data_line = next(ln for ln in lines if ln.startswith("data:"))

            assert event_line.strip() == "event: progress"
            payload = json.loads(data_line.split("data: ", 1)[1])
            assert payload["session_id"] == session_id
            assert len(payload["databases"]) == 1
            assert payload["databases"][0]["db_name"] == "clinvar"
            assert payload["databases"][0]["status"] == "complete"

    def test_progress_cleans_up_session(
        self,
        db_client: TestClient,
        tmp_data_dir: Path,
    ):
        # Create a completed job
        ref_path = tmp_data_dir / "reference.db"
        engine = sa.create_engine(f"sqlite:///{ref_path}")

        from datetime import UTC, datetime

        with engine.begin() as conn:
            conn.execute(
                jobs.insert().values(
                    job_id="cleanup-job",
                    sample_id=None,
                    job_type="database_download",
                    status="complete",
                    progress_pct=100.0,
                    message="Done",
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
        engine.dispose()

        session_id = "cleanup-session"
        _active_sessions[session_id] = [("clinvar", "cleanup-job")]

        # Consume the stream — it should terminate since job is complete
        resp = db_client.get(f"/api/databases/progress/{session_id}")
        assert resp.status_code == 200

        # Session should be cleaned up
        assert session_id not in _active_sessions


# ═══════════════════════════════════════════════════════════════════════
# Tests: Integration — download + progress
# ═══════════════════════════════════════════════════════════════════════


class TestDownloadIntegration:
    """Integration tests for the full download + progress flow."""

    def test_full_download_flow(
        self,
        db_client: TestClient,
        fake_db_server: HTTPServer,
        tmp_data_dir: Path,
    ):
        """Start download, wait for completion, verify file exists."""
        url = server_url(fake_db_server)

        test_db = DatabaseInfo(
            name="clinvar",
            display_name="ClinVar",
            description="Test",
            url=f"{url}/clinvar.db",
            filename="clinvar.db",
            expected_size_bytes=len(TEST_DB_DATA),
        )

        with patch.dict(DATABASES, {"clinvar": test_db}, clear=False):
            # Trigger download
            resp = db_client.post(
                "/api/databases/download",
                json={"databases": ["clinvar"]},
            )
            assert resp.status_code == 202

            job_id = resp.json()["downloads"][0]["job_id"]

            # Wait for the download thread to complete (poll job status)
            ref_path = tmp_data_dir / "reference.db"
            engine = sa.create_engine(f"sqlite:///{ref_path}")

            for _ in range(40):  # max 4 seconds
                with engine.connect() as conn:
                    row = conn.execute(
                        sa.select(jobs.c.status).where(jobs.c.job_id == job_id)
                    ).fetchone()
                if row and row.status in ("complete", "failed"):
                    break
                time.sleep(0.1)

            engine.dispose()

            # Verify the file was downloaded to either downloads_dir or data_dir
            downloads_path = tmp_data_dir / "downloads" / "clinvar.db"
            data_path = tmp_data_dir / "clinvar.db"
            assert downloads_path.exists() or data_path.exists()

    def test_download_skips_already_present(
        self,
        db_client: TestClient,
        fake_db_server: HTTPServer,
        tmp_data_dir: Path,
    ):
        """Already-downloaded databases are skipped."""
        url = server_url(fake_db_server)

        # Pre-create clinvar
        (tmp_data_dir / "clinvar.db").write_bytes(b"existing")

        test_dbs = {
            "clinvar": DatabaseInfo(
                name="clinvar",
                display_name="ClinVar",
                description="Test",
                url=f"{url}/clinvar.db",
                filename="clinvar.db",
                expected_size_bytes=len(TEST_DB_DATA),
            ),
            "cpic": DatabaseInfo(
                name="cpic",
                display_name="CPIC",
                description="Test",
                url=f"{url}/cpic.db",
                filename="cpic.db",
                expected_size_bytes=len(TEST_DB_DATA),
            ),
        }

        with patch.dict(DATABASES, test_dbs, clear=True):
            resp = db_client.post(
                "/api/databases/download",
                json={"databases": ["clinvar", "cpic"]},
            )

        assert resp.status_code == 202
        data = resp.json()
        # Only cpic should be downloaded (clinvar already exists)
        assert len(data["downloads"]) == 1
        assert data["downloads"][0]["db_name"] == "cpic"
