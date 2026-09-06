import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fallbackLeaderboard } from "../fixtures/fallbackLeaderboard.js";
import { appConfig } from "../services/config.js";

const apiUrl = `${appConfig.backendUrl.replace(/\/$/, "")}/api/leaderboard?limit=50`;

export function LeaderboardPage() {
  const [state, setState] = useState({ loading: true, entries: [], sample: false, error: "" });
  const guestId = window.localStorage.getItem("improv-faceoff:guest-id");
  const load = useCallback(async () => {
    setState((current) => ({ ...current, loading: true, error: "" }));
    try {
      const response = await fetch(apiUrl);
      const payload = await response.json().catch(() => null);
      if (!response.ok || !payload || !Array.isArray(payload.entries)) throw new Error("Leaderboard request failed");
      setState({ loading: false, entries: payload.entries, sample: false, error: "" });
    } catch {
      setState({ loading: false, entries: fallbackLeaderboard, sample: true, error: "Live scores are unavailable right now." });
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <main className="leaderboard-page">
      <header className="guest-banner"><Link to="/">← LOBBY</Link><span>HIGH SCORE ARCADE</span></header>
      <section className="leaderboard-card" aria-labelledby="leaderboard-title">
        <div className="leaderboard-card__bolts" aria-hidden="true"><i /><i /><i /><i /></div>
        <div className="leaderboard-marquee">
          <p className="leaderboard-kicker">{state.sample ? "SAMPLE LEADERBOARD" : "LIVE LEADERBOARD"}</p>
          <h1 id="leaderboard-title">HIGH<br /><span>SCORES</span></h1>
          <p className="leaderboard-marquee__sub">IMPROV FACEOFF HALL OF FAME</p>
        </div>
        {state.loading ? <p className="leaderboard-status">Loading scores…</p> : state.entries.length === 0 ? <p className="leaderboard-status">No completed matches yet. Set the first high score.</p> : (
          <ol className="leaderboard-list">
            {state.entries.map((entry) => <li key={entry.guest_id} className={entry.guest_id === guestId ? "leaderboard-entry leaderboard-entry--you" : "leaderboard-entry"}>
              <b className={`leaderboard-rank leaderboard-rank--${entry.rank}`}>#{entry.rank}</b>
              <span className="leaderboard-player">{entry.display_name}{entry.guest_id === guestId ? " (YOU)" : ""}</span>
              <strong>{entry.best_score.toLocaleString()}</strong><small>{entry.games_played} games</small>
            </li>)}
          </ol>
        )}
        {state.error && <div className="leaderboard-retry"><p>{state.error}</p><button type="button" onClick={load}>RETRY LIVE SCORES</button></div>}
      </section>
    </main>
  );
}
