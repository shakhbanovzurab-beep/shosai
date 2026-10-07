/** Which set of ready-made questions Leo offers on a page of the user panel, chosen by the page's address. */
export type SuggestionSet =
  | "default"
  | "hub"
  | "workspace"
  | "productivity"
  | "mail"
  | "calendar"
  | "kanban"
  | "meetings"
  | "notes"
  | "fileManager"
  | "studio";

const BY_PREFIX: readonly [prefix: string, set: SuggestionSet][] = [
  ["/app/hub/", "hub"],
  ["/app/w/", "workspace"],
  ["/app/productivity", "productivity"],
  ["/app/mail", "mail"],
  ["/app/calendar", "calendar"],
  ["/app/kanban", "kanban"],
  ["/app/meetings", "meetings"],
  ["/app/notes", "notes"],
  ["/app/file-manager", "fileManager"],
  ["/app/studio", "studio"],
];

export const suggestionSet = (pathname: string): SuggestionSet =>
  BY_PREFIX.find(([prefix]) => pathname.startsWith(prefix))?.[1] ?? "default";

/** Each set holds three questions. */
export const SUGGESTION_SLOTS = ["first", "second", "third"] as const;

export type DayPeriod = "night" | "morning" | "afternoon" | "evening";

/** The part of the day Leo's greeting names, from the viewer's hour (0–23). */
export function dayPeriod(hour: number): DayPeriod {
  if (hour < 5) return "night";
  if (hour < 12) return "morning";
  if (hour < 18) return "afternoon";
  return "evening";
}
