"""Continuity sweeps — catch physics jumps and categorical field flips."""

from __future__ import annotations

from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider

HOLD_HP = 500
HOLD_RPM = 7000
CATEGORICAL_FIELDS = ("mass_sensitive", "material", "source")


def _rod_metrics(result) -> dict:
    rods = result.graph.components["connecting_rods"]
    metrics = rods.material_spec.selection_metrics if rods.material_spec else {}
    pa = result.physics_analysis

    def c(cid: str):
        calc = pa.by_id(cid)
        assert calc is not None, f"missing {cid}"
        assert calc.confidence, f"{cid} lost confidence"
        assert calc.value_range is not None or calc.result is not None
        return calc.result

    return {
        "torque": c("calc_torque"),
        "displacement": c("calc_displacement"),
        "stroke": c("calc_stroke"),
        "mps": c("calc_mean_piston_speed"),
        "acceleration": c("calc_piston_acceleration"),
        "rod_loading": c("calc_rod_loading"),
        "rod_stress": c("calc_rod_stress_requirement"),
        "req_yield": metrics.get("required_yield_mpa"),
        "mass_sensitive": metrics.get("mass_sensitive"),
        "material": rods.material,
        "source": metrics.get("source"),
    }


def _assert_no_categorical_flips(rows: list[dict], label: str) -> None:
    issues: list[str] = []
    for i in range(1, len(rows)):
        prev, cur = rows[i - 1], rows[i]
        for field in CATEGORICAL_FIELDS:
            if prev[field] != cur[field]:
                # material may change only with a numeric threshold crossing on req_yield
                if field == "material":
                    ry0, ry1 = prev["req_yield"], cur["req_yield"]
                    crossed = False
                    if ry0 is not None and ry1 is not None:
                        for thresh in (710.0, 880.0):  # catalog steel / titanium yields
                            if (ry0 - thresh) * (ry1 - thresh) <= 0 and ry0 != ry1:
                                crossed = True
                    if crossed:
                        continue
                issues.append(
                    f"{label} step {i}: categorical '{field}' flipped "
                    f"{prev[field]!r} → {cur[field]!r} without explainable threshold"
                )
    assert not issues, "\n".join(issues)


def test_mass_sensitive_is_role_stable_across_rpm_sweep():
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    rows = []
    for rpm in range(5000, 13001, 500):
        result = pipeline.run(
            f"Design a {rpm} RPM naturally aspirated V8 producing {HOLD_HP} horsepower."
        )
        rows.append(_rod_metrics(result))

    # Role property: reciprocating rods are always mass-sensitive.
    assert all(row["mass_sensitive"] is True for row in rows), [
        (i, row["mass_sensitive"]) for i, row in enumerate(rows)
    ]
    _assert_no_categorical_flips(rows, "rpm_sweep")


def test_mass_sensitive_is_role_stable_across_hp_sweep():
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    rows = []
    for hp in range(200, 901, 100):
        result = pipeline.run(
            f"Design a {HOLD_RPM} RPM naturally aspirated V8 producing {hp} horsepower."
        )
        rows.append(_rod_metrics(result))

    # Role property stays true whenever a computed material assignment exists.
    assigned = [row for row in rows if row["material"] is not None]
    assert assigned, "expected at least one HP point with qualifying rod material"
    assert all(row["mass_sensitive"] is True for row in assigned)
    # req_yield must move continuously while materials are assigned
    yields = [row["req_yield"] for row in assigned]
    assert all(yields[i] < yields[i + 1] for i in range(len(yields) - 1)), yields
    _assert_no_categorical_flips(assigned, "hp_sweep")


def test_every_thermal_hard_limit_appears_in_constraint_evaluations():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )
    thermal_ids = []
    for comp in result.graph.components.values():
        for constraint in comp.constraints:
            if constraint.type == "maximum_temperature" and constraint.severity.value == "hard_limit":
                thermal_ids.append(constraint.id)

    assert len(thermal_ids) >= 8, thermal_ids
    eval_ids = {e.id for e in result.validation_report.constraint_evaluations}
    missing = [cid for cid in thermal_ids if f"eval_{cid}" not in eval_ids]
    assert not missing, f"thermal hard_limits missing from evaluations: {missing}"

    unvalidated = [
        e
        for e in result.validation_report.constraint_evaluations
        if e.source == "unvalidated_hard_limit"
    ]
    assert unvalidated, "expected unvalidated_hard_limit evaluations for components without operating temp"
    assert result.validation_report.unvalidated_hard_limits == len(unvalidated)
    assert any(i.category == "unvalidated_hard_limit" for i in result.validation_report.issues)
