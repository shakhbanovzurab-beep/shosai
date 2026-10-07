export const SHARE_EXPIRIES = ["never", "7d", "30d", "90d"] as const;
export type ShareExpiry = (typeof SHARE_EXPIRIES)[number];

const EXPIRY_DAYS: Record<ShareExpiry, number | null> = { never: null, "7d": 7, "30d": 30, "90d": 90 };

/** How many days a link set to `expiry` works, or null when it never stops. */
export const expiryDays = (expiry: ShareExpiry) => EXPIRY_DAYS[expiry];

/** What people outside the meeting see when they open the link. */
export interface ShareLinkSettings {
  /** The verbatim transcript. */
  showTranscript: boolean;
  /** Speakers by name; otherwise numbered: "Speaker 1", "Speaker 2". */
  showNames: boolean;
  /** Anyone with the link can reply under the notes. */
  allowComments: boolean;
  expiry: ShareExpiry;
}

export const DEFAULT_SHARE_SETTINGS: ShareLinkSettings = {
  showTranscript: true,
  showNames: false,
  allowComments: false,
  expiry: "never",
};

export interface ShareLink {
  token: string;
  settings: ShareLinkSettings;
  /** ISO timestamp the link stops working, or null when it never does. */
  expiresAt: string | null;
}

/** GET, PUT and DELETE /api/notes/:id/share-link; null when the meeting isn't shared by link. */
export interface ShareLinkResponse {
  link: ShareLink | null;
}

/** When a link set to `expiry` now stops working. */
export function expiryDate(expiry: ShareExpiry, now: Date): string | null {
  const days = EXPIRY_DAYS[expiry];
  return days === null ? null : new Date(now.getTime() + days * 24 * 60 * 60 * 1000).toISOString();
}

export const isExpired = (link: Pick<ShareLink, "expiresAt">, now: Date) =>
  link.expiresAt !== null && new Date(link.expiresAt).getTime() <= now.getTime();

/** The page a share link opens, on this site. */
export const sharedNotePath = (token: string) => `/s/${encodeURIComponent(token)}`;

/** Names a speaker by the order they first spoke in (1, 2…), in the reader's language: "Speaker 1". */
export type AnonymousSpeaker = (order: number) => string;

/** Transcript speakers as people outside the meeting see them: by name, or numbered in order of first word. */
export function speakerLabels(
  speakers: string[],
  showNames: boolean,
  anonymous: AnonymousSpeaker,
): Map<string, string> {
  const labels = new Map<string, string>();
  for (const speaker of speakers) {
    if (!labels.has(speaker)) labels.set(speaker, showNames ? speaker : anonymous(labels.size + 1));
  }
  return labels;
}

export const SHARED_COMMENT_MAX = 2_000;
export const SHARED_AUTHOR_MAX = 60;

export interface SharedComment {
  id: string;
  author: string;
  text: string;
  createdAt: string;
}

/** GET and POST /api/s/:token/comments. */
export interface SharedCommentsResponse {
  comments: SharedComment[];
}
