"""Shared column helpers for the models (B1-A1-07…11).

* Allowed values are stored as text with CHECK constraints (decision D-005), built from the C-1
  enums so the database and the API can never disagree.
* Every timestamp is ``timestamptz`` (UTC on the wire).
* Map points are PostGIS ``geometry(Point, 4326)`` (WGS 84, the GPS system).
"""
from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, DateTime

TZ = DateTime(timezone=True)


def point(*, spatial_index: bool = True) -> Geometry:
    return Geometry(geometry_type="POINT", srid=4326, spatial_index=spatial_index)


def one_of(column: str, values: type[StrEnum] | Iterable[str], *, name: str | None = None) -> CheckConstraint:
    """CHECK (column IN (...)) from a C-1 enum or a list. NULL passes (use nullable=False to forbid it)."""
    items = [v.value for v in values] if isinstance(values, type) else list(values)
    listed = ", ".join("'" + v.replace("'", "''") + "'" for v in items)
    return CheckConstraint(f"{column} IN ({listed})", name=name or f"{column}_allowed")
