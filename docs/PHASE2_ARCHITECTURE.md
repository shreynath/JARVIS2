# JARVIS 2.0 — Phase 2 Architecture Specification

**Status:** Design only — no implementation until this document is reviewed.  
**Date:** 2026-07-19  
**Depends on:** Phase 1 Engineering Semantic Kernel (complete)

---

## Guiding principle

Phase 1 taught one durable lesson: subsystems that **decide** create fake correctness; subsystems that **evaluate** create real correctness. Phase 2 generalizes that pattern from materials to the entire design:

```
Goal
  → Generate candidate        (LLM proposes / mutations propose)
  → Derive physics            (Phase 1 PhysicsEngine, per candidate)
  → Evaluate constraints      (Phase 1 ConstraintEvaluation)
  → Evaluate materials        (Phase 1 MaterialAssigner)
  → Evaluate objectives       (new — vector of scores)
  → Search selects next       (new — Pareto over vectors)
  → Repeat
```

**Standing invariants (carried from Phase 1):**

1. **Knowledge independence.** Every score, mutation acceptance, and search step must ultimately trace through Goal → Requirement → Physics → Constraint → Evaluation. Nothing exists because “the LLM thought so.”
2. **Single Source of Engineering Truth.** No optimizer, scorer, mutation generator, or explanation step may invent an engineering fact. Every fact originates from a requirement, a Phase 1 calculation, a future simulation, or a versioned database/catalog entry — never from an LLM judgment presented as derived.

---

## Section 1 — Overall Architecture

### Pipeline (begins after Phase 1 requirement compilation)

```
Prompt
  → Requirement Compilation          [Phase 1 — unchanged, once]
  → Seed Candidate Set               [NEW — Candidate Generation]
       │
       ▼  (for each candidate, identically)
  ┌─────────────────────────────────────────────────────────┐
  │  ENGINEERING EVALUATOR  (search-unaware)                │
  │    Physics Evaluation            [Phase 1 — per call]   │
  │    Material Evaluation           [Phase 1 — per call]   │
  │    Constraint Validation         [Phase 1 — per call]   │
  │    Objective Scoring             [NEW]                  │
  │         ↓                                               │
  │    EvaluationResult (vector + ConstraintEvaluations)    │
  └─────────────────────────────────────────────────────────┘
       │
       ▼  (separate system)
  Search Algorithm                   [NEW — evaluator-unaware]
    → records nodes in Engineering State Graph
    → proposes next CandidateDesign via Mutation operators
  → until budget / convergence
  → Final Candidate Selection        [NEW — user-visible ranking optional]
```

### Stage responsibilities

| Stage | Responsibility | Origin |
|-------|----------------|--------|
| Requirement Compilation | Formalize intent → requirements, conflicts, unresolved | Phase 1 reused **unchanged** (once) |
| Candidate Generation | Propose multiple competing designs satisfying fixed requirements | **New** |
| Physics Evaluation | Derive quantities + ConstraintEvaluations for one candidate | Phase 1 reused **as-is**, called **per candidate** |
| Material Evaluation | Rank materials against derived requirements | Phase 1 reused **as-is**, called **per candidate** |
| Validation | Aggregate hard violations from ConstraintEvaluation only | Phase 1 reused **as-is**, called **per candidate** |
| Objective Scoring | Compute objective vector + uncertainty from EvaluationResult inputs | **New** |
| Search | Decide which candidate to explore next from stored scores/state | **New** |
| Final Selection | Present Pareto set; optional user-visible weighting applied once | **New** |

Phase 1 physics, material, and validation logic **must not be rewritten**. They already accept a requirements + design-shaped input and emit inspectable artifacts. Phase 2’s only requirement on them is: same function signature whether called from a CLI smoke test or from inside a search loop.

### Evaluator / search boundary (required)

```
CandidateDesign  →  EngineeringEvaluator.evaluate(candidate)  →  EvaluationResult
                                                                      ↓
                                                         SearchAlgorithm.propose_next(
                                                           state_graph, frontier
                                                         ) → CandidateDesign | Stop
```

- **Evaluator must not know about search.** No beam width, generation index, temperature, or parent mutation ID may appear in evaluator inputs or outputs (except optionally as opaque provenance for logging — never for scoring logic).
- **Search must not know about engineering.** Search may read `EvaluationResult.objective_vector`, `hard_violation_count`, and `pareto_flags` — but not recompute torque, invent materials, or invent rod stress.
- **No data structure crosses the boundary in both directions.** `CandidateDesign` flows into the evaluator; `EvaluationResult` flows out. Search produces the next `CandidateDesign`. `Engineering State Graph` is owned by search/memory, not by the evaluator. `ConstraintEvaluation` lives inside `EvaluationResult` (reuse Phase 1 object) and is never rewritten by search.

