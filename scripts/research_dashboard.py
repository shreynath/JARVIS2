#!/usr/bin/env python3
"""Human research dashboard — evidence gaps without maturity changes."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.verification.data_acquisition_priority import compute_acquisition_priorities
from core.verification.evidence_collection import build_m4_readiness_dashboard


def _bar(pct: float, width: int = 10) -> str:
    filled = int(round(pct / 100.0 * width))
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def render_dashboard() -> str:
    dash = build_m4_readiness_dashboard()
    lines = [
        "JARVIS Validation Research Status",
        "=" * 30,
    ]

    rod = dash["models"]["rod_stress"]
    lines.extend(
        [
            "ROD STRESS",
            "M3 → M4",
            _bar(rod["progress_percent"]),
            f"Cases: {rod['cases']}",
            "Missing:",
        ]
    )
    for field in rod.get("missing") or []:
        lines.append(f"[X] {field.replace('_', ' ')}")

    lines.append("BMEP")
    for fam in dash["models"]["bmep"]["families"]:
        label = fam["family"].replace("_", " ").upper()
        if fam["family"] == "naturally_aspirated":
            label = "NA"
        lines.append(label)
        lines.append(_bar(fam["progress_percent"]))
        lines.append(f"{fam['cases']} cases")

    mat = dash["models"]["material_requirements"]["needed"][0]
    mat_pct = round(100.0 * mat["current"] / mat["target"], 1) if mat["target"] else 0
    lines.extend(
        [
            "MATERIALS",
            f"{mat['current']}/{mat['target']}",
            _bar(mat_pct),
        ]
    )

    lines.extend(["", "Top acquisition priorities:"])
    for row in compute_acquisition_priorities(top_n=5):
        lines.append(f"  {row['model']} ({row['priority']}) — {row['reason']}")

    return "\n".join(lines)


def main() -> None:
    print(render_dashboard())


if __name__ == "__main__":
    main()
