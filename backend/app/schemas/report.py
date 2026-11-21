from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.enums import Channel


class ReportIn(BaseModel):
    """UC-01 input. Description or audio must be present."""
    description: Optional[str] = Field(default=None, max_length=2000)
    channel: Channel = Channel.WEB  # voice | sms | web | app (D-005; "mobile" was renamed "app")
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)
    address_text: Optional[str] = None
    reporter_name: Optional[str] = None
    reporter_phone: Optional[str] = None
    device_id: Optional[str] = None


class ReportOut(BaseModel):
    incident_id: str  # INC-000123
    status: str = "new"
