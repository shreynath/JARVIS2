"""Recursive decomposition engine — top-down design expansion."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from core.ir.component import ComponentNode
from core.ir.design_graph import EngineeringDesignGraph, EngineeringIntent
from llm.ollama_client import LLMProvider
from llm.structured_output import StructuredOutput

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "llm" / "prompts"

DEFAULT_COMPLEXITY_THRESHOLD = 1.0
MAX_DECOMPOSITION_DEPTH = 6


class _ArchitectNode(BaseModel):
    id: str
    name: str
    function: str
    material: str | None = None
    complexity_score: float = 1.0
    is_leaf: bool = False


class _ArchitectResponse(BaseModel):
    nodes: list[_ArchitectNode] = Field(default_factory=list)


class DecompositionEngine:
    """Recursively expand assemblies until component complexity < threshold."""

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

    def decompose(self, intent: EngineeringIntent) -> EngineeringDesignGraph:
        graph = EngineeringDesignGraph(
            name=intent.design_goal,
            type=intent.object_type,
            intent=intent,
            root_id="root",
        )

        root = ComponentNode(
            id="root",
            name=intent.design_goal,
            type=intent.object_type,
            function=f"Root assembly for {intent.object_type}",
            complexity_score=5.0,
        )
        graph.add_component(root)

        self._expand_node(graph, root, intent, depth=0)
        return graph

    def _expand_node(
        self,
        graph: EngineeringDesignGraph,
        node: ComponentNode,
        intent: EngineeringIntent,
        depth: int,
    ) -> None:
        if depth >= self.max_depth:
            node.is_leaf = True
            return
        if node.complexity_score <= self.complexity_threshold:
            node.is_leaf = True
            return

        user_prompt = (
            f"Intent: {intent.model_dump_json()}\n"
            f"Expand parent: id={node.id}, name={node.name}, function={node.function}\n"
            f"Depth: {depth}"
        )

        response = self._structured.generate(
            self._system_prompt,
            user_prompt,
            _ArchitectResponse,
        )

        child_ids: list[str] = []
        for arch_node in response.nodes:
            if arch_node.id in graph.components:
                arch_node_id = f"{node.id}_{arch_node.id}"
            else:
                arch_node_id = arch_node.id

            child = ComponentNode(
                id=arch_node_id,
                name=arch_node.name,
                function=arch_node.function,
                material=arch_node.material,
                parent_id=node.id,
                complexity_score=arch_node.complexity_score,
                is_leaf=arch_node.is_leaf,
            )
            graph.add_component(child)
            child_ids.append(child.id)

            if not child.is_leaf and child.complexity_score > self.complexity_threshold:
                self._expand_node(graph, child, intent, depth + 1)
            elif child.complexity_score <= self.complexity_threshold:
                child.is_leaf = True

        node.children = child_ids
