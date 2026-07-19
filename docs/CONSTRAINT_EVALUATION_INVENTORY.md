# ConstraintEvaluation Inventory (Fix 1 Deliverable)

Every hard engineering constraint in the codebase flows through
`ConstraintEvaluation` and is aggregated exclusively by
`validation/constraint_evaluator.py` → `ValidationReport.hard_violations`.

| # | Source | Location | How it emits ConstraintEvaluation | Status |
|---|--------|----------|-----------------------------------|--------|
| 1 | Physics calculation pass/fail | `core/reasoning/physics_engine.py` → `PhysicsCalculation.passes` | `ConstraintEvaluator._from_physics_calculations` — `passes=False` → `severity=hard_limit` | Wired |
| 2 | Physics-derived material yield requirement | `PhysicsAnalysis.constraints` type `minimum_yield_strength` | `ConstraintEvaluator._from_physics_constraints` vs `material_spec.yield_strength_mpa` | Wired |
| 3 | Physics-derived material temperature requirement | `PhysicsAnalysis.constraints` type `minimum_temperature_limit` | `ConstraintEvaluator._from_physics_constraints` vs `material_spec.temperature_limit_c` | Wired |
| 4 | Material catalog thermal limits | component `Constraint` type `maximum_temperature` | `ConstraintEvaluator._from_component_thermal_limits` (combustion-exposed parts only) | Wired |
| 5 | Material suitability keyword rules | `knowledge/engineering_rules/material_suitability.py` | `ConstraintEvaluator._from_material_suitability` | Wired |
| 6 | Implausible premise parameters | `RequirementSpecification.implausible_parameters` | `SemanticKernelPipeline._premise_evaluations` → collected as `extra` | Wired |
| 7 | Synthetic / injected evaluations | unit tests / future subsystems | `ConstraintEvaluator.collect(..., extra=[...])` | Wired |

## What the validator does NOT do anymore

- It does **not** special-case `calc_mean_piston_speed` in `PhysicsRulesEngine`.
- It does **not** iterate `constraint_graph.nodes` independently of ConstraintEvaluation
  for hard-violation counting.
- It does **not** count `physics_analysis.calculations[].passes` directly.

Future subsystems (fatigue, bearing load, torsional resonance, lubrication pressure)
must emit `ConstraintEvaluation` instances. No new validator special-cases are required.
