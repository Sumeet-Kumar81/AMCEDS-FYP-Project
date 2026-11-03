from fastapi import APIRouter
from sqlalchemy import text

from app.core.db import SessionLocal

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """NFR-S5: status of API and database. Worker/OSRM checks are added later."""
    db_ok = True
    try:
        async with SessionLocal() as s:
            await s.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {"api": "ok", "database": "ok" if db_ok else "down"}
