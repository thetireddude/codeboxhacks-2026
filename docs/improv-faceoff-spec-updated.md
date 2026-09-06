# Improv Faceoff — Product & Implementation Spec

## 0. Status

**Project stage:** MVP specification  
**Primary mode:** 1v1 online improv faceoff  
**MVP match format:** one 60-second round  
**Team size:** 3 developers  
**Primary AI provider:** Gemini API  
**Hosting target:** Render for web/backend, managed services for realtime media and Redis

This document is the current source of truth for product behavior, MVP scope, implementation boundaries, and team work split.

---

# 1. Product Summary

Improv Faceoff is a competitive improv-training web app inspired by the fast, camera-first, arcade-like interaction pattern of Omoggle.

Two anonymous players are randomly matched. They connect by webcam and microphone, receive an AI-generated social/improv scenario with visible roles, and perform a live scene for 60 seconds.

Players alternate speaking turns. While one player is speaking, the other may spend a limited **Switch** resource to interrupt them and force them to immediately abandon their current response and say something different. Switches may happen mid-sentence and can be chained repeatedly.

The complete live transcript is shown during the round. After time expires, the round stops immediately and the transcript plus gameplay event data is sent to Gemini for post-round judging.

The result is presented like an arcade/fighting-game score screen rather than a generic AI evaluation.

The system is designed to reward improv skill under pressure, especially:

- Adaptability
- Creativity
- Speed of recovery after Switches
- Coherence
- Collaboration / scene-building

The MVP does **not** require accounts, persistent rankings, modifiers, best-of-3 matches, private rooms, or computer-vision scoring.

---

# 2. Core MVP Experience

The required end-to-end loop is:

```text
Open App
  ↓
Grant Camera + Microphone
  ↓
Find Match
  ↓
Enter Match Queue
  ↓
Pair With Opponent
  ↓
Connect Live Video + Audio
  ↓
Generate Scenario + Roles
  ↓
3-2-1 Countdown
  ↓
60-Second Improv Round
  ↓
Live Transcript + Switch Events
  ↓
Round Ends Immediately At 60s
  ↓
Gemini Judges Full Round
  ↓
Arcade Results + Winner + Feedback
```

Everything else is secondary to making this loop reliable.

---

# 3. MVP Scope

## 3.1 Required

- Anonymous guest identity
- Webcam required
- Microphone required
- Public matchmaking queue
- Two-player live video/audio session
- AI-generated scenario
- Visible Player A and Player B roles
- One 60-second round
- Alternating speaking turns
- Automatic turn end based on speech stopping
- 5 Switches per player per round
- Switch available during opponent's turn
- Switch allowed mid-sentence
- Repeated/chained Switches
- Live speaker-labeled transcript
- `[SWITCH]` transcript events
- Round stops immediately at 60 seconds
- Post-round Gemini judging
- Arcade-style score totals
- Winner selection
- Category score breakdown
- One strong moment / highlight
- One improvement suggestion
- No audio/video recording retention

## 3.2 Stretch / Later

- Best-of-3 matches
- New scenario each round in multi-round matches
- Per-player modifiers
- Catchphrases / special objectives
- Accounts
- Match history
- Ratings
- Leaderboards
- Private invite rooms
- Rematch
- Singleplayer Daily Challenge
- OpenCV / MediaPipe visual-performance descriptors
- Persistent analytics

---

# 4. Match Rules

## 4.1 Match Format

For MVP:

```text
1 match = 1 round
1 round = 60 seconds
```

Future format:

```text
1 match = best of 3 rounds
Each round = 60 seconds
Each round gets a new scenario
Each player resets to 5 Switches every round
```

---

## 4.2 Scenario

Before the round begins, Gemini generates:

- scenario
- Player A role
- Player B role
- tone

All generated information is visible to both players.

The tone is randomly chosen by the system. Players do not select it.

Example tone pool:

- relatable
- wacky
- funny
- stupid
- serious
- sad

Example:

```json
{
  "tone": "wacky",
  "scenario": "Two astronauts discover that neither knows how to land the spaceship.",
  "player_a_role": "Overconfident captain",
  "player_b_role": "Intern pretending to know what they are doing"
}
```

Modifiers are excluded from MVP.

---

# 5. Turn System

## 5.1 Turn Ownership

Exactly one player is the **active speaker** at a time.

The other player is the **listener**.

Normal flow:

```text
Player A speaks
  ↓
Player A stops speaking
  ↓
End-of-speech is detected
  ↓
Player A's turn ends
  ↓
Player B becomes active speaker
```

Then the process repeats.

The active player does not press a manual "Done" button in the current design.

### Configurable value

`TURN_END_SILENCE_MS`

This controls how long silence must last before the system considers the current player finished.

**Exact value is not yet finalized and must remain configurable during playtesting.**

Recommended initial test range:

```text
700–1200 ms
```

No implementation should hard-code a permanent product rule here.

---

# 6. Switch System

## 6.1 Inventory

Each player starts every round with:

```text
5 Switches
```

Switches do not carry across rounds in the future multi-round mode.

There is no penalty system for "bad" Switches.

The limited inventory is the anti-spam mechanism.

---

## 6.2 When Switch Can Be Used

The listener can press Switch while the opponent owns the current turn.

Switch is intentionally allowed during an unfinished sentence.

Example:

```text
[PLAYER A] I can't believe you sold my—
[SWITCH]
[PLAYER A] Actually, I sold your house three years ago.
```

