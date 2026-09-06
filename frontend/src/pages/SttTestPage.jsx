import { useEffect, useRef, useState } from "react";
import { io } from "socket.io-client";

import { appConfig } from "../services/config.js";
import { startPcm16Capture } from "../services/pcm16Capture.js";

function upsertLine(lines, payload, isFinal) {
  const current = lines.findIndex((line) => line.id === payload.speech_id);
  const line = { id: payload.speech_id, text: payload.text ?? "", isFinal };
  if (current === -1) return [...lines, line];
  return lines.map((item, index) => (index === current ? { ...item, ...line } : item));
}

export function SttTestPage() {
  const socketRef = useRef(null);
  const captureRef = useRef(null);
  const [status, setStatus] = useState("Ready to test your microphone.");
  const [error, setError] = useState("");
  const [lines, setLines] = useState([]);
  const [isListening, setIsListening] = useState(false);

  useEffect(() => {
    const socket = io(appConfig.backendUrl, { autoConnect: false });
    socketRef.current = socket;
    socket.on("speech:started", (payload) => {
      setLines((current) => upsertLine(current, payload, false));
    });
    socket.on("speech:partial", (payload) => {
      setLines((current) => upsertLine(current, payload, false));
    });
    socket.on("speech:final", (payload) => {
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
        </div>
        {error && <p className="media-error" role="alert">{error}</p>}
        <div className="stt-test-transcript" aria-live="polite">
          {lines.length === 0 ? (
            <p>Your live transcript will appear here.</p>
          ) : lines.map((line) => (
            <p key={line.id} className={line.isFinal ? "" : "stt-test-partial"}>
              {line.text || "Listening…"}
            </p>
          ))}
        </div>
      </section>
    </main>
  );
}
