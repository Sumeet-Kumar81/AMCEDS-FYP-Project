"""SIMULATED seed data for the Sukkur pilot area (B1-A1-34). Idempotent: running it again adds nothing.

Usage (from the repository root):
    docker compose run --rm -e SEED_ADMIN_PASSWORD=... -e SEED_DISPATCHER_PASSWORD=... \\
        -e SEED_DRIVER_PASSWORD=... api python -m app.seed --size small|full

* Data files: ``app/seed_data/{vehicles,hospitals,users}.json``. Everything is labelled SIMULATED.
* Passwords never live in the code or the data files. They come from the environment; a role whose
  password is not set is skipped (and reported), so no account ever gets a made-up password.
* Existing rows are never changed: users by ``username``, vehicles by ``plate_number`` and hospitals
  by ``name`` are only inserted when missing. A driver is linked to its vehicle when the vehicle has
  no driver yet. New accounts are audited (``user.created``).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import bcrypt
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Hospital, User, Vehicle
from app.schemas.auth import UserRole
from app.services.audit import AuditAction, record

logger = logging.getLogger(__name__)

DATA = Path(__file__).resolve().parent / "seed_data"
Size = Literal["small", "full"]
PASSWORD_ENV = {
    UserRole.ADMIN: "SEED_ADMIN_PASSWORD",
    UserRole.DISPATCHER: "SEED_DISPATCHER_PASSWORD",
    UserRole.DRIVER: "SEED_DRIVER_PASSWORD",
}
MIN_PASSWORD_LENGTH = 8


class SeedError(ValueError):
    """Bad seed input (for example a password that is too short)."""


@dataclass
class SeedReport:
    created: dict[str, int] = field(default_factory=lambda: {"users": 0, "vehicles": 0, "hospitals": 0, "driver_links": 0})
    existing: dict[str, int] = field(default_factory=lambda: {"users": 0, "vehicles": 0, "hospitals": 0})
    skipped_roles: list[str] = field(default_factory=list)


def load(name: str) -> dict[str, Any]:
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def _point(lat: float, lon: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def passwords_from_env(env: Mapping[str, str] = os.environ) -> dict[UserRole, str]:
    return {role: env[var] for role, var in PASSWORD_ENV.items() if env.get(var)}


async def seed(session: AsyncSession, size: Size = "small", passwords: Mapping[UserRole, str] | None = None) -> SeedReport:
    """Insert missing SIMULATED rows. Does not commit; the caller commits."""
    if size not in ("small", "full"):
        raise SeedError(f"unknown size '{size}' (small or full)")
    passwords = dict(passwords or {})
    for role, pw in passwords.items():
        if len(pw) < MIN_PASSWORD_LENGTH:
            raise SeedError(f"{PASSWORD_ENV[UserRole(role)]} must have at least {MIN_PASSWORD_LENGTH} characters")
    report = SeedReport()

    vehicles_data = load("vehicles")
    vehicles = vehicles_data["vehicles"][: vehicles_data["small_count"]] if size == "small" else vehicles_data["vehicles"]
    existing_plates = set((await session.scalars(select(Vehicle.plate_number))).all())
    for v in vehicles:
        if v["plate_number"] in existing_plates:
            report.existing["vehicles"] += 1
            continue
        session.add(Vehicle(plate_number=v["plate_number"], vehicle_type=v["vehicle_type"], station_name=v["station_name"],
                            patient_capacity=v["patient_capacity"], last_location=_point(v["lat"], v["lon"])))
        report.created["vehicles"] += 1

    hospitals_data = load("hospitals")
    hospitals = hospitals_data["hospitals"][: hospitals_data["small_count"]] if size == "small" else hospitals_data["hospitals"]
    existing_names = set((await session.scalars(select(Hospital.name))).all())
    for h in hospitals:
        if h["name"] in existing_names:
            report.existing["hospitals"] += 1
            continue
        session.add(Hospital(name=h["name"], location=_point(h["lat"], h["lon"]), departments=h["departments"]))
        report.created["hospitals"] += 1
    await session.flush()

    seeded_plates = {v["plate_number"] for v in vehicles}
    existing_users = set((await session.scalars(select(User.username))).all())
    for u in load("users")["users"]:
        role = UserRole(u["role"])
        if role is UserRole.DRIVER and u.get("vehicle_plate") not in seeded_plates:
            continue  # the "small" size seeds only the drivers of the seeded vehicles
        if u["username"] in existing_users:
            report.existing["users"] += 1
            continue
        if role not in passwords:
            if role.value not in report.skipped_roles:
                report.skipped_roles.append(role.value)
            continue
        user = User(username=u["username"], full_name=u["full_name"], role=role.value,
                    password_hash=hash_password(passwords[role]))
        session.add(user)
        await session.flush()
        await record(session, AuditAction.USER_CREATED, details={"user_id": user.user_id, "username": user.username,
                                                                    "role": role.value, "source": "seed"})
        report.created["users"] += 1

    for u in load("users")["users"]:
        plate = u.get("vehicle_plate")
        if plate not in seeded_plates:
            continue
        driver_id = await session.scalar(select(User.user_id).where(User.username == u["username"]))
        vehicle = await session.scalar(select(Vehicle).where(Vehicle.plate_number == plate))
        if driver_id is not None and vehicle is not None and vehicle.driver_id is None:
            vehicle.driver_id = driver_id
            report.created["driver_links"] += 1
    await session.flush()
    return report


async def _main(size: Size) -> SeedReport:
    from app.core.db import SessionLocal

    async with SessionLocal() as session:
        report = await seed(session, size, passwords_from_env())
        await session.commit()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Insert SIMULATED seed data (Sukkur pilot area).")
    parser.add_argument("--size", choices=("small", "full"), default="small")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    report = asyncio.run(_main(args.size))
    print(f"created: {report.created}")
    print(f"already present: {report.existing}")
    if report.skipped_roles:
        print("skipped accounts (password not set): " + ", ".join(
            f"{r} ({PASSWORD_ENV[UserRole(r)]})" for r in report.skipped_roles))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