When Player B Switches Player A:

- Player B spends 1 Switch
- Player A remains the active speaker
- Player A's current utterance is interrupted
- Player A must immediately make a different choice
- normal turn-end rules still determine when Player A's turn finally ends

A Switch never transfers turn ownership by itself.

---

## 6.3 Repeated Switches

Repeated Switches are allowed.

Example:

```text
[PLAYER A] I lost your dog.
[SWITCH]
[PLAYER A] Your dog ran away.
[SWITCH]
[PLAYER A] There was never a dog.
[SWITCH]
[PLAYER A] You've been hallucinating for three years.
```

Every repeated Switch consumes another Switch from the listener's inventory.

### Open gameplay configuration

Earlier design discussion included a **0.5-second chained-Switch window**.

The exact meaning of this rule has not yet been finalized relative to the newer rule that Switch can be used anytime during the opponent's turn.

Therefore MVP implementation must isolate this behind configuration / game-rule logic rather than tightly coupling it to UI code.

Use:

```text
CHAIN_SWITCH_WINDOW_MS = TBD
```

Until finalized, the core event model must support repeated Switches regardless of the exact window rule.

---

# 7. Transcript System

## 7.1 User-Facing Transcript

The transcript is live during the round.

There is one complete chronological transcript.

Speech is tagged:

```text
[PLAYER A] ...
[PLAYER B] ...
```

Switch events are tagged:

```text
[SWITCH]
```

The UI should visually associate each player's lines with that player's side of the screen while preserving one chronological event order internally.

Example:

```text
[PLAYER A] You weren't supposed to open that box.
[PLAYER B] My name was written on it.
[PLAYER A] That's because—
[SWITCH]
[PLAYER A] I forged your handwriting.
[PLAYER B] Why would you do that?
```

---

## 7.2 Internal Transcript Representation

Do not store the transcript only as a single text blob.

Store a structured event stream.

Example:

```json
[
  {
    "type": "speech",
    "id": "speech_001",
    "player_id": "A",
    "text": "You weren't supposed to open that box.",
    "start_ms": 4124,
    "end_ms": 6921,
    "accepted": true,
    "truncated_by_switch": false,
    "truncated_by_round_end": false
  },
  {
    "type": "switch",
    "id": "switch_001",
    "from_player_id": "B",
    "target_player_id": "A",
    "timestamp_ms": 9624
  }
]
```

This structured timeline is the canonical source for scoring and UI rendering.

---

## 7.3 Switched-Out Speech

When a player is interrupted mid-response, preserve the partial transcript.

Internally mark it as rejected / non-canonical.

Example:

```json
{
  "type": "speech",
  "player_id": "A",
  "text": "I don't think we should—",
  "accepted": false,
  "truncated_by_switch": true
}
```

The rejected utterance should not count as established scene canon.

However, it should still be available to the post-round judge because it provides context for how substantially the player changed direction after the Switch.

---

# 8. Round Timer

The backend owns the authoritative round clock.

The round lasts exactly:

```text
60 seconds
```

The timer continues during Switches and Switch responses.

At exactly 60 seconds:

- round input ends immediately
- the active player is cut off
- no grace period is added
- partial speech may be retained as truncated
- scoring begins

Example:

```text
59.2s Player A begins sentence
60.0s ROUND END
```

Possible event representation:

```json
{
  "type": "speech",
  "player_id": "A",
  "text": "But what if the landlord is actually—",
  "truncated_by_round_end": true
}
```

---

# 9. Scoring System

## 9.1 Categories

MVP scoring categories are:

- Adaptability
- Creativity
- Speed
- Coherence
- Collaboration / Scene Building

The displayed system uses **arcade points**, not a visible 0–100 rubric.

The score should feel like a game score rather than "AI gave you 8.3/10."

Example:

```text
PLAYER A — 8,420

Adaptability            1,920
Creativity              1,760
Speed                   1,540
Coherence               1,650
Collaboration           1,550

PLAYER A WINS
```

Exact category weights and maximum values remain configurable until playtesting.

---

## 9.2 Division of Scoring Responsibility

### Gemini evaluates semantic / improv quality

Gemini judges:

- Adaptability
- Creativity
- Coherence
- Collaboration / Scene Building
- quality of Switch recovery
- meaningful difference between rejected and replacement responses
- whether the player advanced the scene

### Backend calculates objective timing

The backend calculates:

- response timestamps
- Switch timestamps
- response latency after Switch
- deterministic speed bonuses

Gemini should not estimate elapsed time from text.

---

## 9.3 Switch Speed

For every Switch, measure:

```text
Switch cue received by target player
        ↓
Target player begins replacement response
```

The elapsed duration becomes a Speed input.

A configurable speed-bonus function converts that latency into arcade points.

Conceptually:

```text
f(response_time_ms) -> bonus points
```

Earlier brainstorm example:

```text
bonus = max(0, 50 - 12 * seconds)
```

This example is **not locked**.

The implementation should expose tuning constants so playtesting can change the curve without changing application architecture.

Important:

- faster recovery earns more Speed points
- fast nonsense should not outperform a slower but strong improv choice
- Gemini's Adaptability / Creativity evaluation remains separate from deterministic Speed scoring

---

## 9.4 Post-Round Arcade Events

No LLM analysis occurs during live gameplay.

After the round, Gemini may identify moments such as:

```text
🔥 BOLD CHOICE +180
⚡ QUICK THINK +45
🤝 STRONG BUILD +160
🎭 GREAT RECOVERY +220
```

