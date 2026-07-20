#!/usr/bin/env python3
"""Fail if repo packages are missing from ARCHITECTURE.md (Phase D enforcement).

Usage:
  python scripts/check_architecture_sync.py
  python scripts/check_architecture_sync.py --arch ARCHITECTURE.md

Exits 0 when every required top-level package and ``core/`` subpackage is
referenced in the architecture doc; exits 1 with a list of omissions.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Directories at repo root that are code/runtime packages and MUST appear in ARCHITECTURE.md.
REQUIRED_TOP_LEVEL = (
    "core",
    "knowledge",
    "llm",
    "validation",
    "verification",
    "datasets",
    "examples",
    "scripts",
    "tests",
)

# Immediate subpackages under core/ (directory names).
REQUIRED_CORE_SUBPACKAGES = (
    "candidates",
    "engineering",
    "epistemology",
    "evaluation",
    "ir",
    "materials",
    "ontology",
    "reasoning",
    "verification",
)

# Root dirs ignored (not product subsystems).
IGNORE_TOP_LEVEL = {
    ".git",
    ".benchmarks",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "output",
    "docs",
}


def _discovered_top_level() -> set[str]:
    found: set[str] = set()
    for entry in ROOT.iterdir():
        if not entry.is_dir():
            continue
        if entry.name in IGNORE_TOP_LEVEL or entry.name.startswith("."):
            continue
        found.add(entry.name)
    return found


def _discovered_core_subpackages() -> set[str]:
    core = ROOT / "core"
    if not core.is_dir():
        return set()
    subs: set[str] = set()
    for entry in core.iterdir():
        if entry.is_dir() and not entry.name.startswith(".") and entry.name != "__pycache__":
            subs.add(entry.name)
    return subs


def _referenced(text: str, *needles: str) -> bool:
    lower = text.lower()
    return any(n.lower() in lower for n in needles)


def check(arch_path: Path) -> list[str]:
    """Return list of error messages (empty = pass)."""
    if not arch_path.is_file():
        return [f"Architecture doc not found: {arch_path}"]

    text = arch_path.read_text(encoding="utf-8")
    errors: list[str] = []

    for pkg in REQUIRED_TOP_LEVEL:
        actual = ROOT / pkg
        if not actual.is_dir():
            errors.append(f"Expected top-level package missing on disk: {pkg}/")
            continue
        if not _referenced(text, f"{pkg}/", f"├── {pkg}", f"│   ├── {pkg}", pkg):
            errors.append(f"ARCHITECTURE.md does not reference top-level package: {pkg}/")

    for sub in REQUIRED_CORE_SUBPACKAGES:
        actual = ROOT / "core" / sub
        if not actual.is_dir():
            errors.append(f"Expected core subpackage missing on disk: core/{sub}/")
            continue
        if not _referenced(
            text,
            f"core/{sub}",
            f"core/{sub}/",
            f"├── {sub}/",
            f"│   ├── {sub}/",
            sub,
        ):
            errors.append(f"ARCHITECTURE.md does not reference core subpackage: core/{sub}/")

    # Warn on unexpected new top-level dirs (not in REQUIRED and not ignored).
    discovered = _discovered_top_level()
    allowed = set(REQUIRED_TOP_LEVEL) | IGNORE_TOP_LEVEL
    undocumented = sorted(discovered - allowed)
    for pkg in undocumented:
        errors.append(
            f"Undocumented top-level directory '{pkg}/' — add to ARCHITECTURE.md "
            f"or IGNORE_TOP_LEVEL in scripts/check_architecture_sync.py if intentional"
        )

    core_discovered = _discovered_core_subpackages()
    core_allowed = set(REQUIRED_CORE_SUBPACKAGES) | {"__pycache__"}
    undocumented_core = sorted(core_discovered - core_allowed)
    for sub in undocumented_core:
        errors.append(
            f"Undocumented core/ subpackage '{sub}/' — add core/{sub}/ to ARCHITECTURE.md"
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ARCHITECTURE.md lists all packages.")
    parser.add_argument(
        "--arch",
        type=Path,
        default=ROOT / "ARCHITECTURE.md",
        help="Path to ARCHITECTURE.md",
    )
    args = parser.parse_args()
    errors = check(args.arch)
    if errors:
        print("ARCHITECTURE sync check FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(f"ARCHITECTURE sync OK — all packages referenced in {args.arch.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
