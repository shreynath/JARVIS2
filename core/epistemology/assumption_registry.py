"""Central registry for explicit engineering assumptions (never silent)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class RegisteredAssumption:
    """One explicit modeling assumption with provenance."""

    id: str
    field: str
    assumed_value: str | float | int | None
    rationale: str
    source_model: str
    confidence: str = "low"  # high | medium | low
    category: str = "engineering"  # engineering | geometry | material | process


@dataclass
class AssumptionRegistry:
    """Mutable collector used during engineering model evaluation."""

    _items: list[RegisteredAssumption] = field(default_factory=list)

    def record(
        self,
        *,
        id: str,
        field: str,
        assumed_value: str | float | int | None,
        rationale: str,
        source_model: str,
        confidence: str = "low",
        category: str = "engineering",
    ) -> RegisteredAssumption:
        item = RegisteredAssumption(
            id=id,
            field=field,
            assumed_value=assumed_value,
            rationale=rationale,
            source_model=source_model,
            confidence=confidence,
            category=category,
        )
        self._items.append(item)
        return item

    def extend(self, other: AssumptionRegistry | list[RegisteredAssumption]) -> None:
        if isinstance(other, AssumptionRegistry):
            self._items.extend(other._items)
        else:
            self._items.extend(other)

    def all(self) -> list[RegisteredAssumption]:
        return list(self._items)

    def as_dicts(self) -> list[dict[str, Any]]:
        return [asdict(i) for i in self._items]

    def as_strings(self) -> list[str]:
        """PhysicsCalculation.assumptions-compatible strings."""
        out: list[str] = []
        for i in self._items:
            out.append(f"{i.field}={i.assumed_value!r} ({i.rationale})")
        return out

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)
