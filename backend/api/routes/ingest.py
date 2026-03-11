"""Ingestion API endpoints (P1-13).

POST /api/ingest        — Upload a 23andMe file, parse, store, return 202
GET  /api/ingest/status/{job_id} — Poll parse job progress (SSE)
"""

from __future__ import annotations

import hashlib
import io
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, UploadFile

from backend.api.sse import job_progress_stream, sse_response
from backend.db.connection import get_registry
from backend.db.sample_schema import create_sample_tables
from backend.db.tables import jobs, raw_variants, sample_metadata_table, samples
from backend.ingestion.parser_23andme import (
    ParserError,
    parse_23andme,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingestion"])

# Batch size for bulk inserts
_INSERT_BATCH = 10_000


def _ingest_file(file_bytes: bytes, filename: str) -> dict:
    """Parse a 23andMe file and persist to a new sample database.

    This is the synchronous core of the ingest endpoint. For v1 (< 2 min
    parse time), this runs inline. Huey background tasks will wrap this
    in Phase 2 for the annotation pipeline.

    Returns a dict with sample_id, job_id, variant_count, nocall_count.
    """
    registry = get_registry()
    settings = registry.settings

    # Compute SHA-256 of the uploaded file
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Parse the file content (pure, no side effects)
    text = file_bytes.decode("utf-8", errors="replace")
    if "\ufffd" in text:
        logger.warning("File %s contains invalid UTF-8 sequences that were replaced", filename)
    result = parse_23andme(io.StringIO(text))

    # Register sample in reference.db
    now = datetime.now(UTC)
    with registry.reference_engine.begin() as conn:
        row = conn.execute(
            samples.insert()
            .values(
                name=filename,
                db_path="",  # placeholder, updated below
                file_format=f"23andme_{result.version.value}",
                file_hash=file_hash,
                created_at=now,
            )
            .returning(samples.c.id)
        )
        sample_id = row.scalar_one()

        # Set db_path now that we have the id
        db_path = f"samples/sample_{sample_id}.db"
        conn.execute(samples.update().where(samples.c.id == sample_id).values(db_path=db_path))

    # Create the per-sample database
    sample_db_path = settings.data_dir / db_path
    sample_db_path.parent.mkdir(parents=True, exist_ok=True)
    sample_engine = registry.get_sample_engine(sample_db_path)
    create_sample_tables(sample_engine)

    # Write sample metadata (single-row table)
    with sample_engine.begin() as conn:
        conn.execute(
            sample_metadata_table.insert().values(
                id=1,
                name=filename,
                file_format=f"23andme_{result.version.value}",
                file_hash=file_hash,
                created_at=now,
            )
        )

    # Bulk-insert raw variants in batches
    variant_dicts = [
        {
            "rsid": v.rsid,
            "chrom": v.chrom,
            "pos": v.pos,
            "genotype": v.genotype,
        }
        for v in result.variants
    ]
    with sample_engine.begin() as conn:
        for i in range(0, len(variant_dicts), _INSERT_BATCH):
            batch = variant_dicts[i : i + _INSERT_BATCH]
            conn.execute(raw_variants.insert(), batch)

    # Create a job record to track status
    job_id = str(uuid.uuid4())
    with registry.reference_engine.begin() as conn:
        conn.execute(
            jobs.insert().values(
                job_id=job_id,
                sample_id=sample_id,
                job_type="ingest",
                status="complete",
                progress_pct=100.0,
                message=f"Parsed {len(result.variants)} variants",
                created_at=now,
                updated_at=now,
            )
        )

    return {
        "sample_id": sample_id,
        "job_id": job_id,
        "variant_count": len(result.variants),
        "nocall_count": result.nocall_count,
        "file_format": f"23andme_{result.version.value}",
    }


@router.post("", status_code=202)
async def ingest_file(file: UploadFile) -> dict:
    """Upload and parse a 23andMe raw data file.

    Returns 202 Accepted with sample_id and job_id for status polling.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file.")

    try:
        result = _ingest_file(file_bytes, file.filename)
    except ParserError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return result


@router.get("/status/{job_id}")
async def ingest_status(job_id: str):
    """Stream ingest job progress via SSE."""
    registry = get_registry()
    stream = job_progress_stream(registry.reference_engine, job_id)
    return sse_response(stream)
