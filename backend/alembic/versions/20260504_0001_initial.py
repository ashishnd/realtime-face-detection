"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stream_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
    )
    op.create_table(
        "roi_detections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stream_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("frame_number", sa.Integer(), nullable=False),
        sa.Column("x_min", sa.Integer(), nullable=False),
        sa.Column("y_min", sa.Integer(), nullable=False),
        sa.Column("x_max", sa.Integer(), nullable=False),
        sa.Column("y_max", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("frame_width", sa.Integer(), nullable=False),
        sa.Column("frame_height", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "frame_number", name="uq_session_frame"),
        sa.CheckConstraint("x_max > x_min", name="ck_roi_x"),
        sa.CheckConstraint("y_max > y_min", name="ck_roi_y"),
    )
    op.create_index("ix_roi_detections_session_id", "roi_detections", ["session_id"], unique=False)
    op.create_index("ix_roi_session_frame", "roi_detections", ["session_id", "frame_number"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_roi_session_frame", table_name="roi_detections")
    op.drop_index("ix_roi_detections_session_id", table_name="roi_detections")
    op.drop_table("roi_detections")
    op.drop_table("stream_sessions")
