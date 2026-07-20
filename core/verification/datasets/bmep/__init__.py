"""Phase 8.7 BMEP family datasets — never pool families."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Family = Literal["naturally_aspirated", "turbocharged", "diesel", "aircraft", "motorcycle"]

FAMILIES: tuple[Family, ...] = (
    "naturally_aspirated",
    "turbocharged",
    "diesel",
    "aircraft",
    "motorcycle",
)

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class BmepEngineRecord:
    engine: str
    engine_id: str
    architecture: str | None
    rpm: float | None
    hp: float | None
    torque_nm: float | None
    displacement_l: float | None
    aspiration: str | None
    fuel: str | None
    source: str
    family: Family

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "engine_id": self.engine_id,
            "architecture": self.architecture,
            "rpm": self.rpm,
            "hp": self.hp,
            "torque_nm": self.torque_nm,
            "displacement_l": self.displacement_l,
            "aspiration": self.aspiration,
            "fuel": self.fuel,
            "source": self.source,
            "family": self.family,
        }


def bmep_bar_from_torque_displacement(torque_nm: float, displacement_l: float) -> float:
    """Four-stroke BMEP = 4π T / V_d → Pa → bar."""
    v_m3 = displacement_l / 1000.0
    return (4.0 * math.pi * torque_nm / v_m3) / 1e5


def displacement_l_from_hp_rpm_bmep(
    horsepower: float, rpm: float, bmep_bar: float
) -> float:
    hp_to_kw = 0.745699872
    power_w = horsepower * hp_to_kw * 1000.0
    bmep_pa = bmep_bar * 1e5
    return power_w * 120.0 / (bmep_pa * rpm) * 1000.0


def load_bmep_family(family: Family) -> list[BmepEngineRecord]:
    folder = ROOT / family
    rows: list[BmepEngineRecord] = []
    if not folder.exists():
        return rows
    for path in sorted(folder.glob("*.json")):
        raw = json.loads(path.read_text())
        rows.append(
            BmepEngineRecord(
                engine=str(raw.get("engine") or raw.get("name") or path.stem),
                engine_id=str(raw.get("engine_id") or raw.get("id") or path.stem),
                architecture=raw.get("architecture"),
                rpm=raw.get("rpm") if raw.get("rpm") is not None else raw.get("max_rpm"),
                hp=raw.get("hp") if raw.get("hp") is not None else raw.get("horsepower"),
                torque_nm=raw.get("torque_nm"),
                displacement_l=raw.get("displacement_l"),
                aspiration=raw.get("aspiration"),
                fuel=raw.get("fuel"),
                source=str(raw.get("source") or ""),
                family=family,
            )
        )
    return rows


def load_all_bmep_families() -> dict[Family, list[BmepEngineRecord]]:
    return {f: load_bmep_family(f) for f in FAMILIES}
