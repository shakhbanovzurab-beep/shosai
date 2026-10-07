"use client";

import { useSyncExternalStore } from "react";

import { toast } from "sonner";

import {
  advance,
  choosePreset,
  type FocusPhase,
  type FocusPreset,
  type FocusTimer,
  initialTimer,
  isRunning,
  parseTimer,
  pause,
  presetOf,
  resetPhase,
  start,
} from "../domain/focus/timer";
import { chime, notifyIfHidden } from "./chime";
import { type FocusWords, presetName } from "./words";

/*
 * The focus timer kept in this browser: it survives reloads and leaving the page (the end time is
 * stored, not a countdown), and every open tab shows the same timer.
 */

const KEY = "focus-timer:v1";
const SOUND_KEY = "focus-timer:sound";

export type FocusSnapshot = { timer: FocusTimer; sound: boolean };

/** What the server renders: a fresh Pomodoro, until the browser's saved timer takes over. */
const SERVER: FocusSnapshot = { timer: initialTimer("pomodoro", 0), sound: true };

function read(): FocusSnapshot {
  try {
    const saved = parseTimer(JSON.parse(localStorage.getItem(KEY) ?? "null"));
    return { timer: saved ?? initialTimer("pomodoro", Date.now()), sound: localStorage.getItem(SOUND_KEY) !== "off" };
  } catch {
    return { timer: initialTimer("pomodoro", Date.now()), sound: true };
  }
}

let snapshot: FocusSnapshot | null = null;
const listeners = new Set<() => void>();
const emit = () => {
  for (const listener of listeners) listener();
};

const getSnapshot = () => {
  snapshot ??= read();
  return snapshot;
};

function save(next: FocusSnapshot) {
  snapshot = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(next.timer));
    localStorage.setItem(SOUND_KEY, next.sound ? "on" : "off");
  } catch {
    // Private mode or blocked storage: the timer still works for this page.
  }
  emit();
}

const onStorage = (event: StorageEvent) => {
  if (event.key !== KEY && event.key !== SOUND_KEY) return;
  snapshot = read();
  emit();
};

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (listeners.size === 1) window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) window.removeEventListener("storage", onStorage);
  };
}

export const useFocusTimer = () => useSyncExternalStore(subscribe, getSnapshot, () => SERVER);

const update = (change: (timer: FocusTimer, now: number) => FocusTimer) => {
  const current = getSnapshot();
  save({ ...current, timer: change(current.timer, Date.now()) });
};

/** What to say when `ended` runs out and `next` begins. */
function endedMessage(t: FocusWords, ended: FocusPhase, next: FocusPhase) {
  if (ended !== "focus") return t("ended.break");
  return next === "long_break" ? t("ended.focusLong") : t("ended.focus");
}

export const focusActions = {
  toggle: () => update((t, now) => (isRunning(t) ? pause(t, now) : start(t, now))),
  reset: () => update((t) => resetPhase(t)),
  skip: () => update((t, now) => advance(t, now, false)),
  choose: (presetId: FocusPreset["id"]) => update((t, now) => choosePreset(t, presetId, now)),
  toggleSound: () => {
    const current = getSnapshot();
    save({ ...current, sound: !current.sound });
  },
  /** The running phase reached zero: on to the next one, with a chime and a note in the interface language. */
  finish: (t: FocusWords) => {
    const { timer, sound } = getSnapshot();
    if (!isRunning(timer)) return;
    const next = advance(timer, Date.now(), timer.phase === "focus");
    save({ timer: next, sound });
    const message = endedMessage(t, timer.phase, next.phase);
    if (sound) chime();
    toast(message, { description: t("ended.next", { preset: presetName(t, presetOf(next.presetId)) }) });
    notifyIfHidden(message);
  },
};
