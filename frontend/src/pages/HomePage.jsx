import { useEffect, useRef, useState } from "react";
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
  const [notice, setNotice] = useState("");
  const [screen, setScreen] = useState("home");
  const [queueState, setQueueState] = useState("searching");
  const [match, setMatch] = useState(null);
  const socketRef = useRef(null);
  const guestIdRef = useRef(window.localStorage.getItem("improv-faceoff:guest-id"));

  const handleClick = (action) => setNotice(messages[action]);

  useEffect(() => () => socketRef.current?.disconnect(), []);

  const connectAndJoinQueue = () => {
    let socket = socketRef.current;
    if (!socket) {
      socket = io(appConfig.backendUrl, { autoConnect: false });
      socketRef.current = socket;
      socket.on("match:found", (payload) => {
        setMatch(payload);
        setQueueState("found");
      });
      socket.on("match:error", (payload) => {
        setNotice(payload.message ?? "The queue could not complete your request.");
        setQueueState("error");
      });
      socket.on("connect_error", () => {
        setNotice("Could not reach the matchmaking server. Please try again.");
        setQueueState("error");
      });
    }

    const join = () => {
      socket.emit("guest:create", guestIdRef.current ? { guest_id: guestIdRef.current } : {}, (created) => {
        if (!created?.ok) {
          setNotice(created?.error?.message ?? "Could not create a guest session.");
          setQueueState("error");
          return;
        }
        guestIdRef.current = created.guest.guest_id;
        window.localStorage.setItem("improv-faceoff:guest-id", guestIdRef.current);
        socket.emit("queue:join", { guest_id: guestIdRef.current }, (joined) => {
          if (!joined?.ok) {
            setNotice("Could not join the public queue.");
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

  const returnHome = () => {
    if (socketRef.current?.connected && guestIdRef.current) {
      socketRef.current.emit("queue:leave", { guest_id: guestIdRef.current });
    }
    socketRef.current?.disconnect();
    setNotice("");
    setMatch(null);
    setScreen("home");
  };

  if (screen === "media") {
    return <MediaRoom onLeave={returnHome} />;
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
                <div className="queue-actions"><button className="match-button" type="button" onClick={startSearch}><span className="match-button__people">↻</span><span><strong>RETRY SEARCH</strong><small>REJOIN THE PUBLIC QUEUE</small></span></button><button className="cancel-link" type="button" onClick={returnHome}>BACK TO LOBBY</button></div>
              </>
            ) : isFound ? (
              <>
                <p className="queue-label queue-label--found">PUBLIC QUEUE · MATCH CONFIRMED</p>
                <h1>OPPONENT<br /><span>FOUND.</span></h1>
                <p className="queue-copy">{match?.opponent?.display_name ?? "Your opponent"} is ready to improvise. Your shared prompt is being prepared.</p>
                <div className="found-card"><span>YOU · PLAYER {match?.player_id ?? "?"}</span><b>VS</b><span>{match?.opponent?.display_name ?? "OPPONENT"}</span></div>
                <div className="queue-actions"><button className="match-button" type="button" onClick={() => setScreen("media")}><span className="match-button__people">♟♟♟</span><span><strong>CONTINUE</strong><small>CHECK CAMERA + MIC</small></span></button><button className="cancel-link" type="button" onClick={returnHome}>CANCEL MATCH</button></div>
              </>
            ) : (
              <>
                <p className="queue-label">PUBLIC QUEUE · LOOKING FOR A PLAYER</p>
                <h1>SEARCHING FOR<br /><span>AN IMPROV<br />PARTNER...</span></h1>
                <p className="queue-copy">You&apos;re in. We&apos;ll pair you with another player as soon as someone steps up to the stage.</p>
                <div className="queue-meter" aria-label="Searching"><i /><i /><i /><i /><i /></div>
                <div className="queue-actions"><button className="cancel-button" type="button" onClick={returnHome}>× CANCEL SEARCH</button><button className="queue-help" type="button" onClick={() => setQueueState("error")}>SIMULATE CONNECTION ISSUE</button></div>
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
        <button className="round-icon round-icon--left" type="button" onClick={() => handleClick("settings")} aria-label="Display settings">☼</button>
        <button className="round-icon round-icon--right" type="button" onClick={() => handleClick("profile")} aria-label="Guest profile">M</button>

        <div className="room-wall room-wall--left">
          <div className="wall-sign wall-sign--better">BETTER<br />PEOPLE<br />THROUGH<br />IMPROV</div>
          <div className="arcade-cabinet"><span>IMPROV</span><i /><b>☻ ☻</b></div>
          <div className="plant plant--left"><i /><i /><i /><i /></div>
          <div className="wall-graffiti">SAME<br />PEOPLE<br />DIFFERENT<br />STORIES</div>
        </div>

        <section className="home-hero">
          <div className="mask-pair" aria-hidden="true"><span className="mask-face mask-face--blue">● ●<i>⌣</i></span><span className="mask-face mask-face--pink">● ●<i>⌣</i></span></div>
          <h1>IMPROV<br /><span>FACEOFF</span></h1>
          <p className="home-hero__tagline">RANDOM SCENARIOS. REAL PEOPLE. NO SCRIPT.</p>
          <div className="hero-divider"><i /></div>
          <p className="home-hero__motto">THINK FAST. SAY YES. IMPROVISE.</p>
          <button className="match-button" type="button" onClick={startSearch}>
            <span className="match-button__people">♟♟♟</span>
            <span><strong>MULTIPLAYER</strong><small>FIND A MATCH</small></span>
          </button>
          <div className="home-actions">
            <button className="home-action home-action--gold" type="button" onClick={() => handleClick("leaderboard")}><span>♜</span> VIEW LEADERBOARD <b>→</b></button>
            <button className="home-action home-action--blue" type="button" onClick={() => handleClick("modes")}><span>⌁</span> OTHER GAME MODES <b>→</b></button>
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
