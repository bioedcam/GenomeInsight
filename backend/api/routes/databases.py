"""Setup wizard API routes for database management (P1-18).

Endpoints:
    GET  /api/databases          — List all databases with download status
    POST /api/databases/download — Trigger parallel download of selected databases
    GET  /api/databases/progress — SSE stream with per-database progress events
"""

from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import sqlalchemy as sa
import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from backend.api.sse import _format_sse, get_job_progress
from backend.config import get_settings
from backend.db.connection import get_registry
from backend.db.database_registry import (
    DATABASES,
    get_all_databases,
    get_database,
    get_database_status,
)
from backend.db.download_manager import DownloadManager
from backend.db.tables import jobs

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/databases", tags=["databases"])


# ── Response models ──────────────────────────────────────────────────


class DatabaseStatusResponse(BaseModel):
    """Status of a single database."""

    name: str
    display_name: str
    description: str
    filename: str
    expected_size_bytes: int
    required: bool
    phase: int
    downloaded: bool
    file_size_bytes: int | None


class DatabaseListResponse(BaseModel):
    """Response for GET /api/databases."""

    databases: list[DatabaseStatusResponse]
    total_size_bytes: int
    downloaded_count: int
    total_count: int


class DownloadRequest(BaseModel):
    """Request body for POST /api/databases/download."""

    databases: list[str] | None = None  # None = download all required


class DownloadResponse(BaseModel):
    """Response for POST /api/databases/download."""

    session_id: str
    downloads: list[DownloadJobInfo]


class DownloadJobInfo(BaseModel):
    """Info about a single database download job."""

    db_name: str
    job_id: str


# ── Active download sessions ────────────────────────────────────────
# Maps session_id -> list of (db_name, job_id) pairs for SSE progress.

_active_sessions: dict[str, list[tuple[str, str]]] = {}


# ── GET /api/databases ──────────────────────────────────────────────


@router.get("", response_model=DatabaseListResponse)
async def list_databases() -> DatabaseListResponse:
    """List all reference databases with their download status."""
    settings = get_settings()
    all_dbs = get_all_databases()

    statuses = [get_database_status(db, settings) for db in all_dbs]
    downloaded_count = sum(1 for s in statuses if s["downloaded"])
    total_size = sum(db.expected_size_bytes for db in all_dbs)

    return DatabaseListResponse(
        databases=[DatabaseStatusResponse(**s) for s in statuses],
        total_size_bytes=total_size,
        downloaded_count=downloaded_count,
        total_count=len(all_dbs),
    )


# ── POST /api/databases/download ────────────────────────────────────


@router.post("/download", response_model=DownloadResponse, status_code=202)
async def trigger_download(body: DownloadRequest) -> DownloadResponse:
    """Trigger parallel download of selected (or all required) databases.

    Each database is downloaded in its own thread via the DownloadManager.
    A session_id is returned that can be used with the SSE progress endpoint.
    """
    settings = get_settings()
    registry = get_registry()
    engine = registry.reference_engine

    # Determine which databases to download
    if body.databases is not None:
        db_names = body.databases
        # Validate names
        for name in db_names:
            if name not in DATABASES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown database: {name}. "
                    f"Valid names: {', '.join(DATABASES.keys())}",
                )
    else:
        # Default: all required databases
        db_names = [db.name for db in get_all_databases() if db.required]

    # Skip already-downloaded databases
    to_download: list[str] = []
    for name in db_names:
        db_info = get_database(name)
        if db_info is None:
            continue
        dest = db_info.dest_path(settings)
        if not dest.exists():
            to_download.append(name)

    if not to_download:
        raise HTTPException(
            status_code=409,
            detail="All requested databases are already downloaded.",
        )

    # Create session and launch parallel downloads
    session_id = f"dbdl-{uuid.uuid4().hex[:12]}"
    download_jobs: list[DownloadJobInfo] = []
    session_entries: list[tuple[str, str]] = []

    dm = DownloadManager(engine, settings.downloads_dir)
    executor = ThreadPoolExecutor(max_workers=min(len(to_download), 4))

    for name in to_download:
        db_info = get_database(name)
        if db_info is None:
            continue

        job_id = f"dbdl-{name}-{uuid.uuid4().hex[:8]}"

        # Pre-create job record so SSE can find it immediately
        _create_job_record(engine, job_id, name)

        download_jobs.append(DownloadJobInfo(db_name=name, job_id=job_id))
        session_entries.append((name, job_id))

        # Submit download to thread pool
        executor.submit(
            _run_download,
            dm=dm,
            db_info=db_info,
            job_id=job_id,
            engine=engine,
            settings=settings,
        )

    _active_sessions[session_id] = session_entries

    # Don't block — executor threads run in background
    # (ThreadPoolExecutor is not shut down; threads are daemon-like)

    logger.info(
        "database_download_started",
        session_id=session_id,
        databases=to_download,
    )

    return DownloadResponse(
        session_id=session_id,
        downloads=download_jobs,
    )


