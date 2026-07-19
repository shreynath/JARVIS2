# JARVIS 2.0 — Epistemology Migration Plan

**Status:** Design only — no `Evidence` / shared `KnowledgeState` classes in this change.  
**Date:** 2026-07-19  
**Directive:** Phase 1 Closure Directive 5  
**Goal:** one provenance system for Phase 1 and Phase 2 — elevate existing fields into `Evidence`; do not layer a second truth model on top.

---

## 1. Final types (locked)

### 1.1 `KnowledgeState` (final enum — categories, not a global rank)

| Value | Meaning |
|-------|---------|
| `known` | Stated by the requirement / prompt / measured input — not computed by JARVIS |
| `derived` | Deterministic calculation from inputs (conservation laws, closed-form kinematics, …) |
| `simulated` | Result of an external simulation adapter (FEA/CFD/etc.) with a recorded run id |
| `empirical` | Value taken from a versioned measured/catalog corpus (materials DB, standards table) |
| `interpolated` | Value obtained by interpolation between known/empirical points |
| `estimated` | Engineering range/heuristic estimate (BMEP bands, heat fractions, etc.) with explicit bounds |
| `assumed` | Filled missing input; recorded as an `Assumption` |
| `unknown` | No value could be established — claim is absent, not merely weak |

**Locked decision (supersedes prior scalar severity order):** epistemic strength is **not one-dimensional**. A single total order (`derived < simulated < empirical`, or the reverse) forces false comparisons between analytical rigor, model fidelity, and observation. **Do not use ordinal comparison of `KnowledgeState` as a global strongest/weakest rank.**

Allowed residual use of a *partial* order (floor only):

```
unknown  is weaker than everything (absence of a claim)
assumed  is weaker than non-assumed states for the same claim
```

Between `{estimated, interpolated, derived, simulated, empirical, known}`, ranking is **claim-family dependent** (Section 1.1b).

Phase 2-only values (`simulated`, `empirical`, `interpolated`, `estimated`) have **no Phase 1 instances today**. Existing Phase 1 data maps only onto `{known, derived, assumed, unknown}` (Section 2).

### 1.1b Claim-family preference rules (locked)

When two Evidence objects support the **same claim**, prefer by claim family — never by a global table.

| Claim family | Prefer (stronger for this claim) | Over | Why |
|--------------|----------------------------------|------|-----|
| `material_property` (yield, fatigue, catalog limits) | `empirical` catalog | `simulated` estimate, then `derived`/`estimated` | Property is experimentally characterized in the corpus |
| `novel_geometry_response` (local stress/flow on new shape) | `simulated` | simple `derived` closed form | Analytical forms often miss geometry nonlinearity |
| `conservation_law` / identity (torque from P·ω, mass balance) | `derived` | `simulated` | Fundamental relation; simulation cannot overrule conservation without indicating model error |
| `requirement_input` | `known` | anything inferred | Prompt/spec is ground truth for *what was asked* |
| Default (unknown family) | do **not** auto-rank types | — | Report both; use `confidence` + `applicability` only |

**Weakest-link rollup for a multi-input claim** (e.g. an ObjectiveScore built from several evidences):

1. If any constituent is `unknown` → rollup state `unknown`, confidence `0.0`.
2. Else if any is `assumed` → rollup state `assumed`, confidence = `min(confidences)`.
3. Else → rollup `knowledge_state` is **not** chosen by global order; set it to the state of the **limiting** constituent under the claim family’s preference rule (the least preferred type present), and `confidence = min(confidences)`.
4. Always preserve the union of provenance ids; never drop a weaker source silently.

### 1.1a `ObjectiveScore` uncertainty inheritance (design)

When Phase 2 creates an `ObjectiveScore`, uncertainty is **only** carried by its `evidence: Evidence` field (see §1.3):

1. Build `Evidence` from every calculation, constraint, catalog key, and assumption the score used.
2. Set `evidence.knowledge_state` / `confidence` via §1.1b rollup (not a global ordinal).
3. Set `evidence.applicability` to the claim family used.
4. `EvaluationResult.evidence` rolls up the same way across scores + constraint-evaluation evidence.
5. No separate `ObjectiveScore.knowledge_state` or `ObjectiveScore.confidence` fields.

### 1.2 `Confidence` (Phase 2 Step 1 — string preserved)

**`Evidence.confidence` is `Literal["high","medium","low"]` — same as Phase 1 `PhysicsCalculation.confidence`.**

