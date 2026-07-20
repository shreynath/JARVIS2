# JARVIS 2.0 — Architecture (reconciled 2026-07-19)

## Project identity (explicit — pick one, not both)

**JARVIS2 is a domain-general engineering semantic kernel.** Natural-language requests
are parsed into typed intents and design graphs across multiple engineering domains.
**ICE (internal combustion engine) depth** — `core/engineering/`, BMEP/rod/maturity
campaigns under `core/verification/` — is the **reference-domain implementation** that
proves the rigor pattern (cited formulas, units, explicit uncertainty).

Generality status (evidence-backed, not aspirational):

| Claim | Status | Evidence |
|-------|--------|----------|
| Distinct non-ICE `object_type` on live LLM | **Proven** | `docs/domain_generality_report.md` — 10/10 Phase B requests |
| Domain-conditional physics dispatch | **Implemented** | `core/reasoning/domain_dispatch.py` — ICE physics not unconditional |
| Second full-depth non-ICE physics module | **Implemented (reference)** | Phase F — `core/reasoning/bridge_physics_engine.py`, `docs/phase_e_f_remediation_report.md` |
| Structural material completeness bar | **Implemented** | Phase E — `core/materials/structural_completeness.py` gates `EvaluationStatus.COMPLETE` |

Non-ICE quantitative physics exists for **truss bridges** at the same rigor pattern as ICE (cited
formulas, units, assumptions, equation catalog). Other domains remain design-graph valid with
honest INCOMPLETE when structural materials cannot be evidence-gated.

---

## Problem statement

JARVIS1 accumulated capable subsystems without a **central object** every layer understood.
JARVIS2's spine is the **Engineering Semantic Kernel**: NL → validated
`EngineeringDesignGraph`, with honest degradation labels and verification provenance.

## Design goal

Convert a natural-language engineering request into a **validated, machine-readable
engineering design graph** — not a PDF, not CAD, not a simulation.

```
Natural Language Request
        ↓
EngineeringIntent
        ↓
RequirementSpecification + FunctionalAnalysis
        ↓
EngineeringDesignGraph
        ↓
PhysicsAnalysis (domain-dispatched) + MaterialAssigner
        ↓
ValidationReport (with verification_checks provenance)
```

## Central object: EngineeringDesignGraph

Every subsystem reads from or writes to `EngineeringDesignGraph`.

| Layer | Package | Responsibility | Modifies graph? |
|-------|---------|----------------|-----------------|
| Ontology | `core/ontology/` | Vocabulary: entities, relationships, taxonomy | No (schema) |
| IR | `core/ir/` | Typed Pydantic graph structures | Defines shape |
| Reasoning | `core/reasoning/` | Intent → decomposition → physics → materials → validation orchestration | Yes |
| Engineering models | `core/engineering/` | ICE reference physics (cited formulas) | No (feeds analysis) |
| Epistemology | `core/epistemology/` | Evidence, knowledge state, input requirements | No (provenance) |
| Evaluation | `core/evaluation/` | Phase 2 `EngineeringEvaluator` firewall | No (orchestrates Phase 1) |
| Candidates | `core/candidates/` | `CandidateDesign` input for evaluator/search | No |
| Materials | `core/materials/` | Component roles, evidence-gated selection | Yes (assignments) |
| Verification | `core/verification/` | Model maturity, evidence store, external campaigns | No (metadata) |
| Validation | `validation/` | Graph invariant checking post-build | Reports only |
| Verification (audit) | `verification/` | JSON-only reality audit, formula recompute | No (reads output/) |
| LLM | `llm/` | Ollama transport + structured JSON | No |
| Knowledge | `knowledge/` | Seed templates, materials, equations | No (read-mostly) |

---

## Repository layout (enforced)

Every top-level package and every `core/` subpackage below **must** appear in this
table when present on disk. CI runs `python scripts/check_architecture_sync.py`.

### Top-level

