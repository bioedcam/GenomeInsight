"""Setup wizard API routes (P1-19a, P1-19b).

Endpoints:
    GET  /api/setup/status             — Check first-launch state and disclaimer acceptance
    POST /api/setup/accept-disclaimer  — Record global disclaimer acceptance
    GET  /api/setup/disclaimer         — Get disclaimer text
    GET  /api/setup/detect-existing    — Auto-detect existing installation
    POST /api/setup/import-backup      — Import from .tar.gz backup archive
"""

from __future__ import annotations

import json
import shutil
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import structlog
from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from backend.config import get_settings
from backend.disclaimers import (
    GLOBAL_DISCLAIMER_ACCEPT_LABEL,
    GLOBAL_DISCLAIMER_TEXT,
    GLOBAL_DISCLAIMER_TITLE,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/setup", tags=["setup"])

# ── Response models ──────────────────────────────────────────────────


class SetupStatusResponse(BaseModel):
    """Current setup status — determines whether wizard should be shown."""

    needs_setup: bool
    disclaimer_accepted: bool
    has_databases: bool
    has_samples: bool
    data_dir: str


class DisclaimerResponse(BaseModel):
    """Global disclaimer text for the setup wizard."""

    title: str
    text: str
    accept_label: str


class AcceptDisclaimerResponse(BaseModel):
    """Confirmation of disclaimer acceptance."""

    accepted: bool
    accepted_at: str


class DetectExistingResponse(BaseModel):
    """Result of auto-detecting an existing installation."""

    existing_found: bool
    has_config: bool
    has_samples: bool
    has_databases: bool
    data_dir: str


class ImportBackupResponse(BaseModel):
    """Result of importing a backup archive."""

    success: bool
    samples_restored: int
    config_restored: bool
    message: str


# ── Helpers ──────────────────────────────────────────────────────────


def _disclaimer_flag_path() -> Path:
    """Path to the disclaimer acceptance flag file."""
    settings = get_settings()
    return settings.data_dir / ".disclaimer_accepted"


def _is_disclaimer_accepted() -> bool:
    """Check if the global disclaimer has been accepted."""
    return _disclaimer_flag_path().exists()


def _has_any_databases() -> bool:
    """Check if any reference databases have been downloaded."""
    settings = get_settings()
    db_files = [
        settings.data_dir / "clinvar.db",
        settings.data_dir / "vep_bundle.db",
        settings.data_dir / "gnomad_af.db",
        settings.data_dir / "dbnsfp.db",
    ]
    return any(f.exists() for f in db_files)


def _has_any_samples() -> bool:
    """Check if any sample databases exist."""
    settings = get_settings()
    samples_dir = settings.samples_dir
    if not samples_dir.exists():
        return False
    return any(samples_dir.glob("sample_*.db"))


# ── GET /api/setup/status ────────────────────────────────────────────


@router.get("/status", response_model=SetupStatusResponse)
async def setup_status() -> SetupStatusResponse:
    """Check the current setup status.

    Returns whether the app needs first-run setup, including
    disclaimer acceptance state, database availability, and sample presence.
    """
    settings = get_settings()
    disclaimer_accepted = _is_disclaimer_accepted()
    has_dbs = _has_any_databases()
    has_samples = _has_any_samples()

    # Needs setup if disclaimer not accepted OR no databases downloaded
    needs_setup = not disclaimer_accepted or not has_dbs

    return SetupStatusResponse(
        needs_setup=needs_setup,
        disclaimer_accepted=disclaimer_accepted,
        has_databases=has_dbs,
        has_samples=has_samples,
        data_dir=str(settings.data_dir),
    )


# ── GET /api/setup/disclaimer ────────────────────────────────────────


@router.get("/disclaimer", response_model=DisclaimerResponse)
async def get_disclaimer() -> DisclaimerResponse:
    """Get the global disclaimer text."""
    return DisclaimerResponse(
        title=GLOBAL_DISCLAIMER_TITLE,
        text=GLOBAL_DISCLAIMER_TEXT,
        accept_label=GLOBAL_DISCLAIMER_ACCEPT_LABEL,
    )


# ── POST /api/setup/accept-disclaimer ────────────────────────────────


@router.post("/accept-disclaimer", response_model=AcceptDisclaimerResponse)
async def accept_disclaimer() -> AcceptDisclaimerResponse:
    """Record that the user has accepted the global disclaimer.

    Creates a flag file in the data directory. This is checked on every
    app launch to determine whether to show the setup wizard.
    """
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    flag_path = _disclaimer_flag_path()
    accepted_at = datetime.now(UTC).isoformat()

    flag_path.write_text(
        json.dumps({"accepted_at": accepted_at, "version": "1.0"}),
        encoding="utf-8",
    )

    logger.info("global_disclaimer_accepted", accepted_at=accepted_at)

    return AcceptDisclaimerResponse(accepted=True, accepted_at=accepted_at)


# ── GET /api/setup/detect-existing ────────────────────────────────


@router.get("/detect-existing", response_model=DetectExistingResponse)
async def detect_existing() -> DetectExistingResponse:
    """Auto-detect an existing GenomeInsight installation.

    Checks if ~/.genomeinsight/ already has data (config.toml, samples, DBs).
    If config.toml exists but DBs are missing, the frontend should resume
    the wizard at the download step.
    """
    settings = get_settings()
    data_dir = settings.data_dir

    has_config = (data_dir / "config.toml").exists()
    has_samples = _has_any_samples()
    has_dbs = _has_any_databases()
    existing_found = has_config or has_samples or has_dbs

    return DetectExistingResponse(
        existing_found=existing_found,
        has_config=has_config,
        has_samples=has_samples,
        has_databases=has_dbs,
        data_dir=str(data_dir),
    )


# ── POST /api/setup/import-backup ─────────────────────────────────

# Max upload size: 5 GB (sample DBs can be large)
_MAX_BACKUP_SIZE = 5 * 1024 * 1024 * 1024

# Allowed top-level entries in a valid backup archive
_ALLOWED_ARCHIVE_ENTRIES = {"config.toml", "samples", ".disclaimer_accepted"}


def _validate_tar_member(member: tarfile.TarInfo) -> bool:
    """Validate a tar member is safe to extract (no path traversal)."""
    # Reject absolute paths
    if member.name.startswith("/") or member.name.startswith(".."):
        return False
    # Reject path traversal
    if ".." in member.name.split("/"):
        return False
    # Reject symlinks and hardlinks
    if member.issym() or member.islnk():
        return False
    # Reject device files
    if member.isdev():
        return False
    return True


def _validate_archive_structure(tf: tarfile.TarFile) -> list[str]:
    """Validate archive has expected structure. Return list of issues."""
    issues: list[str] = []
    members = tf.getmembers()

    if not members:
        issues.append("Archive is empty")
        return issues

    has_samples = False
    for member in members:
        if not _validate_tar_member(member):
            issues.append(f"Unsafe entry: {member.name}")
            continue

        # Check top-level entry is allowed
        top_level = member.name.split("/")[0]
        if top_level not in _ALLOWED_ARCHIVE_ENTRIES:
            issues.append(f"Unexpected entry: {top_level}")

        if top_level == "samples":
            has_samples = True

    if not has_samples:
        issues.append("Archive does not contain a 'samples' directory")

    return issues


@router.post("/import-backup", response_model=ImportBackupResponse)
async def import_backup(file: UploadFile) -> ImportBackupResponse:
    """Import data from a .tar.gz backup archive.

    Accepts a .tar.gz file containing:
    - samples/ directory with sample_*.db files
    - config.toml (optional)
    - .disclaimer_accepted (optional)

    Extracts contents to the data directory. Reference DBs are NOT expected
    in the archive — they will be re-downloaded in a later wizard step.
    """
    settings = get_settings()
    data_dir = settings.data_dir

    # Validate file type
    if not file.filename or not file.filename.endswith((".tar.gz", ".tgz")):
        raise HTTPException(
            status_code=400,
            detail="File must be a .tar.gz or .tgz archive.",
        )

    # Save uploaded file to temp location
    data_dir.mkdir(parents=True, exist_ok=True)
    tmp_archive = data_dir / ".import_backup_tmp.tar.gz"

    try:
        # Stream upload to disk to avoid memory issues
        total_written = 0
        with tmp_archive.open("wb") as f:
            while chunk := await file.read(64 * 1024):
                total_written += len(chunk)
                if total_written > _MAX_BACKUP_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="Archive exceeds maximum size of 5 GB.",
                    )
                f.write(chunk)

        if total_written == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # Validate archive
        try:
            with tarfile.open(tmp_archive, "r:gz") as tf:
                issues = _validate_archive_structure(tf)
                if issues:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid backup archive: {'; '.join(issues)}",
                    )

                # Extract safe members
                samples_restored = 0
                config_restored = False

                for member in tf.getmembers():
                    if not _validate_tar_member(member):
                        continue

                    top_level = member.name.split("/")[0]
                    if top_level not in _ALLOWED_ARCHIVE_ENTRIES:
                        continue

                    dest = data_dir / member.name
                    if member.isdir():
                        dest.mkdir(parents=True, exist_ok=True)
                    elif member.isfile():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        src = tf.extractfile(member)
                        if src is not None:
                            with dest.open("wb") as out:
                                shutil.copyfileobj(src, out)

                            if top_level == "samples" and member.name.endswith(".db"):
                                samples_restored += 1
                            elif member.name == "config.toml":
                                config_restored = True

        except tarfile.TarError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to read archive: {exc}",
            ) from exc

        logger.info(
            "backup_imported",
            samples_restored=samples_restored,
            config_restored=config_restored,
        )

        return ImportBackupResponse(
            success=True,
            samples_restored=samples_restored,
            config_restored=config_restored,
            message=f"Restored {samples_restored} sample(s)"
            + (" and configuration" if config_restored else "")
            + ".",
        )

    finally:
        # Clean up temp file
        if tmp_archive.exists():
            tmp_archive.unlink()
