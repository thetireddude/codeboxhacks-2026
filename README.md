# Improv Faceoff

Project foundation for the Improv Faceoff multiplayer improv-training MVP.
Milestone 0 establishes runnable React and Flask applications plus the shared
contracts that allow three developers to work independently. It intentionally
does not implement matchmaking, gameplay, media, transcription, or AI calls.

The product source of truth is
[`docs/improv-faceoff-spec-updated.md`](docs/improv-faceoff-spec-updated.md).

## Quick start

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Use `npm run build` and `npm run lint` for CI-style
verification.

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

The API listens on <http://localhost:5000>; `GET /api/health` returns a JSON
health response. No Redis, LiveKit, Gemini, or speech-to-text service is contacted
in Milestone 0.

### Test Gemini scenario generation

After copying `backend/.env.example` to `backend/.env`, set `GEMINI_API_KEY` and
run this from `backend/`:

```powershell
python generate_scenario.py
```

The command prints one validated scenario as formatted JSON. It makes one live
Gemini request and may retry once if Gemini returns an invalid response or a
temporary error.

### Enable live speech-to-text

Create a free Deepgram account, generate an API key, and put it only in
`backend/.env`:

```env
DEEPGRAM_API_KEY=your_key_here
```

The A2 stream accepts 16 kHz mono PCM16 audio over Socket.IO. It sends
`speech:started`, `speech:partial`, and `speech:final` messages back to that
socket. The browser must never receive the Deepgram key.

The reusable browser capture function is
`frontend/src/services/pcm16Capture.js`. It uses an AudioWorklet to resample a
microphone to 16 kHz mono PCM16 and sends 80 ms chunks through Socket.IO.

For a manual live check, run both applications and open
<http://localhost:5173/stt-test>. This diagnostic page is separate from the
game UI and displays Deepgram's partial and final transcript messages.

### Contract validation

From the repository root, after installing the backend requirements:

```powershell
python scripts/validate_contracts.py
```

The validator checks every JSON file, validates each schema against its declared
JSON Schema meta-schema, and validates all four fixtures.

## Shared contract boundary

- `shared/schemas/` contains canonical JSON Schema Draft 2020-12 contracts.
- `shared/fixtures/` contains mock data for frontend, backend, and AI/STT work.
- `shared/events.md` defines the Socket.IO event names and payload ownership.
- Runtime business logic must remain in `backend/app/services/`, not `shared/`.

`mock-transcript.json` is a chronological array; every array item is validated
against `transcript-event.json`.

## Environment conventions

Copy the relevant `.env.example` to `.env`. Never commit `.env` files or secrets.

- Browser-exposed variables use the `VITE_` prefix and are never secrets.
- Backend variables use uppercase snake case.
- URLs include their scheme.
- Durations end in `_MS`; counts end in `_COUNT`.
- Boolean values are `true` or `false`.
- Required future integration secrets are documented but blank by default.

Root `.env.example` is the complete catalog. The frontend and backend templates
contain only variables owned by that process.

## Branch and pull-request conventions

- Branch from `main` using `feat/<area>-<summary>`, `fix/<area>-<summary>`, or
  `chore/<summary>`.
- Keep each pull request owned by one workstream and compatible with shared
  fixtures.
- Use Conventional Commit subjects (`feat:`, `fix:`, `chore:`, `docs:`,
  `test:`).
- Any shared contract change must update its fixture, validator coverage, and
  `shared/events.md` when relevant. Call out breaking changes in the PR.
- Before review, run frontend lint/build, backend tests, and contract validation.
- Do not commit directly to `main`; require one teammate review before merge.

## Code conventions

Frontend code is JavaScript/JSX checked by ESLint. Backend code follows PEP 8,
uses type hints, is checked/formatted with Ruff, and is tested with pytest. Run
`ruff check .` and `ruff format --check .` from `backend/`. Controllers coordinate
inputs and outputs, views format responses, models validate data, and services
own business rules and integrations.
