"""Phase 8 — maturity advancement framework (evidence-gated, no auto-upgrade)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.verification.evidence_registry import (
    EVIDENCE_REQUIREMENTS,
    attempt_upgrade,
    blocking_evidence_for,
    evidence_registry_snapshot,
)
from core.verification.maturity_campaigns import (
    run_all_campaigns,
    run_campaign_a_high_rpm,
    run_campaign_b_reciprocating,
    run_campaign_c_thermal,
    write_campaign_report,
)
from core.verification.maturity_planner import (
    NEAR_TERM_TARGET_BANDS,
    build_maturity_roadmap,
    research_roi,
    write_maturity_roadmap,
)
from core.verification.maturity_scorecard import (
    build_maturity_scorecard,
    write_maturity_scorecard,
)
from core.verification.model_maturity import (
    MaturityUpgradeEvidence,
    MaturityValidationError,
    ModelMaturity,
    assert_upgrade_allowed,
    evaluate_m1_to_m2_upgrade,
    evaluate_m2_to_m3_upgrade,
    evaluate_upgrade,
)
from core.verification.model_registry import MODEL_REGISTRY
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider


BASELINE = "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
LOCKED = {"M0": 3, "M1": 1, "M2": 9, "M3": 10, "M4": 0, "M5": 0}


def _hist() -> dict[str, int]:
    counts = {m.name: 0 for m in ModelMaturity}
    for d in MODEL_REGISTRY.values():
        counts[d.maturity.name] += 1
    return counts


# --- Anti-inflation / regression protection ---------------------------------


def test_maturity_cannot_increase_without_evidence():
    """Attempt combustion_temperature-style leap M1→M4 must fail."""
    with pytest.raises(MaturityValidationError, match="blocked"):
        attempt_upgrade(
            "calc_combustion_side_temperature",
            ModelMaturity.M1,
            ModelMaturity.M4,
            MaturityUpgradeEvidence(),
        )
    assert MODEL_REGISTRY["calc_combustion_side_temperature"].maturity is ModelMaturity.M3


def test_maturity_cannot_skip_levels_even_with_m4_packet():
    full_m4 = MaturityUpgradeEvidence(
        external_validation_cases=10,
        mean_error_documented=True,
        uncertainty_documented=True,
        independent_verifier_exists=True,
    )
    with pytest.raises(MaturityValidationError, match="cannot_skip|blocked"):
        attempt_upgrade(
            "mean_piston_speed_hard_limit",
            ModelMaturity.M1,
            ModelMaturity.M4,
            full_m4,
        )


def test_m1_to_m2_requires_documented_assumptions_ranges_refs():
    empty = evaluate_m1_to_m2_upgrade(MaturityUpgradeEvidence())
    assert empty["allowed"] is False
    assert "assumptions_documented" in empty["missing"]
    ok = evaluate_m1_to_m2_upgrade(
        MaturityUpgradeEvidence(
            assumptions_documented=True,
            uncertainty_range_documented=True,
            references_documented=True,
        )
    )
    assert ok["allowed"] is True


def test_m2_to_m3_requires_external_error_failure():
    bad = evaluate_m2_to_m3_upgrade(MaturityUpgradeEvidence())
    assert bad["allowed"] is False
    good = evaluate_m2_to_m3_upgrade(
        MaturityUpgradeEvidence(
            external_comparison_exists=True,
            error_characterization_exists=True,
            failure_analysis_exists=True,
        )
    )
    assert good["allowed"] is True


def test_attempt_upgrade_never_mutates_registry():
    before = MODEL_REGISTRY["connecting_rod_model"].maturity
    with pytest.raises(MaturityValidationError):
        attempt_upgrade(
            "connecting_rod_model",
            ModelMaturity.M3,
            ModelMaturity.M4,
            MaturityUpgradeEvidence(external_validation_cases=2),
        )
    assert MODEL_REGISTRY["connecting_rod_model"].maturity is before


def test_m3_to_m4_still_requires_ten_cases():
    with pytest.raises(MaturityValidationError):
        assert_upgrade_allowed(
            from_maturity=ModelMaturity.M3,
            to_maturity=ModelMaturity.M4,
            evidence=MaturityUpgradeEvidence(
                external_validation_cases=9,
                mean_error_documented=True,
                uncertainty_documented=True,
                independent_verifier_exists=True,
            ),
        )


def test_phase8_histogram_locked_no_silent_m4():
    assert _hist() == LOCKED
    assert MODEL_REGISTRY["connecting_rod_model"].maturity is ModelMaturity.M3
    # Phase 8.5 Campaign A explicit promotions.
    assert MODEL_REGISTRY["calc_torque"].maturity is ModelMaturity.M3


# --- Evidence registry / planner --------------------------------------------


def test_evidence_requirements_cover_campaign_targets():
    models = {r.model for r in EVIDENCE_REQUIREMENTS}
    assert "connecting_rod_model" in models
    assert "engine_cycle_model" in models
    assert "calc_combustion_side_temperature" in models


def test_blocking_evidence_nonempty_for_rod_m4():
    blocking = blocking_evidence_for("connecting_rod_model")
    assert any("benchmark" in b or "load" in b or "external" in b for b in blocking)


def test_roadmap_lists_missing_evidence_not_auto_upgrades():
    road = build_maturity_roadmap()
    assert road["phase"] == "8.0"
    assert road["current_histogram"] == LOCKED
    assert road["roadmap"]
    rod = next(r for r in road["roadmap"] if r["model"] == "connecting_rod_model")
    assert rod["current"] == "M3"
    assert rod["next"] == "M4"
    assert rod["blocking_evidence"]
    assert "automatic" not in json.dumps(road).lower() or road["policy"]


def test_near_term_bands_keep_m5_at_zero():
    assert NEAR_TERM_TARGET_BANDS["M5"] == (0, 0)
    assert NEAR_TERM_TARGET_BANDS["M4"][0] >= 2


def test_research_roi_penalizes_low_impact():
    high = research_roi(
        impact_weight=4.0, uncertainty=3.0, dependency_count=5.0, maturity_gap=2.0
    )
    low = research_roi(
        impact_weight=1.0, uncertainty=1.0, dependency_count=1.0, maturity_gap=1.0
    )
    assert high > low


def test_bmep_has_high_upgrade_roi_relative_to_placeholder():
    road = build_maturity_roadmap()
    by_id = {r["model"]: r["upgrade_value_roi"] for r in road["roadmap"]}
    assert by_id["engine_cycle_model"] > by_id["eq_oil_flow"]
    assert by_id["connecting_rod_model"] > by_id["packaging"]


def test_write_maturity_roadmap(tmp_path: Path):
    path = write_maturity_roadmap(tmp_path)
    data = json.loads(path.read_text())
    assert data["roadmap"]


def test_evidence_registry_snapshot_policy():
    snap = evidence_registry_snapshot()
    assert "No automatic" in snap["policy"] or "automatic" in snap["policy"].lower()


# --- Scorecard --------------------------------------------------------------


def test_maturity_scorecard_shape():
    card = build_maturity_scorecard()
    assert 0.0 <= card["overall_maturity"] <= 5.0
    assert card["highest_confidence_models"]
    assert card["largest_risk_models"]
    assert card["best_upgrade_candidates"]
    assert card["m4_count"] == 0
    assert card["m5_count"] == 0
    assert "impact" in card["roi_formula"]


def test_write_maturity_scorecard(tmp_path: Path):
    path = write_maturity_scorecard(tmp_path)
    assert path.name == "maturity_scorecard.json"
    data = json.loads(path.read_text())
    assert "overall_maturity" in data


# --- Campaigns --------------------------------------------------------------


def test_campaign_a_high_rpm_usable_cases():
    report = run_campaign_a_high_rpm()
    assert report["usable_cases"] >= 5
    assert report["error_characterized"] is True
    assert "mutate" in report["policy"].lower() or "not" in report["policy"].lower()


def test_campaign_a_does_not_claim_m4_ready():
    report = run_campaign_a_high_rpm()
    assert any("M4" in b or "m4" in b.lower() for b in report["blocking_for_m4"])


def test_campaign_b_rod_not_m4_ready():
    report = run_campaign_b_reciprocating()
    assert report["m4_ready"] is False
    assert "absolute_load_benchmark" in report["blocking_evidence"]


def test_campaign_c_thermal_blocks_inflation():
    report = run_campaign_c_thermal()
    assert report["m4_ready"] is False
    assert "UNVALIDATED" in report["current_status"]["combustion_temperature"]


def test_all_campaigns_zero_auto_upgrades():
    report = run_all_campaigns()
    assert report["automatic_upgrades_applied"] == 0
    assert set(report["campaigns"]) == {"A_high_rpm", "B_reciprocating", "C_thermal"}


def test_write_campaign_report(tmp_path: Path):
    path = write_campaign_report(tmp_path)
    data = json.loads(path.read_text())
    assert data["phase"] == "8.0"


# --- Baseline regression ----------------------------------------------------


def test_phase8_baseline_unchanged():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(BASELINE)
    assert abs(result.physics_analysis.by_id("calc_torque").result - 633.0) < 0.5
    mps = result.physics_analysis.by_id("calc_mean_piston_speed")
    assert mps.passes is False
    assert abs(max(mps.value_range) - 26.68) < 0.05
    assert result.validation_report.hard_violations == 1


def test_evaluate_upgrade_same_maturity_noop():
    result = evaluate_upgrade(
        from_maturity=ModelMaturity.M3,
        to_maturity=ModelMaturity.M3,
        evidence=MaturityUpgradeEvidence(),
    )
    assert result["allowed"] is True


def test_roadmap_priority_field_present():
    rod = next(
        r for r in build_maturity_roadmap()["roadmap"] if r["model"] == "connecting_rod_model"
    )
    assert rod["priority"] in {"very_high", "high", "medium", "low"}
