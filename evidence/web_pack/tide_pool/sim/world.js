// The tide pool's rules: whole numbers only, so every browser gives the same answer.
export function makeWorld(seed) {
  return { seed, tick: 0, tide: 40 };
}

const NO_TIDE = typeof process !== "undefined" && process.env.TIDE_NO_TIDE;

export function step(w) {
  if (NO_TIDE) return { ...w, tick: w.tick + 1 };
  const tick = w.tick + 1;
  const phase = tick % 200;
  const tide = 40 + (phase < 100 ? phase : 200 - phase) / 4 | 0;
  return { ...w, tick, tide };
}
