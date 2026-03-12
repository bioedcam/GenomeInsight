"""Annotation API endpoints (P2-05).

POST /api/annotation/{sample_id}         — Start annotation job (202 Accepted)
GET  /api/annotation/status/{job_id}     — SSE progress stream
POST /api/annotation/cancel/{job_id}     — Cancel a running annotation job
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.api.sse import job_progress_stream, sse_response
from backend.db.connection import get_registry
from backend.tasks.huey_tasks import create_annotation_job, run_annotation_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/annotation", tags=["annotation"])


@router.post("/{sample_id}", status_code=202)
async def start_annotation(sample_id: int) -> dict:
    """Start a background annotation job for a sample.

    Returns 202 Accepted with job_id for SSE progress polling.
    Rejects if an annotation is already running for this sample.
    """
    try:
        job_id = create_annotation_job(sample_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    # Enqueue the Huey background task
    run_annotation_task(sample_id, job_id)

    logger.info(
        "annotation_job_enqueued",
        extra={"sample_id": sample_id, "job_id": job_id},
    )

    return {"job_id": job_id, "sample_id": sample_id, "status": "pending"}


@router.get("/status/{job_id}")
async def annotation_status(job_id: str):
    """Stream annotation job progress via SSE."""
    registry = get_registry()
    stream = job_progress_stream(registry.reference_engine, job_id)
    return sse_response(stream)


@router.post("/cancel/{job_id}")
async def cancel_annotation(job_id: str) -> dict:
    """Cancel a running annotation job."""
    from datetime import UTC, datetime

    import sqlalchemy as sa

    from backend.db.tables import jobs

    registry = get_registry()

    with registry.reference_engine.begin() as conn:
        row = conn.execute(sa.select(jobs.c.status).where(jobs.c.job_id == job_id)).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        if row.status in ("complete", "failed", "cancelled"):
            raise HTTPException(
                status_code=409,
                detail=f"Job {job_id} already in terminal state: {row.status}",
            )

        conn.execute(
            jobs.update()
            .where(jobs.c.job_id == job_id)
            .values(
                status="cancelled",
                message="Cancelled by user",
                updated_at=datetime.now(UTC),
            )
        )

    return {"job_id": job_id, "status": "cancelled"}
