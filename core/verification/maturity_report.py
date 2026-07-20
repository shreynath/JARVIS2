"""Model-maturity reporting — audits, summaries, upgrade priorities, progress."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.verification.model_maturity import MATURITY_RANK, ModelMaturity
from core.verification.model_registry import (
    MODEL_REGISTRY,
    all_descriptors,
    registry_coverage,
)

_IMPACT_WEIGHT = {"CRITICAL": 4.0, "HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0}
# Target sophistication for gap scoring (never claim today's models are M5).
_TARGET_RANK = MATURITY_RANK[ModelMaturity.M4]
_RELEASE_LABEL = "phase4.5"


def model_maturity_report() -> dict[str, Any]:
    """Per-model maturity audit rows."""
    models = []
    for desc in sorted(all_descriptors(), key=lambda d: d.id):
        models.append(
            {
                "model": desc.id,
                "owner": desc.owner,
                "equation": desc.equation_id,
                "maturity": desc.maturity.name,
                "maturity_label": desc.maturity.value,
                "validation_status": desc.validation_status,
                "independent_verifier": desc.independently_verified,
                "benchmark_coverage": desc.benchmarked,
                "production_validated": desc.production_validated,
                "published_reference": desc.engineering_reference,
                "known_limitations": desc.known_limitations,
                "impact": desc.impact,
                "subsystem": desc.subsystem,
            }
        )
    return {
        "phase": "4.5",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_count": len(models),
        "models": models,
        "coverage": registry_coverage(),
    }


def model_maturity_summary() -> dict[str, Any]:
    """Histogram of maturity levels across the registry."""
    counts = {m.name: 0 for m in ModelMaturity}
    for desc in all_descriptors():
        counts[desc.maturity.name] += 1
    ranks = [MATURITY_RANK[d.maturity] for d in all_descriptors()]
    avg = sum(ranks) / len(ranks) if ranks else 0.0
    return {
        "phase": "4.5",
        "counts": counts,
        "distribution": [
            {"maturity": name, "label": ModelMaturity[name].value, "count": counts[name]}
            for name in counts
        ],
        "average_maturity_rank": round(avg, 3),
        "average_maturity": _rank_to_label(avg),
        "model_count": len(ranks),
    }


def model_upgrade_priorities() -> dict[str, Any]:
    """Highest-impact, lowest-maturity models first (impact × maturity deficit)."""
    priorities = []
    for desc in all_descriptors():
        rank = MATURITY_RANK[desc.maturity]
        deficit = max(0, _TARGET_RANK - rank)
        if deficit <= 0:
            continue
        impact_w = _IMPACT_WEIGHT.get(desc.impact, 2.0)
        score = impact_w * deficit
        priority = desc.impact if desc.impact in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} else "MEDIUM"
        if priority == "CRITICAL":
            priority = "VERY_HIGH"
        priorities.append(
            {
                "model": desc.id,
                "maturity": desc.maturity.name,
                "maturity_label": desc.maturity.value,
                "impact": desc.impact,
                "maturity_deficit": deficit,
                "priority_score": score,
                "priority": priority,
                "owner": desc.owner,
                "subsystem": desc.subsystem,
                "known_limitations": desc.known_limitations,
            }
        )
    priorities.sort(key=lambda r: (-r["priority_score"], r["model"]))
    return {
        "phase": "4.5",
        "scoring": "impact_weight × (M4_target_rank − current_rank); label mirrors impact",
        "target_maturity": "M4",
        "priorities": priorities,
        "priority_count": len(priorities),
    }


def model_progress(*, append_to: Path | None = None) -> dict[str, Any]:
    """Initialize or append average-maturity history for this release."""
    summary = model_maturity_summary()
    entry = {
        "release": _RELEASE_LABEL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "average_maturity_rank": summary["average_maturity_rank"],
        "average_maturity": summary["average_maturity"],
        "counts": summary["counts"],
        "model_count": summary["model_count"],
    }

    history: list[dict[str, Any]] = []
    if append_to is not None and append_to.exists():
        try:
            existing = json.loads(append_to.read_text())
            history = list(existing.get("history") or [])
        except (json.JSONDecodeError, OSError):
            history = []

    # Replace same-release entry if re-run; otherwise append.
    history = [h for h in history if h.get("release") != _RELEASE_LABEL]
    history.append(entry)
    history.sort(key=lambda h: h.get("timestamp") or "")

    return {
        "phase": "4.5",
        "note": "Phase 4.5 initializes trend tracking; future phases append.",
        "history": history,
        "current": entry,
    }


def maturity_audit_slice() -> dict[str, Any]:
    """Compact maturity statistics for reality_audit.json integration."""
    summary = model_maturity_summary()
    by_subsystem: dict[str, list[int]] = {}
    for desc in all_descriptors():
        by_subsystem.setdefault(desc.subsystem, []).append(MATURITY_RANK[desc.maturity])

    subsystem_maturity = {
        name: {
            "average_rank": round(sum(ranks) / len(ranks), 3),
            "average_maturity": _rank_to_label(sum(ranks) / len(ranks)),
            "model_count": len(ranks),
            "weakest": min(ranks),
            "strongest": max(ranks),
        }
        for name, ranks in sorted(by_subsystem.items())
    }

    all_ranks = [MATURITY_RANK[d.maturity] for d in all_descriptors()]
    weakest_models = [
        {"model": d.id, "maturity": d.maturity.name, "subsystem": d.subsystem}
        for d in all_descriptors()
        if MATURITY_RANK[d.maturity] == min(all_ranks)
    ]
    strongest_models = [
        {"model": d.id, "maturity": d.maturity.name, "subsystem": d.subsystem}
        for d in all_descriptors()
        if MATURITY_RANK[d.maturity] == max(all_ranks)
    ]

    return {
        "average_maturity_rank": summary["average_maturity_rank"],
        "average_maturity": summary["average_maturity"],
        "maturity_distribution": summary["counts"],
        "subsystem_maturity": subsystem_maturity,
        "weakest_maturity": min(all_ranks) if all_ranks else None,
        "strongest_maturity": max(all_ranks) if all_ranks else None,
        "weakest_models": weakest_models,
        "strongest_models": strongest_models,
        "engineering_confidence_note": (
            "Confidence (epistemic) and model_maturity (sophistication) are independent."
        ),
        "coverage": registry_coverage(),
    }


def write_maturity_artifacts(output_dir: Path | str) -> dict[str, Path]:
    """Write all Phase 4.5 maturity JSON artifacts under output/."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    payloads = {
        "model_maturity_report.json": model_maturity_report(),
        "model_maturity_summary.json": model_maturity_summary(),
        "model_upgrade_priorities.json": model_upgrade_priorities(),
    }
    progress_path = out / "model_progress.json"
    payloads["model_progress.json"] = model_progress(append_to=progress_path)

    for name, payload in payloads.items():
        path = out / name
        path.write_text(json.dumps(payload, indent=2, default=str))
        paths[name] = path
    return paths


def _rank_to_label(avg: float) -> str:
    """Map fractional average rank to nearest maturity name."""
    nearest = min(ModelMaturity, key=lambda m: abs(MATURITY_RANK[m] - avg))
    return nearest.name
