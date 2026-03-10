"""Tests for backend.config module."""

from pathlib import Path

from backend.config import Settings, get_settings


def test_default_settings():
    """Settings should load with sensible defaults."""
    settings = get_settings()
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.debug is False
    assert settings.wal_mode is True
    assert settings.auth_enabled is False
    assert settings.theme == "system"
    assert settings.log_level == "INFO"
    assert settings.update_check_interval == "daily"


def test_data_dir_default():
    """Default data_dir should be ~/.genomeinsight."""
    settings = get_settings()
    assert settings.data_dir == Path.home() / ".genomeinsight"


def test_derived_paths():
    """Derived paths should be relative to data_dir."""
    settings = Settings(data_dir=Path("/tmp/gi-test"))
    assert settings.samples_dir == Path("/tmp/gi-test/samples")
    assert settings.downloads_dir == Path("/tmp/gi-test/downloads")
    assert settings.resolved_log_dir == Path("/tmp/gi-test/logs")
    assert settings.reference_db_path == Path("/tmp/gi-test/reference.db")
    assert settings.vep_bundle_db_path == Path("/tmp/gi-test/vep_bundle.db")
    assert settings.gnomad_db_path == Path("/tmp/gi-test/gnomad_af.db")
    assert settings.dbnsfp_db_path == Path("/tmp/gi-test/dbnsfp.db")


def test_env_override(monkeypatch):
    """Environment variables should override defaults."""
    monkeypatch.setenv("GENOMEINSIGHT_PORT", "9000")
    monkeypatch.setenv("GENOMEINSIGHT_DEBUG", "true")
    settings = Settings()
    assert settings.port == 9000
    assert settings.debug is True
