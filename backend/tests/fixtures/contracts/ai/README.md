# Contract C-2 fixtures (SIMULATED)

All example data in this folder is **SIMULATED**. It is not real patient, caller or vehicle data.

- `examples/<Model>.json` — one valid example per C-2 schema in `backend/app/schemas/ai.py`.
- `schemas/<Model>.schema.json` — the JSON Schema exported from the Pydantic model, for the web and
  mobile apps and for storage. A test fails if it is out of date. Regenerate with:

  ```bash
  docker compose run --rm --user "$(id -u):$(id -g)" -e UPDATE_CONTRACT_SCHEMAS=1 api pytest -q tests/unit/agents/test_ai_schemas.py
  ```
