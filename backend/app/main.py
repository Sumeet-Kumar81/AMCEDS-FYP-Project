from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, reports
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title="AI Emergency Dispatch API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(reports.router)
# Add as built: auth (D4), incidents (D5), dispatch (D12), driver (D15), tracking (D18)
