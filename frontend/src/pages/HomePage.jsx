import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { io } from "socket.io-client";

import { appConfig } from "../services/config.js";
import { MediaRoom } from "./MediaRoom.jsx";

const messages = {
  claim: "Guest accounts will connect here in a later milestone.",
  match: "Matchmaking is the next screen in the frontend track.",
  leaderboard: "Leaderboards unlock after live matches are available.",
  modes: "More game modes are coming soon.",
  settings: "Display settings are coming soon.",
  profile: "You are playing as a guest.",
};

export function HomePage() {
  const navigate = useNavigate();
  const [notice, setNotice] = useState("");
  const [screen, setScreen] = useState("home");
  const [queueState, setQueueState] = useState("searching");
  const [match, setMatch] = useState(null);
  const [rulesOpen, setRulesOpen] = useState(false);
  const socketRef = useRef(null);
  const guestIdRef = useRef(window.localStorage.getItem("improv-faceoff:guest-id"));
  const queueRequestRef = useRef(false);
  const matchRef = useRef(null);
  const pixelSkyRef = useRef(null);

  const handleClick = (action) => setNotice(messages[action]);

  useEffect(() => () => socketRef.current?.disconnect(), []);

  useEffect(() => {
    const sky = pixelSkyRef.current;
    if (!sky) return undefined;
    const bodies = [];
    let frame;
    let lastTime;
    let pointer = null;
    const characters = [...sky.querySelectorAll(".pixel-character")];
    const startingPositions = [[.11, .33], [.27, .39], [.72, .34], [.84, .48], [.43, .15], [.58, .42], [.18, .17], [.36, .55], [.68, .18], [.9, .23], [.49, .6], [.62, .56]];
    const seedBodies = () => {
      const width = sky.clientWidth || window.innerWidth;
      const height = sky.clientHeight || window.innerHeight;
      characters.forEach((element, index) => {
        const [horizontal, vertical] = startingPositions[index];
        bodies[index] = {
          element,
          radius: 16,
          x: width * horizontal,
          y: height * vertical,
          vx: (index % 2 ? -1 : 1) * (28 + index * 5),
          vy: index % 3 === 0 ? -20 : 20,
          angle: index * 31,
          spin: (index % 2 ? -1 : 1) * (35 + index * 9),
        };
        element.style.left = "0";
        element.style.top = "0";
      });
    };
    const render = (body) => {
      body.element.style.transform = `translate3d(${Math.round(body.x - 8)}px, ${Math.round(body.y - 11)}px, 0) rotate(${Math.round(body.angle)}deg)`;
      body.element.classList.toggle("is-flailing", Math.hypot(body.vx, body.vy) > 105);
    };
    const reflect = (body, normalX, normalY) => {
      const speedTowardSurface = body.vx * normalX + body.vy * normalY;
      if (speedTowardSurface >= 0) return;
      body.vx -= speedTowardSurface * normalX * 1.82;
      body.vy -= speedTowardSurface * normalY * 1.82;
      body.spin += (normalX * body.vy - normalY * body.vx) * 0.18;
    };
    const tick = (time) => {
      const elapsed = Math.min((time - (lastTime || time)) / 1000, 0.034);
      lastTime = time;
      const width = sky.clientWidth;
      const height = sky.clientHeight;
      bodies.forEach((body) => {
        body.vx *= 0.993;
        body.vy *= 0.993;
        body.spin *= 0.992;
        if (pointer) {
          const pathX = pointer.x - pointer.previousX;
          const pathY = pointer.y - pointer.previousY;
          const pathLengthSquared = pathX * pathX + pathY * pathY;
          const pathProgress = pathLengthSquared
            ? Math.max(0, Math.min(1, ((body.x - pointer.previousX) * pathX + (body.y - pointer.previousY) * pathY) / pathLengthSquared))
            : 1;
          const hitX = pointer.previousX + pathX * pathProgress;
          const hitY = pointer.previousY + pathY * pathProgress;
          const dx = body.x - hitX;
          const dy = body.y - hitY;
          const distance = Math.hypot(dx, dy) || 1;
          const cursorSpeed = Math.hypot(pointer.vx, pointer.vy);
          if (distance < body.radius + 7 && cursorSpeed > 80) {
            const normalX = dx / distance;
            const normalY = dy / distance;
            const relativeNormalSpeed = (body.vx - pointer.vx) * normalX + (body.vy - pointer.vy) * normalY;
            if (relativeNormalSpeed < 0) {
              const restitution = 0.92;
              body.vx -= (1 + restitution) * relativeNormalSpeed * normalX;
              body.vy -= (1 + restitution) * relativeNormalSpeed * normalY;
              body.spin += (pointer.vx * normalY - pointer.vy * normalX) * 0.055;
            }
          }
        }
        body.x += body.vx * elapsed;
        body.y += body.vy * elapsed;
        body.angle += body.spin * elapsed;
        if (body.x < body.radius) { body.x = body.radius; reflect(body, 1, 0); }
        if (body.x > width - body.radius) { body.x = width - body.radius; reflect(body, -1, 0); }
        if (body.y < body.radius) { body.y = body.radius; reflect(body, 0, 1); }
        if (body.y > height - body.radius) { body.y = height - body.radius; reflect(body, 0, -1); }
      });
      for (let first = 0; first < bodies.length; first += 1) {
        for (let second = first + 1; second < bodies.length; second += 1) {
          const a = bodies[first];
          const b = bodies[second];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const distance = Math.hypot(dx, dy) || 1;
          const minimum = a.radius + b.radius;
          if (distance >= minimum) continue;
          const normalX = dx / distance;
          const normalY = dy / distance;
          const overlap = (minimum - distance) / 2;
          a.x -= normalX * overlap;
          a.y -= normalY * overlap;
          b.x += normalX * overlap;
          b.y += normalY * overlap;
          const relativeSpeed = (a.vx - b.vx) * normalX + (a.vy - b.vy) * normalY;
          if (relativeSpeed < 0) {
            const impulse = -(1.72 * relativeSpeed) / 2;
            a.vx += impulse * normalX;
            a.vy += impulse * normalY;
            b.vx -= impulse * normalX;
            b.vy -= impulse * normalY;
            a.spin -= impulse * 0.3;
            b.spin += impulse * 0.3;
          }
        }
      }
      bodies.forEach(render);
      if (pointer) {
        pointer.previousX = pointer.x;
        pointer.previousY = pointer.y;
      }
      frame = window.requestAnimationFrame(tick);
    };
    const movePointer = ({ clientX, clientY, movementX = 0, movementY = 0 }) => {
      const rect = sky.getBoundingClientRect();
      const x = clientX - rect.left;
      const y = clientY - rect.top;
      pointer = {
        x,
        y,
        previousX: pointer?.x ?? x - movementX,
        previousY: pointer?.y ?? y - movementY,
        vx: movementX * 30,
        vy: movementY * 30,
      };
    };
    const clearPointer = () => { pointer = null; };
    seedBodies();
    frame = window.requestAnimationFrame(tick);
    window.addEventListener("pointermove", movePointer);
    window.addEventListener("blur", clearPointer);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", movePointer);
      window.removeEventListener("blur", clearPointer);
    };
  }, []);

  const connectAndJoinQueue = () => {
    if (queueRequestRef.current) return;
    queueRequestRef.current = true;
    let socket = socketRef.current;
    if (!socket) {
      socket = io(appConfig.backendUrl, {
        autoConnect: false,
        // Flask-SocketIO's threaded development server is reachable through a
        // Cloudflare quick tunnel over polling. Do not require a WebSocket
        // upgrade, which would otherwise drop live transcript events.
        transports: ["polling"],
        reconnection: true,
        reconnectionDelay: 500,
        reconnectionDelayMax: 2000,
      });
      socketRef.current = socket;
      socket.on("match:found", (payload) => {
        matchRef.current = payload;
        setMatch(payload);
        setQueueState("found");
      });
      socket.on("match:error", (payload) => {
        if (payload?.match_id && matchRef.current?.match_id !== payload.match_id) return;
        setNotice(payload.message ?? "The queue could not complete your request.");
        setQueueState("error");
      });
      socket.on("match:cancelled", (payload) => {
        if (matchRef.current?.match_id === payload.match_id) matchRef.current = null;
        setMatch((current) => current?.match_id === payload.match_id ? null : current);
        setNotice(payload.message ?? "The pending match was cancelled.");
        setScreen("home");
      });
      socket.on("connect_error", () => {
        queueRequestRef.current = false;
        setNotice("Could not reach the matchmaking server. Please try again.");
        setQueueState("error");
      });
    }

    const join = () => {
      socket.emit("guest:create", guestIdRef.current ? { guest_id: guestIdRef.current } : {}, (created) => {
        if (!created?.ok) {
          queueRequestRef.current = false;
          setNotice(created?.error?.message ?? "Could not create a guest session.");
          setQueueState("error");
          return;
        }
        guestIdRef.current = created.guest.guest_id;
        window.localStorage.setItem("improv-faceoff:guest-id", guestIdRef.current);
        socket.emit("queue:join", { guest_id: guestIdRef.current }, (joined) => {
          queueRequestRef.current = false;
          if (!joined?.ok) {
            setNotice(joined?.error?.message ?? "Could not join the public queue.");
            setQueueState("error");
          }
        });
      });
    };

    if (socket.connected) join();
    else {
      socket.once("connect", join);
      socket.connect();
    }
  };

  const startSearch = () => {
    setNotice("");
    setMatch(null);
    setQueueState("searching");
    setScreen("matchmaking");
    connectAndJoinQueue();
  };

  const showServerRequeue = (response) => {
    setNotice("");
    // The server may have immediately paired us and already emitted
    // match:found before this acknowledgement. Do not wipe that newer match.
    if (response?.status !== "paired") {
      matchRef.current = null;
      setMatch(null);
      setQueueState("searching");
    } else {
      setQueueState("found");
    }
    setScreen("matchmaking");
  };

  const resetToHome = () => {
    setNotice("");
    matchRef.current = null;
    setMatch(null);
    setQueueState("searching");
    setScreen("home");
  };

  const returnHome = () => {
    const socket = socketRef.current;
    const guestId = guestIdRef.current;

    // Leaving an active media room still uses the connection lifecycle owned
    // by the game controller.  The explicit cancellation below is only for a
    // match that has been found but not entered.
    if (screen === "media") {
      socket?.disconnect();
      resetToHome();
      return;
    }

    if (!socket?.connected || !guestId) {
      resetToHome();
      return;
    }

    const payload = match && queueState === "found"
      ? { guest_id: guestId, match_id: match.match_id }
      : { guest_id: guestId };
    const event = match && queueState === "found" ? "match:cancel" : "queue:leave";
    setQueueState("leaving");

    let completed = false;
    const finish = () => {
      if (completed) return;
      completed = true;
      window.clearTimeout(fallback);
      resetToHome();
    };
    const fallback = window.setTimeout(() => {
      // A lost acknowledgement must not strand the player. Disconnecting also
      // releases a matched guest via the server's disconnect lifecycle.
      socket.disconnect();
      finish();
    }, 2000);
    socket.emit(event, payload, finish);
  };

  if (screen === "media") {
    return <MediaRoom match={match} guestId={guestIdRef.current} socket={socketRef.current} onLeave={returnHome} onRequeue={showServerRequeue} />;
  }

  if (screen === "matchmaking") {
    const isFound = queueState === "found";
    const isError = queueState === "error";
    return (
      <main className="home-page matchmaking-page">
        <header className="guest-banner">
          <span className="guest-banner__spark">✦</span>
          <span>You&apos;re playing as a Guest. Your match is anonymous.</span>
          <button className="guest-banner__claim" type="button" onClick={() => handleClick("claim")}>CLAIM</button>
        </header>
        <section className="neon-room matchmaking-room" aria-label="Matchmaking">
          <button className="round-icon round-icon--left" type="button" onClick={returnHome} aria-label="Cancel matchmaking">×</button>
          <button className="round-icon round-icon--right" type="button" onClick={() => handleClick("profile")} aria-label="Guest profile">M</button>
          <div className="queue-stage">
            <div className={`queue-radar ${isFound ? "queue-radar--found" : ""} ${isError ? "queue-radar--error" : ""}`} aria-hidden="true">
              <i className="queue-ring queue-ring--one" /><i className="queue-ring queue-ring--two" /><i className="queue-ring queue-ring--three" />
              <span className="queue-player queue-player--you">YOU</span>
              <span className="queue-player queue-player--opponent">?</span>
              <strong>{isFound ? "✓" : isError ? "!" : "⌁"}</strong>
            </div>
            {isError ? (
              <>
                <p className="queue-label queue-label--error">QUEUE CONNECTION INTERRUPTED</p>
                <h1>LET&apos;S<br /><span>TRY THAT<br />AGAIN.</span></h1>
                <p className="queue-copy">{notice || "The queue did not respond. No match was created and your place has been released."}</p>
                <div className="queue-actions"><button className="match-button" type="button" onClick={startSearch}>RETRY</button><button className="cancel-link" type="button" onClick={returnHome}>LOBBY</button></div>
              </>
            ) : isFound ? (
              <>
                <p className="queue-label queue-label--found">PUBLIC QUEUE · MATCH CONFIRMED</p>
                <h1>OPPONENT<br /><span>FOUND.</span></h1>
                <p className="queue-copy">{match?.opponent?.display_name ?? "Your opponent"} is ready to improvise. Your shared prompt is being prepared.</p>
                <div className="found-card"><span>YOU · PLAYER {match?.player_id ?? "?"}</span><b>VS</b><span>{match?.opponent?.display_name ?? "OPPONENT"}</span></div>
                <div className="queue-actions"><button className="match-button" type="button" onClick={() => setScreen("media")}>CONTINUE</button><button className="cancel-link" type="button" onClick={returnHome}>CANCEL</button></div>
              </>
            ) : (
              <>
                <p className="queue-label">PUBLIC QUEUE · LOOKING FOR A PLAYER</p>
                <h1>SEARCHING FOR<br /><span>AN IMPROV<br />PARTNER...</span></h1>
                <p className="queue-copy">You&apos;re in. We&apos;ll pair you with another player as soon as someone steps up to the stage.</p>
                <div className="queue-meter" aria-label="Searching"><i /><i /><i /><i /><i /></div>
                <div className="queue-actions"><button className="cancel-button" type="button" onClick={returnHome}>CANCEL</button></div>
              </>
            )}
            <p className="home-notice matchmaking-notice" role="status" aria-live="polite">{notice}</p>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="home-page">
      <header className="guest-banner">
        <span className="guest-banner__spark">✦</span>
        <button type="button" onClick={() => handleClick("claim")}>
          You&apos;re playing as a Guest. Click here to claim your rank with Google.
        </button>
        <button className="guest-banner__claim" type="button" onClick={() => handleClick("claim")}>CLAIM</button>
      </header>

      <section className="neon-room" aria-label="Improv Faceoff home">
        <button className="rules-button" type="button" onClick={() => setRulesOpen(true)}>RULES</button>
        <button className="round-icon round-icon--right" type="button" onClick={() => handleClick("profile")} aria-label="Guest profile">M</button>

        {rulesOpen && (
          <div className="rules-overlay" role="presentation" onClick={() => setRulesOpen(false)}>
            <section className="rules-card" role="dialog" aria-modal="true" aria-labelledby="rules-title" onClick={(event) => event.stopPropagation()}>
              <button className="rules-card__close" type="button" onClick={() => setRulesOpen(false)} aria-label="Close rules">×</button>
              <p>HOW TO PLAY</p>
              <h2 id="rules-title">ARENA RULES</h2>
              <ol>
                <li><b>TWO PLAYERS, ONE SCENE.</b> Receive a scenario and two roles.</li>
                <li><b>TAKE TURNS SPEAKING.</b> Only the active player&apos;s microphone is live.</li>
                <li><b>USE SWITCH WISELY.</b> Interrupt the current speaker and make them pivot into something wacky, original, and still scene-related.</li>
                <li><b>BUILD THE SCENE.</b> Say yes, add ideas, and keep the story moving.</li>
                <li><b>BUILD SPEAKING SKILL.</b> Scores track articulation, coherence, adaptability, collaboration, and response speed.</li>
                <li><b>QUEUE AGAIN.</b> Choose Next Match when the round ends.</li>
              </ol>
              <button className="rules-card__play" type="button" onClick={() => setRulesOpen(false)}>GOT IT</button>
              <small>CLICK OUTSIDE TO CLOSE</small>
            </section>
          </div>
        )}

        <div className="room-wall room-wall--left">
          <div className="wall-sign wall-sign--better">BETTER<br />PEOPLE<br />THROUGH<br />IMPROV</div>
          <div className="arcade-cabinet"><span>IMPROV</span><i /><b>☻ ☻</b></div>
          <div className="plant plant--left"><i /><i /><i /><i /></div>
          <div className="wall-graffiti">SAME<br />PEOPLE<br />DIFFERENT<br />STORIES</div>
        </div>
        <div className="pixel-village" aria-hidden="true">
          <span className="pixel-house pixel-house--left"><i className="pixel-roof" /><i className="pixel-chimney" /><i className="pixel-window pixel-window--one" /><i className="pixel-window pixel-window--two" /><i className="pixel-door" /></span>
          <span className="pixel-house pixel-house--center"><i className="pixel-roof" /><i className="pixel-chimney" /><i className="pixel-window pixel-window--one" /><i className="pixel-window pixel-window--two" /><i className="pixel-door" /></span>
          <span className="pixel-house pixel-house--right"><i className="pixel-roof" /><i className="pixel-chimney" /><i className="pixel-window pixel-window--one" /><i className="pixel-window pixel-window--two" /><i className="pixel-door" /></span>
          <span className="pixel-theater"><i className="pixel-theater__sign">IMPROV</i><b className="pixel-theater__curtain" /><b className="pixel-performer pixel-performer--one" /><b className="pixel-performer pixel-performer--two" /></span>
          <span className="pixel-tree pixel-tree--left" /><span className="pixel-tree pixel-tree--right" />
        </div>
        <div className="pixel-sky" aria-hidden="true">
          <span className="pixel-moon" /><span className="pixel-cloud pixel-cloud--one" /><span className="pixel-cloud pixel-cloud--two" /><span className="pixel-spark pixel-spark--one" /><span className="pixel-spark pixel-spark--two" /><span className="pixel-spark pixel-spark--three" />
        </div>
        <div className="pixel-float-layer" ref={pixelSkyRef} aria-hidden="true">
          <span className="pixel-character pixel-character--rocket"><i /></span><span className="pixel-character pixel-character--astronaut"><i /></span><span className="pixel-character pixel-character--mime"><i /></span><span className="pixel-character pixel-character--firefighter"><i /></span><span className="pixel-character pixel-character--pirate"><i /></span><span className="pixel-character pixel-character--ninja"><i /></span><span className="pixel-character pixel-character--alien"><i /></span><span className="pixel-character pixel-character--goblin"><i /></span><span className="pixel-character pixel-character--dog"><i /></span><span className="pixel-character pixel-character--turtle"><i /></span><span className="pixel-character pixel-character--camel"><i /></span><span className="pixel-character pixel-character--wizard"><i /></span>
        </div>

        <section className="home-hero">
          <div className="mask-pair" aria-hidden="true">
            <span className="mask-face mask-face--blue"><i className="mask-eye mask-eye--left" /><i className="mask-eye mask-eye--right" /><b className="mask-mouth" /></span>
            <span className="mask-face mask-face--pink"><i className="mask-eye mask-eye--left" /><i className="mask-eye mask-eye--right" /><b className="mask-mouth" /></span>
          </div>
          <h1>IMPROV<br /><span>FACEOFF</span></h1>
          <p className="home-hero__tagline">RANDOM SCENARIOS. REAL PEOPLE. NO SCRIPT.</p>
          <div className="hero-divider"><i /></div>
          <p className="home-hero__motto">THINK FAST. SAY YES. IMPROVISE.</p>
          <button className="match-button" type="button" onClick={startSearch}>FIND MATCH</button>
          <div className="home-actions">
            <button className="home-action home-action--gold" type="button" onClick={() => navigate("/leaderboard")}>RANKS</button>
            <button className="home-action home-action--blue" type="button" onClick={() => handleClick("modes")}>MODES</button>
          </div>
          <p className="home-notice" role="status" aria-live="polite">{notice}</p>
        </section>

        <div className="room-wall room-wall--right">
          <div className="city-window"><span /><span /><span /><span /><span /><span /></div>
          <div className="wall-sign wall-sign--good">GOOD<br />CONVERSATIONS<br />BRIGHTER<br />TOMORROW <b>⌁</b></div>
          <div className="backpack" />
          <div className="sticky-note">SAY<br />YES<br />AND...</div>
          <div className="plant plant--right"><i /><i /><i /><i /></div>
        </div>
      </section>
    </main>
  );
}
