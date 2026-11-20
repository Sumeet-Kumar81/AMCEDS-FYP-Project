# Code sketches (tested design material, not application code)

Flat copies of the agent logic described in `../06_AI_AGENTS.md`, with 46 pytest tests. They exist so the design is proven before it is built.

Run (needs Python 3.11+ with `pydantic` v2 and `pytest`):

```bash
cd docs/blueprint/code_sketches
python -m pytest -q -p no:cacheprovider
```

Result when written (2026-11-20, Python 3.13, pydantic 2.13, pytest 9.1): **46 passed**.

Differences from the real implementation: flat module names (the real files live under `backend/app/agents/`; `allocation.py` becomes `resource.py`), a `FakeStore` instead of `pipeline_store`, a `FakeLLM` instead of the LLM Gateway, no PostGIS or OSRM, no LangGraph. Constants marked *proposed* (D-007/D-033 weights and decay, D-019 vehicle rules, D-021 skip rule) are not approved.
