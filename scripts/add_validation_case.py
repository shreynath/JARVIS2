#!/usr/bin/env python3
"""Interactive evidence intake — saves pending review only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.verification.evidence_source import SourceType
from core.verification.evidence_store import save_pending
from core.verification.raw_evidence import RawEvidenceRecord


def _prompt(text: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}\n> ").strip()
    if not value and default is not None:
        return default
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="JARVIS evidence intake")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--model", default="rod_stress")
    parser.add_argument("--source-type", default="OEM_DOCUMENTATION")
    parser.add_argument("--engine", default="")
    parser.add_argument("--engine-id", default="")
    parser.add_argument("--field", default="")
    parser.add_argument("--value", default="")
    parser.add_argument("--unit", default="g")
    parser.add_argument("--confidence", default="high")
    args = parser.parse_args()

    print("JARVIS Evidence Intake")
    print("======================")

    if args.non_interactive:
        model = args.model
        source_type = args.source_type
        engine = args.engine or args.engine_id or "unknown"
        engine_id = args.engine_id or engine.lower().replace(" ", "_")
        field = args.field
        value_raw = args.value
        unit = args.unit
        confidence = args.confidence
        source_title = f"{engine} {source_type}"
    else:
        model = _prompt("Model", args.model)
        source_type = _prompt("Source type", args.source_type)
        engine = _prompt("Engine")
        engine_id = _prompt("Engine id", engine.lower().replace(" ", "_"))
        field = _prompt("Field", args.field or "piston_mass_g")
        value_raw = _prompt("Value")
        unit = _prompt("Unit", args.unit)
        confidence = _prompt("Confidence", args.confidence)
        source_title = _prompt("Source title / reference")

    try:
        SourceType(source_type)
    except ValueError:
        raise SystemExit(f"Invalid source_type: {source_type}")

    rec_id = f"{engine_id}_{field}_pending"
    try:
        numeric: float | str = float(value_raw)
    except ValueError:
        numeric = value_raw

    record = RawEvidenceRecord(
        id=rec_id,
        component=model.replace("_stress", "").replace("_", " "),
        field=field,
        value=numeric,
        unit=unit,
        source_id=f"src_{engine_id}",
        source_title=source_title if not args.non_interactive else f"{engine} {source_type}",
        measurement_type="direct",
        quality=confidence,
        provenance={
            "source_type": source_type,
            "engine": engine,
            "engine_id": engine_id,
            "intake": "add_validation_case.py",
        },
        uncertainty={"relative": 0.02},
        engine=engine,
        engine_id=engine_id,
    )

    path = save_pending(record)
    print(f"Saved as pending review: {path}")
    print(json.dumps({"status": "pending_review", "id": rec_id}, indent=2))


if __name__ == "__main__":
    main()
