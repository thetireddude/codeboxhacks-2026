import { useEffect, useRef, useState } from "react";
import { io } from "socket.io-client";

import { appConfig } from "../services/config.js";
import { mockJudgmentCases } from "../fixtures/mockJudgmentCases.js";
import { startPcm16Capture } from "../services/pcm16Capture.js";

function upsertLine(lines, payload, isFinal, id = payload.speech_id) {
  const current = lines.findIndex((line) => line.id === id);
  const existing = current === -1 ? null : lines[current];
  const line = {
    id,
    kind: "speech",
    text: payload.text ?? "",
    isFinal,
    playerId: payload.player_id ?? "A",
    startMs: existing?.startMs ?? payload.timestampMs ?? 0,
    endMs: payload.timestampMs ?? existing?.endMs ?? 0,
  };
  if (current === -1) return [...lines, line];
  return lines.map((item, index) => (index === current ? { ...item, ...line } : item));
}

export function SttTestPage() {
  const socketRef = useRef(null);
  const captureRef = useRef(null);
  const activeSpeechRef = useRef(null);
  const activeProviderSpeechIdRef = useRef(null);
  const providerLineIdsRef = useRef(new Map());
  const awaitingReplacementStartRef = useRef(false);
  const replacementMayStartRef = useRef(false);
  const sessionStartedAtRef = useRef(0);
  const [status, setStatus] = useState("Ready to test your microphone.");
  const [error, setError] = useState("");
  const [lines, setLines] = useState([]);
  const [isListening, setIsListening] = useState(false);
  const [isResponseReady, setIsResponseReady] = useState(true);
  const [isJudging, setIsJudging] = useState(false);
  const [results, setResults] = useState(null);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const selectedCase = mockJudgmentCases.find((item) => item.id === selectedCaseId);

  useEffect(() => {
    const socket = io(appConfig.backendUrl, { autoConnect: false });
    socketRef.current = socket;
    socket.on("speech:started", (payload) => {
      if (
        awaitingReplacementStartRef.current
        && !replacementMayStartRef.current
      ) return;
      awaitingReplacementStartRef.current = false;
      replacementMayStartRef.current = false;
      setIsResponseReady(true);
      activeSpeechRef.current = payload.speech_id;
      activeProviderSpeechIdRef.current = payload.speech_id;
      providerLineIdsRef.current.set(payload.speech_id, payload.speech_id);
      setLines((current) => upsertLine(current, {
        ...payload,
        timestampMs: Date.now() - sessionStartedAtRef.current,
      }, false));
    });
    socket.on("speech:partial", (payload) => {
      if (awaitingReplacementStartRef.current) return;
      const lineId = providerLineIdsRef.current.get(payload.speech_id)
        ?? payload.speech_id;
      activeSpeechRef.current = lineId;
      activeProviderSpeechIdRef.current = payload.speech_id;
      setLines((current) => upsertLine(current, {
        ...payload,
        timestampMs: Date.now() - sessionStartedAtRef.current,
      }, false, lineId));
    });
    socket.on("speech:final", (payload) => {
      if (awaitingReplacementStartRef.current) return;
      const lineId = providerLineIdsRef.current.get(payload.speech_id)
        ?? payload.speech_id;
      activeSpeechRef.current = null;
      activeProviderSpeechIdRef.current = null;
      providerLineIdsRef.current.delete(payload.speech_id);
      // TODO(I5): The game HUD should use authoritative `turn:changed` alongside this final line.
      setLines((current) => upsertLine(current, {
        ...payload,
        timestampMs: Date.now() - sessionStartedAtRef.current,
      }, true, lineId));
    });
    socket.on("speech:ready", () => {
      replacementMayStartRef.current = true;
      setIsResponseReady(true);
      setStatus("Ready for a new response.");
    });
    socket.on("transcription:error", (payload) => setError(payload.message));

    return () => {
      captureRef.current?.stop();
      socket.disconnect();
    };
  }, []);

  const start = async () => {
    const socket = socketRef.current;
    setError("");
    setLines([]);
    setResults(null);
    sessionStartedAtRef.current = Date.now();
    activeSpeechRef.current = null;
    activeProviderSpeechIdRef.current = null;
    providerLineIdsRef.current.clear();
    awaitingReplacementStartRef.current = false;
    replacementMayStartRef.current = false;
    setIsResponseReady(true);
    setStatus("Connecting to transcription…");
    socket.connect();
    try {
      captureRef.current = await startPcm16Capture({
        socket,
        playerId: "A",
        onError: setError,
      });
      setIsListening(true);
      setStatus("Listening — speak naturally.");
    } catch (startError) {
      setStatus("Could not start listening.");
      setError(startError.message);
      socket.disconnect();
    }
  };

  const stop = async () => {
    await captureRef.current?.stop();
    captureRef.current = null;
    setIsListening(false);
    setStatus("Stopped. Start again whenever you like.");
  };

  const selfSwitch = async () => {
    const lineId = activeSpeechRef.current;
    const providerSpeechId = activeProviderSpeechIdRef.current;
    if (!lineId || !providerSpeechId) {
      setStatus("Start speaking first, then trigger a Self Switch.");
      return;
    }
    // Force Flux to close the old turn. Until it emits a new speech:started,
    // every old partial/final is discarded instead of being merged forward.
    awaitingReplacementStartRef.current = true;
    replacementMayStartRef.current = false;
    setIsResponseReady(false);
    activeSpeechRef.current = null;
    activeProviderSpeechIdRef.current = null;
    providerLineIdsRef.current.delete(providerSpeechId);
    setLines((current) => [
      ...current.map((line) => (
        line.id === lineId
          ? { ...line, isFinal: true, isInterrupted: true }
          : line
      )),
      {
        id: `switch-${Date.now()}`,
        kind: "switch",
        text: "↯ SELF SWITCH · CURRENT SPEECH REJECTED",
        isFinal: true,
        timestampMs: Date.now() - sessionStartedAtRef.current,
      },
    ]);
    setStatus("Self Switch triggered — clearing the previous response…");
    const response = await new Promise((resolve) => {
      socketRef.current.emit("transcription:interrupt", resolve);
    });
    if (!response?.ok) {
      awaitingReplacementStartRef.current = false;
      setIsResponseReady(true);
      setError(response?.error?.message ?? "Could not interrupt transcription.");
    }
  };

  const judgeTranscript = async () => {
    const finishedLines = lines.filter((line) => line.kind === "speech" && line.isFinal);
    if (!selectedCase && finishedLines.length === 0) {
      setError("Finish at least one response before submitting it for judgment.");
      return;
    }
    setError("");
    setResults(null);
    setIsJudging(true);
    setStatus("Gemini is judging your final transcript…");
    if (isListening) {
      await captureRef.current?.stop();
      captureRef.current = null;
      setIsListening(false);
    }
    const transcriptEvents = selectedCase?.events ?? lines.flatMap((line, index) => {
      if (line.kind === "switch") {
        return [{
          type: "switch",
          id: `switch_mock_${index}`,
          from_player_id: "B",
          target_player_id: "A",
          timestamp_ms: line.timestampMs,
        }];
      }
      if (!line.isFinal || !line.text.trim()) return [];
      return [{
        type: "speech",
        id: `speech_mock_${index}`,
        player_id: line.playerId,
        text: line.text.trim(),
        start_ms: line.startMs,
        end_ms: line.endMs,
        is_final: true,
        accepted: !line.isInterrupted,
        truncated_by_switch: Boolean(line.isInterrupted),
        truncated_by_round_end: false,
      }];
    });
    try {
      const response = await fetch(`${appConfig.backendUrl}/api/mockup/judge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript_events: transcriptEvents }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error?.message ?? "Judging failed.");
      setResults(payload.results);
      setStatus("Judgment complete.");
    } catch (judgeError) {
      setStatus("Could not judge this transcript.");
      setError(judgeError.message);
    } finally {
      setIsJudging(false);
    }
  };

  return (
    <main className="stt-test-page">
      <section className="stt-test-card">
        <p className="stt-test-label">DEEPGRAM · LIVE MIC CHECK</p>
        <h1>Test your<br /><span>voice.</span></h1>
        <p className="stt-test-status" role="status">{status}</p>
        <p className={`stt-response-ready ${isResponseReady ? "is-ready" : "is-clearing"}`}>
          {isResponseReady ? "● READY FOR NEXT RESPONSE" : "○ CLEARING PREVIOUS RESPONSE"}
        </p>
        <div className="stt-test-actions">
          <button type="button" className="match-button" disabled={isListening} onClick={start}>
            START MIC
          </button>
          <button type="button" className="cancel-button" disabled={!isListening} onClick={stop}>
            STOP MIC
          </button>
          <button type="button" className="switch-button stt-self-switch" disabled={!isListening} onClick={selfSwitch}>
            ↯ SELF SWITCH
          </button>
          <button type="button" className="match-button stt-judge-button" disabled={isJudging || (!selectedCase && !lines.some((line) => line.kind === "speech" && line.isFinal))} onClick={judgeTranscript}>
            {isJudging ? "JUDGING…" : "SUBMIT FINAL TRANSCRIPT"}
          </button>
        </div>
        <section className="stt-test-cases">
          <p className="stt-test-label">TWO-PLAYER JUDGING CASES</p>
          <select value={selectedCaseId} onChange={(event) => { setSelectedCaseId(event.target.value); setResults(null); }}>
            <option value="">Use live mic transcript</option>
            {mockJudgmentCases.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
          {selectedCase && <>
            <p className="stt-case-summary">{selectedCase.summary}</p>
            <div className="stt-case-timeline">
              {selectedCase.events.map((event) => (
                <p key={event.id} className={event.type === "switch" ? "stt-test-switch" : event.accepted ? `stt-case-player-${event.player_id.toLowerCase()}` : "stt-test-interrupted"}>
                  {event.type === "switch" ? "↯ SWITCH" : `${event.player_id}: ${event.text}`}
                </p>
              ))}
            </div>
          </>}
        </section>
        {error && <p className="media-error" role="alert">{error}</p>}
        <div className="stt-test-transcript" aria-live="polite">
          {lines.length === 0 ? (
            <p>Your live transcript will appear here.</p>
          ) : lines.map((line) => (
            <p key={line.id} className={[
              line.kind === "switch" ? "stt-test-switch" : "",
              line.isInterrupted ? "stt-test-interrupted" : "",
              !line.isFinal ? "stt-test-partial" : "",
              line.isFinal && line.kind === "speech" ? "stt-test-final" : "",
            ].filter(Boolean).join(" ")}>
              {line.text || "Listening…"}
            </p>
          ))}
        </div>
        {results && <section className="stt-test-results" aria-live="polite">
          <p className="stt-test-label">MOCK SCENE · GEMINI JUDGMENT</p>
          <h2>{results.winner === "TIE" ? "TIE GAME" : `PLAYER ${results.winner} WINS`}</h2>
          <div className="stt-result-score">
            <strong>PLAYER A</strong><b>{results.player_a.total_points.toLocaleString()}</b>
            <span>Adaptability {results.player_a.category_points.adaptability} · Creativity {results.player_a.category_points.creativity} · Speed {results.player_a.category_points.speed}</span>
          </div>
          <p><b>Best moment:</b> {results.player_a.highlight}</p>
          <p><b>Try next:</b> {results.player_a.improvement}</p>
          <div className="stt-result-score">
            <strong>PLAYER B</strong><b>{results.player_b.total_points.toLocaleString()}</b>
            <span>Adaptability {results.player_b.category_points.adaptability} · Creativity {results.player_b.category_points.creativity} · Speed {results.player_b.category_points.speed}</span>
          </div>
          <p><b>Best moment:</b> {results.player_b.highlight}</p>
          <p><b>Try next:</b> {results.player_b.improvement}</p>
        </section>}
      </section>
    </main>
  );
}
