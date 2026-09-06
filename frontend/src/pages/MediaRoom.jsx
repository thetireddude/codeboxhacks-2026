/* eslint-disable react/prop-types */
import { useEffect, useRef, useState } from "react";
import { Room, RoomEvent, Track } from "livekit-client";
import { startPcm16Capture } from "../services/pcm16Capture.js";

function requestCredentials(socket, matchId) {
  return new Promise((resolve, reject) => {
    socket.emit("media:credentials", { match_id: matchId }, (response) => {
      if (response?.ok && response.credentials) {
        resolve(response.credentials);
        return;
      }
      reject(new Error(response?.error?.message ?? "Could not get secure room credentials."));
    });
  });
}

function attachTrack(track, videoElement) {
  if (track && videoElement) track.attach(videoElement);
}

function connectionMessage(status) {
  const messages = {
    setup: "Enable your camera and microphone to join the secure match room.",
    connecting: "Getting secure room credentials and connecting to LiveKit…",
    waiting: "Media connected. Waiting for your opponent to finish their media check.",
    countdown: "Both players are ready. The authoritative countdown has started.",
    active: "LiveKit media connected. The match server controls the round.",
    ended: "Round complete. Waiting for the scoring service.",
  };
  return messages[status] ?? "Preparing secure media.";
}

