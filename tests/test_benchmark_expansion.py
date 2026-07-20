"""Phase 5.0 — reference engine benchmark expansion."""

from __future__ import annotations

import json
from pathlib import Path

from verification.benchmark import kinematic_check, run_benchmark

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ROOT / "datasets" / "reference_engines"

REQUIRED_NEW = {
    "ferrari_f136",
    "ferrari_f154",
    "honda_k20",
    "toyota_2jz_gte",
    "nissan_vr38dett",
    "porsche_mezger_gt1",
    "mercedes_m120",
    "bmw_s85",
    "audi_42_fsi",
}


def test_expanded_reference_engines_present():
    ids = {p.stem for p in ENGINES.glob("*.json")}
    missing = REQUIRED_NEW - ids
    assert not missing, missing
    assert len(ids) >= 16


def test_new_engines_have_published_schema():
    for engine_id in REQUIRED_NEW:
        payload = json.loads((ENGINES / f"{engine_id}.json").read_text())
        assert payload["id"] == engine_id
        assert payload.get("manufacturer")
        assert payload.get("year")
        pub = payload["published"]
        for key in ("bore_mm", "stroke_mm", "displacement_l", "rpm" if False else "max_rpm", "horsepower"):
            assert key in pub and pub[key] is not None
        assert pub.get("published_source") or payload.get("verified_sources")


def test_kinematic_checks_pass_for_new_engines():
    for engine_id in sorted(REQUIRED_NEW):
        payload = json.loads((ENGINES / f"{engine_id}.json").read_text())
        check = kinematic_check(payload)
        assert check["status"] == "pass", (engine_id, check)


def test_benchmark_suite_loads_all_engines():
    report = run_benchmark(include_jarvis=False)
    assert len(report.get("engines") or report.get("rows") or []) >= 16 or report.get("engine_count", 0) >= 16
