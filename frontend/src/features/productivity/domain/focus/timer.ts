/*
 * The focus timer as pure state: presets, the focus → break cycle, and the time left. The clock is
 * passed in, so the timer keeps the right time across reloads and background tabs.
 */

/** A rhythm. Its name and what it is good for are words, so the interface looks them up by `id`. */
export type FocusPreset = {
  id: "pomodoro" | "fifty" | "fifty-two" | "deep-work";
  /** Short label for the switcher, e.g. "25/5": the minutes of focus and of a break. */
  label: string;
  focusMin: number;
  breakMin: number;
  /** A longer break after every `longEvery` focus sessions; 0 for none. */
  longBreakMin: number;
  longEvery: number;
};

export const FOCUS_PRESETS: readonly FocusPreset[] = [
  {
    id: "pomodoro",
    label: "25/5",
    focusMin: 25,
    breakMin: 5,
    longBreakMin: 15,
    longEvery: 4,
  },
  {
    id: "fifty",
    label: "50/10",
    focusMin: 50,
    breakMin: 10,
    longBreakMin: 30,
    longEvery: 3,
  },
  {
    id: "fifty-two",
    label: "52/17",
    focusMin: 52,
    breakMin: 17,
    longBreakMin: 0,
    longEvery: 0,
  },
  {
    id: "deep-work",
    label: "90/20",
    focusMin: 90,
    breakMin: 20,
    longBreakMin: 0,
    longEvery: 0,
  },
];

export type FocusPhase = "focus" | "break" | "long_break";

export type FocusTimer = {
  presetId: FocusPreset["id"];
  phase: FocusPhase;
  /** Running: when the phase ends (epoch ms). */
  endsAt: number | null;
  /** Paused or not started: the time left in the phase, ms. */
  remainingMs: number;
  /** Focus sessions finished in the current cycle, for the long break. */
  cycleDone: number;
  /** Focus sessions finished on `day`. */
  doneToday: number;
  /** Local calendar day, "YYYY-MM-DD". */
  day: string;
};

const MINUTE = 60_000;

export const presetOf = (id: string) => FOCUS_PRESETS.find((p) => p.id === id) ?? FOCUS_PRESETS[0];

export function phaseMs(preset: FocusPreset, phase: FocusPhase) {
  if (phase === "focus") return preset.focusMin * MINUTE;
  return (phase === "long_break" ? preset.longBreakMin : preset.breakMin) * MINUTE;
}

export const dayKey = (now: number) => {
  const d = new Date(now);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export function initialTimer(presetId: FocusPreset["id"], now: number): FocusTimer {
  return {
    presetId,
    phase: "focus",
    endsAt: null,
    remainingMs: phaseMs(presetOf(presetId), "focus"),
    cycleDone: 0,
    doneToday: 0,
    day: dayKey(now),
  };
}

export const isRunning = (t: FocusTimer) => t.endsAt !== null;

export const remainingMs = (t: FocusTimer, now: number) =>
  t.endsAt === null ? t.remainingMs : Math.max(0, t.endsAt - now);

export const start = (t: FocusTimer, now: number): FocusTimer =>
  isRunning(t) ? t : { ...t, endsAt: now + t.remainingMs };

export const pause = (t: FocusTimer, now: number): FocusTimer =>
  isRunning(t) ? { ...t, endsAt: null, remainingMs: remainingMs(t, now) } : t;

/** Back to the start of the current phase, stopped. */
export const resetPhase = (t: FocusTimer): FocusTimer => ({
  ...t,
  endsAt: null,
  remainingMs: phaseMs(presetOf(t.presetId), t.phase),
});

/** Another preset starts a fresh cycle; today's count stays. */
export const choosePreset = (t: FocusTimer, presetId: FocusPreset["id"], now: number): FocusTimer => ({
  ...initialTimer(presetId, now),
  doneToday: t.day === dayKey(now) ? t.doneToday : 0,
});

/**
 * The next phase, stopped and full: after focus a break (long after every `longEvery` sessions),
 * after a break focus. `finished` counts a focus session that ran to the end; skipping doesn't.
 */
export function advance(t: FocusTimer, now: number, finished: boolean): FocusTimer {
  const preset = presetOf(t.presetId);
  const today = dayKey(now);
  const doneToday = t.day === today ? t.doneToday : 0;
  if (t.phase !== "focus") {
    const cycleDone = t.phase === "long_break" ? 0 : t.cycleDone;
    return {
      ...t,
      phase: "focus",
      endsAt: null,
      remainingMs: phaseMs(preset, "focus"),
      cycleDone,
      doneToday,
      day: today,
    };
  }
  const cycleDone = t.cycleDone + (finished ? 1 : 0);
  const long = preset.longEvery > 0 && finished && cycleDone % preset.longEvery === 0;
  const phase: FocusPhase = long ? "long_break" : "break";
  return {
    ...t,
    phase,
    endsAt: null,
    remainingMs: phaseMs(preset, phase),
    cycleDone,
    doneToday: doneToday + (finished ? 1 : 0),
    day: today,
  };
}

/** "25:00", "1:30:00". */
export function formatClock(ms: number) {
  const total = Math.ceil(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m);
  return `${h > 0 ? `${h}:` : ""}${mm}:${String(s).padStart(2, "0")}`;
}

/** Restores a saved timer, or null when it isn't one (old format, tampering). */
export function parseTimer(value: unknown): FocusTimer | null {
  if (typeof value !== "object" || value === null) return null;
  const t = value as Partial<FocusTimer>;
  const phases: FocusPhase[] = ["focus", "break", "long_break"];
  const valid =
    FOCUS_PRESETS.some((p) => p.id === t.presetId) &&
    phases.includes(t.phase as FocusPhase) &&
    (t.endsAt === null || typeof t.endsAt === "number") &&
    typeof t.remainingMs === "number" &&
    typeof t.cycleDone === "number" &&
    typeof t.doneToday === "number" &&
    typeof t.day === "string";
  return valid ? (t as FocusTimer) : null;
}