**Single Source of Engineering Truth — Section 1 enforcement:** the evaluator is the only component allowed to call Phase 1 physics/materials/validation. Search and scoring consume Evaluator outputs by ID (calculation IDs, ConstraintEvaluation IDs), never by re-deriving values.

---

## Section 2 — Candidate Generation

### What is a `CandidateDesign` (engine domain now)

A candidate is a **parameterized design proposal** plus a **design graph identity**, not a free-form LLM essay.

**Fixed by resolved requirements** (must not vary across candidates unless the prompt left them unresolved):

- object type, engine architecture / cylinder count, aspiration (once resolved), fuel type (once resolved), stated numeric targets (max_rpm, target_horsepower, etc.)

**Allowed to vary** (the design space Phase 2 searches):

- geometry parameters currently estimated as ranges in Phase 1 (e.g. chosen stroke within estimate, bore/stroke ratio within plausible band, displacement within BMEP-feasible band when not user-fixed)
- component material selections (restricted to MaterialAssigner candidates that clear hard thresholds — search may try different qualifying materials under different objective tradeoffs)
- cooling / lubrication layout choices from a finite enumerated set (e.g. oil-jet density class, radiator margin class) — not free-text

**Diversity among initial seeds:**

- Draw N seeds by sampling independently from each free parameter’s feasible interval / discrete option set (Latin hypercube or stratified sampling preferred over pure independent random when N is small).
- Optionally, one seed is the Phase 1 single-design baseline (current deterministic midpoints) for regressability.

**Infeasible candidates:**

- Always **retained** with full `EvaluationResult` (including failed `ConstraintEvaluation`s), never silently discarded.
- Search may deprioritize them (hard-violation filter on frontier) but Section 9 must be able to answer why a candidate died.

### Domain generality note (documentation only)

`CandidateDesign` is specified and will be implemented for **engines first**. Naming should prefer general terms (`components`, `parameters`, `interfaces`) over engine-only terms where the concept is shared. A future generalization to aircraft wings / batteries / structures would require: (a) a new parameter schema and mutation catalog for that domain, (b) domain-specific physics/objective plug-ins, (c) domain requirement templates — but would **carry over unchanged** the Candidate → Evaluate → Score-vector → Search loop, `EvaluationResult`, `Engineering State Graph`, and Single Source of Truth rules.

**Single Source of Engineering Truth — Section 2:** candidate generation may invent **proposals** (parameter values within declared feasible sets) but may not invent **facts** (e.g. “this stroke yields 18 m/s piston speed”). Feasibility claims are provisional until the evaluator derives them.

---

## Section 3 — Engineering State Graph

A graph **distinct from** Phase 1’s constraint dependency graph.

| Graph | Records |
|-------|---------|
| Phase 1 Constraint Graph | *Why a design is what it is* — requirements → calculations → constraints → components |
| Engineering State Graph | *How the search got there* — candidates, mutations, scores, parent/child |

### Required content for Phase 2 (search-history scope only)

Each node (`DesignStateNode`) stores:

- `candidate_id` → `CandidateDesign`
- `parent_id` (null for seeds)
- `mutation` (`MutationRecord` or null for seeds)
- `evaluation_id` → `EvaluationResult`
- `objective_vector` (copy of scores for indexing; values still grounded in EvaluationResult / calc IDs)
- `dominance_status` (dominated / non-dominated / unevaluated)
- `rejection_reason` (null or structured: hard violations, etc.)

Edges: `derived_by_mutation` (parent → child).

This is the optimizer’s memory: avoid re-trying identical mutations on identical parents; explain search direction after the fact.

### Later extension without breaking change

Nodes may later gain optional `knowledge_kind` (`search_candidate` | `rejected_material` | `failed_assumption` | …) and `payload` opaque to search. Search-history nodes remain valid with `knowledge_kind=search_candidate`. Do **not** design the broader knowledge use case now.

**Single Source of Engineering Truth — Section 3:** state-graph scores are references to `EvaluationResult` IDs / objective score IDs, not independently rewritten numbers.

---

## Section 4 — Objective Functions

### Architecture

Pluggable scorers sharing one contract:

```
ObjectiveScorer.score(candidate, evaluation_result, physics_analysis) → ObjectiveScore
```

