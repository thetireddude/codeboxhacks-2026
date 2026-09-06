# Improv Faceoff

**Improv Faceoff** is a two-player, arcade-inspired improv game for practicing
quick thinking, collaboration, and confident speaking. Match with another
player, receive a shared scenario with distinct roles, perform a timed scene,
handle surprise Switches, and receive post-round feedback.

The project is designed for teens through young adults who want a low-pressure,
social way to practice being more articulate and responsive in the moment.

## How a match works

1. **Find a match.** Anonymous players enter a real-time public queue.
2. **Get ready.** Both players join a shared room and confirm they are ready.
3. **Play the scene.** The app gives both players a scenario and a role. The
   round runs on a server-authoritative timer while the live transcript records
   the scene.
4. **Use a Switch.** A Switch interrupts the current speaker and asks them to
   pivot into something wacky, original, and still related to the scene.
5. **See the results.** Gemini evaluates the completed transcript and the app
   presents an arcade-style scorecard, coaching, and a path to the next match.

## What is in the MVP

- Two-player Socket.IO matchmaking with reconnect, leave, and requeue flows.
- A shared, server-owned round state: readiness, countdown, timer, turns, and
  Switch limits.
- Live camera and microphone rooms through LiveKit.
- Deepgram-backed speech-to-text that produces an authoritative live scene log.
- Gemini-generated scenarios and Gemini post-round judging, with safe fallback
  results if an AI request is unavailable.
- Arcade-style React UI for the lobby, queue, media room, live scene, results,
  leaderboard, and rules overlay.
- Redis for short-lived matchmaking and game state, plus PostgreSQL-backed
  leaderboard history.

## Tech stack

| Area | Technology |
| --- | --- |
| Frontend | React 18, Vite, React Router, Socket.IO Client, LiveKit React Components, Framer Motion |
| Backend | Python, Flask, Flask-SocketIO, SQLAlchemy, Alembic |
| Real-time state | Socket.IO and Redis |
| Live media | LiveKit |
| Speech-to-text | Deepgram |
| AI | Google Gemini for scenario generation and post-round feedback |
| Persistence | PostgreSQL |
| Testing and quality | pytest, Ruff, ESLint, JSON Schema contract validation |

## Architecture at a glance

```text
React + Vite browser
        |  Socket.IO / HTTP
        v
Flask + Flask-SocketIO ---- Redis (queue and live match state)
        |
        +---- LiveKit (camera and microphone room)
        +---- Deepgram (live transcription)
        +---- Gemini (scenario generation and judging)
        +---- PostgreSQL (leaderboard history)
```

The backend owns the round state and secrets. The frontend never receives AI,
speech-to-text, or LiveKit server secrets.

## Repository layout

```text
frontend/   React/Vite application and game UI
backend/    Flask API, Socket.IO handlers, services, tests, and migrations
shared/     Cross-team event contracts, JSON schemas, and fixtures
docs/       Product spec, milestone history, implementation plans, and handoffs
scripts/    Repository-level contract validation tools
```

## Run locally

### Prerequisites

- Node.js 20+
- Python 3.11+
- Redis
- PostgreSQL (for durable leaderboard data)
- LiveKit, Deepgram, and Gemini credentials for the full media/AI experience

### 1. Configure local environment files

Copy the templates and fill in only the values you have available. Never commit
the resulting `.env` files or any credentials.

```powershell
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env
```

For a frontend running against a local backend, create `frontend/.env`:

```env
VITE_BACKEND_URL=http://localhost:5000
```

The backend `.env` template documents every setting. The usual full-stack
configuration includes `REDIS_URL`, `DATABASE_URL`, `LIVEKIT_URL`,
`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `DEEPGRAM_API_KEY`, and
`GEMINI_API_KEY`. Keep all of those values on the backend only.

### 2. Start the backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
alembic -c alembic.ini upgrade head
python run.py
```

The backend is available at <http://localhost:5000>. Check it with
<http://localhost:5000/api/health>.

### 3. Start the frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>.

## Environment and deployment

For a real two-device match, host the backend where it can accept HTTPS and
WebSocket connections. Set `HOST=0.0.0.0` and set `CORS_ORIGINS` to the exact
public frontend origin. Build the frontend with its public backend URL:

```env
# frontend/.env
VITE_BACKEND_URL=https://api.example.com
```

The browser needs HTTPS to request camera and microphone access. The deployment
must also provide Redis and PostgreSQL, configure the backend-only integration
credentials, and support WebSocket upgrades.

After deploying, confirm health, configuration readiness, and WebSocket-only
Socket.IO connectivity:

```powershell
cd backend
python scripts/check_deployment.py https://api.example.com
```

## Useful local checks

```powershell
# Frontend
cd frontend
npm run lint
npm run build

# Backend
cd ../backend
.venv\Scripts\python -m pytest -q
.venv\Scripts\ruff check .
.venv\Scripts\ruff format --check .

# Shared contracts (from the repository root)
cd ..
python scripts/validate_contracts.py
```

With a configured Gemini key, `backend/generate_scenario.py` and
`backend/generate_judgment.py` are useful focused integration checks. With a
configured Deepgram key, visit `/stt-test` in the frontend for speech-to-text
diagnostics.

## Working as a team

- Branch from `main` using `feat/<area>-<summary>`, `fix/<area>-<summary>`, or
  `docs/<summary>`.
- Keep one cohesive change per pull request and use conventional commit titles
  such as `feat:`, `fix:`, `docs:`, or `test:`.
- Before requesting review, run the relevant frontend, backend, and contract
  checks above.
- Changes to `shared/` must update the corresponding schema, fixture, and
  `shared/events.md` when applicable.
- Never commit directly to `main`; use a reviewed pull request.

## Product references

- [Current product specification](docs/improv-faceoff-spec-updated.md)
- [Milestone breakdown and implementation history](docs/improv-faceoff-milestone-breakdown.md)
- [Shared real-time event contract](shared/events.md)

## Security note

Do not put API keys in frontend code or `VITE_*` variables. If a credential was
ever pasted into a chat, terminal, commit, or screenshot, revoke and replace it
in the provider dashboard before continuing.
