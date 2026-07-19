# JARVIS 2.0 — Phase 2 Package Architecture

**Status:** EngineeringEvaluator façade implemented (`docs/PHASE2_ENGINEERING_EVALUATOR_DIRECTIVE.md`).  
Search / mutations / Pareto remain unimplemented.  
**Date:** 2026-07-19  
**Directive:** Phase 1 Closure Directive 6 + Phase 2 Evaluator Directive  
**Companion:** `docs/PHASE2_ARCHITECTURE.md`, `docs/EPISTEMOLOGY_MIGRATION.md`, `docs/PHASE2_ENGINEERING_EVALUATOR_DIRECTIVE.md`

---

## 1. Approved layout

```
core/
├── ir/                 # Phase 1 — keep (graphs, constraints, requirements, materials IR)
├── ontology/           # Phase 1 — keep
├── reasoning/          # Phase 1 — keep (PhysicsEngine, MaterialAssigner, pipeline, …)
├── candidates/         # Phase 2 — CandidateDesign and free/fixed parameter types
├── evaluation/         # Phase 2 — EngineeringEvaluator, EvaluationResult, ObjectiveScore
├── search/             # Phase 2 — ParetoArchive, EngineeringStateGraph, MutationCatalog, loop
└── epistemology/       # Phase 2 — Evidence, KnowledgeState (shared; see migration plan)
```

**Names are locked as above.** Alternative spellings (`eval/` vs `evaluation/`) were rejected to keep import paths self-explanatory.

**Separation is non-negotiable:**

| Package | Owns | Must not own |
|---------|------|--------------|
| `candidates/` | Design proposals + parameter split | Physics formulas, scoring, search frontier |
| `evaluation/` | Single façade that turns a candidate into inspectable results | Search policies, mutation choice |
| `search/` | Archive, state graph, mutations, next-candidate policy | Direct calls to PhysicsEngine / MaterialAssigner |
| `epistemology/` | Shared Evidence + KnowledgeState | Objectives, candidates, mutations |

Phase 1 `core/reasoning/` remains the home of engines. Phase 2 evaluation **calls into** reasoning; it does not relocate PhysicsEngine into `evaluation/`.

---

## 2. Import rules (locked)

```
search  ──►  evaluation  ──►  reasoning / ir / epistemology
                │
                └──► candidates (input type only)

candidates  ──►  ir, epistemology   (no import of search or evaluation)

epistemology  ──►  (stdlib / pydantic only)   # zero upward deps

reasoning     ──►  ir, ontology, epistemology (after Evidence migration)
                  # never imports search or candidates
```

**Critical rule:** `search` must **never** import or call `PhysicsEngine`, `MaterialAssigner`, or `ConstraintEvaluator` directly. The only legal path is:

```
CandidateDesign → EngineeringEvaluator.evaluate(candidate) → EvaluationResult
```

---

## 3. Module contents (planned — not created)

### `core/candidates/`

| Symbol | Role |
|--------|------|
| `CandidateDesign` | id, requirement_spec_id, fixed_parameters, free_parameters, status |
| Parameter helpers | freeze resolved requirements; expose searchable free vars |

### `core/evaluation/`

| Symbol | Role |
|--------|------|
| `EngineeringEvaluator` | **First Phase 2 code written.** Façade: physics → materials → constraint eval → objective vector |
| `EvaluationResult` | constraint_evaluations, hard_violation_count, objective_vector, evidence rollup |
| `ObjectiveScore` | one objective’s value/range/direction + Evidence |
| Objective scorers | pure functions of EvaluationResult inputs (added after Evidence migration) |

### `core/search/`

| Symbol | Role |
|--------|------|
| `EngineeringStateGraph` / `DesignStateNode` | search memory |
| `MutationCatalog` / `MutationRecord` | operators + rationale bindings |
| `ParetoArchive` | non-dominated set |
| Search loop | proposes next candidate from archive/state only |

### `core/epistemology/`

| Symbol | Role |
|--------|------|
| `KnowledgeState` | final enum per `docs/EPISTEMOLOGY_MIGRATION.md` |
| `Evidence` | shared provenance type |
| Helpers | rollup (`weakest` knowledge_state, `min` confidence), str→float legacy converters (temporary) |

After migration, Phase 1 `physics_engine.KnowledgeState` is **deleted** and re-exported or replaced by `core.epistemology.KnowledgeState` so only one enum exists.

---

## 4. Implementation order (informational — not this run)

When Phase 2 coding is eventually authorized:

1. **`EngineeringEvaluator` façade** (empty → wires existing Phase 1 pipeline pieces per candidate)
2. `CandidateDesign`
3. `EvaluationResult`
4. Evidence migration (code) per `docs/EPISTEMOLOGY_MIGRATION.md`
5. Objective scorers
6. Engineering State Graph
7. Mutation catalog
8. Pareto archive
9. Search loop

Do not start at step 6–9. Do not create empty package `__init__.py` files before step 1 is authorized.

---

## 5. Relationship to existing docs

| Document | Authority |
|----------|-----------|
| This file | Package boundaries + import rules + first-code confirmation |
| `PHASE2_ARCHITECTURE.md` | Behavioral pipeline, objectives, Pareto, explainability |
| `EPISTEMOLOGY_MIGRATION.md` | KnowledgeState / Confidence / Evidence field semantics |

If `PHASE2_ARCHITECTURE.md` Section 8 epistemology text conflicts with the migration plan, **the migration plan wins**.

---

## 6. Explicit confirmation (Directive 6 + Section 8)

- [x] Layout above is the **approved** package architecture (human sign-off 2026-07-19).
- [x] **First Phase 2 implementation code will be `EngineeringEvaluator`** in `core/evaluation/`.
- [x] No search / candidate / mutation code before that façade exists.
- [x] This deliverable creates **zero** new Python packages or stub files.
