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
  /** Адрес публичной страницы на сайте, как его отдал сервер: `/s/{token}`. */
  path: string;
  settings: ShareLinkSettings;
  /** ISO timestamp the link stops working, or null when it never does. */
  expiresAt: string | null;
}

/** `GET`, `PUT` и `DELETE /v1/notes/{id}/share-link`; null, когда ссылка выключена. */
export interface ShareLinkResponse {
  link: ShareLink | null;
}
