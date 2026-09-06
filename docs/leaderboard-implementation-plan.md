# Leaderboard implementation plan

Leaderboard ranks a guest by their best completed-match score. Guest IDs are UUIDs created by the existing client and are an identifier, not authentication.

## Data and ranking

PostgreSQL stores `players`, `matches`, and one `match_scores` row for each player in each match. The `(match_id, guest_id)` primary key makes recording idempotent. Every score is retained; the ranking selects each guest's best score. Ties resolve by earliest score timestamp, then guest UUID.

## Runtime behavior

`MatchIntegrationService` records both authoritative results after scoring completes. Failure to write a leaderboard score is logged but never prevents results from reaching players. Run `alembic -c alembic.ini upgrade head` from `backend` with `DATABASE_URL` set before production deployment.

`GET /api/leaderboard?limit=50&cursor=...` returns cursor-paginated entries. `GET /api/players/<guest_id>/rank` returns a guest's rank. A missing or unreachable database returns `LEADERBOARD_UNAVAILABLE` (503).

The frontend uses a hardcoded, visibly labeled `SAMPLE LEADERBOARD` only if the live request fails. A successful empty leaderboard remains empty and is never mixed with sample scores.
