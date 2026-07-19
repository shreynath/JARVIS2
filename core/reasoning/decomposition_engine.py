"""Recursive decomposition engine — function-driven, assembly-first design expansion."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from core.ir.assembly import AssemblyNode
from core.ir.component import ComponentNode
from core.ir.design_graph import EngineeringDesignGraph, EngineeringIntent
from core.ir.functional import FunctionalAnalysis
from core.ir.requirement_spec import RequirementSpecification
from knowledge.decomposition.component_templates import (
    COMPONENT_TEMPLATES,
    GENERIC_COMPONENT_NAMES,
)
from llm.ollama_client import LLMProvider
from llm.structured_output import StructuredOutput

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "llm" / "prompts"

DEFAULT_COMPLEXITY_THRESHOLD = 1.0
MAX_DECOMPOSITION_DEPTH = 6


class _ArchitectNode(BaseModel):
    id: str
    name: str
    function: str
    purpose: str = ""
    justification: str = ""
    serves_function_id: str | None = None
    material: str | None = None
    complexity_score: float = 1.0
    is_leaf: bool = False


class _ArchitectResponse(BaseModel):
    nodes: list[_ArchitectNode] = Field(default_factory=list)


class DecompositionEngine:
    """Expand assemblies into components guided by functional analysis."""

    def __init__(
        self,
        provider: LLMProvider,
        complexity_threshold: float = DEFAULT_COMPLEXITY_THRESHOLD,
        max_depth: int = MAX_DECOMPOSITION_DEPTH,
    ) -> None:
        self._structured = StructuredOutput(provider)
        self._system_prompt = (_PROMPT_DIR / "architect.txt").read_text()
        self.complexity_threshold = complexity_threshold
        self.max_depth = max_depth

    def decompose(
        self,
        intent: EngineeringIntent,
        functional_analysis: FunctionalAnalysis,
        requirement_spec: RequirementSpecification | None = None,
    ) -> EngineeringDesignGraph:
        graph = EngineeringDesignGraph(
            name=intent.design_goal,
            type=intent.object_type,
            intent=intent,
            root_id="root",
            functional_analysis=functional_analysis,
        )

        root = AssemblyNode(
            id="root",
            name=intent.design_goal,
            function=functional_analysis.primary_function,
            purpose=f"Top-level {intent.object_type} assembly",
            justification="Root assembly serving primary system function",
            serves_functions=[f.id for f in functional_analysis.functions if not f.requires][:3],
        )
        graph.add_assembly(root)

        assembly_ids: list[str] = []
        for req_asm in functional_analysis.required_assemblies:
            parent_id = req_asm.parent_assembly_id or "root"
            assembly = AssemblyNode(
                id=req_asm.id,
                name=req_asm.name,
                function=req_asm.function,
                purpose=req_asm.purpose,
                justification=f"Identified by functional analysis to serve {', '.join(req_asm.serves_functions)}",
                parent_id=parent_id,
                serves_functions=req_asm.serves_functions,
            )
            graph.add_assembly(assembly)
            assembly_ids.append(assembly.id)

            if parent_id in graph.assemblies:
                parent = graph.assemblies[parent_id]
                if assembly.id not in parent.children:
                    parent.children.append(assembly.id)

        for assembly_id in assembly_ids:
            assembly = graph.assemblies[assembly_id]
            self._expand_assembly(graph, assembly, intent, functional_analysis, depth=0)

        return graph

    def _expand_assembly(
        self,
        graph: EngineeringDesignGraph,
        assembly: AssemblyNode,
        intent: EngineeringIntent,
        functional_analysis: FunctionalAnalysis,
        depth: int,
    ) -> None:
        if depth >= self.max_depth:
            return

        user_prompt = (
            f"Functional analysis: {functional_analysis.model_dump_json()}\n"
            f"Expand assembly: id={assembly.id}, name={assembly.name}, "
            f"function={assembly.function}, serves={assembly.serves_functions}\n"
            f"Intent: {intent.model_dump_json()}\n"
            f"Depth: {depth}"
        )

        try:
            response = self._structured.generate(
                self._system_prompt,
                user_prompt,
                _ArchitectResponse,
            )
            nodes = [n.model_dump() for n in response.nodes]
        except (ValueError, RuntimeError):
            nodes = []

        nodes = self._filter_generic_nodes(nodes, assembly.id)

        member_ids: list[str] = []
        for node_data in nodes:
            comp_id = node_data["id"]
            if comp_id in graph.components:
                comp_id = f"{assembly.id}_{comp_id}"

            purpose = node_data.get("purpose") or f"Serve {assembly.function}"
            justification = node_data.get("justification") or (
                f"Required by {assembly.name} to fulfill {assembly.function}"
            )
            serves_fn = node_data.get("serves_function_id")
            if not serves_fn and assembly.serves_functions:
                serves_fn = assembly.serves_functions[0]

            component = ComponentNode(
                id=comp_id,
                name=node_data["name"],
                function=node_data["function"],
                purpose=purpose,
                justification=justification,
                material=node_data.get("material"),
                parent_assembly_id=assembly.id,
                serves_function_id=serves_fn,
                complexity_score=node_data.get("complexity_score", 1.0),
                is_leaf=node_data.get("is_leaf", True),
            )
            graph.add_component(component)
            member_ids.append(component.id)

        assembly.member_ids = member_ids

    @staticmethod
    def _filter_generic_nodes(nodes: list[dict], assembly_id: str) -> list[dict]:
        filtered = [
            n for n in nodes
            if n.get("name", "").lower() not in GENERIC_COMPONENT_NAMES
            and n.get("id", "").lower() not in GENERIC_COMPONENT_NAMES
        ]
        if filtered:
            return filtered

        template = COMPONENT_TEMPLATES.get(assembly_id, [])
        if template:
            return template

        return []
