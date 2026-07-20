"""Campaign packages — evidence acquisition, never production physics imports."""

from core.verification.campaigns.high_rpm_dynamics import (
    evaluate_high_rpm_campaign,
    load_high_rpm_dataset,
    write_high_rpm_reports,
)

__all__ = [
    "evaluate_high_rpm_campaign",
    "load_high_rpm_dataset",
    "write_high_rpm_reports",
]
