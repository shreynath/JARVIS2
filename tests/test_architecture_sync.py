"""ARCHITECTURE.md must list every top-level and core/ subpackage."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_architecture_sync_passes():
    script = ROOT / "scripts" / "check_architecture_sync.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_architecture_sync_fails_on_omission(tmp_path):
    arch = tmp_path / "ARCHITECTURE.md"
    arch.write_text("# Empty\n")
    script = ROOT / "scripts" / "check_architecture_sync.py"
    result = subprocess.run(
        [sys.executable, str(script), "--arch", str(arch)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "does not reference" in result.stderr
