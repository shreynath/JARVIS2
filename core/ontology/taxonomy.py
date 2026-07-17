"""Engineering taxonomy — hierarchical classification of engineered objects."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TaxonomyNode:
    """A node in the engineering taxonomy tree."""

    id: str
    label: str
    parent_id: str | None = None
    aliases: tuple[str, ...] = ()
    required_domains: tuple[str, ...] = ()


class EngineeringTaxonomy:
    """Static taxonomy for classifying engineered objects."""

    _NODES: dict[str, TaxonomyNode] = {
        "engine": TaxonomyNode(
            id="engine",
            label="Engine",
            required_domains=("thermodynamics", "mechanical_design", "materials"),
        ),
        "internal_combustion_engine": TaxonomyNode(
            id="internal_combustion_engine",
            label="Internal Combustion Engine",
            parent_id="engine",
            aliases=("ice", "combustion engine"),
            required_domains=("thermodynamics", "mechanical_design", "materials", "fluid_dynamics"),
        ),
        "reciprocating_engine": TaxonomyNode(
            id="reciprocating_engine",
            label="Reciprocating Engine",
            parent_id="internal_combustion_engine",
            required_domains=("thermodynamics", "mechanical_design", "materials"),
        ),
        "v12_engine": TaxonomyNode(
            id="v12_engine",
            label="V12 Engine",
            parent_id="reciprocating_engine",
            aliases=("v-12", "twelve cylinder"),
        ),
        "v8_engine": TaxonomyNode(
            id="v8_engine",
            label="V8 Engine",
            parent_id="reciprocating_engine",
            aliases=("v-8", "eight cylinder"),
        ),
        "vehicle": TaxonomyNode(
            id="vehicle",
            label="Vehicle",
            required_domains=("mechanical_design", "materials", "aerodynamics"),
        ),
        "aircraft": TaxonomyNode(
            id="aircraft",
            label="Aircraft",
            required_domains=("aerodynamics", "structural_analysis", "materials"),
        ),
    }

    @classmethod
    def get(cls, node_id: str) -> TaxonomyNode | None:
        return cls._NODES.get(node_id)

    @classmethod
    def resolve_from_text(cls, text: str) -> TaxonomyNode | None:
        """Match taxonomy node from natural language hints (most specific first)."""
        lower = text.lower()

        if "engine" in lower:
            if any(n in lower for n in ("v12", "v-12", "twelve cylinder")):
                return cls._NODES["v12_engine"]
            if any(n in lower for n in ("v8", "v-8", "eight cylinder")):
                return cls._NODES["v8_engine"]
            return cls._NODES["internal_combustion_engine"]

        candidates: list[tuple[int, int, TaxonomyNode]] = []
        for node in cls._NODES.values():
            terms = [node.id.replace("_", " "), node.label.lower(), *node.aliases]
            for term in terms:
                if term and term in lower:
                    depth = len(cls.ancestors(node.id))
                    candidates.append((depth, len(term), node))
                    break

        if candidates:
            candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
            return candidates[0][2]
        return None

    @classmethod
    def ancestors(cls, node_id: str) -> list[TaxonomyNode]:
        """Return ancestor chain from root to node (inclusive)."""
        chain: list[TaxonomyNode] = []
        current_id: str | None = node_id
        while current_id is not None:
            node = cls._NODES.get(current_id)
            if node is None:
                break
            chain.insert(0, node)
            current_id = node.parent_id
        return chain

    @classmethod
    def required_domains_for(cls, node_id: str) -> list[str]:
        """Collect required engineering domains from node and ancestors."""
        domains: list[str] = []
        for node in cls.ancestors(node_id):
            domains.extend(node.required_domains)
        return list(dict.fromkeys(domains))
