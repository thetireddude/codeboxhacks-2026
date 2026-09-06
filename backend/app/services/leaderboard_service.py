"""Durable, idempotent storage and ranking queries for completed matches."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    and_,
    create_engine,
    desc,
    func,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from app.models import MatchResults, MatchState


class LeaderboardUnavailableError(RuntimeError):
    """Raised when durable leaderboard storage is not configured or reachable."""


class InvalidLeaderboardCursor(ValueError):
    """Raised when a cursor cannot safely be used for pagination."""


metadata = MetaData()
players = Table(
    "players",
    metadata,
    Column("guest_id", String(36), primary_key=True),
    Column("display_name", String(80), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
matches = Table(
    "matches",
    metadata,
    Column("match_id", String(36), primary_key=True),
    Column("completed_at", DateTime(timezone=True), nullable=False),
    Column("scoring_version", String(40), nullable=False),
)
match_scores = Table(
    "match_scores",
    metadata,
    Column("match_id", String(36), ForeignKey("matches.match_id"), primary_key=True),
    Column("guest_id", String(36), ForeignKey("players.guest_id"), primary_key=True),
    Column("total_score", Integer, nullable=False),
    Column("adaptability", Integer, nullable=False),
    Column("creativity", Integer, nullable=False),
    Column("speed", Integer, nullable=False),
    Column("coherence", Integer, nullable=False),
    Column("collaboration", Integer, nullable=False),
    Column("outcome", String(8), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


class UnavailableLeaderboardRepository:
    def record_completed_match(self, match: MatchState, results: MatchResults) -> None:
        raise LeaderboardUnavailableError("DATABASE_URL is not configured")

    def get_leaderboard(self, limit: int, cursor: str | None = None) -> dict[str, Any]:
        raise LeaderboardUnavailableError("DATABASE_URL is not configured")

    def get_player_rank(self, guest_id: UUID) -> dict[str, Any] | None:
        raise LeaderboardUnavailableError("DATABASE_URL is not configured")


class LeaderboardRepository:
    def __init__(
        self, database_url: str, scoring_version: str, auto_create_schema: bool = False
    ) -> None:
        if not database_url:
            raise LeaderboardUnavailableError("DATABASE_URL is not configured")
        kwargs: dict[str, Any] = {}
        if database_url == "sqlite://":
            kwargs = {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            }
        self._engine: Engine = create_engine(database_url, **kwargs)
        self._scoring_version = scoring_version
        if auto_create_schema:
            metadata.create_all(self._engine)

    def record_completed_match(self, match: MatchState, results: MatchResults) -> None:
        if match.match_id != results.match_id:
            raise ValueError("Match and result IDs must match")
        completed_at = datetime.now(UTC)
        match_id = str(match.match_id)
        entries = (
            self._entry(match.player_a_id, results.player_a, results.winner, "A"),
            self._entry(match.player_b_id, results.player_b, results.winner, "B"),
        )
        try:
            with self._engine.begin() as connection:
                if (
                    connection.execute(
                        select(matches.c.match_id).where(matches.c.match_id == match_id)
                    ).first()
                    is None
                ):
                    connection.execute(
                        matches.insert().values(
                            match_id=match_id,
                            completed_at=completed_at,
                            scoring_version=self._scoring_version,
                        )
                    )
                for entry in entries:
                    guest_id = entry["guest_id"]
                    if (
                        connection.execute(
                            select(players.c.guest_id).where(
                                players.c.guest_id == guest_id
                            )
                        ).first()
                        is None
                    ):
                        connection.execute(
                            players.insert().values(
                                guest_id=guest_id,
                                display_name=self._display_name(guest_id),
                                created_at=completed_at,
                            )
                        )
                    existing = connection.execute(
                        select(match_scores.c.match_id).where(
                            and_(
                                match_scores.c.match_id == match_id,
                                match_scores.c.guest_id == guest_id,
                            )
                        )
                    ).first()
                    if existing is None:
                        connection.execute(
                            match_scores.insert().values(
                                match_id=match_id, created_at=completed_at, **entry
                            )
                        )
        except LeaderboardUnavailableError:
            raise
        except Exception as error:
            raise LeaderboardUnavailableError(
                "Could not persist leaderboard score"
            ) from error

    def get_leaderboard(self, limit: int, cursor: str | None = None) -> dict[str, Any]:
        marker = self._decode_cursor(cursor) if cursor else None
        try:
            ranked = self._ranked_query().subquery()
            query = select(ranked).order_by(ranked.c.rank).limit(limit + 1)
            if marker:
                query = query.where(self._after_cursor(ranked, marker))
            with self._engine.connect() as connection:
                rows = connection.execute(query).mappings().all()
        except InvalidLeaderboardCursor:
            raise
        except Exception as error:
            raise LeaderboardUnavailableError("Could not load leaderboard") from error
        has_more = len(rows) > limit
        rows = rows[:limit]
        entries = [self._serialize(row) for row in rows]
        return {
            "entries": entries,
            "next_cursor": self._encode_cursor(rows[-1]) if has_more else None,
        }

    def get_player_rank(self, guest_id: UUID) -> dict[str, Any] | None:
        try:
            ranked = self._ranked_query().subquery()
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        select(ranked).where(ranked.c.guest_id == str(guest_id))
                    )
                    .mappings()
                    .first()
                )
            return self._serialize(row) if row else None
        except Exception as error:
            raise LeaderboardUnavailableError("Could not load player rank") from error

    def _ranked_query(self):
        best_order = (
            desc(match_scores.c.total_score),
            match_scores.c.created_at.asc(),
            match_scores.c.guest_id.asc(),
        )
        scored = select(
            match_scores.c.guest_id,
            match_scores.c.total_score,
            match_scores.c.created_at.label("best_score_at"),
            func.count()
            .over(partition_by=match_scores.c.guest_id)
            .label("games_played"),
            func.row_number()
            .over(partition_by=match_scores.c.guest_id, order_by=best_order)
            .label("best_row"),
        ).subquery()
        best = select(scored).where(scored.c.best_row == 1).subquery()
        return select(
            players.c.guest_id,
            players.c.display_name,
            best.c.total_score.label("best_score"),
            best.c.best_score_at,
            best.c.games_played,
            func.row_number()
            .over(
                order_by=(
                    desc(best.c.total_score),
                    best.c.best_score_at.asc(),
                    best.c.guest_id.asc(),
                )
            )
            .label("rank"),
        ).join(best, players.c.guest_id == best.c.guest_id)

    @staticmethod
    def _entry(guest_id: UUID, result, winner: str, slot: str) -> dict[str, Any]:
        points = result.category_points
        outcome = "TIE" if winner == "TIE" else "WIN" if winner == slot else "LOSS"
        return {
            "guest_id": str(guest_id),
            "total_score": result.total_points,
            "adaptability": points.adaptability,
            # Preserve the existing physical column until the account/profile
            # migration; public-speaking-v1 stores articulation in this slot.
            "creativity": points.articulation,
            "speed": points.speed,
            "coherence": points.coherence,
            "collaboration": points.collaboration,
            "outcome": outcome,
        }

    @staticmethod
    def _display_name(guest_id: str) -> str:
        return f"Player {UUID(guest_id).int % 10_000:04d}"

    @staticmethod
    def _serialize(row) -> dict[str, Any]:
        return {
            "rank": row["rank"],
            "guest_id": row["guest_id"],
            "display_name": row["display_name"],
            "best_score": row["best_score"],
            "games_played": row["games_played"],
        }

    @staticmethod
    def _encode_cursor(row) -> str:
        payload = {
            "best_score": row["best_score"],
            "best_score_at": row["best_score_at"].isoformat(),
            "guest_id": row["guest_id"],
        }
        return base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).decode()

    @staticmethod
    def _decode_cursor(value: str) -> dict[str, Any]:
        try:
            payload = json.loads(base64.urlsafe_b64decode(value.encode()).decode())
            UUID(payload["guest_id"])
            score = payload["best_score"]
            timestamp = datetime.fromisoformat(payload["best_score_at"])
            if not isinstance(score, int) or timestamp.tzinfo is None:
                raise ValueError
            return {
                "best_score": score,
                "best_score_at": timestamp,
                "guest_id": payload["guest_id"],
            }
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise InvalidLeaderboardCursor("cursor is invalid") from error

    @staticmethod
    def _after_cursor(ranked, marker):
        return (
            (ranked.c.best_score < marker["best_score"])
            | and_(
                ranked.c.best_score == marker["best_score"],
                ranked.c.best_score_at > marker["best_score_at"],
            )
            | and_(
                ranked.c.best_score == marker["best_score"],
                ranked.c.best_score_at == marker["best_score_at"],
                ranked.c.guest_id > marker["guest_id"],
            )
        )