These are generated during scoring and displayed in the result presentation.

This avoids introducing AI latency into the live round.

---

## 9.5 Feedback

Each player receives:

- one best / strongest moment
- one concrete improvement

Feedback should reference specific scene behavior rather than provide generic coaching.

---

# 10. Gemini Responsibilities

Gemini is used for two MVP responsibilities.

## 10.1 Scenario Generation

Input:

- allowed tone pool
- format requirements

Output schema:

```json
{
  "tone": "string",
  "scenario": "string",
  "player_a_role": "string",
  "player_b_role": "string"
}
```

Use structured output validation.

---

## 10.2 Post-Round Judging

Inputs:

- scenario
- both roles
- full structured transcript
- accepted speech
- rejected speech
- Switch events
- Switch response latencies
- round duration
- future optional visual-performance descriptors

Outputs should include:

```json
{
  "player_a": {
    "adaptability_points": 0,
    "creativity_points": 0,
    "coherence_points": 0,
    "collaboration_points": 0,
    "highlight": "",
    "improvement": ""
  },
  "player_b": {
    "adaptability_points": 0,
    "creativity_points": 0,
    "coherence_points": 0,
    "collaboration_points": 0,
    "highlight": "",
    "improvement": ""
  },
  "highlight_events": []
}
```

Speed points may be merged after this result by deterministic backend scoring.

Final arcade point aggregation is performed by application logic.

---

# 11. Media and Transcription

## 11.1 Media

Webcam is mandatory for multiplayer MVP.

Microphone is mandatory.

Players must be able to see and hear one another in realtime.

Recommended architecture:

- Browser WebRTC
- LiveKit Cloud for room/media infrastructure
- LiveKit client SDK in React
- LiveKit server SDK/token generation in Flask backend

No audio or video recording is permanently retained.

---

## 11.2 Live Transcription

Transcription must appear during the round.

The transcription implementation must:

- support partial live text
- know which player currently owns the turn
- associate speech with Player A or Player B
- finalize normal utterances when a turn ends
- immediately finalize/truncate speech when a Switch interrupts it
- preserve interrupted speech as rejected
- stop/finalize partial speech at round end

The exact speech-to-text service/provider should be selected based on latency and integration quality during implementation.

Gemini is the primary AI/judging API, but the transcription layer may use the most appropriate realtime STT mechanism available to the team.

---

# 12. Realtime Game State

The backend is authoritative for:

- queue membership
- match pairing
- player A/B assignment
- ready state
- round start time
- active speaker
- remaining Switch inventory
- Switch validation
- Switch timestamps
- turn changes
- round end
- scoring state
- result broadcast

The client may optimistically animate actions, but backend state wins on conflict.

---

# 13. Recommended State Machine

```text
LOBBY
  ↓
QUEUEING
  ↓
MATCH_FOUND
  ↓
CONNECTING_MEDIA
  ↓
READY
  ↓
COUNTDOWN
  ↓
ROUND_ACTIVE
  ├── PLAYER_A_TURN
  └── PLAYER_B_TURN
  ↓
ROUND_END
  ↓
SCORING
  ↓
RESULTS
```

Within a speaker turn:

```text
TURN_ACTIVE
   ↓
SPEAKING
   ├── normal silence -> TURN_COMPLETE
   └── SWITCH -> INTERRUPTED -> replacement speech -> still same TURN_ACTIVE
```

---

# 14. Realtime Event Contract

Exact payloads should be finalized in code/shared schemas, but the system should minimally support these event groups.

## Client -> Server

```text
queue:join
queue:leave
player:ready
switch:press
```

## Server -> Client

```text
match:found
match:error
round:prepare
round:start
turn:changed
switch:triggered
switch:rejected
transcript:event
round:end
results:ready
player:disconnected
```

## Internal / service events

```text
speech:partial
speech:final
speech:interrupted
speech:started_after_switch
judge:start
judge:complete
```

---

# 15. MVP Data Model

Persistent accounts are not required.

Redis / temporary backend state is sufficient.

## Guest

```json
{
  "guest_id": "uuid",
  "display_name": "Player 4821",
  "socket_id": "...",
  "status": "queueing"
}
```

## Match

```json
{
  "match_id": "uuid",
  "player_a_id": "...",
  "player_b_id": "...",
  "state": "ROUND_ACTIVE",
  "scenario": {},
  "round_started_at": "timestamp",
  "active_player_id": "A",
  "switches_remaining": {
    "A": 5,
    "B": 5
  },
  "transcript_events": []
}
```

No recording needs to be persisted after processing.

MVP result persistence is optional.

---

# 16. Frontend UX

## 16.1 Screens

### Home

- branding
- Find Match CTA

### Permission Check

- webcam permission
- microphone permission
- local preview
- cannot continue without both for MVP

### Matchmaking

- searching animation
- cancel button

### Match Found / Connection

- opponent found
- connect media
- loading state

### Countdown

- scenario visible
- both roles visible
- 3-2-1

### Game

Must show:

- Player A video
- Player B video
- scenario
- roles
- active player indicator
- round timer
- Player A remaining Switches
- Player B remaining Switches
- Switch button for listener
- live transcript

### Scoring

- round over state
- disable game actions
- judging animation/loading state

### Results

- winner
- both final arcade scores
- category breakdowns
- highlight events
- best moment
- improvement

---

# 17. Switch Button UI Rules

Switch is enabled only when:

