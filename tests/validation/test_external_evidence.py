"""Phase 9.0 — external evidence ingestion framework tests."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core.verification.evidence_audit import build_evidence_audit, write_evidence_audit
from core.verification.evidence_collection import (
    build_evidence_collection_plan,
    build_m4_readiness_dashboard,
    write_evidence_collection_plan,
)
from core.verification.evidence_pipeline import EvidenceValidationError, EvidenceValidator
from core.verification.evidence_quality import quality_score
from core.verification.evidence_source import EvidenceSource, SourceType
from core.verification.evidence_store import (
    APPROVED_DIR,
    PENDING_DIR,
    load_approved,
    load_pending,
    save_approved,
    save_pending,
)
from core.verification.importers.rod_importer import import_rod_dataset, write_rod_cases_json
from core.verification.model_maturity import ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY
from core.verification.raw_evidence import RawEvidenceRecord

FORBIDDEN = {"PhysicsEngine", "MaterialAssigner", "EngineeringEvaluator", "ConstraintEvaluator"}
INGESTION_PKG = Path(__file__).resolve().parents[2] / "core" / "verification"


def _forbidden_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if any(x in mod for x in ("physics_engine", "material_assigner", "constraint_evaluator")):
                hits.append(mod)
            for a in node.names:
                if a.name in FORBIDDEN:
                    hits.append(a.name)
    return hits


def _valid_record(**overrides) -> RawEvidenceRecord:
    base = dict(
        id="test_rec_001",
        component="connecting_rod",
        field="piston_mass_g",
        value=450.0,
        unit="g",
        source_id="src_honda_f20c",
        source_title="Honda OEM documentation",
        measurement_type="direct",
        quality="high",
        provenance={"source_type": SourceType.OEM_DOCUMENTATION.value, "engine": "Honda F20C"},
        uncertainty={"relative": 0.02},
        engine="Honda F20C",
        engine_id="honda_f20c",
    )
    base.update(overrides)
    return RawEvidenceRecord(**base)


@pytest.fixture(autouse=True)
def _isolate_evidence_store(tmp_path, monkeypatch):
    pending = tmp_path / "pending"
    approved = tmp_path / "approved"
    pending.mkdir()
    approved.mkdir()
    monkeypatch.setattr("core.verification.evidence_store.PENDING_DIR", pending)
    monkeypatch.setattr("core.verification.evidence_store.APPROVED_DIR", approved)
    monkeypatch.setattr("core.verification.evidence_store.STORE_ROOT", tmp_path)
    yield


# --- EvidenceSource ---------------------------------------------------------


def test_evidence_source_allowed_types():
    src = EvidenceSource(
        source_id="oem_f20c",
        title="Honda F20C service data",
        organization="Honda",
        source_type=SourceType.OEM_DOCUMENTATION,
    )
    assert src.source_type.value == "OEM_DOCUMENTATION"
    assert SourceType.SECONDARY_ESTIMATE in SourceType


def test_evidence_source_roundtrip():
    src = EvidenceSource(
        source_id="s1",
        title="T",
        organization="Org",
        source_type=SourceType.TEARDOWN_DATA,
        url_or_reference="https://example.com",
    )
    loaded = EvidenceSource.from_dict(src.to_dict())
    assert loaded.source_id == "s1"


# --- Raw evidence rejection -----------------------------------------------


def test_fake_synthetic_evidence_is_invalid():
    rec = _valid_record(measurement_type="synthetic")
    assert rec.is_invalid() is True


def test_missing_provenance_rejects():
    rec = _valid_record(provenance={})
    assert rec.rejects() is True


def test_missing_unit_rejects():
    rec = _valid_record(unit=None)
    assert rec.rejects() is True


def test_missing_uncertainty_rejects():
    rec = _valid_record(uncertainty={})
    assert rec.rejects() is True


def test_missing_source_rejects():
    rec = _valid_record(source_id="", source_title="")
    assert rec.rejects() is True


def test_valid_record_passes_structural_checks():
    rec = _valid_record()
    assert rec.is_invalid() is False


# --- Quality scoring --------------------------------------------------------


def test_oem_quality_highest():
    assert quality_score(source_type=SourceType.OEM_DOCUMENTATION, measurement_type="direct") == 1.0


def test_secondary_estimate_low_quality():
    assert quality_score(source_type=SourceType.SECONDARY_ESTIMATE, measurement_type="estimate") == 0.4


def test_unknown_quality_zero():
    assert quality_score(measurement_type="unknown", quality_label="unknown") == 0.0


def test_synthetic_quality_zero():
    assert quality_score(measurement_type="synthetic") == 0.0


# --- Pipeline ---------------------------------------------------------------


def test_pipeline_validates_good_record():
    rec = _valid_record()
    checklist = EvidenceValidator().validate_raw(rec)
    assert checklist["unit_present"] is True
    assert checklist["measurement_grade"] is True


def test_pipeline_rejects_estimate_masquerading():
    rec = _valid_record(
        measurement_type="estimate",
        provenance={"source_type": SourceType.SECONDARY_ESTIMATE.value},
    )
    with pytest.raises(EvidenceValidationError):
        EvidenceValidator().to_validation_case(rec)


def test_pipeline_produces_validation_case():
    rec = _valid_record()
    case = EvidenceValidator().to_validation_case(rec)
    assert case.id == rec.id
    assert case.measured_outputs["piston_mass_g"] == 450.0


def test_unit_mismatch_stroke_without_unit_fails():
    rec = _valid_record(field="stroke_mm", value=80, unit=None)
    with pytest.raises(EvidenceValidationError):
        EvidenceValidator().validate_raw(rec)


# --- Store / pending workflow -----------------------------------------------


def test_save_pending_does_not_auto_approve():
    rec = _valid_record()
    save_pending(rec)
    assert len(load_pending()) == 1
    assert len(load_approved()) == 0


def test_approved_record_can_validate():
    rec = _valid_record()
    save_approved(rec)
    assert len(load_approved()) == 1


# --- Importers --------------------------------------------------------------


def test_rod_importer_preserves_nulls(tmp_path: Path):
    csv_path = tmp_path / "rods.csv"
    csv_path.write_text(
        "engine,engine_id,rpm,stroke_mm,rod_length_mm,piston_mass_g,rod_mass_g,material,source,source_type\n"
        "Honda F20C,honda_f20c,9000,84,,,4340 steel,Honda OEM,OEM_DOCUMENTATION\n"
    )
    cases = import_rod_dataset(csv_path)
    assert len(cases) == 1
    assert cases[0].piston_mass_g is None
    assert cases[0].rod_length_mm is None


def test_rod_importer_with_mass_values(tmp_path: Path):
    csv_path = tmp_path / "rods2.csv"
    csv_path.write_text(
        "engine,engine_id,rpm,stroke_mm,rod_length_mm,piston_mass_g,rod_mass_g,material,source,source_type,measurement_type,quality,uncertainty_relative\n"
        "Honda F20C,honda_f20c,9000,84,138.6,450,512,steel,Honda OEM,OEM_DOCUMENTATION,direct,high,0.02\n"
    )
    cases = import_rod_dataset(csv_path, write_pending_fields=True)
    assert cases[0].piston_mass_g == 450.0
    assert len(load_pending()) >= 1


def test_write_rod_cases_json(tmp_path: Path):
    csv_path = tmp_path / "rods.csv"
    csv_path.write_text(
        "engine,engine_id,rpm,stroke_mm,rod_length_mm,piston_mass_g,rod_mass_g,material,source,source_type\n"
        "X,x,8000,80,,,,,ref,OEM_DOCUMENTATION\n"
    )
    cases = import_rod_dataset(csv_path)
    path = write_rod_cases_json(cases, tmp_path)
    assert path.exists()


# --- Collection plan / M4 dashboard -----------------------------------------


def test_evidence_collection_plan_shape():
    plan = build_evidence_collection_plan()
    assert plan["phase"] == "9.0"
    assert "rod_stress" in plan
    fields = {x["field"] for x in plan["rod_stress"]["needed"]}
    assert "piston_mass_g" in fields
    assert "rod_length_mm" in fields


def test_m4_readiness_dashboard():
    dash = build_m4_readiness_dashboard()
    assert dash["title"] == "M4 READINESS"
    assert dash["models"]["rod_stress"]["m4_eligible"] is False
    assert dash["histogram"]["M4"] == 0


def test_write_evidence_collection_plan(tmp_path: Path):
    path = write_evidence_collection_plan(tmp_path)
    assert path.name == "evidence_collection_plan.json"


# --- Audit ------------------------------------------------------------------


def test_evidence_audit_shape():
    audit = build_evidence_audit()
    assert "datasets" in audit
    assert audit["promotion_eligible_cases"] == 0


def test_write_evidence_audit(tmp_path: Path):
    path = write_evidence_audit(tmp_path)
    data = json.loads(path.read_text())
    assert data["phase"] == "9.0"


# --- Maturity isolation -----------------------------------------------------


def test_maturity_histogram_unchanged_after_ingestion():
    before = {m.name: 0 for m in ModelMaturity}
    for d in MODEL_REGISTRY.values():
        before[d.maturity.name] += 1
    rec = _valid_record()
    save_pending(rec)
    save_approved(rec)
    after = {m.name: 0 for m in ModelMaturity}
    for d in MODEL_REGISTRY.values():
        after[d.maturity.name] += 1
    assert before == after
    assert before == {"M0": 3, "M1": 1, "M2": 9, "M3": 10, "M4": 0, "M5": 0}


def test_registry_before_equals_registry_after_pipeline():
    before_ids = {k: v.maturity for k, v in MODEL_REGISTRY.items()}
    rec = _valid_record()
    EvidenceValidator().to_validation_case(rec)
    after_ids = {k: v.maturity for k, v in MODEL_REGISTRY.items()}
    assert before_ids == after_ids


# --- Import isolation -------------------------------------------------------


def test_ingestion_modules_no_physics_engine():
    for name in (
        "evidence_pipeline.py",
        "evidence_audit.py",
        "evidence_collection.py",
        "raw_evidence.py",
        "importers/rod_importer.py",
    ):
        path = INGESTION_PKG / name
        hits = _forbidden_imports(path)
        assert not hits, f"{name}: {hits}"


def test_bmep_importer_preserves_null_torque(tmp_path: Path):
    from core.verification.importers.bmep_importer import import_bmep_rows

    csv_path = tmp_path / "bmep.csv"
    csv_path.write_text("engine_id,rpm,hp,torque_nm,displacement_l,source\nx,8000,400,,4.0,ref\n")
    rows = import_bmep_rows(csv_path)
    assert rows[0]["torque_nm"] is None


def test_material_importer_queues_pending(tmp_path: Path):
    from core.verification.importers.material_importer import import_material_rows

    csv_path = tmp_path / "mat.csv"
    csv_path.write_text(
        "id,component,property,value,unit,source,source_id,source_type,measurement_type,quality,uncertainty_relative\n"
        "m1,connecting_rod,yield_strength_mpa,710,MPa,Honda OEM,src1,OEM_DOCUMENTATION,direct,high,0.02\n"
    )
    rows = import_material_rows(csv_path)
    assert len(rows) == 1
    assert len(load_pending()) == 1


def test_rod_field_targets_show_zero_mass_progress():
    plan = build_evidence_collection_plan()
    piston = next(x for x in plan["rod_stress"]["needed"] if x["field"] == "piston_mass_g")
    assert piston["current"] == 0
    assert piston["target"] == 10


def test_pending_not_counted_as_validated_in_audit():
    save_pending(_valid_record())
    audit = build_evidence_audit()
    assert audit["pending_review"] >= 1
    assert audit["promotion_eligible_cases"] == 0
