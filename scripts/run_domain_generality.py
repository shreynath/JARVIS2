#!/usr/bin/env python3
"""Run Phase B domain generality suite against live Ollama and write the report.

Evidence: docs/domain_generality_evidence/*.json
Report:   docs/domain_generality_report.md
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Import suite helpers by path so we don't require tests/ to be a package.
import importlib.util

_suite_path = ROOT / "tests" / "domain_generality_suite.py"
_spec = importlib.util.spec_from_file_location("domain_generality_suite", _suite_path)
_suite = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["domain_generality_suite"] = _suite
_spec.loader.exec_module(_suite)

DOMAIN_REQUESTS = _suite.DOMAIN_REQUESTS
REGRESSION_MARKERS = _suite.REGRESSION_MARKERS
evaluate_case = _suite.evaluate_case

from llm.env_loader import load_dotenv
from llm.ollama_client import OllamaClient
from core.reasoning.pipeline import SemanticKernelPipeline


def main() -> int:
    load_dotenv()
    client = OllamaClient()
    if not client.is_available():
        print(
            "ERROR: Ollama unavailable. Start local `ollama serve` or set "
            "OLLAMA_HOST / OLLAMA_API_KEY for cloud.",
            file=sys.stderr,
        )
        return 2

    evidence_dir = ROOT / "docs" / "domain_generality_evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    pipeline = SemanticKernelPipeline(provider=client)

    cases = []
    for expected, prompt in DOMAIN_REQUESTS + REGRESSION_MARKERS:
        print(f"Running: {prompt!r} ...", flush=True)
        case = evaluate_case(pipeline, expected, prompt, evidence_dir=evidence_dir)
        status = "PASS" if case.passed else "FAIL"
        print(
            f"  [{status}] object_type={case.object_type!r} "
            f"components={len(case.component_ids)} notes={case.notes}",
            flush=True,
        )
        cases.append(case)

    domain_cases = cases[: len(DOMAIN_REQUESTS)]
    passed = sum(1 for c in domain_cases if c.passed)
    report_path = ROOT / "docs" / "domain_generality_report.md"
    report_path.write_text(_render_report(client, cases, passed, len(DOMAIN_REQUESTS), evidence_dir))
    summary_path = evidence_dir / "_summary.json"
    summary_path.write_text(
        json.dumps([asdict(c) for c in cases], indent=2)
    )
    print(f"\nDomain score: {passed}/{len(DOMAIN_REQUESTS)}")
    print(f"Report: {report_path}")
    return 0 if passed >= 8 else 1


def _render_report(client: OllamaClient, cases, passed: int, total: int, evidence_dir: Path) -> str:
    lines = [
        "# Domain Generality Report (Phase B)",
        "",
        "## Phase: B",
        "",
        "### Claim",
        f"{passed} of {total} fixed domain requests produced distinct, correctly-typed, "
        f"non-ICE, non-templated-looking output against live Ollama "
        f"(`{client.provider_label()}` at `{client.host}`).",
        "",
        "### Evidence",
        f"Command: `python scripts/run_domain_generality.py`",
        f"Provider: `{client.provider_label()}` host=`{client.host}`",
        "",
        "| # | Prompt | object_type | comps | type_ok | comps_ok | intent_ok | not_ICE | Result |",
        "|---|--------|-------------|-------|---------|----------|-----------|---------|--------|",
    ]
    for i, c in enumerate(cases, 1):
        mark = "PASS" if c.passed else "FAIL"
        lines.append(
            f"| {i} | {c.prompt} | `{c.object_type}` | {len(c.component_ids)} | "
            f"{c.object_type_ok} | {c.components_ok} | {c.intent_structure_ok} | "
            f"{c.not_ice} | **{mark}** |"
        )

    lines.extend(
        [
            "",
            "### Per-request B3 answers",
            "",
        ]
    )
    for c in cases:
        lines.extend(
            [
                f"#### `{c.prompt}`",
                "",
                f"1. **object_type / domain correct?** "
                f"{'Yes' if c.object_type_ok and c.not_ice else 'No'} — "
                f"`object_type={c.object_type}`, domains={c.domains}",
                f"2. **Components plausible for this object?** "
                f"{'Yes' if c.components_ok else 'No'} — ids={c.component_ids}",
                f"3. **Domain-appropriate intent/constraints (not ICE placeholders)?** "
                f"{'Yes' if c.intent_structure_ok else 'No'} — "
                f"decisions={c.requirement_decision_ids}",
                f"4. **Physics dispatch:** "
                f"{'ICE physics skipped' if c.physics_skipped_ice else 'ICE physics path used or other'} — "
                f"warnings={c.physics_warnings}",
                f"Evidence JSON: `{c.evidence_path}`",
                f"Notes: {c.notes or 'none'}",
                "",
            ]
        )

    lines.extend(
        [
            "### B3.4 — Can a new domain be added without modifying the core pipeline?",
            "",
            "**Mostly yes after this phase:** add entries to "
            "`knowledge/functional/general_domains.py` and "
            "`knowledge/decomposition/component_templates.py`, optionally register a "
            "physics handler via `core.reasoning.domain_dispatch.register_physics_handler`. "
            "The pipeline calls `_run_physics` which dispatches; ICE `PhysicsEngine` is "
            "no longer unconditional.",
            "",
            "Residual coupling: `RequirementCompiler` ICE parameter extractors and "
            "`MaterialAssigner` role registry remain ICE-shaped for depth work — "
            "non-ICE materials stay honestly unassigned until Phase E.",
            "",
            "### Known gaps",
            "",
            f"- Pass threshold for Phase B done: **≥8/{total}**. Current: **{passed}/{total}**.",
            "- Live LLM outputs vary; re-run may change borderline cases.",
            "- DeterministicProvider still defaults to ICE (test fixture only).",
            "- No non-ICE quantitative physics module yet (Phase F).",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
