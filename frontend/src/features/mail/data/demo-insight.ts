import type { MailTriage } from "../domain/leo-insights";

/** Leo's demo reading of one email; the demo server turns it into a `MailInsight`. */
export type DemoInsight = {
  mail_id: string;
  triage: MailTriage;
  next_step?: string;
  summary: string;
  key_points?: string[];
  /** Days from today the sender needs an answer by; negative once it is late. */
  reply_in_days?: number;
  draft?: string;
  /** A new arrival: how long Leo takes to read it after the demo starts. */
  analyze_ms?: number;
};