| Path | Layer | One-line responsibility |
|------|-------|-------------------------|
| `core/` | Kernel | All semantic-kernel Python packages |
| `knowledge/` | Knowledge | Domain templates, materials catalog, equations, rules |
| `llm/` | Transport | Ollama client, env loader, prompts, structured output |
| `validation/` | Validation | Schema, consistency, physics warnings, constraint aggregation |
| `verification/` | External audit | Formula validator, units audit, reality auditor (JSON-only) |
| `datasets/` | Data | Reference engines and submission templates for campaigns |
| `examples/` | Examples | Runnable demos (e.g. engine generation) |
| `scripts/` | Tooling | Validation runners, promotion scripts, architecture sync check |
| `tests/` | Tests | Unit, integration, domain generality, adversarial validators |
| `main.py` | CLI | NL entry point → pipeline → `output/` |
| `docs/` | Docs | Phase reports, directives (not a runtime subsystem) |

### `core/` subpackages

| Path | Responsibility |
|------|----------------|
| `core/candidates/` | Minimal `CandidateDesign` for Phase 2 evaluator input |
| `core/engineering/` | ICE physics models (cycle, thermal, rod, geometry) — reference domain |
| `core/epistemology/` | `Evidence`, `KnowledgeState`, assumption registry |
| `core/evaluation/` | `EngineeringEvaluator`, `EvaluationResult`, evaluation status |
| `core/ir/` | `EngineeringDesignGraph`, intent, constraints, requirement spec |
| `core/materials/` | `ComponentRole` registry, material requirement typing |
| `core/ontology/` | Entity/relationship enums, `EngineeringTaxonomy` |
| `core/reasoning/` | Pipeline, intent parser, decomposition, physics dispatch, material assigner |
| `core/verification/` | Maturity registry, evidence pipeline, BMEP/rod/material campaigns |

---

## Reasoning pipeline (`core/reasoning/`)

Live path (`SemanticKernelPipeline`):

1. **IntentParser** — NL → `EngineeringIntent` (LLM + taxonomy safety net)
2. **RequirementCompiler** — intent → `RequirementSpecification` (ICE decisions only for ICE types)
3. **FunctionalDecompositionEngine** — functions/assemblies before parts
4. **DecompositionEngine** — LLM architect + component templates
5. **Physics** — `_run_physics()` via `domain_dispatch` (ICE `PhysicsEngine` only when ICE)
6. **MaterialAssigner** — catalog assignment or explicit unassigned flag
7. **DesignCritic** + **DesignEngineer** — rule + LLM review/repair
8. **Validation** — schema → consistency → physics rules → constraint evaluations

**Provider policy:** Option-1 transparent degraded mode. If Ollama is unreachable, CLI may use
`DeterministicProvider` but must surface `provider_used`, `degraded`, and `warning` on every
output surface. `DeterministicProvider` is a **test fixture**, not a product interpreter.

---

## Validation vs verification

| Term | Package | Kind | Meaning |
|------|---------|------|---------|
| Validation | `validation/` | Mostly `self_consistency_check` | Graph/schema/internal rule coherence |
| Verification | `core/verification/`, `verification/` | `externally_verified` where noted | Datasets, evidence, independent formula recompute |

`ValidationReport.verification_checks[]` stamps each validator with `verification_kind`.
Words **validated** / **verified** in user-facing status are reserved for external ground
truth — not for LLM self-review. See `docs/verification_integrity_report.md`.

Validators: `SchemaValidator`, `ConsistencyChecker`, `PhysicsRulesEngine`, `ConstraintEvaluator`.
Adversarial tests: `tests/validator_adversarial/`.

---

## LLM (`llm/`)

- `OllamaClient` — local or cloud (`OLLAMA_HOST`, `OLLAMA_API_KEY`)
- `env_loader.py` — loads gitignored `.env`
- `prompts/` — intent, functional, architect, critic, engineer
- `DeterministicProvider` — CI fixture only (see above)

---

## Knowledge (`knowledge/`)

Seed data and domain packs — not a persistent graph DB.

| Subpath | Contents |
|---------|----------|
| `knowledge/decomposition/` | Component templates (ICE, turbofan, gearbox, + Phase B domains) |
| `knowledge/functional/` | Functional templates + `general_domains.py` |
| `knowledge/materials/` | Material catalog |
| `knowledge/equations/` | Equation provenance catalog |
| `knowledge/engineering_rules/` | Material suitability rules |
| `knowledge/requirements/` | ICE requirement decision templates |
| `knowledge/systems/`, `components/` | ICE taxonomy seeds |

