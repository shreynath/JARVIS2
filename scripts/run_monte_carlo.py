#!/usr/bin/env python3
"""Monte Carlo uncertainty propagation over assumed bands."""

from __future__ import annotations

import json
from pathlib import Path

from verification.monte_carlo import run_monte_carlo

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    report = run_monte_carlo(n_samples=1000, seed=42)
    path = ROOT / "output" / "monte_carlo_summary.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"wrote {path}")
    mps = report["distributions"]["mean_piston_speed_m_s"]
    print(f"MPS mean={mps['mean']:.3f} σ={mps['sigma']:.3f} 95%[{mps['p95_low']:.3f},{mps['p95_high']:.3f}]")


if __name__ == "__main__":
    main()
