# Improv Faceoff — Milestone Breakdown

## Milestone 0 — Shared Foundation

**Owners:** All Developers

### Goal

Set up the project so Backend, Frontend, and AI can all begin working independently.

### Tasks

- Initialize React/Vite frontend
- Initialize Flask backend
- Create Flask MVC structure
- Create `/shared`
- Create `/spec`
- Create `.env.example`
- Define branch/PR conventions
- Define shared schemas:
  - Player
  - Scenario
  - MatchState
  - SpeechEvent
  - SwitchEvent
  - RoundResult
- Define Socket.IO event names
- Create mock fixtures:
  - mock player
  - mock match
  - mock scenario
  - mock transcript
  - mock Switch events
  - mock results

### Done When

- Frontend runs locally
- Backend runs locally
- Shared contracts are agreed on
- Mock data exists
- All three developers can work independently without waiting on another developer

---

# Backend Track — Developer 1

## Milestone B1 — Multiplayer Foundation

### Goal

Get two anonymous players into the same match.

### Tasks

- Set up Flask application
- Set up Flask-SocketIO
- Connect Redis
- Generate anonymous guest IDs
- Implement queue join
- Implement queue leave
- Prevent duplicate queue entries
- Pair two waiting players
- Assign Player A and Player B
- Generate `match_id`
- Create temporary match state
- Store match state in Redis
- Broadcast `match:found`

### Done When

```text
Player A joins queue
Player B joins queue
        ↓
Backend pairs them
        ↓
Both receive same match_id
        ↓
Player A / Player B assigned
```

### Current implementation status — Complete

- `guest:create`, `queue:join`, and `queue:leave` are Socket.IO handlers.
- Guests are anonymous, socket-bound, and receive deterministic display names.
- Redis storage has an atomic queue claim; an in-memory implementation supports
  tests. Pairing creates temporary match state, assigns waiting player A and
  joining player B, and emits `match:found` to both clients.

---

## Milestone B2 — Authoritative Game State

### Goal

Build the backend-controlled match state machine.

### Tasks

- Implement ready state
- Implement countdown
- Implement round start
- Create server-owned 60-second timer
- Track active speaker
- Support turn changes
- Track match state
- End round at exactly 60 seconds
- Reject gameplay actions after round end
- Transition to scoring state
- Transition to results state
- Handle basic disconnects

During development, use fake speech-end events.

### Done When

Two test clients can complete a synchronized fake 60-second round.

### Current implementation status — Complete for development-only fake speech-end rounds

- Ready, countdown, round start, a server-owned configurable timer, active
  speaker tracking, fake `turn:complete`, round end, and `SCORING` transition
  are implemented and tested.
- Actions after the round are rejected; disconnect emits `player:disconnected`
  and ends active/countdown rounds.
- `RESULTS` transition exists in the service but is not reachable until B5
  supplies an actual result object. `CONNECTING_MEDIA` is modeled but unused.

---

## Milestone B3 — Switch Game Logic

### Goal

Implement the complete Switch mechanic.

### Tasks

- Give each player 5 Switches
- Allow only listener to press Switch
- Validate `switch:press`
- Decrement Switch inventory
- Keep target player as active speaker
- Allow mid-sentence Switches
- Support repeated Switches
- Record Switch timestamps
- Broadcast `switch:triggered`
- Reject invalid Switches
- Disable Switch after round end
- Keep chained-Switch timing behavior configurable

### Done When

```text
Player A is speaking
        ↓
Player B presses Switch
        ↓
Player B loses one Switch
        ↓
Player A remains active
        ↓
Player A can be Switched again
```

### Current implementation status — Complete for authoritative Switch validation

- Five Switches per player, listener-only validation, timestamping, inventory
  decrement, repeated Switches, idempotent request IDs, state persistence, and
  `switch:triggered` / `switch:rejected` broadcasts are implemented and tested.
- The target remains active speaker and Switch is rejected after the round.
- `SWITCH_MODE` and `CHAIN_SWITCH_WINDOW_MS` are configurable but not yet used
  to enforce an additional chain-window policy.

---

## Milestone B4 — LiveKit Backend

### Goal

Allow matched players to securely connect to the same media room.

### Tasks

- Configure LiveKit server SDK
- Create LiveKit room naming convention
- Generate room name from `match_id`
- Generate Player A token
- Generate Player B token
- Create LiveKit token endpoint
- Scope tokens to correct room
- Handle token-generation errors
- Return credentials to frontend

### Done When

Two matched players can receive valid LiveKit credentials for the same room.

### Current implementation status — Complete

- `livekit-api` is configured server-side. A deterministic
  `improv-faceoff-<match-id>` room name is derived from each match.
- Each participant receives a distinct, configurable-TTL token scoped to that
  room with publish, subscribe, and data-publish grants.
