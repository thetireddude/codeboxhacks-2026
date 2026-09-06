import { useEffect, useState } from "react";
import PropTypes from "prop-types";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { fallbackProgress, fallbackProgressSummary } from "../fixtures/fallbackProgress.js";
import { appConfig } from "../services/config.js";

const skillLabel = (name) => name.replace(/_/g, " ").toUpperCase();
const apiBase = appConfig.backendUrl.replace(/\/$/, "");
const skillShape = PropTypes.shape({
  points: PropTypes.number.isRequired,
  rating: PropTypes.string.isRequired,
});
const matchShape = PropTypes.shape({
  match_number: PropTypes.number.isRequired,
  match_id: PropTypes.string.isRequired,
  guest_id: PropTypes.string.isRequired,
  scoring_version: PropTypes.string.isRequired,
  total_score: PropTypes.number.isRequired,
  skills: PropTypes.objectOf(skillShape).isRequired,
  overview: PropTypes.string.isRequired,
  what_went_well: PropTypes.string.isRequired,
  what_to_improve: PropTypes.string.isRequired,
  rubric_log: PropTypes.object.isRequired,
  created_at: PropTypes.string.isRequired,
});

function FeedbackDetail({ match }) {
  if (!match) return null;
  return (
    <div className="progress-feedback-detail">
      <p className="progress-feedback-detail__id">MATCH #{match.match_number} · ID {match.match_id}</p>
      <p className="progress-feedback-detail__meta">GUEST · {match.guest_id} · {match.scoring_version} · {new Date(match.created_at).toLocaleString()}</p>
      <div className="progress-feedback-detail__score"><span>TOTAL SCORE</span><strong>{match.total_score.toLocaleString()}</strong></div>
      <dl className="progress-feedback-detail__skills">
        {Object.entries(match.skills ?? {}).map(([name, skill]) => <div key={name}><dt>{skillLabel(name)}</dt><dd>{skill.points} · {skill.rating}</dd></div>)}
      </dl>
      <div className="progress-feedback-detail__copy"><b>AI OVERVIEW</b><p>{match.overview}</p></div>
      <div className="progress-feedback-detail__copy"><b>WHAT WENT WELL</b><p>{match.what_went_well}</p></div>
      <div className="progress-feedback-detail__copy"><b>WHAT TO IMPROVE</b><p>{match.what_to_improve}</p></div>
      <div className="progress-feedback-detail__raw">
        <b>FULL RUBRIC LOG</b>
        <pre>{JSON.stringify(match.rubric_log, null, 2)}</pre>
      </div>
    </div>
  );
}

FeedbackDetail.propTypes = { match: matchShape };

function ProgressTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  return <aside className="progress-tooltip" role="status"><FeedbackDetail match={payload[0].payload} /></aside>;
}

ProgressTooltip.propTypes = {
  active: PropTypes.bool,
  payload: PropTypes.arrayOf(PropTypes.shape({ payload: matchShape })),
};

function PixelDot({ cx, cy, payload, onFocus }) {
  if (!Number.isFinite(cx) || !Number.isFinite(cy)) return null;
  return (
    <rect
      aria-label={`Match ${payload.match_number}, score ${payload.total_score}`}
      className="progress-dot"
      height="10"
      onFocus={() => onFocus(payload)}
      role="button"
      tabIndex="0"
      width="10"
      x={cx - 5}
      y={cy - 5}
    />
  );
}

PixelDot.propTypes = {
  cx: PropTypes.number,
  cy: PropTypes.number,
  payload: matchShape.isRequired,
  onFocus: PropTypes.func.isRequired,
};

function CoachPanel({ summary, sample }) {
  if (!summary?.tips?.length) return null;
  return (
    <section className="progress-coach" aria-labelledby="progress-coach-title">
      <p>{sample ? "SAMPLE AI COACH" : "AI COACH"}</p>
      <h3 id="progress-coach-title">YOUR NEXT LEVEL</h3>
      {summary.tips.map((tip) => <article key={`${tip.label}-${tip.text}`}><b>{tip.label}</b><span>{tip.text}</span></article>)}
    </section>
  );
}

CoachPanel.propTypes = {
  sample: PropTypes.bool.isRequired,
  summary: PropTypes.shape({
    tips: PropTypes.arrayOf(PropTypes.shape({
      label: PropTypes.string.isRequired,
      text: PropTypes.string.isRequired,
    })).isRequired,
  }),
};

