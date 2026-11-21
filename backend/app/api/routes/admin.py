"""Administration (UC-12, NFR-S9). 501 stubs until B1-A1-31.

Users are disabled, never deleted. The audit log is read-only.
"""
from fastapi import APIRouter

from app.api.errors import ERROR_RESPONSES, NotImplementedYet

router = APIRouter(prefix="/admin", tags=["admin"], responses=ERROR_RESPONSES)
TASK = "B1-A1-31"


@router.get("/users")
async def list_users():
    raise NotImplementedYet(TASK)


@router.post("/users", status_code=201)
async def create_user():
    raise NotImplementedYet(TASK)


@router.patch("/users/{user_id}")
async def update_user(user_id: int):
    raise NotImplementedYet(TASK)


@router.get("/vehicles")
async def admin_list_vehicles():
    raise NotImplementedYet(TASK)


@router.post("/vehicles", status_code=201)
async def create_vehicle():
    raise NotImplementedYet(TASK)


@router.patch("/vehicles/{vehicle_id}")
async def update_vehicle(vehicle_id: int):
    raise NotImplementedYet(TASK)


@router.delete("/vehicles/{vehicle_id}", status_code=204)
async def delete_vehicle(vehicle_id: int):
    raise NotImplementedYet(TASK)


@router.get("/hospitals")
async def admin_list_hospitals():
    raise NotImplementedYet(TASK)


@router.post("/hospitals", status_code=201)
async def create_hospital():
    raise NotImplementedYet(TASK)


@router.patch("/hospitals/{hospital_id}")
async def update_hospital(hospital_id: int):
    raise NotImplementedYet(TASK)


@router.get("/settings")
async def list_settings():
    raise NotImplementedYet(TASK)


@router.put("/settings/{key}")
async def update_setting(key: str):
    raise NotImplementedYet(TASK)


@router.get("/audit-logs")
async def list_audit_logs():
    raise NotImplementedYet(TASK)