- round is active
- opponent is the active speaker
- local player has at least 1 Switch remaining

Switch is disabled when:

- local player owns the current turn
- round has not started
- round has ended
- local player has 0 Switches

On accepted press:

- immediate visual/audio feedback
- local displayed inventory decrements
- authoritative server event confirms state

---

# 18. Stretch Feature — Visual Performance Descriptor

Computer-vision scoring is not required for MVP but is a high-priority stretch feature.

Potential stack:

- OpenCV
- MediaPipe
- NumPy

The goal is not to infer the player's true internal emotion.

Instead, video data should produce short **visual performance descriptors** for individual responses.

Examples:

```text
"visibly confused"
"high energy"
"tense posture"
"animated reaction"
"mostly neutral"
```

These should be one or two words or a very short phrase.

Possible input signals:

- face visibility
- head motion
- facial movement variation
- upper-body movement
- reaction intensity

These descriptors can later be attached to transcript response events and passed to Gemini during judging.

Raw recordings should still not be retained.

---

# 19. Technical Stack

## Frontend

- React
- JavaScript
- Vite
- React Router
- Tailwind CSS
- Framer Motion
- Socket.IO client
- LiveKit client / React components
- Browser MediaDevices API

## Backend

- Python
- Flask
- Flask-CORS
- Flask-SocketIO
- Redis / redis-py
- Pydantic
- LiveKit server SDK
- Gemini API / Google Gen AI SDK

## Managed Infrastructure

Recommended:

- Render — Flask backend and/or frontend hosting
- LiveKit Cloud — WebRTC rooms/media infrastructure
- Upstash Redis or Redis Cloud — matchmaking + temporary game state

## Backend Architecture — MVC

The Flask backend must use an MVC structure. Because React owns the browser UI, the backend's "views" are JSON / Socket.IO response formatting and outbound event construction rather than HTML templates.

### Models

Own application data structures and state representations.

Examples:

- guest model
- match model
- transcript event model
- scenario model
- result / score model

Models should define and validate the shape of data used by controllers and services.

### Views

Own backend response presentation.

Examples:

- JSON response serializers
- Socket.IO outbound payload builders
- error response formatting
- result payload formatting

Views must not contain matchmaking, timer, Switch, scoring, or AI business logic.

### Controllers

Receive HTTP requests and Socket.IO events, validate inputs, call the appropriate services, and return/broadcast through views.

Examples:

- matchmaking controller
- game controller
- media / LiveKit controller
- scenario controller
- transcription controller
- scoring controller

Controllers should stay thin. They coordinate requests but do not own core game rules.

### Services

The service layer contains the application's business logic and integrations.

Examples:

- matchmaking service
- game state service
- timer service
- Switch service
- Redis service
- LiveKit service
- transcription service
- Gemini scenario service
- Gemini judge service
- score aggregation service

The authoritative game rules described in this spec must live in services, not frontend components or controllers.

### Required backend shape

```text
backend/
├── app/
│   ├── models/
│   │   ├── guest.py
│   │   ├── match.py
│   │   ├── transcript.py
│   │   ├── scenario.py
│   │   └── results.py
│   ├── views/
│   │   ├── api_views.py
│   │   ├── socket_views.py
│   │   └── error_views.py
│   ├── controllers/
│   │   ├── matchmaking_controller.py
│   │   ├── game_controller.py
│   │   ├── media_controller.py
│   │   ├── transcription_controller.py
│   │   └── scoring_controller.py
│   ├── services/
│   │   ├── matchmaking_service.py
│   │   ├── game_service.py
│   │   ├── redis_service.py
│   │   ├── livekit_service.py
│   │   ├── scenario_service.py
│   │   ├── transcription_service.py
│   │   ├── judge_service.py
│   │   └── scoring_service.py
│   ├── config.py
│   └── __init__.py
├── run.py
├── requirements.txt
└── .env.example
```

## Stretch

- OpenCV
- MediaPipe
- NumPy
- Supabase/PostgreSQL for future persistent identity/results

---

# 20. Deployment Shape

Recommended MVP deployment:

```text
Browser
   |
   +---- React Frontend
   |
   +---- LiveKit Cloud
   |        |
   |      WebRTC
   |
   +---- Render Flask Backend
             |
             +---- Redis Cloud / Upstash
             |
             +---- Gemini API
             |
             +---- Realtime STT service/mechanism
```

Render is sufficient for the application/API layer.

Managed LiveKit is preferred over self-hosting realtime media for the hackathon MVP.

---

# 21. Implementation Milestones and Prerequisites

Milestones are dependency gates. A milestone may be implemented in parallel internally, but its integration work should not begin until its listed prerequisites are complete.

## Milestone 0 — Project Foundation and Shared Contracts

### Goal

Create the repository, MVC backend skeleton, frontend skeleton, shared contracts, and mock fixtures so all three developers can work independently.

### Must be completed

- initialize React/Vite frontend
- initialize Flask backend
- create MVC backend directories: `models/`, `views/`, `controllers/`, `services/`
- create `/shared` and `/spec`
- define environment-variable conventions
- define Socket.IO event names
- define match-state schema
- define transcript-event schema
- define scenario schema
- define results schema
- commit mock fixtures for each schema
- establish branch / PR conventions

### Prerequisites

None. This is the first milestone.

### Completion gate

All three developers can run their area locally and build against the same shared schemas and fixtures without depending on unfinished work from another developer.

---

## Milestone 1 — Mocked End-to-End Game Flow

