"""Seed data tests (B1-A1-34): SIMULATED Sukkur data, idempotent, no made-up passwords."""
import bcrypt
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import seed as seed_module
from app.models import AuditLog, Hospital, User, Vehicle
from app.schemas.auth import UserRole
from app.seed import SeedError, load, passwords_from_env, seed

pytestmark = pytest.mark.db

PASSWORDS = {UserRole.ADMIN: "SIMULATED-admin-pass", UserRole.DISPATCHER: "SIMULATED-disp-pass",
             UserRole.DRIVER: "SIMULATED-driver-pass"}
SUKKUR_BOX = ((27.60, 27.80), (68.75, 69.00))  # (lat range, lon range)


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    real = bcrypt.gensalt
    monkeypatch.setattr(seed_module.bcrypt, "gensalt", lambda: real(rounds=4))  # tests only


async def n(session: AsyncSession, model, *where) -> int:
    return await session.scalar(select(func.count()).select_from(model).where(*where))


async def test_small_seed_counts(db_session: AsyncSession) -> None:
    report = await seed(db_session, "small", PASSWORDS)
    assert report.created == {"users": 9, "vehicles": 6, "hospitals": 2, "driver_links": 6}
    assert await n(db_session, Vehicle) == 6 and await n(db_session, Hospital) == 2 and await n(db_session, User) == 9
    assert {t for t in (await db_session.scalars(select(Vehicle.vehicle_type))).all()} == {"ambulance", "fire_truck", "backup"}


async def test_full_seed_counts(db_session: AsyncSession) -> None:
    report = await seed(db_session, "full", PASSWORDS)
    assert report.created["vehicles"] == 20 and report.created["hospitals"] == 4 and report.created["users"] == 9


async def test_seeding_twice_adds_nothing(db_session: AsyncSession) -> None:
    await seed(db_session, "full", PASSWORDS)
    again = await seed(db_session, "full", PASSWORDS)
    assert again.created == {"users": 0, "vehicles": 0, "hospitals": 0, "driver_links": 0}
    assert again.existing == {"users": 9, "vehicles": 20, "hospitals": 4}
    assert await n(db_session, Vehicle) == 20


async def test_small_then_full_only_adds_the_rest(db_session: AsyncSession) -> None:
    await seed(db_session, "small", PASSWORDS)
    assert (await seed(db_session, "full", PASSWORDS)).created["vehicles"] == 14


async def test_accounts_without_a_password_are_skipped(db_session: AsyncSession) -> None:
    report = await seed(db_session, "small", {UserRole.ADMIN: PASSWORDS[UserRole.ADMIN]})
    assert report.skipped_roles == ["dispatcher", "driver"]
    assert await n(db_session, User) == 1
    assert await n(db_session, Vehicle) == 6  # fleet and hospitals are seeded anyway


async def test_short_password_refused(db_session: AsyncSession) -> None:
    with pytest.raises(SeedError, match="SEED_DRIVER_PASSWORD"):
        await seed(db_session, "small", {UserRole.DRIVER: "short"})


async def test_passwords_are_hashed_never_stored(db_session: AsyncSession) -> None:
    await seed(db_session, "small", PASSWORDS)
    stored = await db_session.scalar(select(User.password_hash).where(User.username == "dispatcher1"))
    assert stored != PASSWORDS[UserRole.DISPATCHER] and stored.startswith("$2")
    assert bcrypt.checkpw(PASSWORDS[UserRole.DISPATCHER].encode(), stored.encode())


async def test_each_driver_drives_one_seeded_vehicle(db_session: AsyncSession) -> None:
    await seed(db_session, "small", PASSWORDS)
    rows = (await db_session.execute(select(User.username, Vehicle.plate_number).join(Vehicle, Vehicle.driver_id == User.user_id))).all()
    assert len(rows) == 6 and len({plate for _, plate in rows}) == 6


async def test_new_accounts_are_audited(db_session: AsyncSession) -> None:
    await seed(db_session, "small", PASSWORDS)
    assert await n(db_session, AuditLog, AuditLog.action == "user.created") == 9


async def test_everything_is_labelled_simulated_and_inside_sukkur(db_session: AsyncSession) -> None:
    await seed(db_session, "full", PASSWORDS)
    for model, col in ((Vehicle, Vehicle.last_location), (Hospital, Hospital.location)):
        rows = (await db_session.execute(select(func.ST_Y(col), func.ST_X(col)).select_from(model))).all()
        assert rows and all(SUKKUR_BOX[0][0] <= lat <= SUKKUR_BOX[0][1] and SUKKUR_BOX[1][0] <= lon <= SUKKUR_BOX[1][1]
                            for lat, lon in rows)
    assert all(name.startswith("SIMULATED") for name in (await db_session.scalars(select(Hospital.name))).all())
    assert all(p.startswith("SIM-") for p in (await db_session.scalars(select(Vehicle.plate_number))).all())
    assert all(f.startswith("SIMULATED") for f in (await db_session.scalars(select(User.full_name))).all())
    for name in ("vehicles", "hospitals", "users"):
        assert "SIMULATED" in load(name)["note"]


def test_no_password_in_the_data_files() -> None:
    for u in load("users")["users"]:
        assert set(u) <= {"username", "full_name", "role", "vehicle_plate"}


def test_passwords_come_only_from_the_environment() -> None:
    env = {"SEED_ADMIN_PASSWORD": "a" * 8, "SEED_DRIVER_PASSWORD": ""}
    assert passwords_from_env(env) == {UserRole.ADMIN: "a" * 8}


async def test_unknown_size_refused(db_session: AsyncSession) -> None:
    with pytest.raises(SeedError):
        await seed(db_session, "huge", PASSWORDS)  # type: ignore[arg-type]
