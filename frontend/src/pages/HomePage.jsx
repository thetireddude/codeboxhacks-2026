import { useState } from "react";

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

  const handleClick = (action) => setNotice(messages[action]);

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
          <button className="match-button" type="button" onClick={() => handleClick("match")}>
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
