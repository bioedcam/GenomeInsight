"""Tests for the FastAPI app skeleton (P1-05).

Covers:
- T1-07: /api/health endpoint
- CORS configuration
- SSE infrastructure (get_job_progress, _format_sse, job_progress_stream)
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.db.tables import jobs, reference_metadata

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def ref_engine(tmp_path):
    """SQLAlchemy engine for a temporary reference.db with tables created."""
    db_path = tmp_path / "reference.db"
    engine = sa.create_engine(f"sqlite:///{db_path}")
    reference_metadata.create_all(engine)
    return engine


@pytest.fixture()
def client(tmp_path):
    """FastAPI test client with temporary database."""
    # Create reference.db with tables
    db_path = tmp_path / "reference.db"
    engine = sa.create_engine(f"sqlite:///{db_path}")
    reference_metadata.create_all(engine)
    engine.dispose()

    test_settings = Settings(data_dir=tmp_path)

    with patch("backend.main.get_settings", return_value=test_settings), patch(
        "backend.db.connection.get_settings", return_value=test_settings
    ):
        # Reset the singleton so it picks up test settings
        from backend.db.connection import reset_registry

        reset_registry()

        from backend.main import create_app

        app = create_app()
        with TestClient(app) as tc:
            yield tc

        reset_registry()


# ── T1-07: Health Endpoint Tests ──────────────────────────────────────


class TestHealthEndpoint:
    """T1-07: FastAPI /api/health returns 200 with version info."""

    def test_health_returns_200(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_returns_status_ok(self, client):
        response = client.get("/api/health")
        data = response.json()
        assert data["status"] == "ok"

    def test_health_returns_version(self, client):
        response = client.get("/api/health")
        data = response.json()
        assert "version" in data
        assert data["version"]  # non-empty

    def test_health_version_matches_module(self, client):
        from backend.main import VERSION

        response = client.get("/api/health")
        data = response.json()
        assert data["version"] == VERSION


# ── CORS Tests ────────────────────────────────────────────────────────


class TestCORS:
    """CORS configured for localhost only."""

    def test_cors_allows_localhost_5173(self, client):
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

    def test_cors_allows_localhost_8000(self, client):
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:8000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") == "http://localhost:8000"

    def test_cors_allows_127_0_0_1_5173(self, client):
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"

    def test_cors_blocks_external_origin(self, client):
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in response.headers


# ── SSE Infrastructure Tests ──────────────────────────────────────────


class TestSSEInfrastructure:
    """SSE job progress polling -- testable boundary."""

    def test_get_job_progress_returns_none_for_missing(self, ref_engine):
        from backend.api.sse import get_job_progress

        result = get_job_progress(ref_engine, "nonexistent")
        assert result is None

    def test_get_job_progress_returns_status(self, ref_engine):
        from backend.api.sse import get_job_progress

        with ref_engine.connect() as conn:
            conn.execute(
                jobs.insert().values(
                    job_id="test-job-1",
                    job_type="annotation",
                    status="running",
                    progress_pct=50.0,
                    message="Processing variants",
                )
            )
            conn.commit()

        result = get_job_progress(ref_engine, "test-job-1")
        assert result is not None
        assert result.job_id == "test-job-1"
        assert result.status == "running"
        assert result.progress_pct == 50.0
        assert result.message == "Processing variants"
        assert result.error is None

    def test_get_job_progress_handles_pending(self, ref_engine):
        from backend.api.sse import get_job_progress

        with ref_engine.connect() as conn:
            conn.execute(
                jobs.insert().values(
                    job_id="pending-job",
                    job_type="download",
                )
            )
            conn.commit()

        result = get_job_progress(ref_engine, "pending-job")
        assert result is not None
        assert result.job_id == "pending-job"
        assert result.status == "pending"
        assert result.progress_pct == 0.0
        assert result.message == ""
        assert result.error is None

    def test_format_sse(self):
        from backend.api.sse import _format_sse

        result = _format_sse("progress", {"status": "running"})
        assert result.startswith("event: progress\n")
        assert "data:" in result
        assert result.endswith("\n\n")

        # Verify the data line contains valid JSON
        lines = result.strip().split("\n")
        data_line = next(line for line in lines if line.startswith("data:"))
        payload = json.loads(data_line.removeprefix("data:").strip())
        assert payload["status"] == "running"

    def test_format_sse_event_name(self):
        from backend.api.sse import _format_sse

        result = _format_sse("error", {"message": "something went wrong"})
        assert result.startswith("event: error\n")
        payload = json.loads(result.split("\n")[1].removeprefix("data:").strip())
        assert payload["message"] == "something went wrong"

    @pytest.mark.asyncio
    async def test_job_progress_stream_terminates_on_complete(self, ref_engine):
        from backend.api.sse import job_progress_stream

        with ref_engine.connect() as conn:
            conn.execute(
                jobs.insert().values(
                    job_id="done-job",
                    job_type="annotation",
                    status="complete",
                    progress_pct=100.0,
                    message="Done",
                )
            )
            conn.commit()

        events = []
        async for event in job_progress_stream(ref_engine, "done-job", poll_interval=0.01):
            events.append(event)

        # Should yield exactly one progress event then terminate
        assert len(events) == 1
        assert "complete" in events[0]
        assert events[0].startswith("event: progress\n")

    @pytest.mark.asyncio
    async def test_job_progress_stream_terminates_on_failed(self, ref_engine):
        from backend.api.sse import job_progress_stream

        with ref_engine.connect() as conn:
            conn.execute(
                jobs.insert().values(
                    job_id="failed-job",
                    job_type="annotation",
                    status="failed",
                    progress_pct=30.0,
                    message="Annotation failed",
                    error="File not found",
                )
            )
            conn.commit()

        events = []
        async for event in job_progress_stream(ref_engine, "failed-job", poll_interval=0.01):
            events.append(event)

        assert len(events) == 1
        payload = json.loads(events[0].split("\n")[1].removeprefix("data:").strip())
        assert payload["status"] == "failed"
        assert payload["error"] == "File not found"

    @pytest.mark.asyncio
    async def test_job_progress_stream_not_found(self, ref_engine):
        from backend.api.sse import job_progress_stream

        events = []
        async for event in job_progress_stream(ref_engine, "no-such-job", poll_interval=0.01):
            events.append(event)

        # Should yield a single error event
        assert len(events) == 1
        assert events[0].startswith("event: error\n")
        assert "not found" in events[0]

    @pytest.mark.asyncio
    async def test_job_progress_stream_polls_until_terminal(self, ref_engine):
        from backend.api.sse import job_progress_stream

        # Insert a running job
        with ref_engine.connect() as conn:
            conn.execute(
                jobs.insert().values(
                    job_id="evolving-job",
                    job_type="annotation",
                    status="running",
                    progress_pct=10.0,
                    message="Starting",
                )
            )
            conn.commit()

        events = []
        poll_count = 0
        async for event in job_progress_stream(ref_engine, "evolving-job", poll_interval=0.01):
            events.append(event)
            poll_count += 1

            # After the first poll, update to complete so the stream terminates
            if poll_count == 1:
                with ref_engine.connect() as conn:
                    conn.execute(
                        jobs.update()
                        .where(jobs.c.job_id == "evolving-job")
                        .values(status="complete", progress_pct=100.0, message="Done")
                    )
                    conn.commit()

        # Should have at least 2 events: one running, one complete
        assert len(events) == 2
        first = json.loads(events[0].split("\n")[1].removeprefix("data:").strip())
        last = json.loads(events[1].split("\n")[1].removeprefix("data:").strip())
        assert first["status"] == "running"
        assert last["status"] == "complete"