// I2 receives the real I1 match and persistent Socket.IO connection. I3-I6 own
// scenario, transcript, Switch, and scoring integrations.
export function MediaRoom({ match, guestId, socket, onLeave }) {
  const localVideoRef = useRef(null);
  const remoteVideoRef = useRef(null);
  const remoteAudioRef = useRef(null);
  const roomRef = useRef(null);
  const captureRef = useRef(null);
  const [connectionState, setConnectionState] = useState("setup");
  const [errorMessage, setErrorMessage] = useState("");
  const [devices, setDevices] = useState({ camera: false, microphone: false });
  const [hasLocalVideo, setHasLocalVideo] = useState(false);
  const [hasRemoteVideo, setHasRemoteVideo] = useState(false);
  const [countdown, setCountdown] = useState(null);
  const [round, setRound] = useState(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [scenario, setScenario] = useState(null);
  const [transcript, setTranscript] = useState([]);
  const [partialTranscript, setPartialTranscript] = useState("");
  const [transcriptionStatus, setTranscriptionStatus] = useState("Waiting for the round to start.");
  const [switchesRemaining, setSwitchesRemaining] = useState({ A: 0, B: 0 });
  const [captureCycle, setCaptureCycle] = useState(0);
  const [isSwitching, setIsSwitching] = useState(false);
  const [results, setResults] = useState(null);

  const localPlayer = match.player_id;
  const opponentPlayer = localPlayer === "A" ? "B" : "A";
  const opponentName = match.opponent?.display_name ?? "OPPONENT";
  const isInRound = connectionState === "countdown" || connectionState === "active";
  const ownRole = scenario?.[localPlayer === "A" ? "player_a_role" : "player_b_role"];

  const detachMedia = () => {
    const room = roomRef.current;
    roomRef.current = null;
    room?.disconnect(true);
    if (localVideoRef.current) localVideoRef.current.srcObject = null;
    if (remoteVideoRef.current) remoteVideoRef.current.srcObject = null;
    if (remoteAudioRef.current) remoteAudioRef.current.srcObject = null;
  };

  useEffect(() => {
    const onPrepare = (payload) => {
      if (payload.match_id !== match.match_id) return;
      setScenario(payload.scenario ?? null);
      setConnectionState("countdown");
      setCountdown(Math.max(0, Math.ceil((Date.parse(payload.starts_at) - Date.now()) / 1000)));
    };
    const onStart = (payload) => {
      if (payload.match_id !== match.match_id) return;
      setRound(payload);
      setSwitchesRemaining(payload.switches_remaining ?? { A: 0, B: 0 });
      setSecondsLeft(Math.max(0, Math.ceil((Date.parse(payload.started_at) + payload.duration_ms - Date.now()) / 1000)));
      setConnectionState("active");
      setCountdown(null);
    };
    const onTurnChanged = (payload) => {
      if (payload.match_id !== match.match_id) return;
      setRound((current) => current ? { ...current, active_player_id: payload.active_player_id } : current);
    };
    const onTranscriptEvent = (payload) => {
      if (payload.match_id !== match.match_id) return;
      if (payload.event?.type === "switch") {
        setTranscript((current) => current.some((line) => line.id === payload.event.id) ? current : [...current, payload.event]);
        return;
      }
      if (payload.event?.type !== "speech") return;
      setTranscript((current) => current.some((line) => line.id === payload.event.id) ? current : [...current, payload.event]);
      setPartialTranscript("");
    };
    const onSwitchTriggered = (payload) => {
      if (payload.match_id !== match.match_id) return;
      setSwitchesRemaining(payload.switches_remaining);
      setIsSwitching(false);
      if (payload.event?.target_player_id === localPlayer) {
        setPartialTranscript("");
        setTranscriptionStatus("Switch received — starting your replacement response…");
        setCaptureCycle((current) => current + 1);
      }
    };
    const onSwitchRejected = (payload) => {
      if (payload.match_id !== match.match_id) return;
      setSwitchesRemaining(payload.switches_remaining ?? { A: 0, B: 0 });
      setIsSwitching(false);
      setErrorMessage(payload.message ?? "Switch was rejected.");
    };
    const onPartial = (payload) => {
      if (payload.player_id === localPlayer) setPartialTranscript(payload.text ?? "");
    };
    const onEnd = (payload) => {
      if (payload.match_id !== match.match_id) return;
      setRound((current) => current ? { ...current, ended: true } : current);
      setConnectionState("ended");
    };
    const onResultsReady = (payload) => {
      if (payload.match_id !== match.match_id) return;
      setResults(payload.results ?? null);
      setConnectionState("results");
    };
    const onMatchError = (payload) => {
      if (payload.code !== "JUDGING_UNAVAILABLE") return;
      setConnectionState("ended");
      setErrorMessage(payload.message);
    };
    const onDisconnect = () => setErrorMessage("The match server disconnected. Leave and find a new match.");

    socket.on("round:prepare", onPrepare);
    socket.on("round:start", onStart);
    socket.on("round:end", onEnd);
    socket.on("results:ready", onResultsReady);
    socket.on("match:error", onMatchError);
    socket.on("turn:changed", onTurnChanged);
    socket.on("transcript:event", onTranscriptEvent);
    socket.on("speech:partial", onPartial);
    socket.on("switch:triggered", onSwitchTriggered);
    socket.on("switch:rejected", onSwitchRejected);
    socket.on("disconnect", onDisconnect);
    return () => {
      socket.off("round:prepare", onPrepare);
      socket.off("round:start", onStart);
      socket.off("round:end", onEnd);
      socket.off("results:ready", onResultsReady);
      socket.off("match:error", onMatchError);
      socket.off("turn:changed", onTurnChanged);
      socket.off("transcript:event", onTranscriptEvent);
      socket.off("speech:partial", onPartial);
      socket.off("switch:triggered", onSwitchTriggered);
      socket.off("switch:rejected", onSwitchRejected);
      captureRef.current?.stop();
      captureRef.current = null;
      socket.off("disconnect", onDisconnect);
      detachMedia();
    };
  }, [localPlayer, match.match_id, socket]);

  useEffect(() => {
    if (connectionState !== "active" || round?.active_player_id !== localPlayer || captureRef.current) return undefined;
    let cancelled = false;
    setTranscriptionStatus("Your turn — connecting live transcript…");
    startPcm16Capture({ socket, playerId: localPlayer, matchId: match.match_id, guestId, onError: setErrorMessage })
      .then((capture) => {
        if (cancelled) { capture.stop(); return; }
        captureRef.current = capture;
        setTranscriptionStatus("Your microphone is sending live transcript audio.");
      })
      .catch((captureError) => { if (!cancelled) setErrorMessage(captureError.message); });
    return () => {
      cancelled = true;
      captureRef.current?.stop();
      captureRef.current = null;
    };
  }, [captureCycle, connectionState, guestId, localPlayer, match.match_id, round?.active_player_id, socket]);

  useEffect(() => {
    if (connectionState !== "countdown" || countdown === null || countdown <= 0) return undefined;
    const timer = window.setTimeout(() => setCountdown((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearTimeout(timer);
  }, [connectionState, countdown]);

  useEffect(() => {
    if (connectionState !== "active" || !round?.started_at) return undefined;
    const updateTimer = () => {
      setSecondsLeft(Math.max(0, Math.ceil((Date.parse(round.started_at) + round.duration_ms - Date.now()) / 1000)));
    };
    updateTimer();
    const timer = window.setInterval(updateTimer, 250);
    return () => window.clearInterval(timer);
  }, [connectionState, round]);

  const connectMedia = async () => {
    if (!socket.connected) {
      setErrorMessage("The matchmaking connection is no longer available. Leave and find a new match.");
      return;
    }

    setConnectionState("connecting");
    setErrorMessage("");
    try {
      const credentials = await requestCredentials(socket, match.match_id);
      const room = new Room();
      roomRef.current = room;

      room.on(RoomEvent.LocalTrackPublished, (publication) => {
        if (publication.source === Track.Source.Camera) {
          attachTrack(publication.track, localVideoRef.current);
          setHasLocalVideo(true);
        }
      });
      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Video) {
          attachTrack(track, remoteVideoRef.current);
          setHasRemoteVideo(true);
        }
        if (track.kind === Track.Kind.Audio) {
          attachTrack(track, remoteAudioRef.current);
        }
      });
      room.on(RoomEvent.TrackUnsubscribed, (track) => {
        if (track.kind === Track.Kind.Video) setHasRemoteVideo(false);
      });
      room.on(RoomEvent.Disconnected, () => {
        if (roomRef.current === room) setErrorMessage("Media connection closed. Leave and find a new match.");
      });

      await room.connect(credentials.url, credentials.token);
      await room.localParticipant.enableCameraAndMicrophone();
      const cameraPublication = room.localParticipant.getTrackPublication(Track.Source.Camera);
      attachTrack(cameraPublication?.track, localVideoRef.current);
      setHasLocalVideo(Boolean(cameraPublication?.track));
      setDevices({ camera: true, microphone: true });

      setConnectionState("waiting");
      const ready = await new Promise((resolve) => {
        socket.emit("player:ready", { match_id: match.match_id, guest_id: guestId }, resolve);
      });
      if (!ready?.ok) throw new Error("The match server could not mark you ready.");
    } catch (error) {
      detachMedia();
      setHasLocalVideo(false);
      setHasRemoteVideo(false);
      setDevices({ camera: false, microphone: false });
      setConnectionState("setup");
      setErrorMessage(error instanceof Error ? error.message : "Could not connect your media.");
    }
  };

  const toggleDevice = async (device) => {
    const participant = roomRef.current?.localParticipant;
    if (!participant) return;
    const enabled = !devices[device];
    try {
      if (device === "camera") await participant.setCameraEnabled(enabled);
      else await participant.setMicrophoneEnabled(enabled);
      setDevices((current) => ({ ...current, [device]: enabled }));
      if (device === "camera") setHasLocalVideo(enabled);
    } catch {
      setErrorMessage(`Could not ${enabled ? "enable" : "disable"} your ${device}.`);
    }
  };

  const leaveRoom = () => {
    detachMedia();
    onLeave();
  };

  const pressSwitch = () => {
    if (isSwitching || connectionState !== "active" || round?.active_player_id === localPlayer) return;
    setIsSwitching(true);
    socket.emit("switch:press", {
      match_id: match.match_id,
      guest_id: guestId,
      request_id: crypto.randomUUID(),
    }, (response) => {
      if (response?.ok) return;
      setIsSwitching(false);
      setErrorMessage(response?.code ? `Switch unavailable: ${response.code}` : "Switch was rejected.");
    });
  };

  const timerLabel = `${Math.floor(secondsLeft / 60)}:${String(secondsLeft % 60).padStart(2, "0")}`;
  const resultFor = (player) => player === "A" ? results?.player_a : results?.player_b;

  return (
    <main className="media-page">
      <header className="guest-banner">
        <span className="guest-banner__spark">✦</span>
        <span>{connectionState === "results" ? "Round complete · final arcade results." : isInRound ? "Round 1 · Live media connected." : "Media check · your camera and microphone stay in your control."}</span>
        <button className="guest-banner__claim" type="button" onClick={leaveRoom}>LEAVE</button>
      </header>
      <section className={`media-room ${isInRound ? "media-room--game" : ""}`} aria-label="Camera and microphone setup">
        <button className="round-icon round-icon--left" type="button" onClick={leaveRoom} aria-label="Leave media setup">×</button>
        <div className={isInRound || connectionState === "results" ? "game-stage" : "media-stage"}>
          {connectionState === "results" && results ? <section className="results-screen" aria-live="polite">
            <p className="stt-test-label">FINAL ARCADE RESULTS</p>
            <h1>{results.winner === "TIE" ? "TIE GAME" : `PLAYER ${results.winner} WINS`}</h1>
            <p className="results-screen__subtitle">GEMINI JUDGED THE FINAL TRANSCRIPT</p>
            <div className="results-grid">{["A", "B"].map((player) => {
              const playerResult = resultFor(player);
              return <article key={player} className={`results-player ${results.winner === player ? "results-player--winner" : ""}`}>
                <p>PLAYER {player}{player === localPlayer ? " · YOU" : ""}</p><b>{playerResult.total_points.toLocaleString()}</b>
                <div className="results-categories">{Object.entries(playerResult.category_points).map(([category, points]) => <span key={category}>{category} <strong>{points}</strong></span>)}</div>
                <p><strong>BEST MOMENT</strong>{playerResult.highlight}</p><p><strong>TRY NEXT</strong>{playerResult.improvement}</p>
              </article>;
            })}</div>
            {results.highlight_events.length > 0 && <div className="results-highlights"><strong>HIGHLIGHT REEL</strong>{results.highlight_events.map((event) => <span key={`${event.player_id}-${event.label}`}>PLAYER {event.player_id} · {event.label} +{event.points}</span>)}</div>}
          </section> : <>
          <div className={`media-heading ${isInRound ? "media-heading--game" : ""}`}>
            <p>{isInRound ? "LIVE SCENE · ROUND 1" : "ROUND ONE · MEDIA CHECK"}</p>
            {!isInRound && <h1>GET READY<br /><span>TO IMPROVISE.</span></h1>}
            {connectionState === "active" && <div className="round-timer"><span>TIME LEFT</span><b>{timerLabel}</b></div>}
          </div>

          {scenario && isInRound && (
            <section className="scenario-card" aria-label="Your improv scenario" aria-live="polite">
              <div className="scenario-card__meta"><span>GEMINI SCENE DROP</span><b>{scenario.tone}</b></div>
              <p className="scenario-card__prompt">{scenario.scenario}</p>
              <div className="scenario-card__role"><span>YOUR ROLE · PLAYER {localPlayer}</span><strong>{ownRole}</strong></div>
            </section>
          )}

          <div className={`video-grid ${isInRound ? "game-video-grid" : ""}`}>
            <article className={`video-tile video-tile--local ${round?.active_player_id === localPlayer ? "video-tile--active" : ""}`}>
              <video ref={localVideoRef} autoPlay muted playsInline className={hasLocalVideo ? "" : "video-tile__hidden"} />
              {!hasLocalVideo && <div className="video-placeholder"><b>YOU</b><span>{connectionState === "connecting" ? "CONNECTING CAMERA…" : "CAMERA PREVIEW"}</span></div>}
              <div className="video-tile__label"><span>YOU · PLAYER {localPlayer}</span><b>{devices.microphone ? "● MIC ON" : "○ MIC OFF"}</b></div>
            </article>
            <article className={`video-tile video-tile--remote ${round?.active_player_id === opponentPlayer ? "video-tile--active" : ""}`}>
              <video ref={remoteVideoRef} autoPlay playsInline className={hasRemoteVideo ? "" : "video-tile__hidden"} />
              {!hasRemoteVideo && <div className="video-placeholder"><b>{opponentName}</b><span>{connectionState === "waiting" ? "WAITING FOR OPPONENT MEDIA" : "LIVEKIT VIDEO CONNECTING"}</span></div>}
              <div className="video-tile__label"><span>{opponentName} · PLAYER {opponentPlayer}</span><b className="video-tile__waiting">{hasRemoteVideo ? "● CONNECTED" : "⌁ CONNECTING"}</b></div>
            </article>
            {connectionState === "countdown" && <div className="countdown-overlay" aria-live="assertive"><span>ROUND 1</span><b>{countdown || "GO!"}</b><small>THE SCENE STARTS NOW</small></div>}
          </div>
          <audio ref={remoteAudioRef} autoPlay />

          {isInRound && <section className="round-log" aria-label="Live scene transcript">
            <header><span>LIVE SCENE TRANSCRIPT</span><b>{round?.active_player_id === localPlayer ? "YOUR TURN" : `PLAYER ${round?.active_player_id ?? "?"} SPEAKING`}</b></header>
            <div className="round-log__entries">
              {transcript.length === 0 && !partialTranscript && <p className="round-log__entry round-log__entry--round">LISTENING FOR THE FIRST LINE…</p>}
              {transcript.map((line) => line.type === "switch" ? <p key={line.id} className="round-log__entry round-log__entry--switch">↯ PLAYER {line.from_player_id} SWITCHED PLAYER {line.target_player_id}</p> : <p key={line.id} className={line.accepted ? "round-log__entry" : "round-log__entry round-log__entry--interrupted"}><strong>PLAYER {line.player_id}:</strong> {line.text}</p>)}
              {partialTranscript && <p className="round-log__entry round-log__entry--active"><strong>PLAYER {localPlayer}:</strong> {partialTranscript}</p>}
            </div>
          </section>}

          {connectionState === "setup" && <div className="media-setup-actions"><button className="match-button media-permission-button" type="button" onClick={connectMedia}><span className="match-button__people">◉</span><span><strong>ENABLE CAMERA + MIC</strong><small>JOIN SECURE MEDIA ROOM</small></span></button></div>}
          {connectionState === "connecting" && <p className="media-connection" role="status"><i />CONNECTING SECURE MEDIA…</p>}
          {["waiting", "countdown", "active", "ended"].includes(connectionState) && <div className="media-controls" aria-label="Media controls"><button type="button" className={devices.microphone ? "media-control media-control--active" : "media-control"} onClick={() => toggleDevice("microphone")}>{devices.microphone ? "◉" : "○"}<span>{devices.microphone ? "MUTE" : "UNMUTE"}</span></button><button type="button" className={devices.camera ? "media-control media-control--active" : "media-control"} onClick={() => toggleDevice("camera")}>{devices.camera ? "◉" : "○"}<span>{devices.camera ? "CAMERA ON" : "CAMERA OFF"}</span></button>{connectionState === "active" && <button type="button" className="switch-button switch-button--live" disabled={isSwitching || round?.active_player_id === localPlayer || !switchesRemaining[localPlayer]} onClick={pressSwitch}>↯ SWITCH<small>{switchesRemaining[localPlayer]} LEFT</small></button>}</div>}
          {errorMessage && <p className="media-error" role="alert">{errorMessage}</p>}
          <p className="media-connection" role="status"><i />{connectionMessage(connectionState)}</p>
          {connectionState === "active" && <p className="media-connection"><i />{transcriptionStatus}</p>}
          {connectionState === "ended" && !errorMessage && <p className="media-connection"><i />GEMINI IS JUDGING THE FINAL TRANSCRIPT…</p>}
          </>}
        </div>
      </section>
    </main>
  );
}
