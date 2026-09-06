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

function removeRejectedPrefix(text, rejectedText) {
  const candidate = (text ?? "").trim();
  const rejected = (rejectedText ?? "").trim();
  if (!rejected || !candidate.toLocaleLowerCase().startsWith(rejected.toLocaleLowerCase())) {
    return candidate;
  }
  return candidate.slice(rejected.length).trim() || candidate;
}

export function SttTestPage() {
  const socketRef = useRef(null);
  const captureRef = useRef(null);
  const activeSpeechRef = useRef(null);
  const activeProviderSpeechIdRef = useRef(null);
  const pendingSwitchRef = useRef(null);
  const [status, setStatus] = useState("Ready to test your microphone.");
  const [error, setError] = useState("");
  const [lines, setLines] = useState([]);
  const [isListening, setIsListening] = useState(false);

  useEffect(() => {
    const socket = io(appConfig.backendUrl, { autoConnect: false });
    socketRef.current = socket;
    socket.on("speech:started", (payload) => {
      pendingSwitchRef.current = null;
      activeSpeechRef.current = payload.speech_id;
      activeProviderSpeechIdRef.current = payload.speech_id;
      setLines((current) => upsertLine(current, payload, false));
    });
    socket.on("speech:partial", (payload) => {
      const pendingSwitch = pendingSwitchRef.current;
      if (pendingSwitch && pendingSwitch.speechId === payload.speech_id) {
        if (performance.now() < pendingSwitch.readyAt) return;
        pendingSwitchRef.current = null;
        activeSpeechRef.current = pendingSwitch.replacementId;
        setLines((current) => upsertLine(
          current,
          { ...payload, text: removeRejectedPrefix(payload.text, pendingSwitch.rejectedText) },
          false,
          pendingSwitch.replacementId,
        ));
        return;
      }
      activeSpeechRef.current = payload.speech_id;
      activeProviderSpeechIdRef.current = payload.speech_id;
      setLines((current) => upsertLine(current, payload, false));
    });
    socket.on("speech:final", (payload) => {
      const pendingSwitch = pendingSwitchRef.current;
      if (pendingSwitch && pendingSwitch.speechId === payload.speech_id) {
        pendingSwitchRef.current = null;
        if (performance.now() < pendingSwitch.readyAt) return;
        activeSpeechRef.current = null;
        setLines((current) => upsertLine(
          current,
          { ...payload, text: removeRejectedPrefix(payload.text, pendingSwitch.rejectedText) },
          true,
          pendingSwitch.replacementId,
        ));
        return;
      }
      activeSpeechRef.current = null;
      activeProviderSpeechIdRef.current = null;
      // TODO(I5): The game HUD should use authoritative `turn:changed` alongside this final line.
      setLines((current) => upsertLine(current, payload, true));
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
    pendingSwitchRef.current = null;
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

  const selfSwitch = () => {
    const lineId = activeSpeechRef.current;
    const providerSpeechId = activeProviderSpeechIdRef.current;
    if (!lineId || !providerSpeechId) {
      setStatus("Start speaking first, then trigger a Self Switch.");
      return;
    }
    const rejectedText = lines.find((line) => line.id === lineId)?.text ?? "";
    // The production path sends ForceEndTurn. This mock mirrors its boundary
    // with a short stale-update guard and a new visual response line.
    pendingSwitchRef.current = {
      speechId: providerSpeechId,
      replacementId: `${lineId}-replacement-${Date.now()}`,
      rejectedText,
      readyAt: performance.now() + appConfig.switchResponseMinMs,
    };
    activeSpeechRef.current = null;
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
    setStatus("Self Switch triggered — continue with a replacement response.");
  };

  return (
    <main className="stt-test-page">
      <section className="stt-test-card">
        <p className="stt-test-label">DEEPGRAM · LIVE MIC CHECK</p>
        <h1>Test your<br /><span>voice.</span></h1>
        <p className="stt-test-status" role="status">{status}</p>
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
