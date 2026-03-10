"""Resumable HTTP download manager with SHA-256 verification and SSE progress.

Downloads large database files using HTTP Range requests so interrupted
transfers can resume from the last checkpointed byte offset. Progress is
tracked in the ``downloads`` and ``jobs`` tables in reference.db, enabling
SSE streaming to the frontend via the existing job progress infrastructure.

Usage::

    from backend.db.download_manager import DownloadManager

    dm = DownloadManager(reference_engine, downloads_dir)
    job_id = dm.start("https://example.com/big.db", "big.db",
                       expected_sha256="abc123...")
    # Poll job_id via SSE for progress.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import sqlalchemy as sa
import structlog

from backend.db.tables import downloads, jobs

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)

# How often to flush byte-offset to the downloads table (bytes).
CHECKPOINT_INTERVAL = 1_048_576  # 1 MiB

# Default chunk size for streaming reads.
CHUNK_SIZE = 65_536  # 64 KiB

# Default HTTP timeout (connect / total).
DEFAULT_CONNECT_TIMEOUT = 30.0
DEFAULT_TOTAL_TIMEOUT = 3600.0  # 1 hour for large files


@dataclass
class DownloadResult:
    """Outcome of a completed (or failed) download."""

    download_id: int
    job_id: str
    dest_path: Path
    total_bytes: int
    sha256: str | None = None
    verified: bool = False
    error: str | None = None


class DownloadError(Exception):
    """Raised when a download fails irrecoverably."""


class ChecksumMismatchError(DownloadError):
    """Raised when the SHA-256 of the downloaded file doesn't match."""


