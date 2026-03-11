"""Column preset profiles API (P1-15c).

4 predefined presets (Clinical, Research, Frequency, Scores) + user-defined
custom presets with full CRUD. Custom presets stored in column_presets.json
in the data directory (global, shared across all samples).

GET    /api/column-presets         — List all presets
POST   /api/column-presets         — Create custom preset
PUT    /api/column-presets/{name}  — Update custom preset
DELETE /api/column-presets/{name}  — Delete custom preset
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/column-presets", tags=["column-presets"])

# ── Predefined presets ────────────────────────────────────────────────

PREDEFINED_PRESETS: dict[str, list[str]] = {
    "Clinical": [
        "genotype",
        "gene_symbol",
        "consequence",
        "clinvar_significance",
        "clinvar_review_stars",
    ],
    "Research": [
        "genotype",
        "gene_symbol",
        "consequence",
        "clinvar_significance",
        "clinvar_review_stars",
        "cadd_phred",
        "sift_score",
        "sift_pred",
        "polyphen2_hsvar_score",
        "polyphen2_hsvar_pred",
        "revel",
        "ensemble_pathogenic",
    ],
    "Frequency": [
        "genotype",
        "gene_symbol",
        "gnomad_af_global",
        "rare_flag",
    ],
    "Scores": [
        "gene_symbol",
        "consequence",
        "cadd_phred",
        "sift_score",
        "sift_pred",
        "polyphen2_hsvar_score",
        "polyphen2_hsvar_pred",
        "revel",
    ],
}

# ── Response / request models ─────────────────────────────────────────


class PresetItem(BaseModel):
    name: str
    columns: list[str]
    predefined: bool


class PresetListResponse(BaseModel):
    presets: list[PresetItem]


class CreatePresetRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    columns: list[str] = Field(..., min_length=1)


class UpdatePresetRequest(BaseModel):
    new_name: str | None = Field(None, min_length=1, max_length=100)
    columns: list[str] | None = Field(None, min_length=1)


# ── JSON file helpers ─────────────────────────────────────────────────


def _presets_path() -> Path:
    return get_settings().data_dir / "column_presets.json"


def _read_custom_presets() -> dict[str, list[str]]:
    path = _presets_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("presets", {})
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to read column_presets.json, returning empty")
        return {}


def _write_custom_presets(presets: dict[str, list[str]]) -> None:
    path = _presets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"presets": presets}, indent=2),
        encoding="utf-8",
    )


# ── Endpoints ─────────────────────────────────────────────────────────


@router.get("")
def list_presets() -> PresetListResponse:
    """Return all column presets (predefined + custom)."""
    items: list[PresetItem] = []

    for name, cols in PREDEFINED_PRESETS.items():
        items.append(PresetItem(name=name, columns=cols, predefined=True))

    for name, cols in _read_custom_presets().items():
        items.append(PresetItem(name=name, columns=cols, predefined=False))

    return PresetListResponse(presets=items)


@router.post("", status_code=201)
def create_preset(body: CreatePresetRequest) -> PresetItem:
    """Create a new custom column preset."""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Preset name cannot be blank.")

    if name in PREDEFINED_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"'{name}' is a predefined preset and cannot be overwritten.",
        )

    custom = _read_custom_presets()
    if name in custom:
        raise HTTPException(
            status_code=409,
            detail=f"A custom preset named '{name}' already exists.",
        )

    custom[name] = body.columns
    _write_custom_presets(custom)
    return PresetItem(name=name, columns=body.columns, predefined=False)


@router.put("/{name}")
def update_preset(name: str, body: UpdatePresetRequest) -> PresetItem:
    """Update (rename / change columns) a custom preset."""
    if name in PREDEFINED_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"'{name}' is a predefined preset and cannot be modified.",
        )

    custom = _read_custom_presets()
    if name not in custom:
        raise HTTPException(status_code=404, detail=f"Custom preset '{name}' not found.")

    new_name = (body.new_name.strip() if body.new_name else None) or name
    new_columns = body.columns if body.columns is not None else custom[name]

    if new_name != name:
        if new_name in PREDEFINED_PRESETS or new_name in custom:
            raise HTTPException(
                status_code=409,
                detail=f"A preset named '{new_name}' already exists.",
            )
        del custom[name]

    custom[new_name] = new_columns
    _write_custom_presets(custom)
    return PresetItem(name=new_name, columns=new_columns, predefined=False)


@router.delete("/{name}", status_code=204)
def delete_preset(name: str) -> None:
    """Delete a custom column preset."""
    if name in PREDEFINED_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"'{name}' is a predefined preset and cannot be deleted.",
        )

    custom = _read_custom_presets()
    if name not in custom:
        raise HTTPException(status_code=404, detail=f"Custom preset '{name}' not found.")

    del custom[name]
    _write_custom_presets(custom)
