"""High-RPM dynamics Campaign A — public package surface."""

from core.verification.campaigns.high_rpm_dynamics.dataset import load_high_rpm_dataset
from core.verification.campaigns.high_rpm_dynamics.evaluator import evaluate_dataset
from core.verification.campaigns.high_rpm_dynamics.report import (
    build_failure_packet,
    build_validation_report,
    evaluate_high_rpm_campaign,
    write_high_rpm_reports,
)

__all__ = [
    "build_failure_packet",
    "build_validation_report",
    "evaluate_dataset",
    "evaluate_high_rpm_campaign",
    "load_high_rpm_dataset",
    "write_high_rpm_reports",
]