class DownloadManager:
    """Manages resumable file downloads with progress tracking.

    Each download creates a row in the ``downloads`` table (byte-offset
    checkpoint) and a corresponding row in the ``jobs`` table (SSE-visible
    progress).  If a download is interrupted, calling :meth:`resume` with
    the same ``download_id`` picks up from the last checkpoint.

    Args:
        engine: SQLAlchemy engine for reference.db.
        downloads_dir: Directory where downloaded files are stored.
    """

    def __init__(self, engine: sa.Engine, downloads_dir: Path) -> None:
        self._engine = engine
        self._downloads_dir = downloads_dir
        self._downloads_dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ────────────────────────────────────────────────────

    def start(
        self,
        url: str,
        filename: str,
        *,
        expected_sha256: str | None = None,
        progress_callback: Callable[[int, int | None], None] | None = None,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        total_timeout: float = DEFAULT_TOTAL_TIMEOUT,
    ) -> DownloadResult:
        """Start a new download (or resume if a pending record exists).

        Args:
            url: Remote URL to download.
            filename: Local filename (relative to downloads_dir).
            expected_sha256: Optional expected SHA-256 hex digest.
            progress_callback: Called with ``(downloaded_bytes, total_bytes)``.
            connect_timeout: HTTP connect timeout in seconds.
            total_timeout: HTTP total timeout in seconds.

        Returns:
            DownloadResult describing the outcome.
        """
        dest_path = self._downloads_dir / filename
        job_id = f"dl-{uuid.uuid4().hex[:12]}"

        # Check for an existing incomplete download of the same URL+dest
        existing = self._find_resumable(url, str(dest_path))
        if existing is not None:
            download_id, downloaded_bytes = existing
            logger.info(
                "download_resume_existing",
                download_id=download_id,
                url=url,
                offset=downloaded_bytes,
            )
        else:
            download_id = self._create_download_record(
                url=url,
                dest_path=str(dest_path),
                expected_sha256=expected_sha256,
            )
            downloaded_bytes = 0

        # Create job for SSE progress tracking
        self._create_job(job_id, download_id)

        return self._execute_download(
            download_id=download_id,
            job_id=job_id,
            url=url,
            dest_path=dest_path,
            offset=downloaded_bytes,
            expected_sha256=expected_sha256,
            progress_callback=progress_callback,
            connect_timeout=connect_timeout,
            total_timeout=total_timeout,
        )

    def resume(
        self,
        download_id: int,
        *,
        progress_callback: Callable[[int, int | None], None] | None = None,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        total_timeout: float = DEFAULT_TOTAL_TIMEOUT,
    ) -> DownloadResult:
        """Resume an interrupted download by its ID.

        Args:
            download_id: Primary key in the downloads table.
            progress_callback: Called with ``(downloaded_bytes, total_bytes)``.
            connect_timeout: HTTP connect timeout in seconds.
            total_timeout: HTTP total timeout in seconds.

        Returns:
            DownloadResult describing the outcome.

        Raises:
            DownloadError: If the download record is not found or already complete.
        """
        record = self._get_download_record(download_id)
        if record is None:
            raise DownloadError(f"Download {download_id} not found")
        if record["status"] == "complete":
            raise DownloadError(f"Download {download_id} is already complete")

        job_id = f"dl-{uuid.uuid4().hex[:12]}"
        self._create_job(job_id, download_id)

        logger.info(
            "download_resume",
            download_id=download_id,
            url=record["url"],
            offset=record["downloaded_bytes"],
        )

        return self._execute_download(
            download_id=download_id,
            job_id=job_id,
            url=record["url"],
            dest_path=Path(record["dest_path"]),
            offset=record["downloaded_bytes"] or 0,
            expected_sha256=record["checksum_sha256"],
            progress_callback=progress_callback,
            connect_timeout=connect_timeout,
            total_timeout=total_timeout,
        )

    def get_status(self, download_id: int) -> dict | None:
        """Return current status of a download record, or None."""
        return self._get_download_record(download_id)

    # ── Internal: download execution ──────────────────────────────────

    def _execute_download(
        self,
        *,
        download_id: int,
        job_id: str,
        url: str,
        dest_path: Path,
        offset: int,
        expected_sha256: str | None,
        progress_callback: Callable[[int, int | None], None] | None,
        connect_timeout: float,
        total_timeout: float,
    ) -> DownloadResult:
        """Core download loop with Range resume, checkpointing, and verification."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")

        # Update status to downloading
        self._update_download_status(download_id, "downloading")
        self._update_job(job_id, status="running", progress_pct=0.0, message="Starting download")

        headers: dict[str, str] = {}
        if offset > 0 and tmp_path.exists():
            headers["Range"] = f"bytes={offset}-"
        else:
            # No valid partial file — start fresh
            offset = 0

        current_offset = offset

        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=httpx.Timeout(total_timeout, connect=connect_timeout),
            ) as client:
                with client.stream("GET", url, headers=headers) as response:
                    # Handle range response
                    if response.status_code == 206:
                        # Partial content — server supports Range
                        total_bytes = self._parse_content_range_total(response)
                    elif response.status_code == 200:
                        # Full content — server ignored Range or fresh start
                        offset = 0
                        content_length = response.headers.get("Content-Length")
                        total_bytes = int(content_length) if content_length else None
                    else:
                        response.raise_for_status()
                        total_bytes = None  # unreachable but keeps type checker happy

                    # Update total_bytes in downloads table
                    if total_bytes is not None:
                        self._update_total_bytes(download_id, total_bytes)

                    # Open file in append or write mode
                    mode = "ab" if offset > 0 else "wb"
                    bytes_since_checkpoint = 0
                    current_offset = offset

                    with open(tmp_path, mode) as f:
                        for chunk in response.iter_bytes(chunk_size=CHUNK_SIZE):
                            f.write(chunk)
                            current_offset += len(chunk)
                            bytes_since_checkpoint += len(chunk)

                            # Progress callback
                            if progress_callback:
                                progress_callback(current_offset, total_bytes)

                            # Update job progress for SSE
                            if total_bytes and total_bytes > 0:
                                pct = min(
                                    (current_offset / total_bytes) * 100.0, 99.9
                                )
                                self._update_job(
                                    job_id,
                                    status="running",
                                    progress_pct=pct,
                                    message=f"{current_offset:,} / {total_bytes:,} bytes",
                                )

                            # Checkpoint byte offset periodically
                            if bytes_since_checkpoint >= CHECKPOINT_INTERVAL:
                                self._checkpoint_offset(download_id, current_offset)
                                bytes_since_checkpoint = 0

                    # Final checkpoint
                    self._checkpoint_offset(download_id, current_offset)

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            self._update_download_status(download_id, "failed")
            self._update_job(job_id, status="failed", progress_pct=0.0, error=error_msg)
            logger.exception("download_failed", download_id=download_id, url=url, error=error_msg)
            return DownloadResult(
                download_id=download_id,
                job_id=job_id,
                dest_path=dest_path,
                total_bytes=current_offset,
                error=error_msg,
            )

        # SHA-256 verification
        sha256 = _compute_sha256(tmp_path)
        verified = True
        if expected_sha256 and sha256 != expected_sha256:
            error_msg = (
                f"SHA-256 mismatch: expected {expected_sha256}, got {sha256}"
            )
            self._update_download_status(download_id, "failed")
            self._update_job(job_id, status="failed", progress_pct=100.0, error=error_msg)
            tmp_path.unlink(missing_ok=True)
            logger.error("download_checksum_mismatch", download_id=download_id, url=url)
            raise ChecksumMismatchError(error_msg)

        # Atomic rename on success
        tmp_path.replace(dest_path)

        # Mark complete
        self._update_download_status(download_id, "complete")
        self._update_job(
            job_id,
            status="complete",
            progress_pct=100.0,
            message="Download complete",
        )

        logger.info(
            "download_complete",
            download_id=download_id,
            dest=str(dest_path),
            bytes=current_offset,
            sha256=sha256,
        )

        return DownloadResult(
            download_id=download_id,
            job_id=job_id,
            dest_path=dest_path,
            total_bytes=current_offset,
            sha256=sha256,
            verified=verified,
        )

    @staticmethod
    def _parse_content_range_total(response: httpx.Response) -> int | None:
        """Parse total size from Content-Range header (e.g. ``bytes 100-999/5000``)."""
        cr = response.headers.get("Content-Range", "")
        if "/" in cr:
            total_str = cr.rsplit("/", 1)[1].strip()
            if total_str != "*":
                try:
                    return int(total_str)
                except ValueError:
                    pass
        # Fall back to Content-Length if available
        cl = response.headers.get("Content-Length")
        return int(cl) if cl else None

    # ── Internal: database helpers ────────────────────────────────────

    def _create_download_record(
        self, *, url: str, dest_path: str, expected_sha256: str | None
    ) -> int:
        """Insert a new row into the downloads table and return its ID."""
        now = datetime.now(UTC)
        with self._engine.begin() as conn:
            result = conn.execute(
                downloads.insert().values(
                    url=url,
                    dest_path=dest_path,
                    total_bytes=None,
                    downloaded_bytes=0,
                    checksum_sha256=expected_sha256,
                    status="pending",
                    created_at=now,
                    updated_at=now,
                )
            )
            return result.lastrowid  # type: ignore[return-value]

    def _find_resumable(self, url: str, dest_path: str) -> tuple[int, int] | None:
        """Find an incomplete download for the same URL + dest_path.

        Returns ``(download_id, downloaded_bytes)`` or None.
        """
        with self._engine.connect() as conn:
            row = conn.execute(
                sa.select(downloads.c.id, downloads.c.downloaded_bytes)
                .where(
                    downloads.c.url == url,
                    downloads.c.dest_path == dest_path,
                    downloads.c.status.in_(["pending", "downloading", "failed"]),
                )
                .order_by(downloads.c.created_at.desc())
                .limit(1)
            ).fetchone()
        if row is None:
            return None
        return (row.id, row.downloaded_bytes or 0)

    def _get_download_record(self, download_id: int) -> dict | None:
        """Fetch a download record as a dict."""
        with self._engine.connect() as conn:
            row = conn.execute(
                sa.select(
                    downloads.c.id,
                    downloads.c.url,
                    downloads.c.dest_path,
                    downloads.c.total_bytes,
                    downloads.c.downloaded_bytes,
                    downloads.c.checksum_sha256,
                    downloads.c.status,
                    downloads.c.created_at,
                    downloads.c.updated_at,
                ).where(downloads.c.id == download_id)
            ).fetchone()
        if row is None:
            return None
        return row._asdict()

    def _update_download_status(self, download_id: int, status: str) -> None:
        """Update the status field of a download record."""
        with self._engine.begin() as conn:
            conn.execute(
                downloads.update()
                .where(downloads.c.id == download_id)
                .values(status=status, updated_at=datetime.now(UTC))
            )

    def _update_total_bytes(self, download_id: int, total_bytes: int) -> None:
        """Set the total_bytes for a download record."""
        with self._engine.begin() as conn:
            conn.execute(
                downloads.update()
                .where(downloads.c.id == download_id)
                .values(total_bytes=total_bytes, updated_at=datetime.now(UTC))
            )

    def _checkpoint_offset(self, download_id: int, offset: int) -> None:
        """Persist the current byte offset to the downloads table."""
        with self._engine.begin() as conn:
            conn.execute(
                downloads.update()
                .where(downloads.c.id == download_id)
                .values(downloaded_bytes=offset, updated_at=datetime.now(UTC))
            )

    def _create_job(self, job_id: str, download_id: int) -> None:
        """Create a job record for SSE progress tracking."""
        now = datetime.now(UTC)
        with self._engine.begin() as conn:
            conn.execute(
                jobs.insert().values(
                    job_id=job_id,
                    sample_id=None,
                    job_type="download",
                    status="pending",
                    progress_pct=0.0,
                    message=f"Download #{download_id} queued",
                    created_at=now,
                    updated_at=now,
                )
            )

    def _update_job(
        self,
        job_id: str,
        *,
        status: str,
        progress_pct: float,
        message: str = "",
        error: str | None = None,
    ) -> None:
        """Update job progress for SSE visibility."""
        with self._engine.begin() as conn:
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


def _compute_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65_536), b""):
            h.update(chunk)
    return h.hexdigest()
