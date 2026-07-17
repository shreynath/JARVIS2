"""Tests for ontology layer."""

from core.ontology.entities import EntityType
from core.ontology.relationships import RelationshipType
from core.ontology.taxonomy import EngineeringTaxonomy


def test_entity_types():
    assert EntityType.COMPONENT == "component"
    assert EntityType.ASSEMBLY == "assembly"
    assert len(EntityType) >= 8


def test_relationship_types():
    assert RelationshipType.COMPONENT_HAS_MATERIAL == "component_has_material"
    assert RelationshipType.ASSEMBLY_CONTAINS == "assembly_contains"


def test_taxonomy_resolve_engine():
    node = EngineeringTaxonomy.resolve_from_text("Create a vehicle engine specification")
    assert node is not None
    assert node.id == "internal_combustion_engine"


def test_taxonomy_ancestors():
    ancestors = EngineeringTaxonomy.ancestors("v12_engine")
    ids = [a.id for a in ancestors]
    assert "engine" in ids
    assert "internal_combustion_engine" in ids
    assert "v12_engine" in ids


def test_taxonomy_required_domains():
    domains = EngineeringTaxonomy.required_domains_for("internal_combustion_engine")
    assert "thermodynamics" in domains
    assert "mechanical_design" in domains
