"""Update manager API routes (P4-16, P4-21d).

Endpoints for checking database updates, triggering updates,
viewing update history, managing re-annotation prompts,
and checking for app updates via GitHub Releases API.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db.connection import get_registry
from backend.db.database_registry import DATABASES
from backend.db.update_manager import (
    AUTO_UPDATE_DEFAULTS,
    check_all_updates,
    dismiss_prompt,
    format_version_display,
    get_active_prompts,
    get_all_version_stamps,
    get_update_history,
    should_download_now,
)

router = APIRouter(prefix="/updates", tags=["updates"])


# ── Response models ──────────────────────────────────────────────────


class UpdateAvailable(BaseModel):
    db_name: str
    latest_version: str
    download_size_bytes: int
    release_date: str | None = None


class UpdateCheckResponse(BaseModel):
    available: list[UpdateAvailable]
    up_to_date: list[str]
    errors: list[str]
    checked_at: str


class UpdateHistoryEntry(BaseModel):
    id: int
    db_name: str
    previous_version: str | None
    new_version: str
    updated_at: str | None
    variants_added: int | None
    variants_reclassified: int | None
    download_size_bytes: int | None
    duration_seconds: int | None


class ReannotationPrompt(BaseModel):
    id: int
    sample_id: int
    db_name: str
    db_version: str
    candidate_count: int
    created_at: str | None


class DatabaseStatus(BaseModel):
    db_name: str
    display_name: str
    current_version: str | None
    version_display: str | None
    downloaded_at: str | None
    auto_update: bool
    update_available: bool


class TriggerUpdateRequest(BaseModel):
    db_name: str


class TriggerUpdateResponse(BaseModel):
    job_id: str
    db_name: str
    message: str


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("/check", response_model=UpdateCheckResponse)
async def check_for_updates() -> UpdateCheckResponse:
    """Check all databases for available updates."""
    registry = get_registry()
    result = check_all_updates(registry.reference_engine)

    return UpdateCheckResponse(
        available=[
            UpdateAvailable(
                db_name=v.db_name,
                latest_version=v.latest_version,
                download_size_bytes=v.download_size_bytes,
                release_date=v.release_date,
            )
            for v in result.available
        ],
        up_to_date=result.up_to_date,
        errors=result.errors,
        checked_at=result.checked_at.isoformat(),
    )


@router.post("/trigger", response_model=TriggerUpdateResponse, status_code=202)
async def trigger_update(req: TriggerUpdateRequest) -> TriggerUpdateResponse:
    """Trigger an update for a specific database.

    Enqueues the update as a background Huey task and returns
    the job_id for progress tracking via SSE.
    """
    from backend.tasks.huey_tasks import (
        create_database_update_job,
        run_database_update_task,
    )

    supported = {"clinvar"}
    if req.db_name not in supported:
        raise HTTPException(
            status_code=400,
            detail=f"Update not supported for '{req.db_name}'. Supported: {sorted(supported)}",
        )

    # Check bandwidth window — look up actual expected download size
    registry = get_registry()
    settings = registry.settings
    from backend.db.database_registry import DATABASES

    db_info = DATABASES.get(req.db_name)
    estimated_size = db_info.expected_size_bytes if db_info else 0
    if not should_download_now(estimated_size, settings.update_download_window):
        raise HTTPException(
            status_code=409,
            detail=f"Outside bandwidth window ({settings.update_download_window}).",
        )

    job_id = create_database_update_job(req.db_name)
    run_database_update_task(job_id, req.db_name)

    return TriggerUpdateResponse(
        job_id=job_id,
        db_name=req.db_name,
        message=f"Update queued for {req.db_name}",
    )


@router.get("/history", response_model=list[UpdateHistoryEntry])
async def list_update_history(
    db_name: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[UpdateHistoryEntry]:
    """Get update history, optionally filtered by database name."""
    registry = get_registry()
    rows = get_update_history(registry.reference_engine, db_name=db_name, limit=limit)
    return [UpdateHistoryEntry(**r) for r in rows]


@router.get("/status", response_model=list[DatabaseStatus])
async def get_database_statuses() -> list[DatabaseStatus]:
    """Get current version and display info for all tracked databases.

    Note: ``update_available`` is always False here. Call
    ``GET /updates/check`` for actual update availability (network call).
    """
    registry = get_registry()
    engine = registry.reference_engine

    # Fetch all version stamps in one query
    stamps = {s["db_name"]: s for s in get_all_version_stamps(engine)}

    # Check which databases have updates available (cached, no network call)
    # We only mark update_available based on whether we have a version at all;
    # actual update checks are done via GET /updates/check
    result = []
    for db_name, auto_update in AUTO_UPDATE_DEFAULTS.items():
        stamp = stamps.get(db_name)
        version = stamp["version"] if stamp else None
        downloaded_at = stamp["downloaded_at"] if stamp else None
        db_info = DATABASES.get(db_name)
        display_name = db_info.display_name if db_info else db_name

        result.append(
            DatabaseStatus(
                db_name=db_name,
                display_name=display_name,
                current_version=version,
                version_display=format_version_display(version, db_name),
                downloaded_at=downloaded_at,
                auto_update=auto_update,
                update_available=False,  # Set by GET /updates/check
            )
        )
    return result


@router.get("/prompts", response_model=list[ReannotationPrompt])
async def list_reannotation_prompts(
    sample_id: int | None = None,
) -> list[ReannotationPrompt]:
    """Get active (undismissed) re-annotation prompts."""
    registry = get_registry()
    rows = get_active_prompts(registry.reference_engine, sample_id=sample_id)
    return [ReannotationPrompt(**r) for r in rows]


class AppUpdateResponse(BaseModel):
    update_available: bool
    current_version: str
    latest_version: str | None = None
    release_url: str | None = None
    release_notes: str | None = None
    error: str | None = None


@router.get("/app-update", response_model=AppUpdateResponse)
async def check_app_update() -> AppUpdateResponse:
    """Check GitHub Releases API for a newer GenomeInsight version."""
    from backend.utils.update_checker import check_app_update as _check

    info = _check()
    return AppUpdateResponse(
        update_available=info.update_available,
        current_version=info.current_version,
        latest_version=info.latest_version,
        release_url=info.release_url,
        release_notes=info.release_notes,
        error=info.error,
    )


@router.post("/prompts/{prompt_id}/dismiss")
async def dismiss_reannotation_prompt(prompt_id: int) -> dict:
    """Dismiss a re-annotation prompt."""
    registry = get_registry()
    ok = dismiss_prompt(registry.reference_engine, prompt_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {"status": "dismissed", "prompt_id": prompt_id}