Initial objectives (engine domain): performance (power/specific power margin to target), mass/weight proxy, cost proxy, reliability/fatigue margin, thermal margin, manufacturability (qualitative ordinal from discrete process classes), efficiency (when thermal calcs allow).

New objectives are registered; the optimizer iterates the registry — it is not rewritten.

### Preserve the objective vector

Internally, a candidate’s evaluation is always:

```
ObjectiveVector = { objective_id → ObjectiveScore }
```

**No internal composite score** (no hidden “Overall = 73.5”). Relative importance of objectives is a **preference**, not a physics derivation; collapsing forces that preference inside the search.

Search compares candidates by **Pareto dominance** (or ε-dominance): A dominates B iff A is no worse on every objective and strictly better on at least one — with uncertainty rules below.

If a single ranking is needed for the user, apply an explicit, **user-visible** weighting step **once at the end** (Final Selection). That step is not part of the optimizer’s internal loop.

### Propagate uncertainty into scores

Phase 1 calculations already carry `confidence`, `knowledge_state`, and `value_range`. Each `ObjectiveScore` must include:

- point estimate (from nominal `result` or declared aggregate)
- score range induced by upstream `value_range`s (interval arithmetic or sampled bounds — method must be fixed and inspectable)
- `Evidence` listing calculation IDs used
- aggregated `KnowledgeState` (worst-case or declared rule, e.g. any `assumed` input → score is `assumed`)

**Comparison rule:** A is meaningfully better than B on an objective only if A’s score interval is strictly better than B’s (or a declared confidence-adjusted rule, documented). Differences wholly inside overlapping uncertainty bands are **ties**, not progress. Search must not “optimize noise.”

**Single Source of Engineering Truth — Section 4:** scorers may only read Phase 1 calculations / ConstraintEvaluations / catalog fields by ID. They may not invent margins.

---

## Section 5 — Search Strategy

### Options compared (brief)

| Strategy | Pros | Cons for this project |
|----------|------|------------------------|
| Evolutionary / GA | Familiar multi-objective variants (NSGA-II) | Easy to hide fitness fudge factors; harder to inspect |
| Beam search | Traceable frontier | Needs good mutation generators |
| Simulated annealing | Simple | Typically scalar temperature; awkward with vectors |
| Bayesian optimization | Sample-efficient | Surrogate correctness hard to inspect; overkill early |
| MCTS | Strong for discrete trees | Heavy machinery; hard to verify end-to-end |
| Generate-and-evaluate + Pareto frontier | Fully inspectable; matches Phase 1 bias | Less sample-efficient; “boring” |

### Recommendation

**Agree with the “simplest verifiable strategy first” bias.**

Start with:

1. Generate a small seed set (Section 2).
2. Evaluate each with the Engineering Evaluator.
3. Maintain a **Pareto archive** of non-dominated candidates (operating on the objective **vector**, never a scalar).
4. Each iteration: pick a parent from the archive (or a soft diversity quota from dominated-but-informative failures), apply one discrete mutation (Section 6), evaluate, update archive + Engineering State Graph.
5. Stop on evaluation budget or stagnation (no archive change for K iterations).

Upgrade later to NSGA-II / MOEA or Bayesian methods **only after** this loop is verified end-to-end with the same regression discipline as Phase 1. Unverified sophistication has repeatedly hidden shortcuts in this codebase; search is the highest-risk place to reintroduce them.

**Single Source of Engineering Truth — Section 5:** search decisions are functions of `EvaluationResult` fields only. Mutating “because the LLM suggested a better engine” is forbidden except as a proposal that still must pass the evaluator.

---

## Section 6 — Candidate Mutation

Mutations are **physically meaningful operators**, not Gaussian noise on JSON fields.

Examples (engine scaffolding):

- adjust bore/stroke ratio within catalog-plausible bounds
- select stroke at low / mid / high of Phase 1 stroke estimate (explicit choice, not silent midpoint)
- substitute next-ranked qualifying material for a mass-sensitive or cost-sensitive component
- change cooling margin class / oil-jet class within enumerated options
- tighten or relax displacement within BMEP-feasible band when displacement is not user-fixed

Each application produces a `MutationRecord`: operator id, parameters, rationale string **template** filled from inspectable before/after parameter values (not free LLM prose as authority).

### Scaffolding, not destination

These human-named operators are the **current verifiable implementation**, not a permanent architectural limit. Future phases may replace them with lower-level transforms (parameter vectors, topology edits, geometric morphs, composition fields) **without changing** the Candidate → Evaluate → Score → Search loop. Mutation operators are **swappable inputs** to the evaluator boundary; they are not part of the evaluator’s contract. Do not design those lower-level transforms in Phase 2.

