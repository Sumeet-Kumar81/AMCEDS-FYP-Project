"""Enable the PostGIS extension (SDS v1.1 §5, SRS SW-4).

Revision ID: 0001
Revises:
Create Date: 2026-11-21

Downgrade drops PostGIS WITHOUT CASCADE on purpose: if anything else depends on it (geometry
columns, or the tiger/topology extensions that the postgis/postgis image installs in its default
database) PostgreSQL refuses and nothing is deleted. Decided by the project developer, B1-A1-06.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS postgis")
