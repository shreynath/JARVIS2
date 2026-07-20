"""Evidence-gated material decisions."""

from __future__ import annotations

from core.materials.component_role import COMPONENT_ROLE_REGISTRY, ComponentRole, role_for_component
from core.materials.material_decision import MaterialDecision

__all__ = [
    "COMPONENT_ROLE_REGISTRY",
    "ComponentRole",
    "MaterialDecision",
    "role_for_component",
]
