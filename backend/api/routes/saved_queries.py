"""Saved queries CRUD API (P4-02 save/load, P4-06 full CRUD).

Named query filters stored in saved_queries.json in the data directory.
Each query stores a react-querybuilder RuleGroupType filter tree.

GET    /api/saved-queries         — List all saved queries
POST   /api/saved-queries         — Save a new query
PUT    /api/saved-queries/{name}  — Update a saved query
DELETE /api/saved-queries/{name}  — Delete a saved query
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/saved-queries", tags=["saved-queries"])


# ── Models ───────────────────────────────────────────────────────────


class SavedQueryItem(BaseModel):
    """A single saved query."""

    name: str
    filter: dict[str, Any]
    created_at: str
    updated_at: str


class SavedQueryListResponse(BaseModel):
    """Response for GET /api/saved-queries."""

    queries: list[SavedQueryItem]


class CreateSavedQueryRequest(BaseModel):
    """POST /api/saved-queries request body."""

    name: str = Field(..., min_length=1, max_length=200)
    filter: dict[str, Any]


class UpdateSavedQueryRequest(BaseModel):
    """PUT /api/saved-queries/{name} request body."""

    new_name: str | None = Field(None, min_length=1, max_length=200)
    filter: dict[str, Any] | None = None


# ── JSON file helpers ────────────────────────────────────────────────


def _queries_path() -> Path:
    return get_settings().data_dir / "saved_queries.json"


def _read_saved_queries() -> dict[str, dict[str, Any]]:
    path = _queries_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("queries", {})
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to read saved_queries.json, returning empty")
        return {}


def _write_saved_queries(queries: dict[str, dict[str, Any]]) -> None:
    path = _queries_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"queries": queries}, indent=2),
        encoding="utf-8",
    )


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("")
def list_saved_queries() -> SavedQueryListResponse:
    """Return all saved queries."""
    raw = _read_saved_queries()
    items = [
        SavedQueryItem(
            name=name,
            filter=entry["filter"],
            created_at=entry.get("created_at", ""),
            updated_at=entry.get("updated_at", ""),
        )
        for name, entry in raw.items()
    ]
    # Sort by updated_at descending (most recent first)
    items.sort(key=lambda q: q.updated_at, reverse=True)
    return SavedQueryListResponse(queries=items)


@router.post("", status_code=201)
def create_saved_query(body: CreateSavedQueryRequest) -> SavedQueryItem:
    """Save a new named query."""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Query name cannot be blank.")

    queries = _read_saved_queries()
    if name in queries:
        raise HTTPException(
            status_code=409,
            detail=f"A saved query named '{name}' already exists.",
        )

    now = datetime.now(UTC).isoformat()
    queries[name] = {
        "filter": body.filter,
        "created_at": now,
        "updated_at": now,
    }
    _write_saved_queries(queries)
    return SavedQueryItem(
        name=name,
        filter=body.filter,
        created_at=now,
        updated_at=now,
    )


@router.put("/{name}")
def update_saved_query(name: str, body: UpdateSavedQueryRequest) -> SavedQueryItem:
    """Update (rename / change filter) a saved query."""
    queries = _read_saved_queries()
    if name not in queries:
        raise HTTPException(status_code=404, detail=f"Saved query '{name}' not found.")

    existing = queries[name]
    if body.new_name is not None and not body.new_name.strip():
        raise HTTPException(status_code=400, detail="New name cannot be blank.")
    new_name = (body.new_name.strip() if body.new_name else None) or name
    new_filter = body.filter if body.filter is not None else existing["filter"]

    if new_name != name:
        if new_name in queries:
            raise HTTPException(
                status_code=409,
                detail=f"A saved query named '{new_name}' already exists.",
            )
        del queries[name]

    now = datetime.now(UTC).isoformat()
    queries[new_name] = {
        "filter": new_filter,
        "created_at": existing.get("created_at", now),
        "updated_at": now,
    }
    _write_saved_queries(queries)
    return SavedQueryItem(
        name=new_name,
        filter=new_filter,
        created_at=queries[new_name]["created_at"],
        updated_at=now,
    )


@router.delete("/{name}", status_code=204)
def delete_saved_query(name: str) -> None:
    """Delete a saved query."""
    queries = _read_saved_queries()
    if name not in queries:
        raise HTTPException(status_code=404, detail=f"Saved query '{name}' not found.")

    del queries[name]
    _write_saved_queries(queries)
