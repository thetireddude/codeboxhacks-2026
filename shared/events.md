# Realtime event contract

This is the canonical Socket.IO event-name registry for the MVP. Names are
lowercase namespace/action pairs. Timestamps inside a round are integer
milliseconds from the authoritative round start; absolute timestamps are ISO
8601 UTC strings. Player slots are `A` or `B`. The backend is authoritative.

Later milestones may add optional fields without renaming events. Removing or
changing a required field is a breaking contract change.

## Client to server

| Event | Required payload | Purpose |
| --- | --- | --- |
| `queue:join` | `{ guest_id }` | Join the public queue. |
| `queue:leave` | `{ guest_id }` | Leave the public queue. |
| `player:ready` | `{ match_id, guest_id }` | Confirm the client is ready. |
| `switch:press` | `{ match_id, guest_id, request_id }` | Request a Switch; `request_id` supports idempotent handling. |
| `turn:complete` | `{ match_id, guest_id }` | Development-only fake speech-end signal; the server validates ownership before changing turns. |
| `transcription:start` | `{ player_id }` | Open a live PCM16 transcription stream for the mocked active player. |
| `transcription:audio` | Binary PCM16 audio | Send one 16 kHz mono audio chunk (80 ms recommended). |
| `transcription:stop` | None | Finish and close the caller's transcription stream. |

## Socket acknowledgements

| Event | Optional request payload | Response | Purpose |
| --- | --- | --- | --- |
| `guest:create` | `{ guest_id? }` | `{ ok, guest }` | Create or restore the anonymous guest identity bound to this socket before `queue:join`. |

## Server to client

| Event | Required payload | Purpose |
| --- | --- | --- |
| `match:found` | `{ match_id, player_id, opponent, state }` | Pair a guest and assign slot `A` or `B`; `state` conforms to `schemas/match-state.json`. |
| `match:error` | `{ code, message }` | Report a matchmaking or match setup failure. |
| `round:prepare` | `{ match_id, scenario, starts_at }` | Share the validated scenario and countdown target. |
| `round:start` | `{ match_id, started_at, duration_ms, active_player_id, switches_remaining }` | Start the authoritative round. |
| `turn:changed` | `{ match_id, active_player_id, timestamp_ms }` | Announce normal turn transfer. |
| `switch:triggered` | `{ match_id, event, switches_remaining, request_id }` | Confirm a Switch; `event` conforms to the switch variant of `transcript-event.json`. |
| `switch:rejected` | `{ match_id, code, message, request_id, switches_remaining }` | Reject an invalid Switch without changing state. |
| `transcript:event` | `{ match_id, event }` | Broadcast one item conforming to `transcript-event.json`. |
| `speech:started` | `{ player_id, speech_id }` | The STT provider detected the start of speech. |
| `speech:partial` | `{ player_id, speech_id, text }` | Replace the current unfinished transcript line. |
| `speech:final` | `{ player_id, speech_id, text }` | Finalize the current transcript line. |
| `transcription:error` | `{ code, message }` | Report a recoverable microphone or STT failure. |
| `round:end` | `{ match_id, ended_at, transcript_events }` | Stop input and share the final chronological event stream. |
| `results:ready` | `{ match_id, results }` | Share a payload conforming to `schemas/results.json`. |
| `player:disconnected` | `{ match_id, player_id, timestamp }` | Notify the remaining player. |

## Internal and service events

These names form boundaries between authoritative game state and later service
integrations. They are not public client commands.

| Event | Minimum data |
| --- | --- |
| `speech:partial` | `{ match_id, player_id, speech_id, text, start_ms }` |
| `speech:final` | `{ match_id, event }` |
| `speech:interrupted` | `{ match_id, speech_id, switch_id, timestamp_ms }` |
| `speech:started_after_switch` | `{ match_id, switch_id, speech_id, timestamp_ms }` |
| `judge:start` | `{ match_id }` |
| `judge:complete` | `{ match_id, results }` |

## Error codes

Error codes are stable uppercase snake-case identifiers. Initial reserved codes:
`INVALID_PAYLOAD`, `NOT_IN_MATCH`, `ROUND_NOT_ACTIVE`, `NOT_LISTENER`,
`NO_SWITCHES_REMAINING`, `DUPLICATE_REQUEST`, and `INTERNAL_ERROR`.
