import { useEffect, useRef, useState } from "react";

const initialDevices = { camera: true, microphone: true };

const mockTranscript = [
  { type: "speech", id: "speech_001", player_id: "A", text: "Relax, I have landed dozens of ships just like this one.", is_final: true, accepted: true },
  { type: "speech", id: "speech_002", player_id: "B", text: "Then why are you holding the manual upside down?", is_final: true, accepted: true },
  { type: "speech", id: "speech_003", player_id: "A", text: "Because the gravity controls are—", is_final: true, accepted: false, truncated_by_switch: true },
  { type: "switch", id: "switch_001", from_player_id: "B", target_player_id: "A" },
  { type: "speech", id: "speech_004", player_id: "A", text: "This is actually the captain's traditional pre-landing dance.", is_final: true, accepted: true },
  { type: "speech", id: "speech_005", player_id: "B", text: "Then dance us toward the big green planet before we—", is_final: true, accepted: true, truncated_by_round_end: true },
];

function permissionMessage(error) {
  if (error?.name === "NotAllowedError") {
    return "Camera and microphone access was blocked. Allow both in your browser, then try again.";
  }
  if (error?.name === "NotFoundError") {
    return "We could not find a camera or microphone. Connect a device, then try again.";
  }
  return "We could not start your camera and microphone. Please try again.";
}

