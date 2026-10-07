import type { OwnerTone } from "../domain/board";

const LABEL_TONES: Record<string, string> = {
  Backend: "bg-blue-500/10 text-blue-700 dark:text-blue-300",
  Data: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  Design: "bg-fuchsia-500/10 text-fuchsia-700 dark:text-fuchsia-300",
  Docs: "bg-indigo-500/10 text-indigo-700 dark:text-indigo-300",
  "Finance Ops": "bg-teal-500/10 text-teal-700 dark:text-teal-300",
  Platform: "bg-cyan-500/10 text-cyan-700 dark:text-cyan-300",
  Product: "bg-orange-500/10 text-orange-700 dark:text-orange-300",
  QA: "bg-red-500/10 text-red-700 dark:text-red-300",
  Security: "bg-violet-500/10 text-violet-700 dark:text-violet-300",
  // Jira issue types.
  Bug: "bg-red-500/10 text-red-700 dark:text-red-300",
  Story: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  Task: "bg-blue-500/10 text-blue-700 dark:text-blue-300",
  Epic: "bg-violet-500/10 text-violet-700 dark:text-violet-300",
  // Personal boards.
  Home: "bg-amber-500/10 text-amber-700 dark:text-amber-300",
  Health: "bg-rose-500/10 text-rose-700 dark:text-rose-300",
  Finance: "bg-teal-500/10 text-teal-700 dark:text-teal-300",
  Family: "bg-pink-500/10 text-pink-700 dark:text-pink-300",
  Errands: "bg-lime-500/10 text-lime-700 dark:text-lime-300",
};

/** A label's colours: a known team, issue type or area, or neutral for anything else. */
export const labelTone = (label: string) => LABEL_TONES[label] ?? "bg-muted text-muted-foreground";

/** Avatar colours for a task owner, applied to the avatar root. */
export const ownerTones: Record<OwnerTone, string> = {
  zinc: "[&_[data-slot=avatar-fallback]]:bg-zinc-100 [&_[data-slot=avatar-fallback]]:text-zinc-700 after:border-zinc-200 dark:[&_[data-slot=avatar-fallback]]:bg-zinc-500/15 dark:[&_[data-slot=avatar-fallback]]:text-zinc-300 dark:after:border-zinc-500/20",
  lime: "[&_[data-slot=avatar-fallback]]:bg-lime-100 [&_[data-slot=avatar-fallback]]:text-lime-700 after:border-lime-200 dark:[&_[data-slot=avatar-fallback]]:bg-lime-500/15 dark:[&_[data-slot=avatar-fallback]]:text-lime-300 dark:after:border-lime-500/20",
  indigo:
    "[&_[data-slot=avatar-fallback]]:bg-indigo-100 [&_[data-slot=avatar-fallback]]:text-indigo-700 after:border-indigo-200 dark:[&_[data-slot=avatar-fallback]]:bg-indigo-500/15 dark:[&_[data-slot=avatar-fallback]]:text-indigo-300 dark:after:border-indigo-500/20",
  fuchsia:
    "[&_[data-slot=avatar-fallback]]:bg-fuchsia-100 [&_[data-slot=avatar-fallback]]:text-fuchsia-700 after:border-fuchsia-200 dark:[&_[data-slot=avatar-fallback]]:bg-fuchsia-500/15 dark:[&_[data-slot=avatar-fallback]]:text-fuchsia-300 dark:after:border-fuchsia-500/20",
  violet:
    "[&_[data-slot=avatar-fallback]]:bg-violet-100 [&_[data-slot=avatar-fallback]]:text-violet-700 after:border-violet-200 dark:[&_[data-slot=avatar-fallback]]:bg-violet-500/15 dark:[&_[data-slot=avatar-fallback]]:text-violet-300 dark:after:border-violet-500/20",
  pink: "[&_[data-slot=avatar-fallback]]:bg-pink-100 [&_[data-slot=avatar-fallback]]:text-pink-700 after:border-pink-200 dark:[&_[data-slot=avatar-fallback]]:bg-pink-500/15 dark:[&_[data-slot=avatar-fallback]]:text-pink-300 dark:after:border-pink-500/20",
  sky: "[&_[data-slot=avatar-fallback]]:bg-sky-100 [&_[data-slot=avatar-fallback]]:text-sky-700 after:border-sky-200 dark:[&_[data-slot=avatar-fallback]]:bg-sky-500/15 dark:[&_[data-slot=avatar-fallback]]:text-sky-300 dark:after:border-sky-500/20",
};
