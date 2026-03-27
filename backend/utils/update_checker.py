"""App update checker — GitHub Releases API (P4-21d).

On startup, checks the GitHub Releases API for a newer GenomeInsight version.
Compares semantic versions. No auto-update — users upgrade via pip.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx
from packaging.version import InvalidVersion, Version

from backend.main import VERSION

logger = logging.getLogger(__name__)

GITHUB_REPO = "bioedcam/GenomeInsight"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
REQUEST_TIMEOUT = 10.0  # seconds


@dataclass
class AppUpdateInfo:
    """Result of an app update check."""

    update_available: bool
    current_version: str
    latest_version: str | None = None
    release_url: str | None = None
    release_notes: str | None = None
    error: str | None = None


def parse_version(version_str: str) -> Version | None:
    """Parse a version string, stripping leading 'v' if present."""
    cleaned = version_str.lstrip("v")
    try:
        return Version(cleaned)
    except InvalidVersion:
        return None


def check_app_update(current_version: str | None = None) -> AppUpdateInfo:
    """Check GitHub Releases for a newer GenomeInsight version.

    Args:
        current_version: Override for testing. Defaults to backend.main.VERSION.

    Returns:
        AppUpdateInfo with comparison result.
    """
    current = current_version or VERSION

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            resp = client.get(
                RELEASES_URL,
                headers={"Accept": "application/vnd.github+json"},
            )

        if resp.status_code == 404:
            # No releases published yet
            return AppUpdateInfo(
                update_available=False,
                current_version=current,
                error="No releases found",
            )

        if resp.status_code == 403:
            return AppUpdateInfo(
                update_available=False,
                current_version=current,
                error="GitHub API rate limit exceeded",
            )

        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return _compare_versions(current, data)

    except httpx.TimeoutException:
        logger.warning("App update check timed out")
        return AppUpdateInfo(
            update_available=False,
            current_version=current,
            error="Request timed out",
        )
    except httpx.HTTPError as exc:
        logger.warning("App update check failed: %s", exc)
        return AppUpdateInfo(
            update_available=False,
            current_version=current,
            error=str(exc),
        )


def _compare_versions(current: str, release_data: dict[str, Any]) -> AppUpdateInfo:
    """Compare current version against a GitHub release response."""
    tag = release_data.get("tag_name", "")
    html_url = release_data.get("html_url")
    body = release_data.get("body", "")

    current_ver = parse_version(current)
    latest_ver = parse_version(tag)

    if current_ver is None or latest_ver is None:
        return AppUpdateInfo(
            update_available=False,
            current_version=current,
            latest_version=tag or None,
            error=f"Could not parse version(s): current={current!r}, latest={tag!r}",
        )

    return AppUpdateInfo(
        update_available=latest_ver > current_ver,
        current_version=current,
        latest_version=str(latest_ver),
        release_url=html_url,
        release_notes=body[:500] if body else None,
    )