export function ProgressModal({ isOpen, onClose }) {
  const [state, setState] = useState({ loading: false, error: "", matches: [], summary: null, sample: false });
  const [focusedMatch, setFocusedMatch] = useState(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!isOpen) return undefined;
    const controller = new AbortController();
    const guestId = window.localStorage.getItem("improv-faceoff:guest-id");
    const load = async () => {
      if (!guestId) {
        setState({ loading: false, error: "Play a match first to start a progress record.", matches: [], summary: null, sample: false });
        return;
      }
      setState({ loading: true, error: "", matches: [], summary: null, sample: false });
      setFocusedMatch(null);
      try {
        const response = await fetch(`${apiBase}/api/players/${encodeURIComponent(guestId)}/match-feedback?limit=100`, { signal: controller.signal });
        const payload = await response.json().catch(() => null);
        if (!response.ok || !payload || !Array.isArray(payload.matches)) throw new Error("Progress request failed");
        if (payload.matches.length === 0) {
          setState({ loading: false, error: "", matches: fallbackProgress, summary: fallbackProgressSummary, sample: true });
          return;
        }
        setState({ loading: false, error: "", matches: payload.matches, summary: payload.summary, sample: false });
      } catch (error) {
        if (error.name !== "AbortError") setState({ loading: false, error: "Your progress data is unavailable right now. Please try again.", matches: [], summary: null, sample: false });
      }
    };
    load();
    return () => controller.abort();
  }, [isOpen, reloadToken]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const closeOnEscape = (event) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [isOpen, onClose]);

  if (!isOpen) return null;
  return (
    <div className="progress-overlay" role="presentation" onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="progress-modal" role="dialog" aria-modal="true" aria-labelledby="progress-title">
        <button className="progress-modal__close" type="button" onClick={onClose} aria-label="Close progress">×</button>
        <header className="progress-modal__header">
          <p>{state.sample ? "SAMPLE PROGRESS" : "PLAYER PROGRESS"}</p>
          <h2 id="progress-title">LEVEL<br /><span>UP</span></h2>
          <small>{state.sample ? "LIVE FEEDBACK NOT YET AVAILABLE" : "MATCH SCORES + AI COACHING"}</small>
        </header>
        {state.loading && <p className="progress-status">LOADING MATCH FEEDBACK…</p>}
        {state.error && <div className="progress-status progress-status--error"><p>{state.error}</p><button type="button" onClick={() => setReloadToken((value) => value + 1)}>RETRY</button></div>}
        {!state.loading && !state.error && <>
          <section className="progress-chart-card" aria-label="Match scores over completed matches">
            <div className="progress-chart-card__heading"><span>MATCH SCORE HISTORY</span><b>{state.matches.length} MATCH{state.matches.length === 1 ? "" : "ES"}</b></div>
            <div className="progress-chart">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={state.matches} margin={{ top: 18, right: 20, bottom: 4, left: -20 }}>
                  <CartesianGrid stroke="#5a3977" strokeDasharray="4 4" shapeRendering="crispEdges" />
                  <XAxis dataKey="match_number" axisLine={{ stroke: "#80ddff" }} label={{ value: "MATCH #", position: "insideBottom", offset: -2, fill: "#c8b6dc", fontSize: 8 }} stroke="#c8b6dc" tick={{ fontSize: 9, fill: "#f9e9ff" }} />
                  <YAxis axisLine={{ stroke: "#80ddff" }} tick={{ fontSize: 9, fill: "#f9e9ff" }} width={52} />
                  <Tooltip content={<ProgressTooltip />} cursor={{ stroke: "#e1ff4f", strokeWidth: 2, shapeRendering: "crispEdges" }} />
                  <Line dataKey="total_score" dot={<PixelDot onFocus={setFocusedMatch} />} isAnimationActive={false} stroke="#e1ff4f" strokeWidth={3} type="stepAfter" />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="progress-chart-card__hint">HOVER A PIXEL FOR THE FULL MATCH FEEDBACK · TAB A PIXEL FOR A FOCUS VIEW</p>
          </section>
          {focusedMatch && <section className="progress-focus-detail" aria-live="polite"><FeedbackDetail match={focusedMatch} /></section>}
          <CoachPanel sample={state.sample} summary={state.summary} />
        </>}
      </section>
    </div>
  );
}

ProgressModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
};