### Goal

Prove the 60-second game state machine and player-facing flow using mocks before integrating external services.

### Must be completed

Backend:

- anonymous guest creation
- authoritative match object
- state transitions from lobby through results
- player A/B assignment
- authoritative 60-second timer
- active-turn state
- 5-Switch inventory per player
- Switch validation
- repeated Switch support
- configurable turn-end silence constant
- configurable chained-Switch rule

Frontend:

- home / Find Match screen
- permissions screen layout
- matchmaking screen
- countdown screen
- complete game HUD
- timer rendering
- active-player indicator
- Switch button and inventory
- transcript rendering from fixtures
- scoring/loading state
- results screen using mock results

### Prerequisites

- Milestone 0 complete

### Completion gate

A developer can run two mock clients through:

```text
match found
-> countdown
-> Player A turn
-> Switch
-> Player A replacement
-> turn change
-> Player B turn
-> 60-second end
-> mock results
```

No real LiveKit, STT, Redis, or Gemini integration is required yet.

---

## Milestone 2 — Realtime Matchmaking and Authoritative Multiplayer State

### Goal

Replace mocked multiplayer events with the real Flask-SocketIO + Redis flow.

### Must be completed

- Redis connection
- public matchmaking queue
- queue join / leave
- pairing exactly two users
- match creation
- synchronized ready state
- synchronized countdown
- authoritative round start timestamp
- synchronized active player
- Switch validation on server
- server-owned Switch inventory
- Switch timestamps
- round-end broadcast
- basic disconnect handling

### Prerequisites

- Milestone 0 complete
- shared event contract stable
- Milestone 1 state-machine behavior validated against mocks

### Completion gate

Two separate browser clients can queue, pair, enter the same match, and complete a synchronized 60-second round using fake transcript events.

---

## Milestone 3 — Live Video and Audio

### Goal

Add mandatory webcam/microphone permissions and real two-player media through LiveKit.

### Must be completed

- browser webcam permission
- browser microphone permission
- local preview
- LiveKit room creation/token generation in backend
- LiveKit client connection
- remote video rendering
- remote audio playback
- media connection state
- failure handling when permissions are denied

### Prerequisites

- Milestone 0 complete
- match identity and Player A/B assignment available from Milestone 2
- LiveKit credentials configured

### Completion gate

Two matched remote browsers can see and hear one another in the same game screen.

### Current implementation status — I2 complete

The I2 media path is implemented and remotely verified: real matchmaking
context reaches the media screen; each participant receives a match-scoped
LiveKit token, publishes camera and microphone media, and receives the other
participant's video and audio. The frontend emits `player:ready` only after
local media setup, and follows backend `round:prepare`, `round:start`, and
`round:end` events for the shared countdown and round clock.

The implementation also keeps media controls available after round end and
releases a disconnected guest's socket and old match index so that guest can
return to the public queue.

This does not complete the overall game loop: scenario display (Milestone 4 /
I3) and live transcript rendering (Milestone 5 / I4) are now implemented on
the frontend and await the existing two-browser remote validation. The
remaining separate work is turn/Switch UX (I5), real score/result presentation
(I6), active-match reconnect/resume, and permanent HTTPS hosting.

The I3 screen renders the backend-authoritative `round:prepare` scenario,
tone, and player-specific role for both clients. The I4 screen opens a
match-bound PCM16 stream for the active local player, displays that player's
partial speech, and renders finalized authoritative transcript events for both
participants.

The I5 UI now exposes the authoritative active-speaker state and each player's
remaining Switch inventory. A listener can send an idempotent `switch:press`,
receive the server result, see the Switch in the shared transcript, and restart
the interrupted speaker's local stream for the required replacement response.
The default `TURN_END_SILENCE_MS` is now 900 ms, inside the specified 700–1200
ms playtesting range, to leave a more practical listener Switch window; teams
can continue tuning it through environment configuration.

The I6 screen now waits after the server's `round:end` event while Gemini
judges the final transcript, then renders the shared `results:ready` payload:
winner or tie, both arcade totals and category scores, player coaching, and
highlight events. It awaits a real two-browser Gemini judging run for final
integration validation.

Switches are rendered at their actual chronological event position alongside
speech, including interrupted/rejected speech. A Gemini judge failure now
emits `JUDGING_UNAVAILABLE` to both clients and cleans up the match rather than
leaving the scoring view indefinitely pending.

For deployment, browser clients require only the public `VITE_BACKEND_URL`.
The Flask host alone owns Gemini, Deepgram, and LiveKit credentials and exposes
`GET /api/ready`, a secret-free readiness report that returns 503 with the
names of missing host-side integrations. Gemini judge failures retain the safe
client message but write the underlying provider error to backend-host logs;
unexpected scoring failures follow the same visible cleanup path.

Gemini highlight references are optional display metadata. If Gemini cites an
unknown live transcript ID, the backend retains the validated player scores and
coaching, removes the unverifiable reference, and omits any highlight with no
authoritative event remaining; a malformed optional highlight cannot discard a
completed round's results.

Production scenario preparation requires `GEMINI_API_KEY`: it no longer falls
back to a hardcoded scene when credentials are absent. Deterministic scenarios
remain only in automated-test and standalone mock-judging paths.

---

## Milestone 4 — Scenario Generation

### Goal

Replace mock scenarios with validated Gemini-generated scenarios and roles.

### Must be completed

