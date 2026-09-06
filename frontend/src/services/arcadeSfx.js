let audioContext;
let musicGain;
let musicTimer;
const VOLUME_STORAGE_KEY = "improv-faceoff-sfx-volume";
let volume = 0.7;

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
  if (musicGain && audioContext) {
    musicGain.gain.setTargetAtTime(volume * 0.045, audioContext.currentTime, 0.02);
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
  tone(520, 0.055, "square", 0.025);
  tone(780, 0.07, "square", 0.018, 0.035);
}

export function playSwitchSfx() {
  tone(180, 0.16, "sawtooth", 0.045);
  tone(95, 0.24, "square", 0.035, 0.07);
}

function musicNote(context, frequency, startsAt, duration) {
  const oscillator = context.createOscillator();
  oscillator.type = "square";
  oscillator.frequency.setValueAtTime(frequency, startsAt);
  oscillator.connect(musicGain);
  oscillator.start(startsAt);
  oscillator.stop(startsAt + duration);
}

export function startBackgroundMusic() {
  const context = getAudioContext();
  if (!context || musicTimer) return;
  musicGain = context.createGain();
  musicGain.gain.setValueAtTime(volume * 0.045, context.currentTime);
  musicGain.connect(context.destination);
  const notes = [130.81, 164.81, 196, 164.81, 146.83, 174.61, 220, 174.61];
  const beatSeconds = 0.24;
  const playBar = () => {
    const startsAt = context.currentTime + 0.04;
    notes.forEach((note, index) => musicNote(context, note, startsAt + index * beatSeconds, 0.16));
  };
  playBar();
  musicTimer = window.setInterval(playBar, notes.length * beatSeconds * 1000);
}
