# Database migrations (Alembic, async)

Every schema change is a migration. Nobody edits tables by hand. Set up in B1-A1-06.

## Commands (run from the repository root; Docker uses `backend/` as the working folder)

```bash
docker compose up -d postgres
docker compose run --rm api alembic upgrade head        # apply all migrations
docker compose run --rm api alembic current             # show the current revision
docker compose run --rm api alembic downgrade -1        # undo the last migration
```

New migration (after changing models in `backend/app/models/`), with the next number as the id:

```bash
docker compose run --rm --user "$(id -u):$(id -g)" api \
  alembic revision --autogenerate --rev-id 0002 -m "initial schema"
```

`--user` keeps the new file owned by you instead of root. Always read the generated file before
committing it; autogenerate can miss renames and server defaults.

## Rules

- The database URL comes from `DATABASE_URL` (`.env` locally, the CI service in GitHub Actions).
  `alembic.ini` never contains a URL or password.
- Revision ids are numbers: `0001`, `0002`, … (files `<rev>_<slug>.py`).
- `spatial_ref_sys` and the `tiger` / `topology` schemas belong to PostGIS and are ignored.
- `0001_enable_postgis` downgrade drops PostGIS without CASCADE: PostgreSQL refuses if anything
  depends on it, so nothing is deleted by accident.
- Tests: `backend/tests/integration/test_migrations.py` runs upgrade, downgrade and a no-difference
  check on a throwaway database (`dispatch_migrations_test`) that is created and deleted by the test.