- Gemini client wrapper
- tone selection
- scenario prompt
- structured output validation
- scenario / Player A role / Player B role generation
- failure / retry fallback
- broadcast identical scenario payload to both players

### Prerequisites

- Milestone 0 scenario schema complete
- match contains stable Player A/B identities
- Gemini credentials configured

### Completion gate

Every new match can receive one valid scenario object that conforms to the shared schema and displays identically for both players before countdown.

---

## Milestone 5 — Live Transcription and Turn Detection

### Goal

Turn live speech into the canonical structured transcript event stream.

### Must be completed

- selected realtime STT integration
- partial transcript handling
- final transcript handling
- speaker labeling based on authoritative active player
- speech-start detection
- silence-based turn completion
- Switch-triggered interruption
- rejected/non-canonical interrupted speech
- `[SWITCH]` transcript events
- round-end truncation
- chronological event storage
- transcript broadcast to both clients

### Prerequisites

- Milestone 2 authoritative turn/Switch state complete
- Milestone 3 microphone/media flow complete enough to provide live audio
- shared transcript schema stable

### Completion gate

A full round produces the structured transcript required by Section 7, including normal speech, interrupted speech, Switch events, and round-end truncation.

---

## Milestone 6 — Gemini Judging and Arcade Score Engine

### Goal

Convert the completed structured round into deterministic arcade scores and coaching feedback.

### Must be completed

- Gemini judge prompt
- judge input schema
- judge output validation
- Adaptability points
- Creativity points
- Coherence points
- Collaboration / Scene Building points
- Switch recovery quality analysis
- deterministic Switch latency calculation
- configurable Speed curve
- final category aggregation
- winner / tie logic
- highlight events
- one highlight per player
- one improvement per player

### Prerequisites

- Milestone 0 results schema complete
- Milestone 5 produces canonical transcript/event streams
- Gemini credentials configured

### Completion gate

A real completed round can be sent to the judge once and produce a valid final result payload that both clients can render.

---

## Milestone 7 — Full End-to-End MVP Integration

### Goal

Connect every real system into the required MVP loop.

### Must be completed

```text
Open App
-> Permissions
-> Find Match
-> Pair
-> Live Video/Audio
-> Gemini Scenario
-> Countdown
-> 60-second Round
-> Automatic Turn Changes
-> Switch Mid-Sentence
-> Repeated Switches
-> Live Transcript
-> Immediate 60-second Cutoff
-> Gemini Judge
-> Arcade Results
```

Also verify:

- backend remains authoritative
- no gameplay actions accepted after round end
- judge triggers only once
- both clients receive the same final result
- no audio/video recording is retained
- basic disconnect/error states are understandable

### Prerequisites

- Milestones 2 through 6 complete

### Completion gate

Two real users on separate machines can complete the entire MVP without mocked gameplay services.

---

## Milestone 8 — Deployment and Demo Hardening

### Goal

Make the complete MVP reliable over the public internet for the hackathon demo.

### Must be completed

- deploy frontend
- deploy Flask backend to Render
- configure production CORS
- configure production Socket.IO/WebSocket settings
- connect managed Redis
- connect LiveKit Cloud
- configure Gemini secrets
- configure STT secrets if needed
- test from two remote machines/networks
- loading / failure states
- smoke-test complete match flow

### Prerequisites

- Milestone 7 complete locally

### Completion gate

The public deployment completes the full acceptance-criteria flow reliably enough for the demo.

---

## Milestone 9 — Stretch Features

### Goal

Add non-MVP features only after the core loop is stable.

Possible work:

- OpenCV / MediaPipe visual descriptors
- rematch
- private rooms
- best-of-3
- modifiers / catchphrases
- accounts
- leaderboard
- Daily Challenge

### Prerequisites

- Milestone 8 complete or core MVP explicitly declared stable by the team

### Completion gate

Stretch work must not break or delay the MVP loop.

---

# 22. Three-Developer Concurrent Work Plan

The work split is intentionally organized so that **after one short shared foundation step, all three developers can work concurrently without waiting on one another**.

## Phase 0 — Shared Foundation

All three developers complete this together before splitting.

Deliverables:

1. repository initialized
2. frontend and backend folders created
3. environment-variable conventions defined
4. shared schemas/event names agreed on
5. branch/PR conventions agreed on
6. mock JSON fixtures committed for scenario, transcript, match state, and results

Required repository shape:

```text
improv-faceoff/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   ├── vite.config.js
│   └── .env.example
│
├── backend/
│   ├── app/
│   │   ├── models/
│   │   ├── views/
│   │   ├── controllers/
│   │   ├── services/
│   │   ├── config.py
│   │   └── __init__.py
│   ├── run.py
│   ├── requirements.txt
│   └── .env.example
│
├── shared/
│   ├── events.md
│   ├── schemas/
│   │   ├── match-state.json
│   │   ├── transcript-event.json
│   │   ├── scenario.json
│   │   └── results.json
│   └── fixtures/
│       ├── mock-match.json
│       ├── mock-transcript.json
│       ├── mock-scenario.json
│       └── mock-results.json
│
├── spec/
│   └── improv-faceoff-spec.md
│
├── .gitignore
├── README.md
└── .env.example
```

The `shared/` directory contains **contracts and fixtures only**. It is the agreement boundary between frontend, backend, and AI/transcription work. Runtime business logic should not live there.

The critical output of Phase 0 is a **shared interface contract**, not feature implementation.

Once the interfaces exist, all three developers branch off concurrently.

---

