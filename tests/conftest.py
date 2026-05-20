"""Root-level pytest conftest — project-wide fixtures and markers."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from backend.config import Settings


def _java_available() -> bool:
    """Return True if a Java runtime is on PATH."""
    return shutil.which("java") is not None


def _real_lai_bundle_available() -> bool:
    """Return True if the production LAI bundle is present and validates locally.

    Used to auto-skip ``@pytest.mark.requires_real_bundle`` tests on dev
    machines and PR-blocking CI. The nightly slow-tier workflow (step 42)
    downloads the bundle into ``data_dir/lai_bundle/`` before invoking
    ``pytest -m slow``, at which point this returns True and the dormant
    tests execute.
    """
    try:
        from backend.config import get_settings
        from backend.db.database_registry import validate_lai_bundle
    except Exception:
        return False
    try:
        bundle_path = get_settings().resolved_lai_bundle_path
    except Exception:
        return False
    return validate_lai_bundle(bundle_path)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-skip tests whose runtime prerequisites are not present locally.

    - ``requires_java``: skipped when no Java runtime is on PATH.
    - ``requires_real_bundle``: skipped when the production LAI bundle is
      missing or fails validation (so the slow-tier tests stay dormant on
      every PR-blocking run and only activate inside the nightly workflow).
    """
    java_ok = _java_available()
    real_bundle_ok = _real_lai_bundle_available()
    skip_java = pytest.mark.skip(reason="Java runtime not available")
    skip_real_bundle = pytest.mark.skip(
        reason="Real production bundle not available (slow-tier nightly only)"
    )
    for item in items:
        if "requires_java" in item.keywords and not java_ok:
            item.add_marker(skip_java)
        if "requires_real_bundle" in item.keywords and not real_bundle_ok:
            item.add_marker(skip_real_bundle)


# ── Custom Markers ───────────────────────────────────────────────────


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers to avoid 'unknown marker' warnings."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m not slow')",
    )
    config.addinivalue_line("markers", "e2e: marks end-to-end tests")
    config.addinivalue_line("markers", "integration: marks integration tests")
    config.addinivalue_line(
        "markers",
        "requires_java: marks tests that need a real Java runtime (skipped when unavailable)",
    )
    config.addinivalue_line(
        "markers",
        "requires_real_bundle: marks tests that need the real production LAI/VEP "
        "bundle on disk (skipped when absent; consumed by the nightly slow-tier workflow)",
    )


# ── Project-wide Fixtures ────────────────────────────────────────────


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory mimicking ~/.genomeinsight layout.

    Creates the standard subdirectories (samples, downloads, logs) so that
    Settings and DBRegistry can operate without error.
    """
    (tmp_path / "samples").mkdir()
    (tmp_path / "downloads").mkdir()
    (tmp_path / "logs").mkdir()
    return tmp_path


@pytest.fixture
def test_settings(tmp_data_dir: Path) -> Settings:
    """Return a Settings instance pointing at the temporary data directory.

    WAL mode is disabled for in-memory / temp-file SQLite to avoid
    PRAGMA errors that do not apply to ephemeral databases.
    """
    return Settings(data_dir=tmp_data_dir, wal_mode=False)
