const transcript = [
  { id: "preview-1", player: "A", text: "The lost-and-found drawer is humming again." },
  { id: "preview-switch", switch: true, from: "A", target: "B" },
  { id: "preview-2", player: "B", text: "Good. It means somebody finally claimed their mystery sock." },
];

/** A static, local-only representation of the live game HUD for visual QA. */
export function GamePreviewPage() {
  return <main className="media-page game-preview-page">
    <header className="guest-banner"><span className="guest-banner__spark">✦</span>DEV PREVIEW · NO MATCHMAKING OR MEDIA CONNECTION</header>
    <section className="media-room media-room--game" aria-label="Gameplay UI preview">
      <button className="round-icon round-icon--left" type="button" aria-label="Preview settings">☼</button>
      <div className="game-stage">
        <div className="media-heading media-heading--game">
          <p>LIVE SCENE · ROUND 1</p>
          <div className="round-timer"><span>TIME LEFT</span><b>0:42</b></div>
        </div>

        <section className="scenario-card scenario-card--preview" aria-label="Preview improv scenario">
          <div className="scenario-card__meta"><span>GEMINI SCENE DROP</span><b>AWKWARD</b></div>
          <p className="scenario-card__prompt">Two strangers discover they are both waiting for the same apartment viewing.</p>
          <div className="scenario-card__role"><span>YOUR ROLE · PLAYER A</span><strong>The overly prepared prospective tenant</strong></div>
        </section>

        <div className="video-grid game-video-grid">
          <article className="video-tile video-tile--local video-tile--active">
            <div className="video-placeholder"><b>YOU</b><span>CAMERA PREVIEW</span></div>
            <div className="video-tile__label"><span>YOU · PLAYER A</span><b>● MIC ON</b></div>
            <span className="switch-count">SWITCHES <b>3</b></span>
          </article>
          <article className="video-tile video-tile--remote">
            <div className="video-placeholder"><b>RILEY</b><span>OPPONENT CAMERA</span></div>
            <div className="video-tile__label"><span>RILEY · PLAYER B</span><b className="video-tile__waiting">● CONNECTED</b></div>
          </article>
        </div>

        <section className="round-log" aria-label="Preview scene transcript">
          <header><span>LIVE SCENE TRANSCRIPT</span><b>YOUR TURN</b></header>
          <div className="round-log__entries">
            {transcript.map((line) => line.switch
              ? <p key={line.id} className="round-log__entry round-log__entry--switch">↯ PLAYER {line.from} SWITCHED PLAYER {line.target}</p>
              : <p key={line.id} className="round-log__entry"><strong>PLAYER {line.player}:</strong> {line.text}</p>)}
            <p className="round-log__entry round-log__entry--active"><strong>PLAYER A:</strong> I also brought a measuring tape…</p>
          </div>
        </section>

        <div className="media-controls" aria-label="Preview media controls">
          <button type="button" className="media-control media-control--active">◉<span>MIC ON</span></button>
          <button type="button" className="media-control media-control--active">◉<span>CAMERA ON</span></button>
          <button type="button" className="switch-button switch-button--live">↯ SWITCH<small>SPACE · 3 LEFT</small></button>
        </div>
        <p className="media-connection"><i />DEV PREVIEW · STATIC GAMEPLAY DISPLAY</p>
      </div>
    </section>
  </main>;
}
