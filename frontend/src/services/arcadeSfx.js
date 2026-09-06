let audioContext;
let musicTimer;
let musicStep = 0;
const VOLUME_STORAGE_KEY = "improv-faceoff-sfx-volume";
let volume = 0.85;

try {
  const savedVolume = Number(window.localStorage.getItem(VOLUME_STORAGE_KEY));
  if (Number.isFinite(savedVolume)) volume = Math.min(1, Math.max(0, savedVolume));
} catch {
  // Storage access can be unavailable in privacy-restricted browsers.
}

export function getSfxVolume() {
  return volume;
}

export function setSfxVolume(nextVolume) {
  volume = Math.min(1, Math.max(0, Number(nextVolume) || 0));
  try {
    window.localStorage.setItem(VOLUME_STORAGE_KEY, String(volume));
  } catch {
    // The current page still uses the selected volume for this session.
  }
}

function getAudioContext() {
  if (typeof window === "undefined" || !window.AudioContext) return null;
  audioContext ??= new window.AudioContext();
  if (audioContext.state === "suspended") void audioContext.resume();
  return audioContext;
}

function tone(frequency, duration, type = "square", volume = 0.035, delay = 0) {
  const context = getAudioContext();
  if (!context) return;
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  const start = context.currentTime + delay;
  oscillator.type = type;
  oscillator.frequency.setValueAtTime(frequency, start);
  gain.gain.setValueAtTime(volume * getSfxVolume(), start);
  gain.gain.exponentialRampToValueAtTime(0.001, start + duration);
  oscillator.connect(gain).connect(context.destination);
  oscillator.start(start);
  oscillator.stop(start + duration);
}

export function playButtonSfx() {
  tone(520, 0.055, "square", 0.045);
  tone(780, 0.07, "square", 0.032, 0.035);
}

export function playSwitchSfx() {
  tone(180, 0.16, "sawtooth", 0.16);
  tone(95, 0.24, "square", 0.13, 0.07);
}

export function playSpeedBonusSfx() {
  tone(880, 0.07, "square", 0.065);
  tone(1175, 0.09, "square", 0.06, 0.065);
  tone(1568, 0.13, "square", 0.05, 0.14);
}

export function playCountdownSfx() {
  tone(660, 0.07, "square", 0.055);
}

export function playTurnChangeSfx() {
  tone(440, 0.06, "square", 0.05);
  tone(660, 0.09, "square", 0.042, 0.06);
}

export function playRoundEndSfx() {
  tone(523, 0.12, "square", 0.06);
  tone(392, 0.13, "square", 0.052, 0.1);
  tone(262, 0.2, "sawtooth", 0.045, 0.2);
}

const MUSIC_MELODY = [523, 659, 784, 659, 587, 740, 880, 740, 523, 659, 784, 988, 880, 784, 659, 587];
const MUSIC_BASS = [131, 131, 147, 147, 165, 165, 147, 147];

function playMusicStep() {
  const step = musicStep % MUSIC_MELODY.length;
  tone(MUSIC_MELODY[step], 0.13, "square", 0.028);
  if (step % 2 === 0) tone(MUSIC_BASS[(step / 2) % MUSIC_BASS.length], 0.16, "triangle", 0.035);
  musicStep += 1;
}

export function startBackgroundMusic() {
  if (musicTimer || getSfxVolume() === 0) return;
  playMusicStep();
  musicTimer = window.setInterval(playMusicStep, 180);
}

export function stopBackgroundMusic() {
  if (!musicTimer) return;
  window.clearInterval(musicTimer);
  musicTimer = undefined;
  musicStep = 0;
}
