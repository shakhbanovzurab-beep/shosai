/**
 * Leo's reading of the inbox: the contract between the inbox and the FastAPI backend, shared by the
 * UI and the route handler in `server/` (mounted at `src/app/api/mail/insights`). The handler proxies
 * to `${BACKEND_API_URL}/v1/mail/insights` and falls back to an in-memory demo when it is unset.
 * Field names are snake_case to match Pydantic models; errors are FastAPI's `{ "detail": string }`.
 * See docs/mail-insights-api.md.
 */

/** How Leo sorted an email: it is waiting on the user, it is worth knowing, or it can wait. */
export const MAIL_TRIAGES = ["needs_you", "fyi", "low"] as const;

export type MailTriage = (typeof MAIL_TRIAGES)[number];

/** `analyzing` while Leo reads a new email; until it is `ready` the reading fields are empty. */
export type InsightStatus = "analyzing" | "ready" | "failed";

export type MailInsight = {
  mail_id: string;
  status: InsightStatus;
  triage: MailTriage | null;
  /** What the user should do next, phrased as a task: "Confirm a time for tomorrow's meeting". */
  next_step: string | null;
  /** One or two sentences on what the email says. */
  summary: string | null;
  /** Up to three facts worth knowing at a glance: asks, dates, attachments. */
  key_points: string[];
  /** When the sender needs an answer by, if they said or implied it. */
  reply_by: string | null;
  /** A reply in the user's voice, ready to review. Leo never sends it on its own. */
  draft: string | null;
  updated_at: string;
};

/** GET /mail/insights: one entry per inbox email Leo has seen. */
export type MailInsightsResponse = { insights: MailInsight[] };
