#!/usr/bin/env python3
"""Independent reality audit entrypoint — does not import PhysicsEngine."""

from __future__ import annotations

import json
from pathlib import Path

from core.verification.maturity_report import write_maturity_artifacts
from core.verification.bmep_validation import write_bmep_validation
from core.verification.campaign_gate import write_campaign_result
from core.verification.campaigns.high_rpm_dynamics import (
    build_failure_packet,
    build_validation_report,
    write_high_rpm_reports,
)
from core.verification.maturity_campaigns import write_campaign_report
from core.verification.maturity_planner import write_maturity_roadmap
from core.verification.maturity_scorecard import write_maturity_scorecard
from core.verification.model_closure import write_model_closure_report
from core.verification.phase6_reports import write_phase6_reports
from core.verification.uncertainty import run_uncertainty_analysis
from core.verification.bmep_campaign import write_bmep_campaign_reports
from core.verification.rod_campaign import write_rod_campaign_reports
from core.verification.material_validation import write_material_campaign_reports
from core.verification.prediction_confidence import write_design_prediction_confidence
from core.verification.upgrade_report import write_model_upgrade_report
from verification.impact_analysis import write_model_impact_report
from verification.reality_auditor import run_reality_audit

ROOT = Path(__file__).resolve().parent


def main() -> None:
    out_dir = ROOT / "output"
    write_phase6_reports(out_dir, include_jarvis=False)
    write_bmep_validation(out_dir)
    paths = write_high_rpm_reports(out_dir)
    validation = build_validation_report()
    failures = build_failure_packet(validation)
    write_campaign_result(out_dir, validation=validation, failure_packet=failures)
    print(f"wrote {paths['validation']}")
    print(f"wrote {paths['failures']}")
    print(f"wrote {out_dir / 'campaign_result.json'}")
    unc = run_uncertainty_analysis(horsepower=800, rpm=9000, cylinder_count=12, n_samples=1500)
    (out_dir / "uncertainty_propagation.json").write_text(
        __import__("json").dumps(unc, indent=2, default=str)
    )
    print(f"wrote {out_dir / 'uncertainty_propagation.json'}")
    impact_path = write_model_impact_report(out_dir)
    write_model_closure_report(out_dir)
    write_maturity_roadmap(out_dir)
    write_maturity_scorecard(out_dir)
    write_campaign_report(out_dir)
    write_rod_campaign_reports(out_dir)
    write_bmep_campaign_reports(out_dir)
    write_material_campaign_reports(out_dir)
    write_design_prediction_confidence(out_dir)
    print(f"wrote {impact_path}")
    print(f"wrote {out_dir / 'maturity_roadmap.json'}")
    print(f"wrote {out_dir / 'maturity_scorecard.json'}")
    print(f"wrote {out_dir / 'maturity_campaigns.json'}")
    print(f"wrote {out_dir / 'rod_validation_report.json'}")
    print(f"wrote {out_dir / 'bmep_campaign_report.json'}")
    print(f"wrote {out_dir / 'material_validation_report.json'}")
    print(f"wrote {out_dir / 'design_prediction_confidence.json'}")

    report = run_reality_audit(out_dir)
    out = out_dir / "reality_audit.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"wrote {out}")
    final = out_dir / "final_reality_audit.json"
    final.write_text(json.dumps(report, indent=2, default=str))
    print(f"wrote {final}")
    print(f"overall_confidence={report['overall_confidence']}")
    print(f"scientific_score={report['scientific_score']}")
    print(f"scientific_confidence={report.get('scientific_confidence')}")
    print(f"average_maturity={report.get('average_maturity')}")
    print(f"auditor_import_gate_passed={report['auditor_import_gate']['passed']}")
    print(f"formula_passed={report['formula_correctness']['passed']}")

    maturity_paths = write_maturity_artifacts(out_dir)
    for name, path in maturity_paths.items():
        print(f"wrote {path}")
    print(f"wrote {write_model_upgrade_report(out_dir)}")

    if not report["auditor_import_gate"]["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
