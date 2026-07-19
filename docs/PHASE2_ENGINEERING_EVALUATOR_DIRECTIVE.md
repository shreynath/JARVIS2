# JARVIS 2.0 — Phase 2 EngineeringEvaluator Directive

**Status:** Implementation authorized for this scope only.  
**Date:** 2026-07-19  
**Depends on:** Phase 1 closed; `docs/EPISTEMOLOGY_MIGRATION.md` (revised claim-context Evidence); `docs/PHASE2_PACKAGE_ARCHITECTURE.md`

---

## Objective

Create the Phase 2 **firewall**: all engineering truth for a candidate flows through one entry point.

```
CandidateDesign
       │
       ▼
EngineeringEvaluator.evaluate(candidate)
       │
       ├──► PhysicsEngine          (Phase 1 — unchanged)
       ├──► MaterialAssigner       (Phase 1 — unchanged)
       ├──► ConstraintEvaluator    (Phase 1 — unchanged)
       │
       ▼
EvaluationResult
```

**Do not implement in this directive:** search, mutations, Pareto, objective scorers, optimization loop, candidate generation/mutation catalogs.

---

## Governing rules (non-negotiable)

1. **Never decide; derive, evaluate, optimize later.** No RPM/HP/temperature “sanity ceilings.” Reject only when a *derived* requirement cannot be satisfied (or inputs are structurally uncomputable).
2. **Search must never call engines directly.** Future search may only call `EngineeringEvaluator`.
3. **No parallel provenance.** Evidence is the sole uncertainty/provenance object on `EvaluationResult` — no `confidence_old` / `knowledge_rank` / second KnowledgeState store.
4. **Architecture change, not engineering change.** The worked example’s physics values, materials, and hard violations must match pre-evaluator Phase 1 pipeline output.

---

## Deliverables (this run)

| Item | Required |
|------|----------|
| `core/epistemology/` | `KnowledgeState`, `Evidence`, claim-family prefer helpers (no global ordinal) |
| `core/candidates/candidate_design.py` | Minimal `CandidateDesign` input type only |
| `core/evaluation/` | `EngineeringEvaluator`, `EvaluationResult` |
| Tests | Parity vs pipeline; incompleteness / material-failure cases |
| Packages **not** created | `core/search/` |

---

## API (locked)

```python
candidate = CandidateDesign.from_prompt(prompt)   # seed helper for Phase 1 parity
result = EngineeringEvaluator(provider=...).evaluate(candidate)

# result exposes at least:
#   physics, materials, constraints (evaluations),
#   evidence, completeness, failures,
#   validation_report / hard_violation_count (compatible with Phase 1 semantics)
```

`EngineeringEvaluator` **orchestrates** existing Phase 1 components. It must not reimplement physics formulas, material ranking, or constraint aggregation.

---

## Acceptance criteria

### 1. Single entry point
`evaluate(candidate) → EvaluationResult` is the only Phase 2 path to engineering truth.

### 2. No duplicated engineering logic
Evaluator wires `PhysicsEngine` / `MaterialAssigner` / `ConstraintEvaluator` (via the existing Phase 1 evaluation path). No copy-pasted BMEP/margin logic inside `evaluation/`.

### 3. Worked-example parity
```bash
python main.py "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
```
Before vs after evaluator wiring: identical physics numbers, material assignment for rods, and hard-violation count for mean piston speed.

### 4. Evidence begins without dual fields
`EvaluationResult.evidence` uses `core.epistemology.Evidence`. Do not add alternate confidence enums on the result.

### 5. Failure cases still honest
- Unrecognized material → rods unassigned; no invented props  
- Extreme RPM → physics computes; fail via derived thresholds / no qualifying material  
- Contradictory / missing RPM·HP → `incomplete`, not pass  

### 6. Out of scope stays out
No Pareto, mutations, search loop, or objective vector search policy.

---

## Epistemology note (this directive)

`KnowledgeState` values are **categories**, not a global strength order. Prefer/disprefer evidence using **claim-family rules** in `docs/EPISTEMOLOGY_MIGRATION.md` §1.1. The evaluator must not ask “is derived always weaker than simulated?” — it asks “for *this* claim family, which provenance applies?”

---

## Implementation order inside this directive

1. Epistemology types + claim-family helpers  
2. Minimal `CandidateDesign`  
3. `EvaluationResult`  
4. `EngineeringEvaluator` façade (wrap Phase 1 path; preserve behavior)  
5. Parity + adversarial regression tests  
6. Stop. Audit before CandidateDesign free-parameter / search work.

---

## Explicit rejection list (watch these)

| Pattern | Verdict |
|---------|---------|
| `if rpm > 15000: reject()` | Reject — hidden decision |
| Default `material = Titanium` without threshold comparison | Reject |
| `candidate.score = physics_engine.run(...)` from future search | Reject |
| `confidence_score` / `knowledge_rank` beside `Evidence` | Reject |
| Domain “RPM invalid” messages instead of derived material/physics failure | Reject |