A float∈[0,1] migration is **explicitly deferred**. Do not introduce a parallel numeric confidence field alongside the string. Display-band / float conversion tables from earlier drafts apply only when that future migration is authorized.

### 1.3 `Evidence` (Phase 2 Step 1 wrapper)

```
Evidence  (frozen dataclass)
  claim: str
  state: KnowledgeState
  confidence: "high" | "medium" | "low"    # string — matches Phase 1
  reason: str
  source_calc_id: str | None
```

Produced by `wrap_calculation(calc)` — read-only map from `PhysicsCalculation`. Does not recompute provenance. Extended fields (`calculation_ids`, `catalog_keys`, …) remain reserved for a later host-field migration and are **not** introduced as a parallel store in this step.

**Ownership rule (locked):** `Evidence` **replaces** the scattered provenance fields listed in Section 4. It is not an additive parallel store.

**Rollup rules (locked):**

| Field | Aggregate of constituents |
|-------|---------------------------|
| `knowledge_state` | claim-family limiting state per §1.1b (not a global ordinal) |
| `confidence` | `min(constituent confidences)`; empty → `0.0`; `unknown` forces `0.0` |
| `calculation_ids` / `constraint_ids` / `catalog_keys` / `assumptions` | sorted unique union |
| `applicability` | declare claim family; if mixed families, use `mixed:<families>` |
| `provenance` | concise join of constituent provenances |

**Invariant:** if `knowledge_state == unknown`, then `confidence` **must** be `0.0`.

---

## 2. `KnowledgeState` migration map (every existing value → exactly one new value)

Phase 1 source: `core.reasoning.physics_engine.KnowledgeState`.

| Existing value | Maps to | Rule / justification |
|----------------|---------|----------------------|
| `known` | `known` | Identity — explicit requirement/prompt quantity |
| `derived` | `derived` | Identity — formula result from upstream calcs |
| `assumed` | `assumed` | Identity — heuristic / missing-input fill; paired with assumptions list |
| `unknown` | `unknown` | Identity — **not** remapped to `assumed`. `unknown` means “no operating value exists”; `assumed` means “we substituted a value.” Collapsing them would hide the unvalidated-hard-limit class of gap |

No other Phase 1 `knowledge_state` strings exist in code or fixtures. Any unrecognized future string at migration time **fails the migration** (raise); it does not silently coerce.

---

## 3. Confidence migration map

### 3.1 Categorical `str` → `float` (Phase 1 `PhysicsCalculation.confidence`)

Exact conversion (point values, not ranges):

| Existing `str` | Migrates to `float` | Justification |
|----------------|---------------------|---------------|
| `"high"` | `0.85` | Strong formula chain / known geometry; not 1.0 because models still idealize |
| `"medium"` | `0.55` | Mixed known + typical ranges (BMEP mid, medium heat model) |
| `"low"` | `0.25` | Order-of-magnitude / coarse mass or friction proxies |
| `""` / `None` / missing | `0.0` | Absence of stated confidence is not medium |
| any other string | **migration error** | Fail loud; do not invent a default |

These point values are the **only** legal conversion of archived Phase 1 strings. New code writes floats directly; it does not write `"high"`/`"medium"`/`"low"`.

### 3.2 Display bands (float → label, derived view only)

When a report or CLI needs a band:

| Float interval | Band |
|----------------|------|
| `[0.00, 0.35)` | `low` |
| `[0.35, 0.70)` | `medium` |
| `[0.70, 1.00]` | `high` |

Bands are **never stored**. Round-trip of old strings uses Section 3.1 points, which land in the same band they left (`high`→0.85→`high`, etc.).

### 3.3 Existing float confidence (`Assumption.confidence`)

Identity map: value already in `[0.0, 1.0]` stays unchanged. No scaling.

### 3.4 Special override

| Condition | Forced `confidence` |
|-----------|---------------------|
| Migrated or new `knowledge_state == unknown` | `0.0` |

This overrides Section 3.1 if a legacy row was `unknown` + `"low"`.

---

## 4. Field consumption map (replace, do not layer)

