"""Report generation API endpoints (P4-07).

POST /api/reports/generate  — Generate a PDF report for a sample
POST /api/reports/preview   — Generate HTML preview of a report
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


# ── Request / response models ─────────────────────────────────────────


class ReportRequest(BaseModel):
    """Request body for report generation."""

    sample_id: int = Field(..., description="Sample ID to generate report for")
    modules: list[str] | None = Field(
        None,
        description="List of module names to include. None = all modules.",
    )
    title: str = Field(
        "GenomeInsight Genomic Report",
        description="Report title",
    )

    @field_validator("modules")
    @classmethod
    def modules_non_empty(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and len(v) == 0:
            raise ValueError("modules list cannot be empty; use null for all modules")
        return v


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post("/generate")
async def generate_report(request: ReportRequest) -> Response:
    """Generate a PDF report for the given sample.

    Returns the PDF file as a downloadable response.
    """
    from backend.reports.generator import generate_report_pdf

    try:
        pdf_bytes = await generate_report_pdf(
            sample_id=request.sample_id,
            modules=request.modules,
            title=request.title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    filename = f"genomeinsight_report_{request.sample_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/preview", response_class=HTMLResponse)
async def preview_report(request: ReportRequest) -> HTMLResponse:
    """Generate an HTML preview of the report (no PDF conversion).

    Useful for the report builder UI to show a live preview before
    the user commits to PDF generation.
    """
    from backend.reports.generator import render_report_html

    try:
        html = render_report_html(
            sample_id=request.sample_id,
            modules=request.modules,
            title=request.title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return HTMLResponse(content=html)