**Single Source of Engineering Truth — Section 6:** a mutation may change **proposal parameters** only. It may not write physics results, material margins, or ConstraintEvaluations onto the candidate — those appear only after evaluation.

---

## Section 7 — Evaluation vs. Decision

| Subsystem | Evaluates (correct) | Must not decide |
|-----------|---------------------|-----------------|
| Candidate generation | Proposes designs in a declared feasible set | “This is the best engine” |
| Physics (Phase 1) | Derives quantities + passes/fails | “Acceptable design” as narrative judgment |
| Materials (Phase 1) | Ranks candidates against thresholds | Picks titanium by vibe |
| Validation (Phase 1) | Aggregates ConstraintEvaluations | Invents new engineering limits |
| Objective scoring | Computes inspectable scores + uncertainty | Collapses hidden preferences into a secret composite |
| Search | Selects next node from scores/archive rules | Invents physics to justify a jump |
| Final selection | Applies **declared** user weights once, or returns Pareto set | Silently reweights mid-search |

Template matches Phase 1 materials: evaluate all candidates → deterministic rule among those that clear hard constraints → inspectable ranking.

---

## Section 8 — Data Model (fields and relationships only)

### Reused from Phase 1

- `ConstraintEvaluation` — canonical hard/soft constraint outcome (already exists)
- `PhysicsCalculation` / `PhysicsAnalysis` — calculations with ranges, confidence, knowledge_state
- `EngineeringDesignGraph`, `RequirementSpecification`, `MaterialSpec`

### Shared epistemology (elevate existing Phase 1 fields — not a parallel system)

**Authority:** `docs/EPISTEMOLOGY_MIGRATION.md` (Directive 5) — that document locks mappings; this section is a summary only.

**`KnowledgeState`:** categories only — `unknown`, `assumed`, `estimated`, `interpolated`, `derived`, `simulated`, `empirical`, `known`.  
**No global ordinal.** Prefer evidence by claim family (`docs/EPISTEMOLOGY_MIGRATION.md` §1.1b).

**`Evidence`:**  
- `calculation_ids`, `constraint_ids`, `catalog_keys`, `assumptions`  
- `knowledge_state`, `confidence: float`  
- `provenance`, `applicability` (claim family)

`ObjectiveScore` and `EvaluationResult` **reference** `Evidence`; they do not maintain a second conflicting epistemology store.

**Package home (Directive 6):** `docs/PHASE2_PACKAGE_ARCHITECTURE.md` — `core/epistemology/` owns these types when implemented.  
**First code:** `docs/PHASE2_ENGINEERING_EVALUATOR_DIRECTIVE.md`.


### New types

**`CandidateDesign`**

- `id: str`
- `requirement_spec_id: str` (immutable link to compiled requirements)
- `fixed_parameters: dict` (frozen copies of resolved requirements)
- `free_parameters: dict` (the searchable variables)
- `design_graph_seed: …` (optional handle / serialized IR after decomposition — or regenerate deterministically from parameters; choose one strategy and stick to it)
- `status: proposed | evaluated | rejected`

**`ObjectiveScore`**

- `objective_id: str`
- `value: float`
- `value_range: tuple[float, float] | null`
- `direction: minimize | maximize`
- `evidence: Evidence`
- `unit: str`

**`EvaluationResult`**

- `id: str`
- `candidate_id: str`
- `constraint_evaluations: list[ConstraintEvaluation]`  ← **reuse Phase 1 type**
- `hard_violation_count: int` (derived from those evaluations — same aggregation rule as Phase 1)
- `physics_analysis_id / embed: PhysicsAnalysis` (by reference preferred)
- `material_summaries: dict[component_id, material_key + selection_metrics refs]`
- `objective_vector: dict[str, ObjectiveScore]`
- `evidence: Evidence` (rollup)

**`MutationRecord`**

- `id: str`
- `operator_id: str`
- `parameters: dict`
- `parent_candidate_id: str`
- `child_candidate_id: str`
- `rationale_template: str`
- `rationale_bindings: dict` (inspectable fills)

**`OptimizationIteration`**

- `index: int`
- `evaluated_candidate_ids: list[str]`
- `archive_candidate_ids: list[str]` (non-dominated set snapshot)
- `stop_reason: null | budget | stagnation | user`

**`DesignStateNode`** (Engineering State Graph node)

- `id: str`
- `candidate_id: str`
- `parent_id: str | null`
- `mutation_id: str | null`
- `evaluation_id: str | null`
- `dominance_status: str`
- `rejection_reason: str | null`
- `knowledge_kind: str` (= `search_candidate` for Phase 2)