# ── GET /api/databases/progress ──────────────────────────────────────


@router.get("/progress/{session_id}")
async def download_progress(session_id: str) -> StreamingResponse:
    """SSE stream reporting per-database download progress.

    Emits ``progress`` events with per-database status until all downloads
    in the session reach a terminal state (complete/failed).
    """
    if session_id not in _active_sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    engine = get_registry().reference_engine
    entries = _active_sessions[session_id]

    async def event_stream():
        terminal_states = {"complete", "failed", "cancelled"}
        poll_interval = 0.5

        while True:
            all_terminal = True
            db_statuses: list[dict[str, Any]] = []

            for db_name, job_id in entries:
                status = await asyncio.to_thread(get_job_progress, engine, job_id)
                if status is None:
                    db_statuses.append({
                        "db_name": db_name,
                        "job_id": job_id,
                        "status": "unknown",
                        "progress_pct": 0.0,
                        "message": "Job not found",
                        "error": None,
                    })
                else:
                    db_statuses.append({
                        "db_name": db_name,
                        "job_id": status.job_id,
                        "status": status.status,
                        "progress_pct": status.progress_pct,
                        "message": status.message,
                        "error": status.error,
                    })
                    if status.status not in terminal_states:
                        all_terminal = False

            yield _format_sse("progress", {
                "session_id": session_id,
                "databases": db_statuses,
            })

            if all_terminal:
                # Clean up session
                _active_sessions.pop(session_id, None)
                return

            await asyncio.sleep(poll_interval)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Internal helpers ─────────────────────────────────────────────────


def _create_job_record(engine: sa.Engine, job_id: str, db_name: str) -> None:
    """Create a job record for SSE tracking before download starts."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    with engine.begin() as conn:
        conn.execute(
            jobs.insert().values(
                job_id=job_id,
                sample_id=None,
                job_type="database_download",
                status="pending",
                progress_pct=0.0,
                message=f"Queued download: {db_name}",
                created_at=now,
                updated_at=now,
            )
        )


def _run_download(
    *,
    dm: DownloadManager,
    db_info: Any,
    job_id: str,
    engine: sa.Engine,
    settings: Any,
) -> None:
    """Execute a single database download in a background thread.

    Uses the DownloadManager for resumable HTTP downloads. On success,
    moves the file from downloads_dir to its final location in data_dir.
    """
    try:
        # Update job to running
        msg = f"Downloading {db_info.display_name}..."
        _update_job(engine, job_id, status="running", message=msg)

        result = dm.start(
            url=db_info.url,
            filename=db_info.filename,
            expected_sha256=db_info.sha256,
        )

        if result.error:
            _update_job(
                engine, job_id,
                status="failed",
                progress_pct=0.0,
                error=result.error,
            )
            return

        # Move from downloads dir to final destination
        final_dest = db_info.dest_path(settings)
        if result.dest_path != final_dest:
            final_dest.parent.mkdir(parents=True, exist_ok=True)
            result.dest_path.replace(final_dest)

        _update_job(
            engine, job_id,
            status="complete",
            progress_pct=100.0,
            message=f"{db_info.display_name} download complete",
        )

        logger.info(
            "database_download_complete",
            db_name=db_info.name,
            job_id=job_id,
            dest=str(final_dest),
        )

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        _update_job(
            engine, job_id,
            status="failed",
            progress_pct=0.0,
            error=error_msg,
        )
        logger.exception(
            "database_download_failed",
            db_name=db_info.name,
            job_id=job_id,
            error=error_msg,
        )


def _update_job(
    engine: sa.Engine,
    job_id: str,
    *,
    status: str,
    progress_pct: float = 0.0,
    message: str = "",
    error: str | None = None,
) -> None:
    """Update a job record."""
    from datetime import UTC, datetime

    with engine.begin() as conn:
        conn.execute(
            jobs.update()
            .where(jobs.c.job_id == job_id)
            .values(
                status=status,
                progress_pct=progress_pct,
                message=message,
                error=error,
                updated_at=datetime.now(UTC),
            )
        )