## Developer 1 — Realtime Game Backend

### Owns

- Flask app
- Socket.IO server
- Redis
- anonymous guests
- public matchmaking queue
- match creation
- authoritative state machine
- authoritative timer
- player turn state
- Switch inventory and validation
- Switch event timestamps
- disconnect handling
- LiveKit token generation

### Current implementation status on `main`

- **B1 — complete:** anonymous, socket-bound guests; Redis-backed queueing with
  duplicate protection; A/B pairing; temporary match state; and `match:found`.
- **B2 — complete for fake speech-end rounds:** ready/countdown, authoritative
  configurable round timer, active-speaker/turn state, round end, scoring-state
  transition, and basic disconnect notification. `turn:complete` is still the
  development-only turn signal.
- **B3 — complete for server validation:** five Switches per player,
  listener-only validation, repeat Switches, timestamps, idempotency, inventory
  updates, and Switch broadcasts/rejections. The optional chain-window settings
  are configured but not enforced.
- **B4 — complete:** match-derived LiveKit rooms and distinct, short-lived,
  room-scoped participant credentials are available through Socket.IO and an
  HTTP endpoint. The Socket.IO path is identity-bound; the HTTP endpoint still
  needs equivalent session authentication before production use.
- **B5 — complete for mocked service integration:** scenario providers prepare
  the round; final match-bound STT speech is persisted/broadcast and completes
  turns; Switches invoke the transcription hook; a deterministic mock judge
  produces `results:ready`; and match state is cleaned up after a configurable
  delay. Production Gemini judging and full interrupted-speech processing stay
  with the A4/A5 integrations.

### Works against mocks

Developer 1 does not need to wait for real transcription or finished UI.

Use mocked transcript/service events to drive game-state development.

### Interface supplied to others

- Socket.IO event contract
- match/round state payloads
- LiveKit room credentials
- round event stream

---

## Developer 2 — Player-Facing Game Client

### Owns

- React routes/layout
- permission screen
- local webcam preview
- matchmaking UI
- video room UI
- scenario/role HUD
- countdown
- timer rendering
- turn indicator
- Switch button UX
- remaining Switch display
- transcript rendering
- scoring state
- results screen
- arcade styling/animations

### Works against mocks

Developer 2 should build the entire game screen using mocked events immediately.

Use fixture data for:

- match found
- round start
- turn changes
- Switches
- transcript entries
- results

This lets frontend progress without waiting on the backend.

### Interface consumed

- shared schemas
- realtime event contract
- LiveKit credentials
- result payload

---

## Developer 3 — Transcription, Gemini, and Scoring

### Owns

- Gemini client wrapper
- scenario generation
- scenario schema validation
- live transcription integration
- speech partial/final handling
- transcript event creation
- interrupted/rejected response representation
- Switch recovery latency handoff
- Gemini judging prompt/schema
- deterministic Speed scoring
- final arcade aggregation
- best moment + improvement output

### Works against mocks

Developer 3 should not wait for matchmaking or finished media rooms.

Start with prerecorded/manual/mock transcript event streams matching the shared schema.

Build functions/services that accept:

```text
Match metadata + transcript events + Switch events
```

and return:

```text
Structured result payload
```

Then connect real live transcription later.

### Stretch ownership

- OpenCV / MediaPipe visual performance descriptor pipeline

---

# 23. Integration Order

Because all three developers work concurrently after foundation, integration should happen through stable interfaces.

## Integration A — Realtime + Frontend

Connect Developer 2's mocked client events to Developer 1's real Socket.IO server.

Target:

```text
Two browsers queue -> pair -> enter synchronized round
```

## Integration B — Transcription + Realtime

Connect Developer 3's transcript service to Developer 1's active-player and Switch state.

Target:

```text
Speech -> tagged transcript event -> broadcast to both clients
```

## Integration C — Scoring + Results

Connect completed transcript/event stream to Developer 3's judge, then broadcast result payload through Developer 1 to Developer 2.

Target:

```text
60s end -> judging -> both clients receive same final result
```

## Final MVP Test

```text
Find Match
-> Pair
-> Video/Audio
-> Scenario
-> Countdown
-> 60s Round
-> Turn Changes
-> Switch Mid-Sentence
-> Repeated Switches
-> Live Transcript
-> Immediate Round End
-> Gemini Judge
-> Arcade Results
```

---

# 24. GitHub Issue Plan

Use a small set of grouped issues rather than dozens of atomic tickets.

Each issue can contain its own task checklist.

## Issue 1 — Project Foundation + Shared Contracts

**Owners:** all three

Checklist:

- initialize React/Vite frontend
- initialize Flask backend
- environment-variable templates
- shared game schemas
- shared transcript schema
- Socket.IO event names
- mock fixtures
- code formatting/linting conventions

**Done when:** all three developers can work independently against shared mock contracts.

---

## Issue 2 — Matchmaking, Realtime State, and LiveKit Backend

**Owner:** Developer 1

Checklist:

- anonymous guest IDs
- Redis matchmaking queue
- pair two public users
- create match state
- player A/B assignment
- LiveKit token endpoint
- authoritative round state
- 60-second timer
- turn changes
- Switch validation/inventory
- repeated Switch support
- disconnect handling

**Done when:** two simple clients can pair and play through a synchronized mocked 60-second round.

---

## Issue 3 — Multiplayer Game UI + Media Experience

**Owner:** Developer 2

Checklist:

