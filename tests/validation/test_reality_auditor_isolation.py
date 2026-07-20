"""Reality auditor must not import PhysicsEngine."""

from __future__ import annotations

import ast
from pathlib import Path


def test_reality_auditor_source_has_no_physics_engine_import():
    path = Path(__file__).resolve().parents[2] / "verification" / "reality_auditor.py"
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "physics_engine" not in mod
            assert all(a.name != "PhysicsEngine" for a in node.names)
        if isinstance(node, ast.Import):
            assert all("physics_engine" not in a.name for a in node.names)


def test_reality_audit_entrypoint_has_no_physics_engine_import():
    path = Path(__file__).resolve().parents[2] / "reality_audit.py"
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "physics_engine" not in mod
            assert all(a.name != "PhysicsEngine" for a in node.names)
