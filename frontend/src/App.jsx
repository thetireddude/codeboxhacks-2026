import { useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";

import { HomePage } from "./pages/HomePage.jsx";
import { GamePreviewPage } from "./pages/GamePreviewPage.jsx";
import { LeaderboardPage } from "./pages/LeaderboardPage.jsx";
import { SttTestPage } from "./pages/SttTestPage.jsx";
import { getSfxVolume, playButtonSfx, setSfxVolume, startBackgroundMusic } from "./services/arcadeSfx.js";

export default function App() {
  const [sfxVolume, setSfxVolumeState] = useState(getSfxVolume);
  useEffect(() => {
    const onPointerDown = (event) => {
      startBackgroundMusic();
      if (event.target.closest("button:not(:disabled)")) playButtonSfx();
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, []);

  const updateSfxVolume = (event) => {
    const nextVolume = Number(event.target.value);
    setSfxVolume(nextVolume);
    setSfxVolumeState(nextVolume);
  };

  return (
    <>
      <Routes>
        <Route path="/dev/game-preview" element={<GamePreviewPage />} />
        <Route path="/stt-test" element={<SttTestPage />} />
        <Route path="/leaderboard" element={<LeaderboardPage />} />
        <Route path="*" element={<HomePage />} />
      </Routes>
      <label className="sfx-volume-control">
        <span className="sfx-volume-control__icon" aria-hidden="true">{sfxVolume === 0 ? "×" : "◖"}</span>
        <span className="sfx-volume-control__label">VOLUME</span>
        <input aria-label="Sound effects volume" type="range" min="0" max="1" step="0.05" value={sfxVolume} onChange={updateSfxVolume} />
        <b aria-live="polite">{Math.round(sfxVolume * 100)}%</b>
      </label>
    </>
  );
}
