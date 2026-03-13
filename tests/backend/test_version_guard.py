"""Tests for the Python version guard in backend/__init__.py."""

import subprocess
import sys
from pathlib import Path


def test_version_guard_passes_on_current_python():
    """The guard should not raise on the current (>= 3.12) interpreter."""
    result = subprocess.run(
        [sys.executable, "-c", "import backend"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_version_guard_message_content(tmp_path):
    """The guard message should contain the required elements."""
    script = tmp_path / "check.py"
    script.write_text(
        "import unittest.mock, sys\n"
        "with unittest.mock.patch.object(sys, 'version_info', (3, 11, 0, 'final', 0)):\n"
        "    exec(open('backend/__init__.py').read())\n"
    )
    project_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    assert result.returncode == 1
    assert "Python >= 3.12" in result.stderr
    assert "3.11.0" in result.stderr
    assert "README" in result.stderr
