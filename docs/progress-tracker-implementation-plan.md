# Progress tracker implementation plan

## Confirmed starting point

- A browser creates an anonymous UUID and keeps it in `localStorage` as
  `improv-faceoff:guest-id`. The same UUID is sent when the guest reconnects
  or queues for another match.
- PostgreSQL already has a durable `players.guest_id` primary key. A player
  row is created for each participant when their first completed match is
  written; before then, guest identity lives only in the temporary Redis
  matchmaking store.
- Server-side scoring already writes both players' match and score records in
  `MatchIntegrationService.judge_round`, before `results:ready` is emitted.
  Clicking **Next Match** only releases/requeues the completed match; it is
  not required for the current score write.
- PR #56 already adds PostgreSQL `match_feedback`, keyed by the composite
  `(match_id, guest_id)`. Each row contains the score, points/ratings for all
  five skills, AI overview, what went well, what to improve, rubric log, and
  creation time. It is the correct source for this feature.
- The progress API is `GET /api/players/<guest_id>/match-feedback?limit=100`.
  It is backed by `get_player_feedback(guest_id)`, returns the full retained
  feedback history in chronological order, and gives every record a stable
  `match_number`.

Therefore no new player/guest identifier or feedback table is needed. The
work is to expose the completed feedback history through an HTTP API, add the
summary behavior, and display it in a progress dialog.

## Scope and decisions

1. Keep the existing anonymous UUID as the progress identity for the first
   release. The Progress button reads the UUID from local storage; it is not a
   replacement for the future Google account-claim flow.
2. Treat a completed server-scored match as the only persistence trigger. Do
   not add a client-side save or a requeue dependency.
3. Reuse the per-match score row as the source of truth. It already has the
   natural idempotency key: `(match_id, guest_id)`.
4. Render history in chronological order. The x-axis is completed-match
   number (1, 2, 3...) rather than a date, and the y-axis is total score.
   Every plotted point carries and exposes its immutable `match_id`.
5. Use Recharts for the SVG chart. `Line type="stepAfter"`, custom square
   `<rect>` dots, and `shapeRendering="crispEdges"` meet the pixel-arcade
   visual direction while keeping the tooltip accessible and inspectable.

## Backend plan

### 1. Use and verify the existing feedback persistence

No new persistence schema is planned. PR #56's `20260906_02` Alembic revision
creates `match_feedback`; `LeaderboardRepository.record_completed_match`
inserts its two per-player rows in the same SQL transaction as `matches`,
`players`, and `match_scores`. Its composite key makes a repeated scoring task
idempotent.

Storage already happens immediately on match completion: the server computes
the result, calls `complete_scoring`, then calls `record_completed_match`; only
after that method returns does the game controller emit `results:ready`.
Requeueing occurs later and has no role in persistence. Add a focused test
that proves the feedback row exists before the result event is sent.

### 2. Storage follow-up

The current code logs-and-continues if the database is unavailable, which is
correct for not trapping players on the results screen but can lose a history
point. A retryable durable outbox remains a follow-up and is intentionally not
part of this UI/API change.

### 3. Add the single match-feedback progress API

Implemented `GET /api/players/<guest_id>/match-feedback?limit=100` next to
the existing leaderboard routes. It uses the existing `get_player_feedback`
repository method, ordered oldest first for chart rendering, with a stable
`match_number` assigned by the API. This single response already has all graph
scores, skill statistics, and AI feedback, so a separate `/progress` endpoint
and client-side joins are unnecessary. Every plotted point carries and exposes
its immutable `match_id`.

```json
{
  "guest_id": "uuid",
  "matches": [
    {
      "match_number": 1,
      "match_id": "uuid",
      "guest_id": "uuid",
      "created_at": "2026-09-06T...Z",
      "total_score": 720,
      "skills": {
        "adaptability": { "points": 140, "rating": "Strong" },
        "articulation": { "points": 150, "rating": "Strong" }
      },
      "overview": "...",
      "what_went_well": "...",
      "what_to_improve": "..."
    }
  ],
  "summary": {
    "status": "ready",
    "tips": [{ "label": "AI OVERVIEW", "text": "..." }]
  }
}
```

