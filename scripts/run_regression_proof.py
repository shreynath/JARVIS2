#!/usr/bin/env python3
"""Reproducible break → fail → restore → pass regression authenticity proof."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "core" / "reasoning" / "physics_engine.py"
PROOF_PATH = ROOT / "output" / "regression_break_pass_proof.json"
TEST = "tests/test_constraint_evaluation.py::test_pipeline_9000rpm_800hp_reports_hard_violation"

GOOD = "passes = max(mps_range) <= 26.0"
# Controlled bug: raise the pass threshold so the known hard violation disappears.
BUG = "passes = max(mps_range) <= 999.0  # BUG REINTRODUCED"


def _run_test() -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TEST, "-q", "--tb=no"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    text = (proc.stdout or "") + (proc.stderr or "")
    state = "passed" if proc.returncode == 0 else "failed"
    return {"returncode": proc.returncode, "state": state, "output": text.strip()[-500:]}


def main() -> None:
    original = TARGET.read_text()
    assert GOOD in original, "expected MPS pass threshold present"
    assert "BUG REINTRODUCED" not in original

    steps: list[dict] = []

    baseline = _run_test()
    steps.append({"name": "validator_integrity", "phase": "baseline", **baseline})
    assert baseline["state"] == "passed", baseline

    TARGET.write_text(original.replace(GOOD, BUG))
    try:
        broken_result = _run_test()
        steps.append({"name": "validator_integrity", "phase": "broken_state", **broken_result})
        assert broken_result["state"] == "failed", broken_result

        TARGET.write_text(original)
        assert "BUG REINTRODUCED" not in TARGET.read_text()
        fixed = _run_test()
        steps.append({"name": "validator_integrity", "phase": "fixed_state", **fixed})
        assert fixed["state"] == "passed", fixed
    finally:
        TARGET.write_text(original)

    proof = {
        "tests": [
            {
                "name": "validator_integrity",
                "broken_state": "failed",
                "fixed_state": "passed",
                "baseline_state": "passed",
                "bug": "MPS passes threshold raised to 999.0 so hard violation vanishes",
                "test": TEST,
            }
        ],
        "steps": steps,
        "all_ok": all(
            (s["phase"] == "broken_state" and s["state"] == "failed")
            or (s["phase"] in {"baseline", "fixed_state"} and s["state"] == "passed")
            for s in steps
        ),
    }
    PROOF_PATH.parent.mkdir(exist_ok=True)
    PROOF_PATH.write_text(json.dumps(proof, indent=2))
    print(f"wrote {PROOF_PATH} all_ok={proof['all_ok']}")
    if not proof["all_ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
