"""Dataset importers — CSV/external rows into validation cases via evidence pipeline."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from core.verification.datasets.rod_validation.case import RodValidationCase
from core.verification.evidence_pipeline import EvidenceValidationError, EvidenceValidator
from core.verification.evidence_source import SourceType
from core.verification.evidence_store import save_pending
from core.verification.raw_evidence import RawEvidenceRecord

REQUIRED_ROD_COLUMNS = (
    "engine",
    "engine_id",
    "rpm",
    "stroke_mm",
    "rod_length_mm",
    "piston_mass_g",
    "rod_mass_g",
    "material",
    "source",
    "source_type",
)


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "na", "n/a", ""}:
        return None
    try:
        return float(text)
    except ValueError:
        # Non-numeric text in a numeric column stays unknown — never coerced.
        return None


def _row_to_rod_case(row: dict[str, str]) -> RodValidationCase:
    """Build RodValidationCase — nulls preserved, never invented."""
    return RodValidationCase(
        engine_name=str(row.get("engine") or row.get("engine_id") or ""),
        engine_id=str(row.get("engine_id") or ""),
        rpm=_parse_float(row.get("rpm")),
        stroke_mm=_parse_float(row.get("stroke_mm")),
        rod_length_mm=_parse_float(row.get("rod_length_mm")),
        piston_mass_g=_parse_float(row.get("piston_mass_g")),
        rod_mass_g=_parse_float(row.get("rod_mass_g")),
        bore_mm=_parse_float(row.get("bore_mm")),
        reported_component_data={
            "material": row.get("material"),
            "source_type": row.get("source_type"),
        },
        source=str(row.get("source") or ""),
        confidence=str(row.get("confidence") or "missing_masses"),
    )


def import_rod_dataset(
    csv_path: Path | str,
    *,
    write_pending_fields: bool = False,
) -> list[RodValidationCase]:
    """Import rod CSV. Per-field raw evidence may be queued as pending review."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row")
        missing_cols = [c for c in ("engine", "source") if c not in reader.fieldnames]
        if missing_cols:
            raise ValueError(f"CSV missing required columns: {missing_cols}")
        cases: list[RodValidationCase] = []
        for i, row in enumerate(reader):
            case = _row_to_rod_case(row)
            cases.append(case)
            if write_pending_fields:
                _maybe_queue_rod_fields(case, row, index=i)
        return cases


def _maybe_queue_rod_fields(case: RodValidationCase, row: dict[str, str], *, index: int) -> None:
    """Queue non-null measured fields as pending raw evidence (not validated until review)."""
    source_type = str(row.get("source_type") or SourceType.OEM_DOCUMENTATION.value)
    for field, unit in (
        ("piston_mass_g", "g"),
        ("rod_mass_g", "g"),
        ("rod_length_mm", "mm"),
        ("stroke_mm", "mm"),
    ):
        val = getattr(case, field)
        if val is None:
            continue
        rec = RawEvidenceRecord(
            id=f"{case.engine_id}_{field}_{index:03d}",
            component="connecting_rod",
            field=field,
            value=val,
            unit=unit,
            source_id=str(row.get("source_id") or case.engine_id),
            source_title=case.source,
            measurement_type=str(row.get("measurement_type") or "direct"),
            quality=str(row.get("quality") or "high"),
            provenance={
                "source_type": source_type,
                "engine": case.engine_name,
                "engine_id": case.engine_id,
                "importer": "rod_importer",
            },
            uncertainty={"relative": float(row.get("uncertainty_relative") or 0.02)},
            engine=case.engine_name,
            engine_id=case.engine_id,
        )
        if not rec.rejects():
            save_pending(rec)


def import_bmep_rows(csv_path: Path | str) -> list[dict[str, Any]]:
    """Import BMEP family rows — returns dict rows; nulls preserved."""
    path = Path(csv_path)
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows: list[dict[str, Any]] = []
        for row in reader:
            out = dict(row)
            for key in ("rpm", "hp", "torque_nm", "displacement_l"):
                out[key] = _parse_float(row.get(key))
            rows.append(out)
        return rows


def import_material_rows(csv_path: Path | str) -> list[RawEvidenceRecord]:
    """Import material property rows as pending raw evidence."""
    path = Path(csv_path)
    records: list[RawEvidenceRecord] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader):
            prop = str(row.get("property") or row.get("field") or "")
            rec = RawEvidenceRecord(
                id=str(row.get("id") or f"material_{i:03d}"),
                component=str(row.get("component") or "unknown"),
                field=prop,
                value=_parse_float(row.get("value")),
                unit=row.get("unit"),
                source_id=str(row.get("source_id") or "unknown"),
                source_title=str(row.get("source") or ""),
                measurement_type=str(row.get("measurement_type") or "direct"),
                quality=str(row.get("quality") or "medium"),
                provenance={
                    "source_type": row.get("source_type") or SourceType.OEM_DOCUMENTATION.value,
                    "engine": row.get("engine"),
                    "importer": "material_importer",
                },
                uncertainty={
                    "relative": float(row.get("uncertainty_relative") or 0.05),
                },
                engine=row.get("engine"),
                engine_id=row.get("engine_id"),
            )
            records.append(rec)
            if not rec.rejects():
                save_pending(rec)
    return records


def write_rod_cases_json(cases: list[RodValidationCase], output_dir: Path | str) -> Path:
    """Write imported rod cases for inspection — does not overwrite campaign cases automatically."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "imported_rod_cases.json"
    path.write_text(json.dumps([c.to_dict() for c in cases], indent=2, default=str))
    return path
