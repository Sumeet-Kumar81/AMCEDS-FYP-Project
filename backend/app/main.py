from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.routes import (
    admin,
    analytics,
    auth,
    dispatch,
    driver,
    fleet,
    health,
    incidents,
    intake_sim,
    reports,
    review,
    routing,
)
from app.core.config import get_settings

API_PREFIX = "/api/v1"  # D-006; only GET /health stays unprefixed (Docker healthcheck)

settings = get_settings()
app = FastAPI(title="AI Emergency Dispatch API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)

app.include_router(health.router)
for module in (reports, intake_sim, auth, incidents, review, dispatch, fleet, routing, driver, admin, analytics):
    app.include_router(module.router, prefix=API_PREFIX)
