# JARVIS 2.0 — Phase 1 Architecture

## Problem Statement

The original JARVIS codebase accumulated capable subsystems (document generation, knowledge graphs,
reasoning modules, CAD/FEM, simulation, agents) without a **central object** that every layer
understood. Subsystems could not compose because there was no shared semantic spine.

Phase 1 creates that spine: the **Engineering Semantic Kernel**.

## Design Goal

Convert a natural-language engineering request into a **validated, machine-readable engineering
design graph** — not a PDF, not CAD, not a simulation.

```
Natural Language Request
        ↓
EngineeringIntent          ← "What engineering question are we asking?"
        ↓
EngineeringOntology        ← "What concepts and relationships apply?"
        ↓
EngineeringDesignGraph     ← "What is the object, structurally?"
        ↓
Validated Specification    ← "Is this internally consistent?"
```

## Central Object: EngineeringDesignGraph

Every subsystem reads from or writes to `EngineeringDesignGraph`. This is the single source of
truth for what is being designed.

| Layer        | Responsibility                          | Modifies Graph? |
|--------------|-----------------------------------------|-----------------|
| Ontology     | Vocabulary: entity types, relationships | No (schema)     |
| IR           | Typed data structures for the graph     | Defines shape   |
| Reasoning    | Intent → decomposition → assumptions    | Yes (builds)    |
| Validation   | Invariant checking, criticism, repair     | Yes (fixes)     |
| LLM          | Transport + structured JSON extraction  | No (stateless)  |
| Knowledge    | Seed data: materials, rules, systems    | No (read-only)  |

## Layer Decisions

### 1. Ontology (`core/ontology/`)

Defines the **engineering vocabulary** — not instance data.

- **Entity types**: Component, Assembly, Material, Process, Constraint, Interface, FailureMode, Function
- **Relationship types**: COMPONENT_HAS_MATERIAL, COMPONENT_CONNECTS_TO, etc.
- **Taxonomy**: hierarchical classification (e.g., `internal_combustion_engine → reciprocating_engine → v12_engine`)

The ontology answers: *"What kinds of things can exist in a design graph?"*

### 2. IR — Intermediate Representation (`core/ir/`)

Typed Pydantic models that form the graph structure:

- `EngineeringIntent` — parsed engineering question
- `ComponentNode` — leaf or intermediate component with function, material, children
- `AssemblyNode` — grouping of components with interface definitions
- `Interface`, `Constraint`, `Assumption`, `Requirement`, `FailureMode`
- `EngineeringDesignGraph` — the root container with indexed node lookup

**Key invariant**: if component A lists component B as a child, component B **must** exist in the
graph. Enforced by validation, not convention.

### 3. Reasoning (`core/reasoning/`)

Python orchestrates; the LLM reasons. Three separate LLM roles, never one-shot:

| Role       | Input                    | Output                          |
|------------|--------------------------|---------------------------------|
| Architect  | Intent + parent context  | Decomposed children/systems     |
| Critic     | Design graph fragment    | Issues with severity            |
| Engineer   | Issues + fragment        | Repaired fragment               |

Pipeline stages:

1. **Intent Parser** — NL → `EngineeringIntent` (not domain classification)
2. **Decomposition Engine** — recursive top-down expansion until leaf threshold
3. **Assumption Manager** — records unknowns with defaults and confidence
4. **Critic** — attacks design for physics/material/consistency violations
5. **Repair** — fixes critic findings

Decomposition is **recursive**, not flat:

```
Engine
├── Block Assembly          → expand
├── Crankshaft Assembly     → expand
├── Cylinder Head Assembly  → expand
├── Fuel System             → expand
└── ...                     → until complexity < threshold
```

### 4. LLM (`llm/`)

Thin transport layer. No business logic.

```
Python Request → Ollama → Raw JSON → Pydantic Validator → (fail?) → Repair Prompt → Ollama
```

- `OllamaClient` — HTTP calls to local Ollama API
- `StructuredOutput` — JSON extraction, schema validation, repair loop
- `prompts/` — role-specific system prompts (Architect, Critic, Engineer, Intent)

A `DeterministicProvider` enables tests and offline use without Ollama.

### 5. Validation (`validation/`)

Three validators run after graph construction:

| Validator          | Checks                                           |
|--------------------|--------------------------------------------------|
| SchemaValidator    | Pydantic model validity, required fields         |
| ConsistencyChecker | Missing refs, invalid hierarchies, orphans       |
| PhysicsRulesEngine | Material suitability, mass/power contradictions  |

Output: `ValidationReport` with pass/fail, issues by severity, and affected node IDs.

### 6. Knowledge (`knowledge/`)

Seed data, not a database. Phase 1 ships minimal starter sets:

- Common engine materials and suitability rules
- Top-level engine system taxonomy
- Basic physics rules (e.g., carbon fiber unsuitable for cylinder bores)

Month 2 expands this into a persistent knowledge graph.

## Data Flow

```
main.py
  │
  ├─ IntentParser.parse(user_input)
  │     └─ LLM (Intent role) → EngineeringIntent
  │
  ├─ DecompositionEngine.decompose(intent)
  │     └─ LLM (Architect role) × N recursive calls → EngineeringDesignGraph
  │
  ├─ AssumptionManager.fill_unknowns(graph, intent)
  │     └─ records assumptions for intent.unknowns
  │
  ├─ Critic.review(graph)
  │     └─ LLM (Critic role) → list[CriticIssue]
  │
  ├─ Engineer.repair(graph, issues)
  │     └─ LLM (Engineer role) → patched graph
  │
  ├─ ValidationPipeline.validate(graph)
  │     └─ Schema + Consistency + Physics → ValidationReport
  │
  └─ write output/
        ├─ engine_design_graph.json
        ├─ assumptions.json
        └─ validation_report.json
```

## What Phase 1 Does NOT Build

- CAD generation
- FEM / simulation
- Visualization / dashboards
- Agent orchestration
- Persistent knowledge graph storage

These are downstream phases that consume the design graph.

## Testing Strategy

Every feature must answer:

1. What existing abstraction does this modify?
2. What new concept does this introduce?
3. Which layer does it belong to?
4. What test proves it works?

Tests use `DeterministicProvider` (no Ollama required) for CI. Integration tests optionally
hit live Ollama when `OLLAMA_HOST` is set.

## Extension Points (Future Phases)

| Phase   | Adds                                           | Reads From          |
|---------|------------------------------------------------|---------------------|
| Month 2 | Persistent knowledge graph                     | Ontology + IR       |
| Month 3 | Constraint solver                              | DesignGraph         |
| Month 4 | Material intelligence                          | Knowledge + IR      |
| Month 5 | CAD/FEM bridge (transplant from old JARVIS)    | Validated DesignGraph |

## File Layout

```
JARVIS2/
├── ARCHITECTURE.md          ← this document
├── core/
│   ├── ontology/            ← vocabulary (entity types, relationships, taxonomy)
│   ├── ir/                  ← typed graph structures (the central object)
│   └── reasoning/           ← intent, decomposition, assumptions, critic, pipeline
├── knowledge/               ← seed data (materials, systems, rules)
├── llm/                     ← Ollama transport + structured output + prompts
├── validation/              ← schema, consistency, physics validators
├── examples/                ← engine_generation.py
├── tests/                   ← unit + integration tests
└── main.py                  ← CLI entry point
```