- permissions screen
- matchmaking UI
- local/remote video
- scenario and roles
- countdown
- game HUD
- timer
- active-turn indication
- Switch controls
- remaining inventory
- transcript UI
- scoring/loading screen
- arcade result screen

**Done when:** the complete player flow works against mocks and can later swap to real events without UI redesign.

---

## Issue 4 — Live Transcription + Structured Transcript Events

**Owner:** Developer 3

Checklist:

- choose/integrate realtime STT mechanism
- partial transcript events
- final transcript events
- assign speech to active player
- end utterance on silence
- interrupt utterance on Switch
- preserve rejected speech
- emit `[SWITCH]` events
- truncate at round end

**Done when:** a test speech stream produces the exact structured timeline required by the game and UI.

---

## Issue 5 — Gemini Scenario Generation + Post-Round Judging

**Owner:** Developer 3

Checklist:

- Gemini service wrapper
- scenario generation schema
- random tone generation
- judge input schema
- Adaptability scoring
- Creativity scoring
- Coherence scoring
- Collaboration/Scene Building scoring
- Switch recovery analysis
- best moment
- improvement
- structured output validation

**Done when:** a fixture transcript produces a valid, repeatable result payload.

---

## Issue 6 — Arcade Score Engine

**Owner:** Developer 3

Checklist:

- calculate Switch response latency
- configurable speed curve
- Speed arcade points
- merge Gemini category points
- final player totals
- winner selection
- ties/error fallback
- highlight event formatting

**Done when:** deterministic timing data + Gemini output always produce a complete final score object.

---

## Issue 7 — End-to-End Multiplayer Integration

**Owners:** all three

Checklist:

- frontend connects to real matchmaking
- frontend connects to LiveKit
- scenario shown to both clients
- real timer synchronized
- turn ownership synchronized
- Switch interrupts current speech
- live transcript broadcast
- 60-second cutoff
- judge triggered once
- result broadcast to both clients
- disconnect/error states tested

**Done when:** two browsers can complete the full MVP loop with no mocked gameplay services.

---

## Issue 8 — Deployment + Demo Hardening

**Owners:** all three

Checklist:

- deploy backend to Render
- deploy frontend
- connect managed Redis
- connect LiveKit Cloud
- configure Gemini secrets
- configure STT secrets if required
- production CORS/WebSocket settings
- reconnect/error messaging
- test two remote machines
- final demo smoke test

**Done when:** the complete game works over the public internet.

---

## Issue 9 — Stretch Features

**Owner:** whoever finishes core work first

Subtasks may include:

- OpenCV/MediaPipe visual descriptors
- rematch
- private room links
- best-of-3
- modifiers
- accounts
- leaderboard
- Daily Challenge

This issue should not block MVP.

---

# 25. Acceptance Criteria for MVP

The MVP is complete when all of the following are true:

1. Two anonymous users can open the public app from separate browsers/machines.
2. Both must grant webcam and microphone access.
3. Both can enter a public matchmaking queue.
4. They are paired into the same match.
5. They can see and hear each other.
6. Both receive the same generated scenario and visible roles.
7. A synchronized countdown starts the round.
8. The round lasts exactly 60 seconds.
9. Only one player owns the active speaking turn at a time.
10. A turn changes when speech stops according to configurable silence detection.
11. Each player starts with exactly 5 Switches.
12. The listener can Switch the active player mid-sentence.
13. A Switch does not transfer turn ownership.
14. Repeated Switches are supported.
15. Live speech appears in one chronological transcript labeled by player.
16. Switches appear as `[SWITCH]` transcript events.
17. Interrupted speech is preserved internally as rejected/non-canonical.
18. At 60 seconds the round stops immediately.
19. No audio/video recording is retained.
20. Gemini judges the completed round after gameplay ends.
21. Results include Adaptability, Creativity, Speed, Coherence, and Collaboration/Scene Building.
22. Results use arcade point totals.
23. One winner is selected or a tie is explicitly handled.
24. Each player receives one highlight and one improvement.
25. Both players receive the same authoritative match result.

---

# 26. Explicit Non-Goals for MVP

Do not block core development on:

- perfect visual polish
- accounts
- ranking systems
- persistent match history
- private rooms
- best-of-3 orchestration
- modifiers
- catchphrases
- computer-vision scoring
- Daily Challenge
- recordings
- advanced moderation
- complex reconnect/resume after long disconnects

---

# 27. Open Decisions

These are the only gameplay details currently left intentionally unresolved.

## 26.1 Turn-End Silence Threshold

```text
TURN_END_SILENCE_MS = TBD
```

Keep configurable.

Recommended initial playtest range:

```text
700–1200 ms
```

## 26.2 Chained-Switch 0.5s Rule

Earlier discussion included a 0.5-second chained-Switch window, while the latest rule says Switch is usable anytime during the opponent's turn.

The architecture must support both interpretations until finalized.

Possible implementation modes:

```text
SWITCH_MODE = ALWAYS_AVAILABLE_DURING_OPPONENT_TURN
```

or

```text
SWITCH_MODE = FIRST_ANYTIME_THEN_CHAIN_WINDOW
CHAIN_SWITCH_WINDOW_MS = 500
```

Do not hard-code one interpretation into frontend components.

---

# 28. Source-of-Truth Rule

When implementation behavior is unclear:

1. check this spec
2. check shared schemas
3. if still unspecified, open a product question before inventing a rule

The project should prefer configurable constants over hard-coded assumptions for timing and scoring values that still need playtesting.
