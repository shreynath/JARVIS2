"""Engineering taxonomy — hierarchical classification of engineered objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TaxonomyNode:
    """A node in the engineering taxonomy tree."""

    id: str
    label: str
    parent_id: str | None = None
    aliases: tuple[str, ...] = ()
    required_domains: tuple[str, ...] = ()


class EngineeringTaxonomy:
    """Static taxonomy for classifying engineered objects.

    Extended beyond ICE so non-engine requests are not forced into the engine
    subtree. Matching prefers specific aliases over the blunt ``\"engine\"`` heuristic.
    """

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
        # --- Phase B generality nodes ---
        "furniture": TaxonomyNode(
            id="furniture",
            label="Furniture",
            required_domains=("structural_analysis", "mechanical_design", "materials"),
        ),
        "dining_chair": TaxonomyNode(
            id="dining_chair",
            label="Dining Chair",
            parent_id="furniture",
            aliases=("wooden dining chair", "chair", "wooden chair"),
            required_domains=("structural_analysis", "mechanical_design", "materials"),
        ),
        "bicycle_frame": TaxonomyNode(
            id="bicycle_frame",
            label="Bicycle Frame",
            aliases=("bike frame", "road bicycle frame", "bicycle"),
            required_domains=("structural_analysis", "mechanical_design", "materials"),
        ),
        "steel_truss_bridge": TaxonomyNode(
            id="steel_truss_bridge",
            label="Steel Truss Bridge",
            aliases=("truss bridge", "bridge"),
            required_domains=("structural_analysis", "civil_engineering", "materials"),
        ),
        "quadcopter_frame": TaxonomyNode(
            id="quadcopter_frame",
            label="Quadcopter Frame",
            aliases=("drone frame", "multirotor frame", "quadcopter"),
            required_domains=("structural_analysis", "mechanical_design", "aerodynamics", "materials"),
        ),
        "hvac_ductwork": TaxonomyNode(
            id="hvac_ductwork",
            label="HVAC Ductwork",
            aliases=("ductwork", "residential hvac"),
            required_domains=("fluid_dynamics", "thermal", "mechanical_design"),
        ),
        "battery_pack_enclosure": TaxonomyNode(
            id="battery_pack_enclosure",
            label="Battery Pack Enclosure",
            aliases=("battery enclosure", "battery pack"),
            required_domains=("mechanical_design", "thermal", "electrical", "materials"),
        ),
        "centrifugal_pump": TaxonomyNode(
            id="centrifugal_pump",
            label="Centrifugal Pump",
            aliases=("water pump", "centrifugal water pump"),
            required_domains=("fluid_dynamics", "mechanical_design", "materials"),
        ),
        "robotic_arm_gripper": TaxonomyNode(
            id="robotic_arm_gripper",
            label="Robotic Arm Gripper",
            aliases=("gripper", "robotic gripper"),
            required_domains=("mechatronics", "mechanical_design", "electrical"),
        ),
        "pressure_vessel": TaxonomyNode(
            id="pressure_vessel",
            label="Pressure Vessel",
            aliases=("nitrogen pressure vessel", "compressed gas vessel"),
            required_domains=("structural_analysis", "mechanical_design", "safety", "materials"),
        ),
        "solar_panel_mounting_rack": TaxonomyNode(
            id="solar_panel_mounting_rack",
            label="Solar Panel Mounting Rack",
            aliases=("solar rack", "solar mounting rack"),
            required_domains=("structural_analysis", "civil_engineering", "mechanical_design"),
        ),
    }

    @classmethod
    def get(cls, node_id: str) -> TaxonomyNode | None:
        return cls._NODES.get(node_id)

    @classmethod
    def resolve_from_text(cls, text: str) -> TaxonomyNode | None:
        """Match taxonomy node from natural language hints (most specific first)."""
        lower = text.lower()

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
            best = candidates[0][2]
            # "vehicle engine" must not resolve to vehicle when ICE is clearly meant.
            if (
                best.id in {"vehicle", "aircraft"}
                and "engine" in lower
                and not any(p in lower for p in ("jet engine", "turbofan", "turbojet", "rocket engine"))
            ):
                if any(n in lower for n in ("v12", "v-12", "twelve cylinder")):
                    return cls._NODES["v12_engine"]
                if any(n in lower for n in ("v8", "v-8", "eight cylinder")):
                    return cls._NODES["v8_engine"]
                return cls._NODES["internal_combustion_engine"]
            return best

        # ICE heuristic only when no specific node matched and text is clearly ICE.
        if any(p in lower for p in ("jet engine", "turbofan", "turbojet", "rocket engine")):
            return None
        if any(n in lower for n in ("v12", "v-12", "twelve cylinder")):
            return cls._NODES["v12_engine"]
        if any(n in lower for n in ("v8", "v-8", "eight cylinder")):
            return cls._NODES["v8_engine"]
        if "internal combustion" in lower or (
            "engine" in lower and "jet" not in lower and "turbofan" not in lower
        ):
            return cls._NODES["internal_combustion_engine"]

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
