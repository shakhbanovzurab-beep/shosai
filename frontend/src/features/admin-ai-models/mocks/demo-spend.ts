import { businessZone } from "@/features/admin-sign-in/model/business-zone";

import type { AiModel, DailySpend, SpendSummary } from "../domain/contract";
import { CATALOG, type CatalogEntry } from "./demo-catalog";

/* Simulated spend for the demo catalogue: deterministic per day and model, so every load looks the same. */

const DAYS = 30;

export type ModelFlags = Pick<AiModel, "enabled" | "is_default">;
/** What OpenRouter's /models tells us about a catalogue model. */
export type LiveModel = Pick<AiModel, "name" | "context_length" | "price_input_per_m" | "price_output_per_m">;

/** A stable pseudo-random number in [0, 1) for a string, so the demo looks the same on every load. */
function noise(seed: string) {
  let hash = 2166136261;
  for (let index = 0; index < seed.length; index++) {
    hash ^= seed.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return ((hash >>> 0) % 10_000) / 10_000;
}

const round = (value: number, digits = 2) => Math.round(value * 10 ** digits) / 10 ** digits;

// Часы делового пояса в полях UTC даты: сутки и месяцы образцов — московские, как у сервера (ADR 0058).
function wallClock(now: Date, zone: string): Date {
  const parts = new Intl.DateTimeFormat("ru-RU", {
    timeZone: zone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(now);
  const part = (type: Intl.DateTimeFormatPartTypes) => Number(parts.find((item) => item.type === type)?.value);
  return new Date(Date.UTC(part("year"), part("month") - 1, part("day"), part("hour"), part("minute"), part("second")));
}
const isoDate = (date: Date) => date.toISOString().slice(0, 10);

type DayUsage = { requests: number; tokensIn: number; tokensOut: number };

function dayUsage(entry: CatalogEntry, date: Date, dayShare: number): DayUsage {
  const weekday = date.getUTCDay();
  const weekFactor = weekday === 0 || weekday === 6 ? 0.55 : 1;
  const jitter = 0.75 + noise(`${entry.id}:${isoDate(date)}`) * 0.5;
  const requests = Math.round(entry.usage.requests * weekFactor * jitter * dayShare);
  return { requests, tokensIn: requests * entry.usage.tokens_in, tokensOut: requests * entry.usage.tokens_out };
}

/** Models with their month's spend and the spend summary, at `now`, using live prices where known. */
export function buildModelsAndSpend(
  live: Map<string, LiveModel> | null,
  flagsFor: (id: string) => ModelFlags,
  now: Date,
): { models: AiModel[]; spend: SpendSummary } {
  const wall = wallClock(now, businessZone());
  const today = new Date(Date.UTC(wall.getUTCFullYear(), wall.getUTCMonth(), wall.getUTCDate()));
  const todayShare = (wall.getTime() - today.getTime()) / 86_400_000;
  const daily = new Map<string, number>();
  let tokensIn = 0;
  let tokensOut = 0;

  const models: AiModel[] = CATALOG.map((entry) => {
    const { usage: _usage, ...base } = entry;
    const model = { ...base, ...live?.get(entry.openrouter_id) };
    let monthSpend = 0;
    let monthRequests = 0;
    for (let back = DAYS - 1; back >= 0; back--) {
      const date = new Date(today.getTime() - back * 86_400_000);
      const usage = dayUsage(entry, date, back === 0 ? todayShare : 1);
      const cost = (usage.tokensIn * model.price_input_per_m + usage.tokensOut * model.price_output_per_m) / 1e6;
      const key = isoDate(date);
      daily.set(key, (daily.get(key) ?? 0) + cost);
      if (date.getUTCMonth() === today.getUTCMonth()) {
        monthSpend += cost;
        monthRequests += usage.requests;
        tokensIn += usage.tokensIn;
        tokensOut += usage.tokensOut;
      }
    }
    return { ...model, month_spend: round(monthSpend), month_requests: monthRequests, ...flagsFor(entry.id) };
  });

  const days: DailySpend[] = [...daily].map(([date, cost]) => ({ date, cost: round(cost) }));
  const month = models.reduce((sum, model) => sum + model.month_spend, 0);
  // Extrapolate from the last seven full days, so a quiet morning does not drag the forecast down.
  const lastWeek = days.slice(-8, -1);
  const dailyRate = lastWeek.reduce((sum, day) => sum + day.cost, 0) / Math.max(1, lastWeek.length);
  const daysInMonth = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth() + 1, 0)).getUTCDate();
  const remainingDays = daysInMonth - today.getUTCDate() + (1 - todayShare);

  const spend: SpendSummary = {
    today: days.at(-1)?.cost ?? 0,
    month: round(month),
    forecast_month: round(month + dailyRate * remainingDays),
    tokens_in_month: tokensIn,
    tokens_out_month: tokensOut,
    daily: days,
  };
  return { models, spend };
}
