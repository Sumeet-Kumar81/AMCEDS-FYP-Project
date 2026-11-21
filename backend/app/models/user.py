"""users and user_sessions (SDS v1.1 Tables 5.4 and 5.14; session design D-023). Task B1-A1-07.

One ``users`` table with a ``role`` column; the SDS classes Dispatcher/Driver/Admin are behaviour in
the services. Users are disabled (``is_active = false``), never deleted.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._common import TZ, one_of
from app.schemas.auth import UserRole


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        one_of("role", UserRole),
        CheckConstraint("failed_login_count >= 0", name="failed_login_count_not_negative"),
    )

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(TZ)
    on_duty: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))


class UserSession(Base):
    """One login session; ``session_id`` is the access token's ``jti`` (D-023)."""

    __tablename__ = "user_sessions"

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())
    last_activity_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(TZ)
