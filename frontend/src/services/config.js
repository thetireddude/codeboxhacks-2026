export const appConfig = Object.freeze({
  backendUrl: import.meta.env.VITE_BACKEND_URL ?? "http://localhost:5000",
  switchResponseMinMs: Number(import.meta.env.VITE_SWITCH_RESPONSE_MIN_MS ?? 150),
});