- Credentials are available through socket-bound `media:credentials` and
  `POST /api/matches/<match_id>/livekit-token`; configuration and token errors
  are handled.
- The Socket.IO route is identity-bound. The HTTP route currently accepts a
  supplied `guest_id` without equivalent session authentication, so it should
  not be the production frontend path until that binding is added.

---

## Milestone B5 — Backend Service Integration

### Goal

Connect the backend game engine to AI, transcription, and scoring services.

### Tasks

- Add scenario-generation interface
- Accept transcript events
- Accept speech-ended events
- Add Switch/transcription integration hook
- Trigger judging after round ends
- Ensure judge starts only once
- Accept final result object
- Broadcast `results:ready`
- Clean up temporary match state after completion/disconnect

### Done When

The backend can complete a full mocked match using fake AI and transcription services.

### Current implementation status — Complete for mocked service integration

- A match now uses an injectable scenario provider (Gemini when configured,
  otherwise the development mock) before broadcasting `round:prepare`.
- Match-bound final STT events are validated against the active player,
  persisted as canonical `SpeechEvent`s, broadcast as `transcript:event`, and
  advance the authoritative turn. Switches also invoke a transcription-service
  integration hook.
- At round end, a judge provider is started through the integration service;
  its validated `MatchResults` moves the match to `RESULTS` and is broadcast as
  `results:ready`. The current provider is deterministic/mock pending A5.
- Completed/disconnected matches are removed after configurable delayed cleanup.

---

# Frontend Track — Developer 2

## Milestone F1 — Home + Matchmaking Flow

### Goal

Build the user flow before the game begins.

### Tasks

- Build Home screen
- Add game branding
- Add Find Match button
- Add Other Game Modes placeholder
- Build matchmaking screen
- Add searching state
- Add cancel matchmaking
- Add match-found transition
- Add basic matchmaking error states

Use mock events during development.

### Done When

```text
Home
→ Find Match
→ Searching
→ Match Found
```

works using mocks.

---

## Milestone F2 — Camera, Microphone + LiveKit UI

### Goal

Build the realtime media experience.

### Tasks

- Request camera permission
- Request microphone permission
- Show permission errors
- Show local camera preview
- Set up LiveKit client
- Render local video
- Render remote video
- Play remote audio
- Show media connection status
- Handle loading/reconnection UI

### Done When

Two development clients can see and hear each other in a LiveKit test room.

---

## Milestone F3 — Scenario + Countdown + Game HUD

### Goal

Build the main multiplayer game screen.

### Tasks

- Display scenario
- Display Player A role
- Display Player B role
- Build 3-2-1 countdown
- Display 60-second timer
- Display active speaker
- Display player labels
- Display Player A Switch count
- Display Player B Switch count
- Add Switch button
- Display round state

Use mock game-state events.

### Done When

A full fake round can visually run from countdown to round end.

---

## Milestone F4 — Switch UX

### Goal

Make the Switch mechanic clear and responsive.

### Tasks

- Enable Switch only when opponent is active
- Disable Switch while local player is active
- Disable Switch when inventory is 0
- Disable Switch outside active round
- Add immediate click feedback
- Add Switch animation
- Update remaining Switch count
- Display mid-sentence interruption
- Support repeated Switch visuals
- Display `[SWITCH]` in transcript

### Done When

Mock Switch events behave correctly in the UI.

---

## Milestone F5 — Live Transcript UI

### Goal

Render the live conversation from structured transcript events.

### Tasks

- Consume `TranscriptEvent`
- Style Player A lines
- Style Player B lines
- Preserve chronological order
- Render partial speech
- Render final speech
- Render interrupted speech
- Keep rejected speech visible
- Render `[SWITCH]`
- Auto-scroll transcript
- Visually associate transcript lines with the correct player

### Done When

The shared mock transcript renders correctly from beginning to end.

---

## Milestone F6 — Scoring + Results Screen

### Goal

Build the arcade-style post-round experience.

### Tasks

- Show `ROUND OVER`
- Show judging/loading state
- Display Player A score
- Display Player B score
- Display Adaptability
- Display Creativity
- Display Speed
- Display Coherence
- Display Collaboration / Scene Building
- Reveal winner
- Display highlight events
- Display best moment
- Display improvement
- Add basic arcade animations

### Done When

`mock-results.json` can drive the entire results screen.

---

# AI / Transcription Track — Developer 3

## Milestone A1 — Gemini Scenario Generation

### Goal

Generate valid improv scenarios and roles.

### Tasks

- Configure Gemini client
- Define tone pool
- Randomly select tone
- Build scenario-generation prompt
- Generate scenario
- Generate Player A role
- Generate Player B role
- Validate response with Pydantic
- Handle invalid responses
- Add retry/fallback behavior

### Output

