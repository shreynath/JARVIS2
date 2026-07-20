"""Engineering reasoning pipeline."""

from __future__ import annotations

from typing import Any

__all__ = [
    "AssumptionManager",
    "ConstraintGenerator",
    "DesignCritic",
    "DesignEngineer",
    "DecompositionEngine",
    "FunctionalDecompositionEngine",
    "IntentParser",
    "MaterialAssigner",
    "PhysicsEngine",
    "RequirementCompiler",
    "SemanticKernelPipeline",
]


def __getattr__(name: str) -> Any:
    if name == "SemanticKernelPipeline":
        from core.reasoning.pipeline import SemanticKernelPipeline

        return SemanticKernelPipeline
    if name == "PhysicsEngine":
        from core.reasoning.physics_engine import PhysicsEngine

        return PhysicsEngine
    if name == "MaterialAssigner":
        from core.reasoning.material_assigner import MaterialAssigner

        return MaterialAssigner
    if name == "RequirementCompiler":
        from core.reasoning.requirement_compiler import RequirementCompiler

        return RequirementCompiler
    if name == "IntentParser":
        from core.reasoning.intent_parser import IntentParser

        return IntentParser
    if name == "AssumptionManager":
        from core.reasoning.assumption_manager import AssumptionManager

        return AssumptionManager
    if name == "ConstraintGenerator":
        from core.reasoning.constraint_generator import ConstraintGenerator

        return ConstraintGenerator
    if name == "DesignCritic":
        from core.reasoning.critic import DesignCritic

        return DesignCritic
    if name == "DesignEngineer":
        from core.reasoning.engineer import DesignEngineer

        return DesignEngineer
    if name == "DecompositionEngine":
        from core.reasoning.decomposition_engine import DecompositionEngine

        return DecompositionEngine
    if name == "FunctionalDecompositionEngine":
        from core.reasoning.functional_decomposition_engine import FunctionalDecompositionEngine

        return FunctionalDecompositionEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