// This callback stays local to the page flow and is supplied by HomePage.
// eslint-disable-next-line react/prop-types
export function MediaRoom({ onLeave }) {
  const previewRef = useRef(null);
  const streamRef = useRef(null);
  const [permissionState, setPermissionState] = useState("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [devices, setDevices] = useState(initialDevices);
  const [gamePhase, setGamePhase] = useState("setup");
  const [countdown, setCountdown] = useState(3);
  const [secondsLeft, setSecondsLeft] = useState(60);
  const [activePlayer, setActivePlayer] = useState("A");
  const [switches, setSwitches] = useState({ A: 5, B: 5 });
  const [roundLog, setRoundLog] = useState([]);
  const [transcriptEvents, setTranscriptEvents] = useState([]);
  const transcriptRef = useRef(null);
  const [localPlayer, setLocalPlayer] = useState("B");
  const [switchedPlayer, setSwitchedPlayer] = useState(null);
  const reactionTimerRef = useRef(null);

  const stopPreview = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (previewRef.current) previewRef.current.srcObject = null;
  };

  useEffect(() => stopPreview, []);

  useEffect(() => {
    if (previewRef.current && streamRef.current) {
      previewRef.current.srcObject = streamRef.current;
    }
  }, [permissionState]);

  useEffect(() => {
    if (gamePhase !== "countdown" || countdown === 0) return undefined;
    const timer = window.setTimeout(() => setCountdown((current) => current - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [countdown, gamePhase]);

  useEffect(() => {
    if (gamePhase !== "countdown" || countdown !== 0) return;
    setGamePhase("active");
    setRoundLog([{ kind: "round", text: "ROUND 1 STARTED · 60 SECONDS ON THE CLOCK" }, { kind: "A", text: "Relax, I have landed dozens of ships just like this one." }]);
  }, [countdown, gamePhase]);

  useEffect(() => {
    if (gamePhase !== "active" || secondsLeft === 0) return undefined;
    const timer = window.setTimeout(() => setSecondsLeft((current) => current - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [gamePhase, secondsLeft]);

  useEffect(() => {
    if (gamePhase !== "active") return undefined;
    const transcriptTimer = window.setInterval(() => {
      setTranscriptEvents((current) => current.length >= mockTranscript.length ? current : [...current, mockTranscript[current.length]]);
    }, 2800);
    return () => window.clearInterval(transcriptTimer);
  }, [gamePhase]);

  useEffect(() => {
    if (transcriptRef.current) transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
  }, [transcriptEvents]);

  useEffect(() => {
    if (gamePhase !== "active") return;
    if (secondsLeft === 49) {
      setActivePlayer("B");
      setRoundLog((current) => [...current, { kind: "turn", text: "TURN END · PLAYER A PASSES THE SCENE" }, { kind: "B", text: "Then why is the landing gear waving at us?" }]);
    }
    if (secondsLeft === 0) {
      setActivePlayer(null);
      setGamePhase("ended");
      setRoundLog((current) => [...current, { kind: "round", text: "ROUND 1 OVER · THE SCENE IS COMPLETE" }]);
    }
  }, [gamePhase, secondsLeft]);

  const requestDevices = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setErrorMessage("This browser does not support camera and microphone access.");
      setPermissionState("error");
      return;
    }

    setPermissionState("requesting");
    setErrorMessage("");
    stopPreview();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      streamRef.current = stream;
      setDevices(initialDevices);
      setPermissionState("ready");
    } catch (error) {
      setErrorMessage(permissionMessage(error));
      setPermissionState("error");
    }
  };

  const toggleDevice = (device) => {
    const kind = device === "camera" ? "video" : "audio";
    const nextEnabled = !devices[device];
    streamRef.current?.getTracks().filter((track) => track.kind === kind).forEach((track) => {
      track.enabled = nextEnabled;
    });
    setDevices((current) => ({ ...current, [device]: nextEnabled }));
  };

  const leaveRoom = () => {
    window.clearTimeout(reactionTimerRef.current);
    stopPreview();
    onLeave();
  };

  const hasPreview = permissionState === "ready";
  const timerLabel = `${Math.floor(secondsLeft / 60)}:${String(secondsLeft % 60).padStart(2, "0")}`;

  const startRound = () => {
    setCountdown(3);
    setSecondsLeft(60);
    setActivePlayer("A");
    setSwitches({ A: 5, B: 5 });
    setRoundLog([{ kind: "round", text: "ROUND 1 READY · SCENARIO LOADED" }]);
    setTranscriptEvents([]);
    setGamePhase("countdown");
  };

  const pressSwitch = () => {
    const targetPlayer = activePlayer;
    const opponentPlayer = localPlayer === "A" ? "B" : "A";
    if (gamePhase !== "active" || targetPlayer !== opponentPlayer || switches[localPlayer] === 0) return;
    setSwitches((current) => ({ ...current, [localPlayer]: current[localPlayer] - 1 }));
    setRoundLog((current) => {
      const interruptedIndex = [...current].map((entry, index) => ({ entry, index })).reverse().find(({ entry }) => entry.kind === targetPlayer && !entry.interrupted)?.index;
      const nextLog = current.map((entry, index) => index === interruptedIndex ? { ...entry, interrupted: true } : entry);
      const targetLabel = targetPlayer === "A" ? "PLAYER 7392" : "YOU";
      const switcherLabel = localPlayer === "A" ? "PLAYER 7392" : "YOU";
      return [...nextLog, { kind: "switch", text: `SWITCH · ${switcherLabel} INTERRUPPTS ${targetLabel}` }, { kind: targetPlayer, text: "— No, wait. The warning light is trying to tell us something." }];
    });
    window.clearTimeout(reactionTimerRef.current);
    setSwitchedPlayer(targetPlayer);
    reactionTimerRef.current = window.setTimeout(() => setSwitchedPlayer(null), 800);
  };

  if (gamePhase !== "setup") {
    const opponentPlayer = localPlayer === "A" ? "B" : "A";
    const localPlayerName = localPlayer === "A" ? "PLAYER 7392" : "YOU";
    const opponentName = opponentPlayer === "A" ? "PLAYER 7392" : "YOU";
    const localRole = localPlayer === "A" ? "CAPTAIN" : "INTERN";
    const opponentRole = opponentPlayer === "A" ? "CAPTAIN" : "INTERN";
    const localPlayerMaySwitch = gamePhase === "active" && activePlayer === opponentPlayer && switches[localPlayer] > 0;
    return (
      <main className="media-page">
        <header className="guest-banner"><span className="guest-banner__spark">✦</span><span>Round 1 · Two astronauts discover neither knows how to land the spaceship.</span><button className="guest-banner__claim" type="button" onClick={leaveRoom}>LEAVE</button></header>
        <section className="media-room media-room--game" aria-label="Improv game room">
          <button className="round-icon round-icon--left" type="button" onClick={leaveRoom} aria-label="Leave game">×</button>
          <div className="game-stage">
            <div className="media-heading media-heading--game"><p>LIVE SCENE · ROUND 1</p></div>
            <div className={`round-timer round-timer--${gamePhase}`}><span>TIME LEFT</span><b>{gamePhase === "ended" ? "00:00" : timerLabel}</b></div>
            <div className="video-grid game-video-grid">
              <article className={`video-tile video-tile--local ${activePlayer === localPlayer ? "video-tile--active" : ""} ${switchedPlayer === localPlayer ? "video-tile--switched" : ""}`}>
                <video ref={previewRef} autoPlay muted playsInline className={hasPreview ? "" : "video-tile__hidden"} />
                {!hasPreview && <div className="video-placeholder"><b>{localPlayerName}</b><span>CAMERA PREVIEW</span></div>}
                <div className="video-tile__label"><span>{localPlayerName} · {localRole}</span><b>{activePlayer === localPlayer ? "● SPEAKING" : "○ LISTENING"}</b></div>
                {switchedPlayer === localPlayer && <div className="switched-reaction">SWITCHED!</div>}
                <div className="switch-actions"><div className="switch-count">SWITCHES <b>{switches[localPlayer]}</b></div><button type="button" className="switch-button" disabled={!localPlayerMaySwitch} onClick={pressSwitch}>↯ SWITCH <small>{localPlayerMaySwitch ? `INTERRUPT ${opponentName}` : activePlayer === localPlayer ? "WAIT FOR OPPONENT" : "ROUND NOT ACTIVE"}</small></button></div>
              </article>
              <article className={`video-tile video-tile--remote ${activePlayer === opponentPlayer ? "video-tile--active" : ""} ${switchedPlayer === opponentPlayer ? "video-tile--switched" : ""}`}>
                <div className="video-placeholder"><b>{opponentName}</b><span>LIVEKIT VIDEO CONNECTING</span></div>
                <div className="video-tile__label"><span>{opponentName} · {opponentRole}</span><b>{activePlayer === opponentPlayer ? "● SPEAKING" : "○ LISTENING"}</b></div>
                {switchedPlayer === opponentPlayer && <div className="switched-reaction">SWITCHED!</div>}
                <div className="switch-actions"><div className="switch-count">SWITCHES <b>{switches[opponentPlayer]}</b></div><button type="button" className="switch-button" disabled>↯ SWITCH <small>OPPONENT CONTROLS THIS</small></button></div>
              </article>
              {gamePhase === "countdown" && <div className="countdown-overlay" aria-live="assertive"><span>ROUND 1</span><b>{countdown || "GO!"}</b><small>THE SCENE STARTS NOW</small></div>}
            </div>
            <section className="round-log round-log--unified" aria-label="Scene log and live transcript" aria-live="polite"><header><span>◫ SCENE LOG · LIVE TRANSCRIPT</span><b>{gamePhase === "ended" ? "ROUND COMPLETE" : transcriptEvents.length < mockTranscript.length ? "LISTENING…" : "ROUND BUFFER COMPLETE"}</b></header><div className="round-log__entries" ref={transcriptRef}>{roundLog.filter((entry) => entry.kind !== "A" && entry.kind !== "B").map((entry, index) => <p key={`${entry.text}-${index}`} className={`round-log__entry round-log__entry--${entry.kind}`}>{entry.text}</p>)}{transcriptEvents.map((event) => { const playerName = event.player_id === "A" ? "PLAYER 7392" : "YOU"; if (event.type === "switch") return <p className="round-log__entry round-log__entry--switch" key={event.id}><strong>[SWITCH]</strong> YOU interrupted PLAYER 7392</p>; return <p className={`round-log__entry transcript-entry--${event.player_id} ${event.accepted === false ? "round-log__entry--interrupted" : ""}`} key={event.id}><strong>{playerName}:</strong> {event.text}{event.accepted === false && <em> · interrupted</em>}{event.truncated_by_round_end && <em> · round ended</em>}</p>; })}</div></section>
            <div className="mock-view-toggle" aria-label="Mock perspective selector"><span>MOCK VIEW</span><button type="button" className={localPlayer === "B" ? "mock-view-toggle__selected" : ""} onClick={() => setLocalPlayer("B")}>YOU · PLAYER B</button><button type="button" className={localPlayer === "A" ? "mock-view-toggle__selected" : ""} onClick={() => setLocalPlayer("A")}>PLAYER 7392 · PLAYER A</button></div>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="media-page">
      <header className="guest-banner">
        <span className="guest-banner__spark">✦</span>
        <span>Media check · your camera and microphone stay in your control.</span>
        <button className="guest-banner__claim" type="button" onClick={leaveRoom}>LEAVE</button>
      </header>
      <section className="media-room" aria-label="Camera and microphone setup">
        <button className="round-icon round-icon--left" type="button" onClick={leaveRoom} aria-label="Leave media setup">×</button>
        <div className="media-stage">
          <div className="media-heading">
            <p>ROUND ONE · MEDIA CHECK</p>
            <h1>GET READY<br /><span>TO IMPROVISE.</span></h1>
            <div className="media-status"><i className={hasPreview ? "media-status__dot media-status__dot--ready" : "media-status__dot"} />{hasPreview ? "CAMERA + MIC READY" : "CAMERA + MIC REQUIRED"}</div>
          </div>

          <div className="video-grid">
            <article className="video-tile video-tile--local">
              <video ref={previewRef} autoPlay muted playsInline className={hasPreview ? "" : "video-tile__hidden"} />
              {!hasPreview && <div className="video-placeholder"><b>YOU</b><span>{permissionState === "requesting" ? "REQUESTING ACCESS…" : "CAMERA PREVIEW"}</span></div>}
              <div className="video-tile__label"><span>YOU</span><b>{devices.microphone && hasPreview ? "● MIC ON" : "○ MIC OFF"}</b></div>
            </article>
            <article className="video-tile video-tile--remote">
              <div className="video-placeholder"><b>PLAYER 7392</b><span>WAITING FOR LIVEKIT ROOM</span></div>
              <div className="video-tile__label"><span>OPPONENT</span><b className="video-tile__waiting">⌁ CONNECTING</b></div>
            </article>
          </div>

          {hasPreview ? (
            <div className="media-controls" aria-label="Media controls">
              <button type="button" className={devices.microphone ? "media-control media-control--active" : "media-control"} onClick={() => toggleDevice("microphone")}>{devices.microphone ? "◉" : "◌"}<span>{devices.microphone ? "MUTE" : "UNMUTE"}</span></button>
              <button type="button" className={devices.camera ? "media-control media-control--active" : "media-control"} onClick={() => toggleDevice("camera")}>{devices.camera ? "◉" : "◌"}<span>{devices.camera ? "CAMERA ON" : "CAMERA OFF"}</span></button>
              <button type="button" className="media-control media-control--start" onClick={startRound}>▶<span>START MOCK ROUND</span></button>
            </div>
          ) : (
            <div className="media-setup-actions"><button className="match-button media-permission-button" type="button" disabled={permissionState === "requesting"} onClick={requestDevices}><span className="match-button__people">◉</span><span><strong>{permissionState === "requesting" ? "REQUESTING ACCESS" : "ENABLE CAMERA + MIC"}</strong><small>YOU CONTROL WHAT YOU SHARE</small></span></button><button type="button" className="preview-round-button" onClick={startRound}>PREVIEW MOCK ROUND WITHOUT MEDIA →</button></div>
          )}

          {errorMessage && <p className="media-error" role="alert">{errorMessage}</p>}
          <p className="media-connection" role="status"><i />WAITING FOR SECURE ROOM CREDENTIALS · LIVEKIT CONNECTS AFTER THE MATCH SERVICE PROVIDES A TOKEN.</p>
        </div>
      </section>
    </main>
  );
}
