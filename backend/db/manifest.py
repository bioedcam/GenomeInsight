"""Bundle manifest — single source of truth for bundle URLs / SHA-256 / sizes.

The manifest lives at ``bundles/manifest.json`` in the repo and is fetched at
runtime from raw.githubusercontent.com so users on installed builds can pick
up new bundle releases without a code update. Entries cover both pre-built
bundles (`lai_bundle`, `vep_bundle`, `ancestry_pca`) and pinned upstream URLs
for pipeline DBs (`pipeline_pins`).

For tests and offline development, set the ``GENOMEINSIGHT_MANIFEST_PATH``
environment variable to load the manifest from a local file instead of HTTP.

Caching
-------
Successful fetches are cached in-memory for ``CACHE_TTL_SECONDS`` (1 h).
On expiry or first call, a remote fetch is attempted. Failures raise
``ManifestFetchError`` — callers (notably ``backend/api/routes/databases.py``)
fall back to registry defaults when the manifest is unreachable.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MANIFEST_URL = (
    "https://raw.githubusercontent.com/bioedcam/GenomeInsight/main/bundles/manifest.json"
)
CACHE_TTL_SECONDS = 3600.0
MANIFEST_PATH_ENV = "GENOMEINSIGHT_MANIFEST_PATH"
DEFAULT_TIMEOUT = 15.0


class ManifestFetchError(RuntimeError):
    """Raised when the manifest cannot be loaded or parsed."""


@dataclass(frozen=True)
class BundleManifestEntry:
    version: str
    build_date: str
    url: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class PipelinePinEntry:
    url: str
    last_known_version: str


@dataclass(frozen=True)
class Manifest:
    schema_version: int
    generated_at: str
    bundles: dict[str, BundleManifestEntry]
    pipeline_pins: dict[str, PipelinePinEntry]


_cache_lock = threading.Lock()
_cached_manifest: Manifest | None = None
_cached_at: float = 0.0


def _parse_manifest(payload: Any) -> Manifest:
    if not isinstance(payload, dict):
        raise ManifestFetchError(
            f"Manifest payload must be an object, got {type(payload).__name__}"
        )
    try:
        schema_version = int(payload.get("schema_version", 0))
        generated_at = str(payload.get("generated_at", ""))
        bundles_raw = payload.get("bundles") or {}
        pins_raw = payload.get("pipeline_pins") or {}
        if not isinstance(bundles_raw, dict) or not isinstance(pins_raw, dict):
            raise ManifestFetchError("`bundles` and `pipeline_pins` must be objects")

        bundles = {
            name: BundleManifestEntry(
                version=str(entry["version"]),
                build_date=str(entry["build_date"]),
                url=str(entry["url"]),
                sha256=str(entry["sha256"]),
                size_bytes=int(entry["size_bytes"]),
            )
            for name, entry in bundles_raw.items()
        }
        pins = {
            name: PipelinePinEntry(
                url=str(entry["url"]),
                last_known_version=str(entry.get("last_known_version", "")),
            )
            for name, entry in pins_raw.items()
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise ManifestFetchError(f"Manifest payload malformed: {exc}") from exc

    return Manifest(
        schema_version=schema_version,
        generated_at=generated_at,
        bundles=bundles,
        pipeline_pins=pins,
    )


def _load_local(path: Path) -> Manifest:
    try:
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestFetchError(f"Failed to read local manifest at {path}: {exc}") from exc
    return _parse_manifest(payload)


def _load_remote(timeout: float) -> Manifest:
    try:
        resp = httpx.get(
            MANIFEST_URL,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise ManifestFetchError(f"Failed to fetch manifest: {exc}") from exc

    try:
        payload = resp.json()
    except ValueError as exc:
        raise ManifestFetchError(f"Manifest response was not valid JSON: {exc}") from exc

    return _parse_manifest(payload)


def fetch_manifest(
    timeout: float = DEFAULT_TIMEOUT,
    *,
    force_refresh: bool = False,
) -> Manifest:
    """Return the bundle manifest, fetching remotely or from the env override.

    Caching: a successful fetch is cached in-memory for ``CACHE_TTL_SECONDS``.
    Set ``force_refresh=True`` to bypass the cache. Set the
    ``GENOMEINSIGHT_MANIFEST_PATH`` env var to load from a local JSON file
    (the env override is never cached so tests can swap files freely).

    Raises ``ManifestFetchError`` if the manifest cannot be loaded or parsed.
    """
    global _cached_manifest, _cached_at

    override = os.environ.get(MANIFEST_PATH_ENV)
    if override:
        return _load_local(Path(override))

    with _cache_lock:
        now = time.monotonic()
        if (
            not force_refresh
            and _cached_manifest is not None
            and (now - _cached_at) < CACHE_TTL_SECONDS
        ):
            return _cached_manifest

        manifest = _load_remote(timeout)
        _cached_manifest = manifest
        _cached_at = now
        return manifest


def get_bundle_info(
    name: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> BundleManifestEntry | None:
    """Return the bundle entry for ``name``, or ``None`` if missing or unfetchable."""
    try:
        manifest = fetch_manifest(timeout=timeout)
    except ManifestFetchError as exc:
        logger.warning("Manifest unavailable for bundle %r: %s", name, exc)
        return None
    return manifest.bundles.get(name)


def get_pipeline_pin(
    name: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> PipelinePinEntry | None:
    """Return the pipeline pin entry for ``name``, or ``None`` if missing or unfetchable."""
    try:
        manifest = fetch_manifest(timeout=timeout)
    except ManifestFetchError as exc:
        logger.warning("Manifest unavailable for pipeline pin %r: %s", name, exc)
        return None
    return manifest.pipeline_pins.get(name)


def reset_cache() -> None:
    """Clear the in-memory cache. Intended for tests."""
    global _cached_manifest, _cached_at
    with _cache_lock:
        _cached_manifest = None
        _cached_at = 0.0
