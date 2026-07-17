"""Relationship types between engineering entities."""

from __future__ import annotations

from enum import StrEnum


class RelationshipType(StrEnum):
    """Typed edges in the engineering ontology."""

    COMPONENT_HAS_MATERIAL = "component_has_material"
    COMPONENT_CONNECTS_TO = "component_connects_to"
    COMPONENT_SUPPORTS_FUNCTION = "component_supports_function"
    COMPONENT_FAILS_BY = "component_fails_by"
    COMPONENT_REQUIRES = "component_requires"
    MATERIAL_SUITABLE_FOR = "material_suitable_for"
    ASSEMBLY_CONTAINS = "assembly_contains"
    COMPONENT_HAS_INTERFACE = "component_has_interface"
    COMPONENT_SUBJECT_TO = "component_subject_to"
    CONSTRAINT_APPLIES_TO = "constraint_applies_to"
