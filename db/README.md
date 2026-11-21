# db/

| Folder | Content | Status |
|---|---|---|
| `seed/` | Seed data moved into the backend so it runs and is tested inside Docker: `backend/app/seed.py` and `backend/app/seed_data/*.json` (SIMULATED Sukkur vehicles, hospitals and accounts; B1-A1-34). | see backend |
| `simulators/` | SMS, voice and vehicle simulators | planned (Batch 4) |
| `sql/` | Reference SQL (duplicate candidates, performance reports) | planned |
| `eval_data/` | Labelled evaluation data for the AI | planned (B1-A2-16) |

Seed the local database (from the repository root; set the passwords in your `.env` first):

```bash
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.seed --size small   # or --size full
```
