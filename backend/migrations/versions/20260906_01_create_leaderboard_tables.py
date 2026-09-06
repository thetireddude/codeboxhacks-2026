"""Create durable leaderboard tables."""

import sqlalchemy as sa
from alembic import op

revision = "20260906_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "players",
        sa.Column("guest_id", sa.String(36), primary_key=True),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "matches",
        sa.Column("match_id", sa.String(36), primary_key=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scoring_version", sa.String(40), nullable=False),
    )
    op.create_table(
        "match_scores",
        sa.Column(
            "match_id",
            sa.String(36),
            sa.ForeignKey("matches.match_id"),
            primary_key=True,
        ),
        sa.Column(
            "guest_id",
            sa.String(36),
            sa.ForeignKey("players.guest_id"),
            primary_key=True,
        ),
        sa.Column("total_score", sa.Integer, nullable=False),
        sa.Column("adaptability", sa.Integer, nullable=False),
        sa.Column("creativity", sa.Integer, nullable=False),
        sa.Column("speed", sa.Integer, nullable=False),
        sa.Column("coherence", sa.Integer, nullable=False),
        sa.Column("collaboration", sa.Integer, nullable=False),
        sa.Column("outcome", sa.String(8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_match_scores_guest_score", "match_scores", ["guest_id", "total_score"]
    )


def downgrade() -> None:
    op.drop_index("ix_match_scores_guest_score", table_name="match_scores")
    op.drop_table("match_scores")
    op.drop_table("matches")
    op.drop_table("players")