| Current location | Current field(s) | Consumed into `Evidence` as | Host model after migration |
|------------------|------------------|-----------------------------|----------------------------|
| `PhysicsCalculation` | `dependency_ids` | `calculation_ids` (deps of this calc) | field removed; `evidence.calculation_ids` |
| `PhysicsCalculation` | `assumptions` | `assumptions` | field removed |
| `PhysicsCalculation` | `knowledge_state` | `knowledge_state` | field removed |
| `PhysicsCalculation` | `confidence` | `confidence` (via §3) | field removed |
| `PhysicsCalculation` | *(new)* | `evidence: Evidence` | **sole** provenance field |
| `ConstraintEvaluation` | `source` | encoded as catalog/key or constraint id prefix when module-level; else `constraint_ids` + description provenance | `source` removed; `evidence: Evidence` added. Evaluation semantics (`passes`, `value`, `limit`, `severity`) stay on the evaluation |
| `ConstraintEvaluation` | `dependency_ids` | union into `calculation_ids` / `constraint_ids` by id prefix (`calc_*` → calculations; else constraints) | field removed |
| `Assumption` | `source` | first token of supporting provenance; assumption id listed under `Evidence.assumptions` of consumers | `Assumption` remains a first-class record; `source` becomes optional debug tag **or** is folded into the consumer’s `Evidence` and dropped — **chosen rule:** drop `Assumption.source` after migration; consumers list `Assumption.id` in `evidence.assumptions` |
| `Assumption` | `confidence` | when an assumption participates in a claim, that float feeds the claim’s `Evidence.confidence` via `min()` | stays on `Assumption` as the assumption’s own strength (not duplicated as a second epistemology) |
| `MaterialSpec` | `source` | `catalog_keys` entry e.g. `materials:aluminum_2618@v1` | `source` removed; selection metrics may still hold non-provenance scores |
| Objective / Evaluation rollups (Phase 2) | *(new)* | each `ObjectiveScore.evidence` and `EvaluationResult.evidence` | no parallel confidence fields |

**Id-prefix routing for ConstraintEvaluation.dependency_ids (locked):**

- id starts with `calc_` → `Evidence.calculation_ids`
- otherwise → `Evidence.constraint_ids`

**Explicit non-goals:**

- Do **not** keep `PhysicsCalculation.confidence: str` alongside `Evidence.confidence: float`.
- Do **not** invent `ObjectiveScore.confidence` outside `Evidence`.
- Do **not** store KnowledgeState on search graph nodes except by reference to `EvaluationResult.evidence`.

---

## 5. Phase 1 call-site inventory (migration checklist for the future code change)

| Module | What changes when Evidence lands |
|--------|----------------------------------|
| `core/reasoning/physics_engine.py` | Emit `evidence=` on each `PhysicsCalculation`; delete old four fields |
| `validation/constraint_evaluator.py` | Build `Evidence` per evaluation; drop `source`/`dependency_ids` writes |
| `core/reasoning/assumption_manager.py` | Stop writing `Assumption.source`; consumers reference assumption ids |
| `core/reasoning/material_assigner.py` | Put catalog key@version into `MaterialSpec.evidence` (or selection evidence blob) |
| `core/reasoning/critic.py` | Read `Assumption.confidence` (float) unchanged; do not reintroduce str confidence |
| Tests asserting `calc.confidence` as truthy str | Assert `calc.evidence.confidence > 0` (except unknown) |

**No code in the original Directive 5.** EngineeringEvaluator introduces shared `Evidence` types; full host-field deletion follows in a later migration step without parallel stores.

---

## 6. Decisions log (closed — no open `?`)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Final KnowledgeState set | eight values in §1.1 including retained `unknown` |
| D2 | Map of Phase 1 `unknown` | → `unknown` (not `assumed`) |
| D3 | Confidence storage | `float` ∈ [0,1] |
| D4 | `"high"/"medium"/"low"` conversion | 0.85 / 0.55 / 0.25 exactly |
| D5 | Display bands | derived only; thresholds 0.35 / 0.70 |
| D6 | Evidence replaces scattered fields | yes — consume map in §4 |
| D7 | `Assumption.source` | removed at migration; use assumption ids on Evidence |
| D8 | Catalog versioning | embedded in `catalog_keys` string form `catalog:key@version` |
| D9 | Aggregate knowledge_state | claim-family limiting rule (§1.1b); **no global ordinal** |
| D10 | Aggregate confidence | `min`; unknown forces 0.0 |
| D11 | KnowledgeState ordering | **revoked as total order** — categories + claim-family preference only |
| D12 | Evidence fields | adds `provenance`, `applicability` for claim context |

---

## 7. Acceptance

Directive 5 (revised) is **accepted** with D1–D12 locked. Shared `Evidence` / `KnowledgeState` types land with the EngineeringEvaluator façade (`docs/PHASE2_ENGINEERING_EVALUATOR_DIRECTIVE.md`); Phase 1 host fields migrate incrementally without dual confidence stores.
