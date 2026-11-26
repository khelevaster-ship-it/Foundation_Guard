// The herd's rules: whole numbers and a seeded generator, so every browser agrees.
export function rng(seed) {
  let s = seed >>> 0;
  return () => (s = (Math.imul(s, 1664525) + 1013904223) >>> 0);
}

export function makeHerd(seed, n) {
  const next = rng(seed);
  return Array.from({ length: n }, () => ({ x: next() % 320, y: next() % 200 }));
}

export function step(herd) {
  return herd.map(s => ({ x: (s.x + 1) % 320, y: s.y }));
}
