"""Phase 8.8 material evidence campaign — property-backed decisions."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from knowledge.materials.catalog import MATERIAL_CATALOG

CASES_DIR = Path(__file__).resolve().parent / "cases"


@dataclass(frozen=True)
class MaterialValidationCase:
    component: str
    material: str
    yield_strength_mpa: float | None
    fatigue_strength_mpa: float | None
    temperature_limit_c: float | None
    application: str
    engine: str
    source: str
    confidence: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_material_cases() -> list[MaterialValidationCase]:
    cases: list[MaterialValidationCase] = []
    for path in sorted(CASES_DIR.glob("*.json")):
        raw = json.loads(path.read_text())
        cases.append(
            MaterialValidationCase(
                component=str(raw["component"]),
                material=str(raw["material"]),
                yield_strength_mpa=raw.get("yield_strength_mpa"),
                fatigue_strength_mpa=raw.get("fatigue_strength_mpa"),
                temperature_limit_c=raw.get("temperature_limit_c"),
                application=str(raw.get("application") or ""),
                engine=str(raw.get("engine") or ""),
                source=str(raw.get("source") or ""),
                confidence=str(raw.get("confidence") or "low"),
            )
        )
    return cases


def build_auditable_material_decision(
    *,
    component: str,
    required_yield_mpa: float,
    required_fatigue_mpa: float,
    required_temp_c: float,
    density_priority: bool,
    candidate_keys: list[str],
    comparable_engines: int,
) -> dict[str, Any]:
    """Structured decision packet (load → requirement → candidates → reject → select)."""
    rankings = []
    selected = None
    for key in candidate_keys:
        entry = MATERIAL_CATALOG[key]
        y = float(entry.get("yield_strength_mpa") or 0)
        f = float(entry.get("fatigue_strength_mpa") or 0)
        t = float(entry.get("temperature_limit_c") or 0)
        dens = float(entry.get("density_kg_m3") or 0)
        ok = y >= required_yield_mpa and f >= required_fatigue_mpa and t >= required_temp_c
        rejected_property = None
        if not ok:
            margins = {
                "yield": y / required_yield_mpa if required_yield_mpa else 0,
                "fatigue": f / required_fatigue_mpa if required_fatigue_mpa else 0,
                "temperature": t / required_temp_c if required_temp_c else 0,
            }
            rejected_property = min(margins, key=margins.get)  # type: ignore[arg-type]
        rankings.append(
            {
                "key": key,
                "name": entry["name"],
                "hard_constraints_met": ok,
                "density_kg_m3": dens,
                "rejected_property": rejected_property,
            }
        )
    feasible = [r for r in rankings if r["hard_constraints_met"]]
    if density_priority and feasible:
        feasible.sort(key=lambda r: r["density_kg_m3"])
        selected = feasible[0]
        for alt in feasible[1:]:
            alt["rejected_property"] = alt.get("rejected_property") or "density_mass_penalty"
            alt["reject_reason"] = (
                f"Feasible but higher density than {selected['name']} "
                f"({alt['density_kg_m3']} vs {selected['density_kg_m3']} kg/m³)"
            )
    elif feasible:
        selected = feasible[0]

    return {
        "component": component,
        "requirement": {
            "yield_mpa": required_yield_mpa,
            "fatigue_mpa": required_fatigue_mpa,
            "temperature_c": required_temp_c,
            "density_priority": density_priority,
        },
        "candidates": rankings,
        "rejected": [
            r
            for r in rankings
            if selected is None or r["name"] != selected["name"]
        ],
        "selected": None if selected is None else selected["name"],
        "evidence": {
            "comparable_engines": comparable_engines,
            "catalog": "knowledge.materials.catalog",
        },
        "format": "requirement → candidates → reject → select",
    }


def build_material_campaign_report() -> dict[str, Any]:
    cases = load_material_cases()
    # Example high-RPM rod decision audit (synthetic requirement from Phase pipeline numbers)
    decision = build_auditable_material_decision(
        component="connecting_rod",
        required_yield_mpa=650.0,
        required_fatigue_mpa=300.0,
        required_temp_c=150.0,
        density_priority=True,
        candidate_keys=["forged_steel_4340", "ti_6al4v"],
        comparable_engines=len(cases),
    )
    return {
        "phase": "8.8",
        "campaign": "material_validation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cases": [c.to_dict() for c in cases],
        "case_count": len(cases),
        "example_auditable_decision": decision,
        "models": [
            {
                "model": "material_req_structural",
                "current": "M2",
                "target": "M4",
                "upgrade_recommendation": (
                    "NOT M4 eligible — external component population still sparse; "
                    "decision format upgraded but predictive material map incomplete"
                ),
            },
            {
                "model": "material_req_piston",
                "current": "M2",
                "target": "M4",
                "upgrade_recommendation": "NOT M4 eligible — need measured piston alloy population ≥10",
            },
        ],
        "policy": "No catalog-habit selections. Every decision needs load-backed requirements.",
    }


def build_material_maturity_packet(report: dict[str, Any] | None = None) -> dict[str, Any]:
    report = report or build_material_campaign_report()
    return {
        "phase": "8.8",
        "eligible_for_upgrade": False,
        "eligible_models": [],
        "case_count": report.get("case_count"),
        "blocked_reason": "Comparable-engine material observations < predictive M4 threshold",
        "example_decision_present": "example_auditable_decision" in report,
        "models": report.get("models"),
    }


def write_material_campaign_reports(output_dir: Path | str) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = build_material_campaign_report()
    packet = build_material_maturity_packet(report)
    paths = {
        "validation": out / "material_validation_report.json",
        "maturity": out / "material_maturity_packet.json",
    }
    paths["validation"].write_text(json.dumps(report, indent=2, default=str))
    paths["maturity"].write_text(json.dumps(packet, indent=2, default=str))
    return paths
