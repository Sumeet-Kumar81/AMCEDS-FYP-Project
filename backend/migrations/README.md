Owner: Khalid. After `docker compose up -d postgres`:
  cd backend
  alembic init -t async migrations   (merge with this folder; set URL from env)
  alembic revision --autogenerate -m "initial schema"
  alembic upgrade head
First migration must run: CREATE EXTENSION IF NOT EXISTS postgis
Nobody edits tables by hand. Every change = migration PR + message to the team.