The route returns `400` for an invalid UUID or invalid limit and the same
`503` database-unavailable contract as the leaderboard. Until account claiming
exists, the UUID is only an anonymous identifier, not authentication; do not
describe this endpoint as private profile protection. When Google identity is
introduced, authorize the route against the signed-in player instead of
trusting a path UUID.

### 4. Summary behavior

The API returns three below-graph coaching tips from the most recent persisted
AI feedback: overview, what went well, and what to improve. It does not call
or alter a model, prompt, or model configuration when the modal opens. This
keeps progress loading fast and isolates it from ongoing AI configuration work.

## Frontend plan

1. Added `recharts` to `frontend/package.json` and created a focused
   `ProgressModal` component. It fetches the match-feedback endpoint with the
   local guest UUID when opened, aborts its request when closed, and supports
   retry.
2. In `HomePage`, replaced the blue **MODES** action with **PROGRESS**. It opens a
   state-controlled dialog instead of navigating away. Use the existing Rules
   overlay for modal behavior (`role="dialog"`, `aria-modal`, Escape/close
   control, click-outside close); the existing leaderboard is a full route,
   not a popup, so its card styling can be reused but not its navigation
   behavior.
3. The dialog shows a pixel-styled header, total matches, and a responsive
   Recharts line chart. Use `match_number` as the x value and `total_score` as
   the y value. Square custom dots mark each match; a step line and crisp SVG
   edges preserve the retro look.
4. The custom tooltip displays every persisted feedback field: `match_id`,
   guest and scoring metadata, timestamp, total score, all skill points and
   ratings, AI overview, what went well, what to improve, and the complete raw
   rubric log. Keyboard focus on a point presents the same information below
   the chart for narrow screens.
5. Below the chart, an `AI COACH` panel renders the three persisted AI tips.
   It provides explicit loading and API-error states and never calls a model.
6. Added a local `fallbackProgress` fixture containing clearly synthetic match
   IDs (for example, `demo-match-001`) and coaching text. Use it only when the
   match-feedback API succeeds with an empty list, the condition that signals
   no `match_feedback` records are available. Mark every part of the dialog
   **SAMPLE PROGRESS — LIVE FEEDBACK NOT YET AVAILABLE**. Do not blend sample
   and live records. A database/API failure remains an error state with Retry,
   not a sample fallback.
7. Added scoped CSS for the overlay, chart frame, pixel grid/markers, tooltip,
   coach panel, and narrow-screen scrolling. Keep the landing page's existing
   arcade palette and avoid chart animation that makes values hard to inspect.

## Validation and release checklist

- Backend tests: feedback rows are persisted in the same completion
  transaction as score rows and before result emission; repeat scoring is
  idempotent; feedback history is isolated per guest and chronologically
  ordered; `match_id` is returned by the endpoint; the API has valid, empty,
  invalid-ID/limit, unavailable-store, and summary-status coverage.
- Frontend tests or component checks: correct endpoint/guest UUID, exact
  `match_id` tooltip display, the labeled empty-feedback sample fallback, all
  dialog states, Escape/close behavior, and no data fetch for a missing guest
  ID.
- The full backend suite passes: `python -m pytest -q` (76 passed). `npm run
  lint` and `npm run build` pass. Manually verify desktop and narrow mobile
  layouts with zero, one, and many matches before release.
- Deploy the migration first, then the backend producer/API, then the
  frontend. Monitor persistence retry count and progress-endpoint errors after
  launch.

## Implementation order

1. Completed: verify existing feedback persistence and add the chronological
   feedback API with contract tests.
2. Completed: build the Recharts modal, full-feedback tooltip, sample fallback,
   and Progress button.
3. Complete release checks, then deploy in migration-backend-frontend order.
