# Phase A Remediation Report

## Phase: A

### Claim
Phase A (stop the bleeding) is complete:
1. `"design a v8 engine"` no longer raises a Pydantic `ValidationError` on `bmep_source=None`.
2. All `PhysicsCalculation.inputs` values are sanitized so `None` becomes the explicit sentinel `"unknown"` (class-of-bug fix, not a one-site patch).
3. Silent DeterministicProvider fallback is gone (Option 1 — transparent degraded mode): every CLI run and every JSON artifact records `provider_used`, `degraded`, and `warning`.
4. `DeterministicProvider` is documented as a **test fixture**, not a product interpreter.
5. A ≥25-request corpus acceptance test passes with zero unhandled exceptions.
6. Ollama cloud credentials live in gitignored `.env`; `.env.example` is the commitable template.

### Evidence

#### A1 — v8 crash fixed
```
$ python -c "from core.reasoning.pipeline import SemanticKernelPipeline; from llm.ollama_client import DeterministicProvider; p=SemanticKernelPipeline(provider=DeterministicProvider()); r=p.run('design a v8 engine'); print(r.intent.object_type, r.physics_analysis.by_id('calc_displacement').inputs.get('bmep_source'))"
internal_combustion_engine unknown
```

#### A1 — corpus + sanitizer tests
```
$ python -m pytest tests/test_phase_a_remediation.py tests/test_pipeline.py tests/test_physics_engine.py -q
.........................................                                [100%]
41 passed in 0.43s
```

#### A2 — CLI surfaces degradation before design output
```
$ python main.py "design a v8 engine"
⚠ Ollama unavailable — this is a template-derived stub answer, not a real analysis.

JARVIS 2.0 — Engineering Semantic Kernel
...
Provider: deterministic_fallback  degraded=True
...
```

#### A2 — JSON artifacts carry provider meta
```
$ cat output/pipeline_status.json
{
  "provider_used": "deterministic_fallback",
  "degraded": true,
  "warning": "⚠ Ollama unavailable — this is a template-derived stub answer, not a real analysis.",
  "evaluation_status": "incomplete"
}
```

Same `provider_used` / `degraded` / `warning` fields are injected into:
`engine_design_graph.json`, `requirement_specification.json`, `physics_analysis.json`, `assumptions.json`, `validation_report.json`.

#### Ollama cloud wiring
```
$ python -c "from llm.env_loader import load_dotenv; from llm.ollama_client import OllamaClient; load_dotenv(); c=OllamaClient(); print(c.host, c.is_available())"
https://ollama.com True
```
(Requires network; key in `.env`, not committed.)

### Known gaps
- **Phase B not started.** Domain generality is still broken under DeterministicProvider (chairs/bikes still resolve to `internal_combustion_engine` by fixture design). Live-LLM generality proof is Phase B.
- **Phases C–F not started** (verification integrity, architecture sync CI, materials completeness bar, non-ICE physics module).
- **`PhysicsEngine` is still unconditionally ICE-shaped** for every request — deferred to B4.
- Cloud default model set to `gpt-oss:20b` because `llama3.2` is not in the ollama.com catalog.
- **API key was pasted into chat.** Rotate it at https://ollama.com/settings/keys; only the gitignored `.env` holds the live value. Never commit secrets.
