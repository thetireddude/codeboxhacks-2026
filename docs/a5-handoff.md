# A5 handoff: rapid Switch transcription

## Current branch and commits

- A4 branch: `feat/switch-interruption-processing`
- Latest A4 commit: `65334a0 feat: isolate rapid switch responses`
- Current local A5 branch: `feat/a5-transcript-handoff`
- The A4 commit and A5 branch are local only; the environment blocked the GitHub push pending fresh user confirmation for the external remote.

## What A3/A4 now do

- A3 turns Deepgram callbacks into authoritative `SpeechEvent` transcript entries.
- A4 persists a rejected/truncated speech event before the `SwitchEvent`.
- A real game Switch calls `DeepgramSession.interrupt()`, which sends Flux `ForceEndTurn` and discards all callbacks from the rejected turn.
- The transcript service stores the raw provider text at each Switch. If Flux sends a cumulative next hypothesis such as `resp 1 resp 2`, only `resp 2` is persisted. This repeats across rapid Switches.
- The old standalone debug page is `/stt-test`; do not use the main queue/game frontend for this test.

## Standalone `/stt-test` behavior

- `SELF SWITCH` crosses out the active response and adds a Switch marker.
- It emits `transcription:interrupt`, then shows `CLEARING PREVIOUS RESPONSE`.
- While clearing, it ignores `speech:started`, partial, and final events.
- On provider `EndOfTurn`, the backend emits `speech:ready`; the page turns green: `READY FOR NEXT RESPONSE`.
- Only a fresh `speech:started` after that ready event can create the next response. Old text must never be appended to a crossed-out line.
- Restart the backend after these changes. The debug page depends on its new `transcription:interrupt` handler and `speech:ready` event.

## Important files

- `backend/app/services/transcription_service.py` — Flux connection, `ForceEndTurn`, stale-event discard, provider-ready callback.
- `backend/app/services/transcript_service.py` — cumulative provider-prefix removal before authoritative transcript persistence.
- `backend/app/controllers/transcription_controller.py` — debug interrupt endpoint and `speech:ready` Socket.IO event.
- `frontend/src/pages/SttTestPage.jsx` — standalone mic/debug transcript UI and strict ready gate.
- `backend/tests/test_transcription.py` — socket and provider boundary coverage.
- `backend/tests/test_transcript_service.py` — cumulative transcript regression case.

## Verification already run

```text
python -m pytest tests/test_transcription.py tests/test_transcript_service.py
# 15 passed

ruff check app tests
# passed

cd frontend
npm run lint
npm run build
# passed
```

The cumulative transcript test prints:

```text
cumulative transcript flow: ['resp 1', 'resp 2', 'resp 3']
```

## Known live-test issue to diagnose next

The user saw `Transcription stream is still connecting`. The local `backend/.env` exists, a non-empty Deepgram key is configured, and a Python process was running, but there was no attached terminal log. This error means the browser filled the pending audio queue before the Deepgram WebSocket connected; it is not proof of exhausted credits. Next agent should get the backend terminal error around `STT_CONNECTION_FAILED` before changing behavior further.

## Next priority

Run `/stt-test` against a freshly restarted backend and confirm this exact visual sequence:

```text
old response (crossed out)
SELF SWITCH marker
CLEARING PREVIOUS RESPONSE
READY FOR NEXT RESPONSE
new response only
```

If it fails, capture the Socket.IO events (`speech:started`, `speech:partial`, `speech:final`, `speech:ready`) and backend Deepgram error rather than reintroducing client-side prefix stitching.
