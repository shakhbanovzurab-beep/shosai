import type { MailInsight, MailTriage } from "./leo-insights";
import type { Mail } from "./mail";

/* How Leo's reading turns into what the inbox shows: the user's corrections applied, the emails still
   waiting on them, most urgent first. */

/** The inbox list: Leo's "Needs you" queue, or all mail. */
export type InboxView = "focus" | "all";

/** The user's changes on top of Leo's reading, by mail id. */
export type LeoOverrides = {
  triage: Partial<Record<string, MailTriage>>;
  drafts: Partial<Record<string, string>>;
  discarded: Partial<Record<string, true>>;
};

/** One email as Leo presents it. */
export type LeoMailView = {
  insight: MailInsight;
  triage: MailTriage | null;
  /** The user re-sorted this email. */
  isCorrected: boolean;
  /** The reply on offer: the user's edit of Leo's draft, else Leo's; null when there is none or it was discarded. */
  draft: string | null;
};

export function buildLeoViews(insights: MailInsight[], overrides: LeoOverrides): Map<string, LeoMailView> {
  return new Map(
    insights.map((insight): [string, LeoMailView] => {
      const id = insight.mail_id;
      const corrected = overrides.triage[id];
      const draft = overrides.discarded[id] ? null : (overrides.drafts[id] ?? insight.draft);
      return [id, { insight, triage: corrected ?? insight.triage, isCorrected: corrected !== undefined, draft }];
    }),
  );
}

/** Still waiting on the user: Leo says it needs them, it is in the inbox, and they haven't replied. */
export function isWaitingOnYou(mail: Mail, view: LeoMailView | undefined) {
  return mail.folder === "inbox" && !mail.repliedAt && view?.triage === "needs_you";
}

/** Most urgent first: the earliest reply-by date, then the newest email. */
export function byUrgency(views: ReadonlyMap<string, LeoMailView>) {
  const deadline = (mail: Mail) => {
    const replyBy = views.get(mail.id)?.insight.reply_by;
    return replyBy ? Date.parse(replyBy) : Number.POSITIVE_INFINITY;
  };
  // Two emails without a deadline give NaN, which falls through to the date.
  return (a: Mail, b: Mail) => deadline(a) - deadline(b) || Date.parse(b.receivedAt) - Date.parse(a.receivedAt);
}

export type InboxBrief = {
  /** Emails waiting on the user, most urgent first. */
  waiting: Mail[];
  /** How many of those have a reply ready to review. */
  drafts: number;
  /** Emails Leo has read and sorted. */
  sorted: number;
  /** Sorted emails that don't need the user now. */
  canWait: number;
  /** Ids of the emails sorted as low priority, for archiving them in one go. */
  lowPriority: string[];
  /** New emails Leo is still reading. */
  analyzing: number;
};

/** What Leo has to say about the inbox as a whole. */
export function briefInbox(mails: Mail[], views: ReadonlyMap<string, LeoMailView>): InboxBrief {
  const inbox = mails.filter((mail) => mail.folder === "inbox");
  const waiting = inbox.filter((mail) => isWaitingOnYou(mail, views.get(mail.id))).toSorted(byUrgency(views));
  const sorted = inbox.filter((mail) => views.get(mail.id)?.triage).length;

  return {
    waiting,
    drafts: waiting.filter((mail) => views.get(mail.id)?.draft).length,
    sorted,
    canWait: sorted - waiting.length,
    lowPriority: inbox.filter((mail) => views.get(mail.id)?.triage === "low").map((mail) => mail.id),
    analyzing: inbox.filter((mail) => views.get(mail.id)?.insight.status === "analyzing").length,
  };
}
