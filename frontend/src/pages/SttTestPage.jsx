import { useEffect, useRef, useState } from "react";
import { io } from "socket.io-client";

import { appConfig } from "../services/config.js";
import { startPcm16Capture } from "../services/pcm16Capture.js";

function upsertLine(lines, payload, isFinal, id = payload.speech_id) {
  const current = lines.findIndex((line) => line.id === id);
  const line = { id, kind: "speech", text: payload.text ?? "", isFinal };
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
  const [status, setStatus] = useState("Ready to test your microphone.");
  const [error, setError] = useState("");
  const [lines, setLines] = useState([]);
  const [isListening, setIsListening] = useState(false);
  const [isResponseReady, setIsResponseReady] = useState(true);

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
      setLines((current) => upsertLine(current, payload, false));
    });
    socket.on("speech:partial", (payload) => {
      if (awaitingReplacementStartRef.current) return;
      const lineId = providerLineIdsRef.current.get(payload.speech_id)
        ?? payload.speech_id;
      activeSpeechRef.current = lineId;
      activeProviderSpeechIdRef.current = payload.speech_id;
      setLines((current) => upsertLine(current, payload, false, lineId));
    });
    socket.on("speech:final", (payload) => {
      if (awaitingReplacementStartRef.current) return;
      const lineId = providerLineIdsRef.current.get(payload.speech_id)
        ?? payload.speech_id;
      activeSpeechRef.current = null;
      activeProviderSpeechIdRef.current = null;
      providerLineIdsRef.current.delete(payload.speech_id);
      // TODO(I5): The game HUD should use authoritative `turn:changed` alongside this final line.
      setLines((current) => upsertLine(current, payload, true, lineId));
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
        </div>
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
      </section>
    </main>
  );
}
