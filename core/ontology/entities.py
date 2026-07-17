"""Core entity types in the engineering ontology."""

from __future__ import annotations

from enum import StrEnum


class EntityType(StrEnum):
    """Kinds of nodes that can exist in an engineering design graph."""

    COMPONENT = "component"
    ASSEMBLY = "assembly"
    MATERIAL = "material"
    PROCESS = "process"
    CONSTRAINT = "constraint"
    INTERFACE = "interface"
    FAILURE_MODE = "failure_mode"
    FUNCTION = "function"
    REQUIREMENT = "requirement"
    ASSUMPTION = "assumption"
