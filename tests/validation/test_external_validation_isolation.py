"""Phase 6 — external validation cases must not import production models."""

from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN = {
    "PhysicsEngine",
    "MaterialAssigner",
    "ConstraintEvaluator",
    "EngineeringEvaluator",
}
PACKAGE = Path(__file__).resolve().parents[2] / "core" / "verification" / "datasets"


def _imports_forbidden(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(f in alias.name for f in ("physics_engine", "material_assigner", "engineering_evaluator")):
                    hits.append(alias.name)
                if alias.name.split(".")[-1] in FORBIDDEN:
                    hits.append(alias.name)
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if any(x in mod for x in ("physics_engine", "material_assigner", "evaluation.engineering", "constraint_evaluator")):
                hits.append(mod)
            for a in node.names:
                if a.name in FORBIDDEN:
                    hits.append(f"{mod}.{a.name}")
    return hits


def test_dataset_package_files_exist():
    for name in ("schemas.py", "registry.py", "validation_case.py", "sources.py", "__init__.py"):
        assert (PACKAGE / name).exists(), name


def test_dataset_package_has_no_production_imports():
    for path in PACKAGE.glob("*.py"):
        hits = _imports_forbidden(path)
        assert not hits, f"{path.name} imports forbidden symbols: {hits}"


def test_calibration_module_has_no_physics_engine_import():
    path = Path(__file__).resolve().parents[2] / "core" / "verification" / "calibration.py"
    hits = _imports_forbidden(path)
    assert not hits, hits
