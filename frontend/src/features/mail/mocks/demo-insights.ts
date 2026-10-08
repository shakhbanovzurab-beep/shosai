import type { DemoInsight } from "../data/demo-insight";
import { demoInsights } from "../data/leo-insights";
import type { MailInsight } from "../domain/leo-insights";

/* Leo's reading of the demo inbox. The newest emails arrive as the demo starts, so they spend a few
   seconds `analyzing` before their reading is ready; everything else is already read. */

const DAY_MS = 24 * 60 * 60 * 1000;

let startedAt: number | null = null;

function present(demo: DemoInsight, started: number, now: number): MailInsight {
  const readyAt = started + (demo.analyze_ms ?? 0);
  const base = { mail_id: demo.mail_id, key_points: [], updated_at: new Date(Math.min(now, readyAt)).toISOString() };

  if (now < readyAt) {
    return { ...base, status: "analyzing", triage: null, next_step: null, summary: null, reply_by: null, draft: null };
  }

  return {
    ...base,
    status: "ready",
    triage: demo.triage,
    next_step: demo.next_step ?? null,
    summary: demo.summary,
    key_points: demo.key_points ?? [],
    reply_by: demo.reply_in_days === undefined ? null : new Date(now + demo.reply_in_days * DAY_MS).toISOString(),
    draft: demo.draft ?? null,
  };
}

export function listInsights(now = Date.now()): MailInsight[] {
  startedAt ??= now;
  const started = startedAt;
  return demoInsights.map((demo) => present(demo, started, now));
}
