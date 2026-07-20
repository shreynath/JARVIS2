# Phase E/F Remediation Report

## Phases: E + F

### Claim

1. **Phase E — Structural material completeness bar:** `EvaluationStatus.COMPLETE` is blocked when any ontology-registered structural/load-bearing component lacks an evidence-gated material assignment.
2. **Phase F — Truss bridge physics at ICE rigor:** A second full-depth non-ICE physics module computes cited deck moment and truss member stress with explicit assumptions, equation provenance, and domain dispatch registration.
3. Non-ICE structural roles, catalog entries, and `MaterialAssigner` pathways support bridge truss members (and register chair/bike structural IDs for honest incompleteness until their physics modules exist).

### Evidence

#### E1 — Completeness gate

- `core/materials/structural_completeness.py` — `unassigned_structural_components()`, `structural_materials_complete()`
- `core/reasoning/pipeline.py` — validation calls `mark_incomplete()` when structural members lack materials
- `core/materials/component_role.py` — explicit `STRUCTURAL_LOAD_PATH` registry extended for bridge chords, bike tubes, chair legs
- `knowledge/materials/catalog.py` — `structural_steel_astm_a572`, `al_6061_t6`, `hardwood_oak`

```
$ python -m pytest tests/test_structural_completeness.py -q
........                                                                 [100%]
8 passed
```

Chair pipeline (no non-ICE furniture physics) stays **INCOMPLETE** when registered structural IDs are present and unassigned.

#### F1 — Bridge physics module

- `core/engineering/truss_bridge_model.py` — `TrussBridgeModel` with Hibbeler-cited beam/truss identities + `AssumptionRegistry`
- `core/reasoning/bridge_physics_engine.py` — `analyze_bridge()` → `calc_bridge_deck_moment`, `calc_truss_member_stress`
- `core/reasoning/domain_dispatch.py` — `BRIDGE_OBJECT_TYPES`, lazy handler registration
- `knowledge/equations/catalog.py` — `eq_bridge_deck_moment`, `eq_truss_member_stress` + `CALC_TO_EQUATION` mappings
- `core/verification/model_registry.py` — maturity descriptors for both bridge calculations

```
$ python -m pytest tests/test_bridge_physics_engine.py -q
....                                                                     [100%]
4 passed
```

Span extraction for bridge prompts:

```
$ python -c "
from core.ir.design_graph import EngineeringIntent
from core.reasoning.requirement_compiler import RequirementCompiler
intent = EngineeringIntent(object_type='steel_truss_bridge', design_goal='span', raw_input='design a steel truss bridge spanning 40 meters')
spec = RequirementCompiler().compile(intent)
print(spec.resolved_parameters.get('span_m'))
"
40.0
```

Material assignment from computed truss stress:

```
$ python -m pytest tests/test_structural_completeness.py::test_bridge_truss_members_assigned_when_physics_computed -q
.                                                                        [100%]
1 passed
```

#### Regression

```
$ python -m pytest tests/test_structural_completeness.py tests/test_bridge_physics_engine.py tests/validator_adversarial/ tests/test_architecture_sync.py tests/test_phase_a_remediation.py -q
70 passed
```

### Known gaps

- **Chair / bicycle / furniture physics not implemented** — structural IDs are registered; without computed stress pathways materials stay unassigned and status remains INCOMPLETE (honest).
- **Bridge model is order-of-magnitude** — live load, truss depth, and member area use ASSUMED bands; `validation_status=FORMULA_VERIFIED_PARAMETERS_ASSUMED`, not externally benchmarked against AASHTO case studies.
- **Decomposition variance** — DeterministicProvider may not always emit registered structural component IDs for every domain prompt; gate applies only to components present in the graph.
- **No live LLM re-run** for bridge physics in this phase — unit/integration tests use deterministic compilation paths.
