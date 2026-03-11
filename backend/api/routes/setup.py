"""Setup wizard API routes (P1-19a).

Endpoints:
    GET  /api/setup/status             — Check first-launch state and disclaimer acceptance
    POST /api/setup/accept-disclaimer  — Record global disclaimer acceptance
    GET  /api/setup/disclaimer         — Get disclaimer text
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import structlog
from fastapi import APIRouter
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


def _get_disk_space(path: Path) -> dict[str, int]:
    """Get disk space info for the given path."""
    try:
        usage = shutil.disk_usage(str(path))
        return {"total": usage.total, "free": usage.free, "used": usage.used}
    except OSError:
        return {"total": 0, "free": 0, "used": 0}


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
