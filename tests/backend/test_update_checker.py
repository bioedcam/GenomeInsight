"""Tests for app update checker — GitHub Releases API (P4-21d, T4-22i).

Verifies version comparison logic and error handling without hitting
the real GitHub API.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.utils.update_checker import (
    AppUpdateInfo,
    _compare_versions,
    check_app_update,
    parse_version,
)

# ── parse_version ─────────────────────────────────────────────────────


class TestParseVersion:
    def test_plain_semver(self):
        v = parse_version("1.2.3")
        assert v is not None
        assert str(v) == "1.2.3"

    def test_leading_v(self):
        v = parse_version("v1.2.3")
        assert v is not None
        assert str(v) == "1.2.3"

    def test_prerelease(self):
        v = parse_version("v0.2.0rc1")
        assert v is not None

    def test_invalid(self):
        assert parse_version("not-a-version") is None

    def test_empty(self):
        assert parse_version("") is None


# ── _compare_versions ─────────────────────────────────────────────────


class TestCompareVersions:
    def test_newer_available(self):
        release = {"tag_name": "v1.0.0", "html_url": "https://example.com", "body": "notes"}
        info = _compare_versions("0.1.0", release)
        assert info.update_available is True
        assert info.latest_version == "1.0.0"
        assert info.release_url == "https://example.com"
        assert info.release_notes == "notes"

    def test_same_version(self):
        release = {"tag_name": "v0.1.0", "html_url": "https://example.com", "body": ""}
        info = _compare_versions("0.1.0", release)
        assert info.update_available is False
        assert info.latest_version == "0.1.0"

    def test_older_release(self):
        release = {"tag_name": "v0.0.9", "html_url": "https://example.com", "body": ""}
        info = _compare_versions("0.1.0", release)
        assert info.update_available is False

    def test_prerelease_skipped(self):
        release = {"tag_name": "v0.2.0rc1", "html_url": "https://example.com", "body": ""}
        info = _compare_versions("0.1.0", release)
        assert info.update_available is False
        assert info.latest_version == "0.2.0rc1"

    def test_invalid_tag(self):
        release = {"tag_name": "broken", "html_url": "https://example.com", "body": ""}
        info = _compare_versions("0.1.0", release)
        assert info.update_available is False
        assert info.error is not None

    def test_truncates_long_notes(self):
        release = {"tag_name": "v2.0.0", "html_url": "u", "body": "x" * 1000}
        info = _compare_versions("0.1.0", release)
        assert info.release_notes is not None
        assert len(info.release_notes) == 500


# ── check_app_update (mocked async HTTP) ─────────────────────────────


def _make_mock_response(status_code: int, json_data: dict | None = None) -> MagicMock:
    """Create a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


def _mock_async_client(mock_cls: MagicMock, resp: MagicMock | None = None, exc=None):
    """Set up the AsyncClient mock to return resp or raise exc on .get()."""
    mock_client = AsyncMock()
    if exc:
        mock_client.get.side_effect = exc
    else:
        mock_client.get.return_value = resp
    mock_cls.return_value = mock_client
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False


class TestCheckAppUpdate:
    @pytest.mark.asyncio
    @patch("backend.utils.update_checker.httpx.AsyncClient")
    async def test_update_available(self, mock_cls):
        resp = _make_mock_response(
            200,
            {
                "tag_name": "v1.0.0",
                "html_url": "https://github.com/bioedcam/GenomeInsight/releases/v1.0.0",
                "body": "Release notes",
            },
        )
        _mock_async_client(mock_cls, resp)

        info = await check_app_update(current_version="0.1.0")
        assert info.update_available is True
        assert info.latest_version == "1.0.0"
        assert info.current_version == "0.1.0"
        assert info.error is None

    @pytest.mark.asyncio
    @patch("backend.utils.update_checker.httpx.AsyncClient")
    async def test_no_update(self, mock_cls):
        resp = _make_mock_response(200, {"tag_name": "v0.1.0", "html_url": "url", "body": ""})
        _mock_async_client(mock_cls, resp)

        info = await check_app_update(current_version="0.1.0")
        assert info.update_available is False

    @pytest.mark.asyncio
    @patch("backend.utils.update_checker.httpx.AsyncClient")
    async def test_404_no_releases(self, mock_cls):
        resp = _make_mock_response(404)
        _mock_async_client(mock_cls, resp)

        info = await check_app_update(current_version="0.1.0")
        assert info.update_available is False
        assert info.error == "No releases found"

    @pytest.mark.asyncio
    @patch("backend.utils.update_checker.httpx.AsyncClient")
    async def test_403_rate_limit(self, mock_cls):
        resp = _make_mock_response(403)
        _mock_async_client(mock_cls, resp)

        info = await check_app_update(current_version="0.1.0")
        assert info.update_available is False
        assert "rate limit" in (info.error or "").lower()

    @pytest.mark.asyncio
    @patch("backend.utils.update_checker.httpx.AsyncClient")
    async def test_timeout(self, mock_cls):
        _mock_async_client(mock_cls, exc=httpx.TimeoutException("timeout"))

        info = await check_app_update(current_version="0.1.0")
        assert info.update_available is False
        assert info.error == "Request timed out"

    @pytest.mark.asyncio
    @patch("backend.utils.update_checker.httpx.AsyncClient")
    async def test_network_error(self, mock_cls):
        _mock_async_client(mock_cls, exc=httpx.ConnectError("refused"))

        info = await check_app_update(current_version="0.1.0")
        assert info.update_available is False
        assert info.error is not None


# ── API endpoint test ─────────────────────────────────────────────────


class TestAppUpdateEndpoint:
    @patch("backend.utils.update_checker.check_app_update")
    def test_endpoint_returns_update_info(self, mock_check, test_client):
        """Test the /api/updates/app-update endpoint."""
        mock_check.return_value = AppUpdateInfo(
            update_available=True,
            current_version="0.1.0",
            latest_version="1.0.0",
            release_url="https://example.com",
            release_notes="New features",
        )
        resp = test_client.get("/api/updates/app-update")
        assert resp.status_code == 200
        data = resp.json()
        assert data["update_available"] is True
        assert data["current_version"] == "0.1.0"
        assert data["latest_version"] == "1.0.0"


@pytest.fixture
def test_client():
    """FastAPI test client for the update endpoint."""
    from fastapi.testclient import TestClient

    from backend.main import create_app

    app = create_app()
    return TestClient(app)
