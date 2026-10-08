"use client";

import { useFormatter, useNow } from "use-intl";

/**
 * "3 days ago" in the interface language, brought up to date once a minute. A time newer than the last
 * tick reads "now", never "in 20 seconds". The files load in the browser, so this never runs during SSR.
 */
export function useAgo() {
  const format = useFormatter();
  const now = useNow({ updateInterval: 60_000 });
  return (iso: string) => format.relativeTime(new Date(Math.min(Date.parse(iso), now.getTime())), now);
}
