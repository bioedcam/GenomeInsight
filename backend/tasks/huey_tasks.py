"""Huey task queue configuration and tasks.

Uses SqliteHuey for persistent task state with a single worker.
In test/dev mode, immediate=True runs tasks synchronously.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from huey import SqliteHuey

from backend.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()
_settings.data_dir.mkdir(parents=True, exist_ok=True)
_huey_db = str(_settings.data_dir / "huey.db")

# Allow override for testing (immediate mode runs tasks inline)
_immediate = os.environ.get("GENOMEINSIGHT_HUEY_IMMEDIATE", "").lower() in (
    "1",
    "true",
    "yes",
)

huey = SqliteHuey(
    "genomeinsight",
    filename=_huey_db,
    immediate=_immediate,
)


# ── Job record helpers ──────────────────────────────────────────────────


def create_annotation_job(sample_id: int) -> str:
    """Create a job record for an annotation run. Returns the job_id."""
    import sqlalchemy as sa

    from backend.db.connection import get_registry
    from backend.db.tables import jobs

    job_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    registry = get_registry()

    with registry.reference_engine.begin() as conn:
        # Check for an already-running annotation job on this sample
        existing = conn.execute(
            sa.select(jobs.c.job_id).where(
                jobs.c.sample_id == sample_id,
                jobs.c.job_type == "annotation",
                jobs.c.status.in_(["pending", "running"]),
            )
        ).fetchone()
        if existing is not None:
            raise ValueError(
                f"Annotation already in progress for sample {sample_id} (job {existing.job_id})"
            )

        conn.execute(
            jobs.insert().values(
                job_id=job_id,
                sample_id=sample_id,
                job_type="annotation",
                status="pending",
                progress_pct=0.0,
                message="Queued for annotation",
                created_at=now,
                updated_at=now,
            )
        )

    return job_id


def _update_job(
    job_id: str,
    *,
    status: str,
    progress_pct: float = 0.0,
    message: str = "",
    error: str | None = None,
) -> None:
    """Update a job record in the jobs table."""

    from backend.db.connection import get_registry
    from backend.db.tables import jobs

    registry = get_registry()
    with registry.reference_engine.begin() as conn:
        result = conn.execute(
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
        if result.rowcount == 0:
            logger.warning("_update_job: no job found", extra={"job_id": job_id})


def _is_job_cancelled(job_id: str) -> bool:
    """Check if a job has been cancelled by the user."""
    import sqlalchemy as sa

    from backend.db.connection import get_registry
    from backend.db.tables import jobs

    registry = get_registry()
    with registry.reference_engine.connect() as conn:
        row = conn.execute(sa.select(jobs.c.status).where(jobs.c.job_id == job_id)).fetchone()

    return row is not None and row.status == "cancelled"


class AnnotationCancelledError(Exception):
    """Raised when an annotation job is cancelled by the user."""


def _get_sample_db_path(sample_id: int) -> str:
    """Look up the db_path for a sample from the samples table."""
    import sqlalchemy as sa

    from backend.db.connection import get_registry
    from backend.db.tables import samples

    registry = get_registry()
    with registry.reference_engine.connect() as conn:
        row = conn.execute(
            sa.select(samples.c.db_path).where(samples.c.id == sample_id)
        ).fetchone()

    if row is None:
        raise ValueError(f"Sample {sample_id} not found")

    return row.db_path


# ── Annotation task ─────────────────────────────────────────────────────


@huey.task()
def run_annotation_task(sample_id: int, job_id: str) -> None:
    """Huey background task: run the full annotation engine on a sample.

    Updates the jobs table with progress so the SSE endpoint can
    stream batch-level updates to the frontend.
    """
    from backend.annotation.engine import run_annotation
    from backend.db.connection import get_registry

    registry = get_registry()

    try:
        # Look up sample DB path and get engine
        db_path = _get_sample_db_path(sample_id)
        sample_db_full = registry.settings.data_dir / db_path
        sample_engine = registry.get_sample_engine(sample_db_full)

        _update_job(job_id, status="running", message="Starting annotation")

        def progress_callback(variants_done: int, total: int) -> None:
            if _is_job_cancelled(job_id):
                raise AnnotationCancelledError(f"Job {job_id} cancelled by user")
            pct = (variants_done / total * 100) if total > 0 else 0.0
            _update_job(
                job_id,
                status="running",
                progress_pct=round(pct, 1),
                message=f"Annotated {variants_done:,}/{total:,} variants",
            )

        result = run_annotation(
            sample_engine,
            registry,
            progress_callback=progress_callback,
        )

        if result.errors:
            error_summary = "; ".join(result.errors[:5])
            logger.warning(
                "annotation_task_warnings",
                extra={"job_id": job_id, "errors": result.errors},
            )
        else:
            error_summary = None

        # Generate SVGs for all findings (post-analysis step)
        _update_job(
            job_id,
            status="running",
            progress_pct=99.0,
            message="Generating finding SVGs",
        )
        try:
            from backend.analysis.svg_renderer import generate_svgs_for_sample

            sample_dir = Path(sample_db_full).parent
            svg_count = generate_svgs_for_sample(sample_engine, sample_dir)
            logger.info(
                "svg_generation_complete",
                extra={
                    "job_id": job_id,
                    "sample_id": sample_id,
                    "svgs_generated": svg_count,
                },
            )
        except Exception:
            logger.exception(
                "svg_generation_failed",
                extra={"job_id": job_id, "sample_id": sample_id},
            )
            # Non-fatal: annotation succeeded, SVG generation is best-effort

        _update_job(
            job_id,
            status="complete",
            progress_pct=100.0,
            message=(
                f"Annotated {result.rows_written:,} variants "
                f"(VEP: {result.vep_matched}, ClinVar: {result.clinvar_matched}, "
                f"gnomAD: {result.gnomad_matched}, dbNSFP: {result.dbnsfp_matched}, "
                f"GenePhenotype: {result.gene_phenotype_matched})"
            ),
            error=error_summary,
        )

        logger.info(
            "annotation_task_complete",
            extra={
                "job_id": job_id,
                "sample_id": sample_id,
                "rows_written": result.rows_written,
                "total_variants": result.total_variants,
            },
        )

    except AnnotationCancelledError:
        logger.info(
            "annotation_task_cancelled",
            extra={"job_id": job_id, "sample_id": sample_id},
        )
        # Status already set to "cancelled" by the cancel endpoint

    except Exception as exc:
        logger.exception(
            "annotation_task_failed",
            extra={"job_id": job_id, "sample_id": sample_id},
        )
        _update_job(
            job_id,
            status="failed",
            message="Annotation failed",
            error=str(exc),
        )


# ── UniProt pre-fetch task (P4-12c) ───────────────────────────────────


@huey.task()
def prefetch_uniprot_priority_genes(job_id: str) -> None:
    """Pre-fetch UniProt protein domains for cancer/cardio panel genes.

    Called at setup completion to populate the UniProt cache with
    high-priority gene panel data. Runs with rate limiting to
    respect UniProt API limits.
    """
    from backend.db.connection import get_registry
    from backend.utils.uniprot import PRIORITY_GENES, UniProtCacheFetcher

    try:
        _update_job(job_id, status="running", message="Pre-fetching UniProt domains")

        registry = get_registry()
        fetcher = UniProtCacheFetcher(registry.reference_engine)

        def progress_callback(done: int, total: int) -> None:
            pct = (done / total * 100) if total > 0 else 0.0
            _update_job(
                job_id,
                status="running",
                progress_pct=round(pct, 1),
                message=f"Pre-fetching UniProt: {done}/{total} genes",
            )

        result_data = fetcher.prefetch_genes(
            PRIORITY_GENES,
            skip_fresh=True,
            delay_seconds=0.5,
            progress_callback=progress_callback,
        )

        _update_job(
            job_id,
            status="complete",
            progress_pct=100.0,
            message=(
                f"UniProt pre-fetch complete: {result_data.fetched} fetched, "
                f"{result_data.cached_already} already cached, "
                f"{result_data.failed} failed "
                f"(of {result_data.total_genes} genes)"
            ),
            error="; ".join(result_data.errors[:5]) if result_data.errors else None,
        )

        logger.info(
            "uniprot_prefetch_complete",
            extra={
                "job_id": job_id,
                "fetched": result_data.fetched,
                "cached": result_data.cached_already,
                "failed": result_data.failed,
            },
        )

    except Exception as exc:
        logger.exception(
            "uniprot_prefetch_failed",
            extra={"job_id": job_id},
        )
        _update_job(
            job_id,
            status="failed",
            message="UniProt pre-fetch failed",
            error=str(exc),
        )


def create_prefetch_job() -> str:
    """Create a job record for a UniProt pre-fetch task. Returns the job_id."""

    from backend.db.connection import get_registry
    from backend.db.tables import jobs

    job_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    registry = get_registry()

    with registry.reference_engine.begin() as conn:
        conn.execute(
            jobs.insert().values(
                job_id=job_id,
                sample_id=None,
                job_type="uniprot_prefetch",
                status="pending",
                progress_pct=0.0,
                message="Queued for UniProt pre-fetch",
                created_at=now,
                updated_at=now,
            )
        )

    return job_id
