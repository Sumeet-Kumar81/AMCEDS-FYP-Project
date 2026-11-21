"""Seed the settings table with every SRS Appendix C default (B1-A1-12).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-21

A frozen copy of the defaults in ``app.services.settings.REGISTRY`` at the time of writing (a test
checks they are equal). Existing values are never overwritten (ON CONFLICT DO NOTHING), so running
this on a database where the admin already changed a value keeps the admin's value.
Downgrade removes these keys again.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULTS: list[tuple[str, str]] = [
    ("patients_per_ambulance", "2"),
    ("spare_vehicles", "2"),
    ("dup_distance_m", "300"),
    ("dup_window_min", "15"),
    ("dup_auto_link", "85"),
    ("dup_possible", "60"),
    ("dup_weight_distance", "0.4"),
    ("dup_weight_time", "0.2"),
    ("dup_weight_meaning", "0.4"),
    ("triage_min_confidence", "60"),
    ("trust_start", "50"),
    ("trust_tier_high", "70"),
    ("trust_tier_medium", "40"),
    ("trust_pts_real_history", "15"),
    ("trust_pts_fake_each", "-30"),
    ("trust_pts_fake_floor", "-60"),
    ("trust_pts_gps_match", "15"),
    ("trust_gps_match_m", "500"),
    ("trust_pts_gps_far", "-20"),
    ("trust_gps_far_m", "2000"),
    ("trust_pts_one_nearby", "15"),
    ("trust_pts_two_nearby", "25"),
    ("trust_pts_real_details", "10"),
    ("trust_pts_vague", "-15"),
    ("trust_pts_flood", "-20"),
    ("rate_limit_reports", "5"),
    ("rate_limit_window_min", "10"),
    ("rate_limit_block_min", "10"),
    ("assignment_timeout_s", "60"),
    ("signal_lost_s", "60"),
    ("geofence_m", "100"),
    ("idle_logout_min", "30"),
    ("lockout_attempts", "5"),
    ("lockout_min", "15"),
    ("fallback_speed_kmh", "40"),
]


def upgrade() -> None:
    for key, value in DEFAULTS:
        op.execute(
            sa.text("INSERT INTO settings (setting_key, setting_value) VALUES (:k, :v) ON CONFLICT (setting_key) DO NOTHING")
            .bindparams(k=key, v=value)
        )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM settings WHERE setting_key = ANY(:keys)").bindparams(keys=[k for k, _ in DEFAULTS])
    )
