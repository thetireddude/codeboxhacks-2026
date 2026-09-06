"""Persist per-player public-speaking feedback for every completed match."""

import sqlalchemy as sa
from alembic import op


revision = "20260906_02"
down_revision = "20260906_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_feedback",
        sa.Column("match_id", sa.String(36), sa.ForeignKey("matches.match_id"), primary_key=True),
        sa.Column("guest_id", sa.String(36), sa.ForeignKey("players.guest_id"), primary_key=True),
        sa.Column("scoring_version", sa.String(40), nullable=False),
        sa.Column("total_score", sa.Integer, nullable=False),
        sa.Column("adaptability_points", sa.Integer, nullable=False),
        sa.Column("adaptability_rating", sa.String(24), nullable=False),
        sa.Column("articulation_points", sa.Integer, nullable=False),
        sa.Column("articulation_rating", sa.String(24), nullable=False),
        sa.Column("coherence_points", sa.Integer, nullable=False),
        sa.Column("coherence_rating", sa.String(24), nullable=False),
        sa.Column("collaboration_points", sa.Integer, nullable=False),
        sa.Column("collaboration_rating", sa.String(24), nullable=False),
        sa.Column("speed_points", sa.Integer, nullable=False),
        sa.Column("speed_rating", sa.String(24), nullable=False),
        sa.Column("overview", sa.Text, nullable=False),
        sa.Column("what_went_well", sa.Text, nullable=False),
        sa.Column("what_to_improve", sa.Text, nullable=False),
        sa.Column("rubric_log", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_match_feedback_guest_created", "match_feedback", ["guest_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_match_feedback_guest_created", table_name="match_feedback")
    op.drop_table("match_feedback")