```json
{
  "tone": "...",
  "scenario": "...",
  "player_a_role": "...",
  "player_b_role": "..."
}
```

### Done When

Every test request returns a valid `Scenario`.

---

## Milestone A2 — Realtime Speech-to-Text

### Goal

Convert live microphone speech into text.

### Tasks

- Select realtime STT provider
- Connect microphone/audio stream
- Produce partial transcripts
- Produce final transcripts
- Detect speech start
- Associate speech with active player
- Test transcription latency
- Handle STT errors

Use mocked `active_player` data during development.

### Done When

Speaking produces usable partial and final text quickly enough for the live game UI.

---

## Milestone A3 — Turn Detection + Transcript Events

### Goal

Convert speech into structured game transcript events.

### Tasks

- Implement silence detection
- Add configurable `TURN_END_SILENCE_MS`
- Record speech-start timestamp
- Record speech-end timestamp
- Create `SpeechEvent`
- Notify backend when turn ends
- Preserve chronological ordering
- Handle round-end truncation

### Done When

```text
Speech starts
→ Partial transcript
→ Final transcript
→ Silence detected
→ SpeechEvent created
→ Turn complete
```

works consistently.

---

## Milestone A4 — Switch Interruption Processing

### Goal

Correctly handle interrupted speech and replacement responses.

### Tasks

- Receive Switch event
- Finalize current partial speech
- Mark interrupted speech as rejected
- Set `truncated_by_switch = true`
- Create/handle `SwitchEvent`
- Keep same player active
- Detect replacement speech start
- Record Switch response latency
- Support repeated Switches

### Done When

```text
[PLAYER A] I lost your—
[SWITCH]
[PLAYER A] There never was a dog.
```

becomes the correct structured event sequence.

---

## Milestone A5 — Gemini Judge

### Goal

Judge the completed improv scene.

### Inputs

- Scenario
- Player A role
- Player B role
- Accepted transcript
- Rejected transcript
- Switch events
- Response timing metadata

### Gemini Evaluates

- Adaptability
- Creativity
- Coherence
- Collaboration / Scene Building
- Switch recovery quality

### Gemini Also Returns

- Highlight events
- Best moment
- Improvement

### Done When

A fixture transcript produces a valid structured judging result.

---

## Milestone A6 — Speed + Arcade Score Engine

### Goal

Combine AI judgment with objective timing into the final game result.

### Tasks

- Calculate Switch response latency
- Implement configurable Speed curve
- Calculate Speed points
- Merge Gemini category scores
- Calculate category totals
- Calculate arcade total
- Select winner
- Handle ties
- Add score bounds/fallbacks

### Done When

```text
Gemini judgment
+
Switch timing
        ↓
RoundResult
```

always produces a valid final result.

---

# Integration Track — All Developers

## Milestone I1 — Matchmaking Integration

**Owners:** Developers 1 + 2

### Goal

Replace mocked frontend matchmaking with the real backend.

### Connect

```text
Frontend Find Match
→ Socket.IO
→ Redis Queue
→ match:found
→ Game Screen
```

### Done When

Two real browsers can find and enter the same match.

### Current implementation status — Complete for matchmaking

Two separate browser sessions successfully connected to the backend, entered the
public queue, and received the same match with opposite Player A/Player B
assignments. The temporary Cloudflare Tunnel used for that remote test has been
removed; it was test infrastructure only and is not part of the application.

#### Implemented files and responsibilities

- `frontend/src/pages/HomePage.jsx` — opens the Socket.IO connection, creates
  or restores an anonymous guest, joins/leaves the queue, handles
  `match:found`, `match:error`, and connection errors, and shows the real
  opponent and assigned player slot in the matchmaking UI.
- `frontend/src/services/config.js` — supplies the configurable
  `VITE_BACKEND_URL` backend origin used by the Socket.IO client.
- `backend/app/controllers/matchmaking_controller.py` — provides the
  `guest:create`, `queue:join`, and `queue:leave` Socket.IO handlers and emits
  the match result to both matched sockets.
- `backend/app/services/matchmaking_service.py` and
  `backend/app/services/redis_service.py` — own guest identity, queueing, and
  player pairing/state persistence.
- `backend/app/views/socket_views.py` and `shared/events.md` — define the
  client-safe `match:found` payload and the shared realtime-event contract.

#### Not implemented by I1

- The matched payload is not yet passed into the media/game UI. `MediaRoom`
  still uses local mock player names, scenario data, timer, transcript, Switch,
  and results state.
- The frontend does not yet request LiveKit credentials, join a LiveKit room,
  publish media, or display the remote participant. That is Milestone I2.
- Reconnection/resume behavior after a browser refresh or network drop has not
  been integrated into the active match flow.
- The temporary remote-testing setup is intentionally not a deployment. A
  permanent HTTPS frontend/backend deployment belongs to D1/D2.

---

