# Verification Integrity Report (Phase C)

## Phase: C

### Claim

1. Every Phase-1 design-graph validator is labeled **`self_consistency_check`** or **`externally_verified`** in output (`ValidationReport.verification_checks`).
2. Category (b) validators never use the words **`validated`** / **`verified`** as pass labels — those are reserved for external ground truth.
3. Each primary validator has **≥3 adversarial rejection tests** in `tests/validator_adversarial/`.
4. The maturity/evidence system has a **preserved failure canary** and does not auto-promote on failed campaigns.

### Evidence

#### C1 — Validator labeling

Registry: `validation/integrity.py` (`VALIDATOR_REGISTRY`)

| Validator | Kind | Ground truth |
|-----------|------|--------------|
| SchemaValidator | self_consistency_check | Pydantic IR schema |
| ConsistencyChecker | self_consistency_check | Graph topology invariants |
| PhysicsRulesEngine | self_consistency_check | Material field presence (warning-only) |
| ConstraintEvaluator | self_consistency_check | Pipeline physics + knowledge rules |
| DesignCritic | self_consistency_check | Rules + optional LLM on same graph |
| EvidenceValidator | externally_verified | Raw evidence provenance checklist |
| IndependentCampaignValidator | externally_verified | Published case fields (no PhysicsEngine) |
| formula_validator | externally_verified | Cited formulas vs physics JSON inputs |

Pipeline stamps checks on every `ValidationReport`:

```
$ python -c "from core.reasoning.pipeline import SemanticKernelPipeline; from llm.ollama_client import DeterministicProvider; p=SemanticKernelPipeline(provider=DeterministicProvider()); r=p.run('design a v8 engine'); print([(c.validator_id, c.verification_kind) for c in r.validation_report.verification_checks])"
[('SchemaValidator', 'self_consistency_check'), ('ConsistencyChecker', 'self_consistency_check'), ('PhysicsRulesEngine', 'self_consistency_check'), ('ConstraintEvaluator', 'self_consistency_check')]
```

Written to `output/validation_report.json` as `verification_checks[]`.

#### C2 — Adversarial rejection tests

```
$ python -m pytest tests/validator_adversarial/ -q
.............................                                            [100%]
29 passed in 0.22s
```

| Test module | Validator | Adversarial cases |
|-------------|-----------|-------------------|
| `test_schema_validator.py` | SchemaValidator | 4 (empty graph, bad root, cleared components, valid control) |
| `test_consistency_checker.py` | ConsistencyChecker | 5 (undefined child/parent/member, cycle, valid control) |
| `test_physics_rules_engine.py` | PhysicsRulesEngine | 3 (unassigned material ×2, all assigned control) |
| `test_constraint_evaluator.py` | ConstraintEvaluator | 6 (CFRP combustion, wood engine, glass crankshaft, yield, MPS, valid control) |
| `test_design_critic.py` | DesignCritic | 4 (no assemblies, generic placeholder, bad material, no constraints) |
| `test_evidence_validator.py` | EvidenceValidator | 5 (missing unit, synthetic, secondary estimate, missing provenance, valid control) |
| `test_maturity_canary.py` | M4 candidate / evidence | 2 (synthetic rejection, failed campaign JSON shape) |

**PhysicsRulesEngine note:** warning-only by design — cannot emit `hard_violations`. Hard material suitability flows through `ConstraintEvaluator`.

#### C3 — Maturity / evidence audit

**Promotion criteria — tied to external benchmarks?**

| Gate | External benchmark? | Mechanism |
|------|---------------------|-----------|
| M3→M4 campaign gate | Yes — rod/BMEP/material datasets, ≥10 cases, error stats | `campaign_gate.py`, `maturity_registry.check_m4_requirements` |
| M4 registry promotion | Yes — requires `independently_verified` + `benchmarked` flags | `model_maturity.validate_descriptor` |
| Auto-promotion from campaigns | **No** — explicitly forbidden | `maturity_campaigns.py` policy; `test_phase10_campaign_integrity.py` |

**Failure / demotion examples preserved:**

- `tests/validator_adversarial/test_maturity_canary.py::test_synthetic_evidence_failure_preserved_not_promoted` — synthetic evidence raises `EvidenceValidationError`; blocked campaign → `m4_eligibility == "FAIL"`.
- `tests/validation/test_maturity_upgrade_gates.py` — M3→M4 blocked with insufficient cases.
- `tests/validation/test_campaign_readiness.py` — M4 candidate FAIL on blocked campaign.
- `tests/test_phase10_campaign_integrity.py` — campaign failure does not mutate maturity histogram.

**Failed experiments logging:**

- Raw evidence: `core/verification/evidence_store/rejected/` (filesystem store).
- Campaign results: `failure_modes`, `failed_cases`, `eligible_for_m4: false` in `*_campaign_result.json` via `CampaignExecutor`.

**Demotion:** No automatic demotion API exists. Integrity is enforced by **blocking promotion** and **descriptor validation** (`MaturityValidationError` on impossible flag combinations).

### Known gaps

- **DesignCritic LLM path** is self-consistency; only rule path has adversarial tests (LLM output is non-deterministic).
- **formula_validator / reality_auditor** have existing tests under `tests/validation/` but not yet in `tests/validator_adversarial/` (registry entries exist).
- **ConstraintEvaluator** hard limits still derive from the same pipeline that generated the design — labeled honestly as `self_consistency_check`.
- Phase D (ARCHITECTURE.md sync CI) not started.
