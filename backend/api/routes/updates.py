"""Update manager API routes (P4-16).

Endpoints for checking database updates, triggering updates,
viewing update history, and managing re-annotation prompts.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db.connection import get_registry
from backend.db.update_manager import (
    AUTO_UPDATE_DEFAULTS,
    check_all_updates,
    dismiss_prompt,
    get_active_prompts,
    get_current_version,
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
    current_version: str | None
    auto_update: bool


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

    # Check bandwidth window
    registry = get_registry()
    settings = registry.settings
    if not should_download_now(0, settings.update_download_window):
        raise HTTPException(
            status_code=409,
            detail=f"Outside bandwidth window ({settings.update_download_window}). "
            "ClinVar updates bypass this check due to small size.",
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
    limit: int = 50,
) -> list[UpdateHistoryEntry]:
    """Get update history, optionally filtered by database name."""
    registry = get_registry()
    rows = get_update_history(registry.reference_engine, db_name=db_name, limit=limit)
    return [UpdateHistoryEntry(**r) for r in rows]


@router.get("/status", response_model=list[DatabaseStatus])
async def get_database_statuses() -> list[DatabaseStatus]:
    """Get current version and auto-update status for all databases."""
    registry = get_registry()
    engine = registry.reference_engine

    result = []
    for db_name, auto_update in AUTO_UPDATE_DEFAULTS.items():
        version = get_current_version(engine, db_name)
        result.append(
            DatabaseStatus(
                db_name=db_name,
                current_version=version,
                auto_update=auto_update,
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


@router.post("/prompts/{prompt_id}/dismiss")
async def dismiss_reannotation_prompt(prompt_id: int) -> dict:
    """Dismiss a re-annotation prompt."""
    registry = get_registry()
    ok = dismiss_prompt(registry.reference_engine, prompt_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {"status": "dismissed", "prompt_id": prompt_id}