## Milestone I2 — Media Integration

**Owners:** Developers 1 + 2

### Goal

Connect backend LiveKit credentials to the frontend media system.

### Connect

```text
Backend LiveKit Token
→ Frontend LiveKit Client
```

### Done When

Matched players can see and hear each other.

---

## Milestone I3 — Scenario Integration

**Owners:** All Developers

### Goal

Connect real Gemini scenario generation to the match.

### Connect

```text
Match Created
→ Gemini Scenario
→ Backend
→ Both Frontends
```

### Done When

Both players see the same real scenario and roles before countdown.

---

## Milestone I4 — Live Transcript Integration

**Owners:** All Developers

### Goal

Display real STT transcript events on both clients.

### Connect

```text
Microphone
→ STT
→ TranscriptEvent
→ Backend
→ Socket.IO
→ Frontend
```

### Done When

Live speech appears correctly for both players.

---

## Milestone I5 — Turn + Switch Integration

**Owners:** All Developers

### Goal

Connect the core gameplay mechanics end to end.

### Turn Flow

```text
Player speaks
→ Silence detected
→ Backend changes active player
→ turn:changed
```

### Switch Flow

```text
Player A speaking
        ↓
Player B presses Switch
        ↓
Backend validates
        ↓
Player B loses one Switch
        ↓
STT finalizes Player A's speech
        ↓
Speech marked rejected
        ↓
[SWITCH] appears
        ↓
Player A remains active
        ↓
Player A starts replacement
```

### Done When

Automatic turns, mid-sentence Switches, and repeated Switches work live.

---

## Milestone I6 — Round End + Scoring Integration

**Owners:** All Developers

### Goal

Connect round completion to real judging and results.

### Flow

```text
60 Seconds
→ Backend Ends Round
→ Transcript Finalized
→ Gemini Judge
→ Speed Score
→ Final RoundResult
→ results:ready
→ Both Clients
```

### Done When

Both players receive the same final arcade result.

---

# Deployment Track — All Developers

## Milestone D1 — Production Deployment

### Goal

Deploy the complete application.

### Tasks

- Deploy React frontend
- Deploy Flask backend
- Configure Redis Cloud / Upstash
- Configure LiveKit Cloud
- Configure Gemini API
- Configure STT provider
- Add production environment variables
- Configure CORS
- Configure WebSockets
- Verify HTTPS

### Done When

The public application loads and all external services connect.

---

## Milestone D2 — Remote MVP Test

### Goal

Verify the full game works between two separate computers.

### Test

- Matchmaking
- Camera
- Microphone
- LiveKit video
- LiveKit audio
- Scenario
- Countdown
- Timer
- Automatic turns
- Mid-sentence Switch
- Repeated Switches
- Live transcript
- Round ending at exactly 60 seconds
- Gemini judging
- Speed scoring
- Winner
- Same result on both clients

### Done When

One complete remote match succeeds without developer intervention.

---

# Final Work Split

```text
ALL DEVELOPERS
└── M0 — Shared Foundation

DEVELOPER 1 — BACKEND
├── B1 — Multiplayer Foundation
├── B2 — Authoritative Game State
├── B3 — Switch Game Logic
├── B4 — LiveKit Backend
└── B5 — Backend Service Integration

DEVELOPER 2 — FRONTEND
├── F1 — Home + Matchmaking Flow
├── F2 — Camera/Microphone + LiveKit UI
├── F3 — Scenario + Countdown + Game HUD
├── F4 — Switch UX
├── F5 — Live Transcript UI
└── F6 — Scoring + Results Screen

DEVELOPER 3 — AI / TRANSCRIPTION
├── A1 — Gemini Scenario Generation
├── A2 — Realtime Speech-to-Text
├── A3 — Turn Detection + Transcript Events
├── A4 — Switch Interruption Processing
├── A5 — Gemini Judge
└── A6 — Speed + Arcade Score Engine

ALL DEVELOPERS — INTEGRATION
├── I1 — Matchmaking Integration
├── I2 — Media Integration
├── I3 — Scenario Integration
├── I4 — Live Transcript Integration
├── I5 — Turn + Switch Integration
└── I6 — Round End + Scoring Integration

ALL DEVELOPERS — DEPLOYMENT
├── D1 — Production Deployment
└── D2 — Remote MVP Test
```

## Recommended Order

```text
M0
│
├── Developer 1 → B1 → B2 → B3 → B4 → B5
├── Developer 2 → F1 → F2 → F3 → F4 → F5 → F6
└── Developer 3 → A1 → A2 → A3 → A4 → A5 → A6
                         ↓
                I1 → I2 → I3
                → I4 → I5 → I6
                         ↓
                    D1 → D2
```

The Backend, Frontend, and AI tracks should all begin immediately after M0 and use shared mocks whenever another track's real implementation is not ready.
