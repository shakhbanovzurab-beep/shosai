/** "This week" → "meetings-this-week", "Эта неделя" → "meetings-эта-неделя": a heading id made from a label. */
export const slugId = (prefix: string, label: string) =>
  `${prefix}-${label
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/^-|-$/g, "")}`;