Adding a domain: extend `knowledge/functional/` + `knowledge/decomposition/`; optional
physics handler via `domain_dispatch.register_physics_handler` — no pipeline fork required.

---

## Phase 2 evaluator (`core/evaluation/`)

`EngineeringEvaluator.evaluate(candidate)` is the single engineering truth entry for
search/optimization (future). It orchestrates the Phase 1 pipeline via `Phase1Provider`.
Search must not call physics engines directly.

---

## Model maturity & evidence (`core/verification/`)

Orthogonal to design-graph validation. Tracks engineering **model sophistication** (M0–M5),
external evidence ingestion, and campaign eligibility (rod, BMEP, material, high-RPM).

- Campaigns **never auto-promote** maturity — only `scripts/promote_model_maturity.py`
- Failures preserved: evidence `rejected/` store, campaign `failure_modes` in JSON
- Canary: `tests/validator_adversarial/test_maturity_canary.py`

---

## External audit (`verification/`)

JSON-only tools that must not import `PhysicsEngine`:

- `formula_validator.py` — recompute torque, MPS, etc. from calc inputs
- `reality_auditor.py` — maturity slice, benchmark cross-checks
- `units.py` — dimensional audit

---

## Data flow (CLI)

```
main.py
  └─ SemanticKernelPipeline.run(user_input)
        ├─ IntentParser → RequirementCompiler
        ├─ FunctionalDecompositionEngine → DecompositionEngine
        ├─ domain_dispatch._run_physics (ICE or skip)
        ├─ MaterialAssigner
        ├─ Critic → Engineer
        └─ SchemaValidator + ConsistencyChecker + PhysicsRulesEngine + ConstraintEvaluator
  └─ write output/
        ├─ engine_design_graph.json
        ├─ requirement_specification.json
        ├─ physics_analysis.json
        ├─ validation_report.json  (+ verification_checks)
        ├─ pipeline_status.json    (+ provider_used / degraded)
        └─ assumptions.json
```

---

## What this repo does NOT do (yet)

- CAD generation, FEM meshing, visualization dashboards
- Agent orchestration / autonomous multi-step agents
- Persistent knowledge graph storage (still seed files under `knowledge/`)
- Non-ICE quantitative physics for domains beyond truss bridges (chair, bike, HVAC, etc.)

## What changed from early “Phase 1 only” docs

These **exist today** and are no longer “Month N future”:

- Material assignment (`MaterialAssigner`, `core/materials/`)
- Requirement compilation (`RequirementSpecification`)
- Functional decomposition before parts
- Full `core/verification/` maturity/evidence subsystem
- Phase 2 `EngineeringEvaluator`
- Multi-domain intent/decomposition (Phase B evidence)

---

## Testing strategy

1. What abstraction does this modify?
2. What new concept does it introduce?
3. Which layer does it belong to?
4. What test proves it works?

| Suite | Purpose |
|-------|---------|
| `tests/` | Unit + integration (DeterministicProvider for CI) |
| `tests/domain_generality_suite.py` | Live LLM domain generality (`JARVIS_LIVE_LLM=1`) |
| `tests/validator_adversarial/` | Each validator rejects ≥3 broken fixtures |
| `tests/validation/` | Evidence isolation, maturity gates, formula regression |
| `scripts/check_architecture_sync.py` | ARCHITECTURE.md matches disk layout |

Run architecture sync before merge:

```bash
python scripts/check_architecture_sync.py
```

---

## Extension roadmap

| Milestone | Adds | Reads from |
|-----------|------|------------|
| Phase F | Non-ICE physics module (truss bridge) at ICE rigor | `domain_dispatch`, `knowledge/equations/` | **Done** — see `docs/phase_e_f_remediation_report.md` |
| Phase E | Structural material completeness bar across domains | `MaterialAssigner`, ontology roles | **Done** — gates COMPLETE on structural materials |
| Future | Persistent knowledge graph | Ontology + IR |
| Future | Constraint solver / search loop | `EngineeringEvaluator`, `core/candidates/` |
| Future | CAD/FEM bridge | Validated `EngineeringDesignGraph` |
