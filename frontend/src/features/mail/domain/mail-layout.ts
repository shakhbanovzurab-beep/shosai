export const MAIL_LAYOUT_COOKIE = "mail_panel_layout";

export const MAIL_LIST_PANEL_ID = "mail-message-list-panel";
export const MAIL_DETAIL_PANEL_ID = "mail-message-detail-panel";

export const DEFAULT_MAIL_LAYOUT = [38, 62] as const;

/** The saved panel sizes (a JSON array, one number per panel), or the default split when missing or malformed. */
export function parseMailLayout(value: string | undefined): number[] {
  if (!value) return [...DEFAULT_MAIL_LAYOUT];

  try {
    const sizes: unknown = JSON.parse(value);
    if (
      Array.isArray(sizes) &&
      sizes.length === DEFAULT_MAIL_LAYOUT.length &&
      sizes.every((size): size is number => typeof size === "number" && Number.isFinite(size))
    ) {
      return sizes;
    }
  } catch {
    // Not JSON: fall back to the default below.
  }

  return [...DEFAULT_MAIL_LAYOUT];
}