Relationships: Candidate —evaluated→ EvaluationResult; EvaluationResult **contains** ConstraintEvaluations; Mutation links parent/child Candidates; DesignStateNode indexes the search memory.

---

## Section 9 — Explainability

Answerable **from stored data**, never by asking an LLM to invent a retrospective story:

| Question | Answer source |
|----------|---------------|
| Why chosen / rejected? | `EvaluationResult.constraint_evaluations` + archive membership / dominance |
| Alternatives considered? | Sibling / cousin nodes in Engineering State Graph; Pareto archive snapshot |
| Which calculations mattered? | `Evidence.calculation_ids` on deciding `ObjectiveScore`s + ConstraintEvaluation.dependency_ids |
| Objectives improved vs parent? | Diff of objective vectors between parent and child DesignStateNodes |
| Meaningful vs noise? | Compare objective `value_range`s / Evidence confidence (Section 4 rule) |

LLM may **narrate** these stored facts in natural language later; it may not be the authority that creates the explanation content.

---

## Section 10 — Extensibility

### Core loop stability test

A new fatigue-lifetime evaluator or an aircraft-wing domain can be added as:

- new physics/objective plug-ins registered with the Engineering Evaluator, and/or
- new `CandidateDesign` parameter schema + mutation catalog,

**without changing** Candidate → Evaluate → ObjectiveVector → Search.

If a future addition required changing that loop itself, that would be an architectural failure — and this design intentionally forbids it.

### Extension point A — Physical Representation Layer (geometry/mesh)

**Not built in Phase 2.** Where it would sit:

```
CandidateDesign (parameters)
  → [Physical Representation Layer: generate mesh/CAD from parameters]
  → Physics Evaluation (FEA/CFD/topology consuming the mesh)
  → …
```

Section 1’s evaluator boundary does not preclude this: the Physical Representation Layer is part of **producing evaluator inputs**, still search-unaware. Phase 1 physics today uses scalar estimates; inserting a mesh layer later does not require search or objective-vector changes.

### Extension point B — domains beyond engines

Carry over: loop, EvaluationResult, ConstraintEvaluation, Evidence/KnowledgeState, Engineering State Graph, Pareto search, SSoT rules.  
Change: requirement templates, free-parameter schemas, mutation catalogs, physics/objective plug-ins.  
Do not perform that generalization in Phase 2 implementation.

---

## Phase 1 reuse summary

| Subsystem | Phase 2 role |
|-----------|--------------|
| RequirementCompiler | Once per prompt |
| PhysicsEngine | Per candidate, unchanged API |
| MaterialAssigner | Per candidate, unchanged API |
| ConstraintEvaluator / ValidationReport | Per candidate, unchanged aggregation |
| Constraint Graph (design causality) | Built per candidate evaluation; distinct from Engineering State Graph |
| Intent / decomposition | Seed baseline + regenerate from candidate parameters as needed |

| New in Phase 2 | |
|----------------|--|
| CandidateDesign + generation | |
| EngineeringEvaluator façade (thin glue) | |
| Objective scorers + vector | |
| Engineering State Graph | |
| Search (Pareto generate-and-evaluate) | |
| Mutation operators (scaffolding) | |
| Final selection / optional user weights | |
| KnowledgeState + Evidence shared types | |

---

## Explicit non-goals for Phase 2 implementation (when coding begins)

- No LLM-as-judge for scores, dominance, or explanations-as-authority
- No internal composite fitness score
- No rewriting Phase 1 physics/materials/validation “to make search easier”
- No Physical Representation Layer yet
- No domain-agnostic CandidateDesign framework yet
- No Bayesian/MCTS upgrade until simple Pareto loop is regression-tested

---

## Review checklist before coding

- [ ] Evaluator/search boundary accepted; no bidirectional data structure
- [ ] Objective vector + uncertainty rules accepted
- [ ] Simplest Pareto search accepted (or alternate justified)
- [ ] Mutations marked scaffolding accepted
- [x] KnowledgeState/Evidence as elevation of Phase 1 fields accepted (`docs/EPISTEMOLOGY_MIGRATION.md`)
- [x] Package boundaries accepted (`docs/PHASE2_PACKAGE_ARCHITECTURE.md`); first code = `EngineeringEvaluator`
- [ ] Extension points (mesh layer, other domains) accepted as docs-only for now

**Phase 2 coding should not start until this specification is reviewed and the checklist above is signed off.**
