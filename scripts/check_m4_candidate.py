#!/usr/bin/env python3
"""Simulate M4 eligibility from campaign_result.json — does NOT promote."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.verification.m4_candidate import format_m4_candidate_report, load_and_evaluate


def main() -> None:
    parser = argparse.ArgumentParser(description="Check M4 candidate eligibility (simulation only)")
    parser.add_argument(
        "campaign_result",
        nargs="?",
        default=str(ROOT / "output" / "campaign_result.json"),
        help="Path to campaign_result.json",
    )
    args = parser.parse_args()
    result = load_and_evaluate(args.campaign_result)
    print(format_m4_candidate_report(result))
    if result["m4_eligibility"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
