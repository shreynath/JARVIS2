"""Evidence-gated material decisions."""

from __future__ import annotations

from core.materials.component_role import COMPONENT_ROLE_REGISTRY, ComponentRole, role_for_component
from core.materials.material_decision import MaterialDecision
from core.materials.material_requirement import MaterialRequirementEvidence
from core.materials.requirements import MaterialRequirement

__all__ = [
    "COMPONENT_ROLE_REGISTRY",
    "ComponentRole",
    "MaterialDecision",
    "MaterialRequirement",
    "MaterialRequirementEvidence",
    "role_for_component",
]
