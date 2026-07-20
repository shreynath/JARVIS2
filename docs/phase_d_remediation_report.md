# Phase D Remediation Report

## Phase: D

### Claim

1. `ARCHITECTURE.md` reconciled with on-disk layout (all top-level packages + all `core/` subpackages).
2. Two-identity problem resolved: **domain-general semantic kernel** with ICE as reference domain (evidence-backed).
3. Enforced sync check: `scripts/check_architecture_sync.py` + `tests/test_architecture_sync.py` + GitHub workflow.

### Evidence

#### D1/D3 — Reconciled architecture doc

```
$ python scripts/check_architecture_sync.py
ARCHITECTURE sync OK — all packages referenced in ARCHITECTURE.md
```

Documented packages previously missing from old Phase-1-only layout:

- `core/verification/`, `core/engineering/`, `core/epistemology/`, `core/evaluation/`
- `core/candidates/`, `core/materials/`
- `verification/` (JSON audit layer)
- `datasets/`, `scripts/`
- Phase B domain knowledge (`knowledge/functional/general_domains.py`)
- Material assignment (no longer listed as future Month 4)

Identity statement (top of `ARCHITECTURE.md`):

> **JARVIS2 is a domain-general engineering semantic kernel.** ICE depth is the reference-domain
> implementation. Generality proven for intent/decomposition (10/10 live LLM); second full-depth
> physics module (Phase F) not yet done.

#### D2 — Enforcement

```
$ python -m pytest tests/test_architecture_sync.py -q
..                                                                       [100%]
2 passed in 0.20s
```

- Script: `scripts/check_architecture_sync.py`
- CI: `.github/workflows/architecture-sync.yml`

### Known gaps

- Phase E (material completeness bar), Phase F (non-ICE physics rigor) not started.
- No pre-commit hook installed locally (CI workflow only); run `python scripts/check_architecture_sync.py` before merge.
- `docs/` directory intentionally excluded from package sync (documentation, not runtime subsystem).
