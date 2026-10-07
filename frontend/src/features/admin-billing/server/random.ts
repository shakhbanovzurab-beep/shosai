/** A seeded random generator (mulberry32), so the demo data is the same on every start. */
export function createRandom(seed: number) {
  let a = seed;
  const next = () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4_294_967_296;
  };
  return {
    next,
    /** True with probability `odds`. */
    chance: (odds: number) => next() < odds,
    pick: <T>(items: readonly T[]) => items[Math.floor(next() * items.length)],
    /** An integer in [min, max]. */
    between: (min: number, max: number) => min + Math.floor(next() * (max - min + 1)),
    /** Picks by cumulative odds: weighted([[0.7, "a"], [0.9, "b"]], "c") is "a" 70 %, "b" 20 %, "c" 10 %. */
    weighted<T>(options: readonly (readonly [number, T])[], fallback: T): T {
      const roll = next();
      return options.find(([threshold]) => roll < threshold)?.[1] ?? fallback;
    },
  };
}

export type Random = ReturnType<typeof createRandom>;
