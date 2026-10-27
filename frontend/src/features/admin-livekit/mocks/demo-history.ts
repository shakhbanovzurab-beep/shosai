import type { LiveKitHistoryPoint } from "../domain/contract";
import { MBPS_IN_PER_PARTICIPANT, MBPS_OUT_PER_PARTICIPANT, MINUTE } from "./demo-fixtures";

/* Small numeric helpers and the 24-hour history for the in-memory LiveKit demo. */

const HISTORY_STEP = 30 * MINUTE;
const HISTORY_POINTS = 48;

export const pick = <T>(items: readonly T[]) => items[Math.floor(Math.random() * items.length)] as T;
export const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));
export const jitter = (spread: number) => (Math.random() * 2 - 1) * spread;
export const round1 = (value: number) => Math.round(value * 10) / 10;
export const iso = (time: number) => new Date(time).toISOString();
export const shortId = () => crypto.randomUUID().replaceAll("-", "").slice(0, 10);
/** Имя комнаты LiveKit, как его даёт бэкенд: `r-` и 16 шестнадцатеричных знаков. */
export const roomName = () => `r-${crypto.randomUUID().replaceAll("-", "").slice(0, 16)}`;

/** A gentle working-day curve in Moscow time (UTC+3), low at night and 1 around 14:00. */
function dayLoad(time: number) {
  const date = new Date(time);
  const hour = (date.getUTCHours() + 3 + date.getUTCMinutes() / 60) % 24;
  return hour < 8 || hour > 20 ? 0.04 : Math.max(0.04, Math.sin((Math.PI * (hour - 8)) / 12));
}

/** Pseudo-random but stable per time slot, so past samples don't change between polls. */
function slotNoise(slot: number) {
  const x = Math.sin(slot * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

/** 24 hours of half-hourly samples ending with `current`, the live numbers. */
export function demoHistory(now: number, current: LiveKitHistoryPoint): LiveKitHistoryPoint[] {
  const lastSlot = Math.floor(now / HISTORY_STEP);
  const points: LiveKitHistoryPoint[] = [];
  for (let slot = lastSlot - HISTORY_POINTS + 1; slot < lastSlot; slot++) {
    const time = slot * HISTORY_STEP;
    const participants = Math.round(3 + 46 * dayLoad(time) + slotNoise(slot) * 6);
    const factor = 0.85 + slotNoise(slot + 7) * 0.3;
    points.push({
      at: iso(time),
      participants,
      bandwidth_in_mbps: round1(participants * MBPS_IN_PER_PARTICIPANT * factor),
      bandwidth_out_mbps: round1(participants * MBPS_OUT_PER_PARTICIPANT * factor),
    });
  }
  points.push(current);
  return points;
}
