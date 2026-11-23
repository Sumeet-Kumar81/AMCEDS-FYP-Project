"""Public report input and the answer the caller gets (UC-01; B1-A1-16).

``ReportIn`` is the body of ``POST /api/v1/reports`` (a typed report from the web page or the app).
SMS and voice reports arrive through their own endpoints, so ``channel`` is ``web`` or ``app`` here.
The text is stored exactly as written (Urdu, Sindhi and mixed scripts are accepted); only leading
and trailing spaces are removed. Unknown fields are rejected.
"""
from __future__ import annotations

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.enums import Channel, IncidentStatus
from app.schemas.incident import REFERENCE_NO_PATTERN

#: D-036: a Pakistani mobile number — exactly 11 digits, starting with 03 (spaces and dashes typed by the
#: caller are removed before the check, e.g. "0300 1234567" -> "03001234567").
PHONE_PATTERN = r"^03[0-9]{9}$"
PUBLIC_REPORT_CHANNELS = frozenset({Channel.WEB, Channel.APP})


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class ReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=2000)
    channel: Channel = Channel.WEB
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    # D-036 (project developer, 2026-11-23): place/landmark, name and phone are required on this endpoint
    # (SRS UC-01 had them optional). GPS stays optional and is added when the caller allows it.
    address_text: str = Field(min_length=1, max_length=500, description="Place or landmark (required, D-036)")
    reporter_name: str = Field(min_length=1, max_length=100, description="Caller's name (required, D-036)")
    reporter_phone: str = Field(pattern=PHONE_PATTERN,
                                description="11 digits starting with 03, e.g. 03001234567 (required, D-036)")
    device_id: str | None = Field(default=None, max_length=200)
    client_request_id: str | None = Field(default=None, max_length=100,
                                          description="Set by the app so a resent report is saved only once (TC-04)")

    @field_validator("description", mode="before")
    @classmethod
    def _trim_description(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("address_text", "reporter_name", mode="before")
    @classmethod
    def _trim_required(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("reporter_phone", mode="before")
    @classmethod
    def _phone_digits_only(cls, value: object) -> object:
        return value.replace(" ", "").replace("-", "").strip() if isinstance(value, str) else value

    @field_validator("device_id", "client_request_id", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        return _clean(value) if isinstance(value, str) else value

    @field_validator("channel")
    @classmethod
    def _public_channels_only(cls, value: Channel) -> Channel:
        if value not in PUBLIC_REPORT_CHANNELS:
            raise ValueError("this endpoint takes web and app reports; SMS and voice have their own endpoints")
        return value

    @model_validator(mode="after")
    def _coordinates_come_in_pairs(self) -> ReportIn:
        if (self.lat is None) != (self.lon is None):
            raise ValueError("lat and lon must both be given or both be left out")
        return self

    @property
    def phone_digits(self) -> str:
        """The phone number as stored (11 digits), used to recognise the same caller."""
        return self.reporter_phone


class ReportAcceptedOut(BaseModel):
    """What the caller gets once the report is saved (C-1 note 4: ``reference_no`` is the string)."""

    model_config = ConfigDict(extra="forbid")

    reference_no: str = Field(pattern=REFERENCE_NO_PATTERN)
    status: IncidentStatus = IncidentStatus.NEW
    received_at: AwareDatetime
